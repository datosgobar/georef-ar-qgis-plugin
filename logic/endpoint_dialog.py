import json
import os
import tempfile
from functools import lru_cache

import requests
from qgis.PyQt import uic, QtWidgets, QtCore
from qgis.core import QgsSettings, QgsVectorLayer, Qgis
from requests import HTTPError

from qgis.core import QgsCoordinateReferenceSystem, QgsProject

from .utils import get_endpoints_config

import logging

ui_path = os.path.join(os.path.dirname(__file__), '..', 'ui', 'endpoint_dialog.ui')
FORM_CLASS, _ = uic.loadUiType(ui_path)

FULL_DOWNLOAD_FORMATS = ['csv', 'geojson', 'json', 'ndjson']

ENDPOINTS = [
    "provincias",
    "departamentos",
    "gobiernos-locales",
    "asentamientos",
    "localidades",
    "aglomerados",
    "localidades-censales",
    "fracciones-censales",
    "radios-censales",
    "calles",
    "establecimientos",
]

logger = logging.getLogger(__name__)

class EndpointDialog(QtWidgets.QDialog, FORM_CLASS):

    def __init__(self, iface, parent=None):
        super(EndpointDialog, self).__init__(parent)
        self.setupUi(self)

        self.iface = iface
        self.settings = QgsSettings()
        self.param_widgets_dict = {}
        self.param_dependencies_dict = {}
        self.endpoints_config = get_endpoints_config()

        self.set_dialog_description(None)
        self._render_layer_combo_box()
        self._render_layer()
        self.set_note(None)

        self.buttonBox.button(QtWidgets.QDialogButtonBox.Apply).clicked.connect(self.run_process)

    def set_dialog_description(self, description):
        """
            Configura la descripción que tendrá el diálogo para informar al usuario.

        :param description: Un str con la descripción del diálogo
        """
        if hasattr(self, 'dialog_description') and description:
            self.dialog_description.setText(description)

    def set_note(self, note):
        """
            Configura una nota al pie que tendrá el diálogo para informar al usuario.

        :param note: Un str con la descripción de la nota
        """
        if hasattr(self, 'dialog_note') and note:
            self.dialog_note.setText(note)

        elif hasattr(self, 'dialog_note'):
            self.dialog_note.setVisible(False)

    def get_enabled_endpoints(self):
        """
            Determina que endpoints de los especificados en el archivo de configuración estarán disponibles para este
            diálogo.

        :return: Un diccionario filtrado
        """
        return {k: self.endpoints_config[k] for k in ENDPOINTS if k in self.endpoints_config}

    def _render_layer_combo_box(self):
        """
            Renderiza el layout del selector de endpoints
        """
        for key, info in self.get_enabled_endpoints().items():
            self.comboBox_endpoints.addItem(self.tr(info['title']), key)
        self.comboBox_endpoints.currentIndexChanged.connect(self._render_layer)

    def _render_layer(self):
        self._render_layout_download()
        self._render_layout_params()
        self._render_layout_response()
        self._render_layout_file()

    def _render_layout_download(self):
        """
            Renderiza el layout que permite al usuario la descarga del recurso completo para el endpoint actual
        """
        key = self.comboBox_endpoints.currentData()
        self.checkBox_full_download.setVisible(self.endpoints_config.get(key).get('full_download', True))
        self.checkBox_full_download.stateChanged.connect(self._on_full_download_changed)

    def _on_full_download_changed(self, state):
        if state == QtCore.Qt.Checked:
            self.scrollArea.setEnabled(False)
        else:
            self.scrollArea.setEnabled(True)

    @property
    def current_layer(self):
        """
            Propiedad que contiene el nombre del endpoint actual

        :return: Un str con el nombre del endpoint actual seleccionado
        """
        return self.comboBox_endpoints.currentData()

    def build_param_widget(self, parent_layout, param):
        """
            Construye el widget del parámetro en función del tipo y lo agrega al layout padre.

        :param param: Un diccionario con las propiedades del parámetro

        """

        label = self.tr(param['label'])

        # Parámetro de tipo booleano
        if param['type'] == 'bool':
            qw = QtWidgets.QCheckBox()
            qw.setChecked(param.get('default', False))
            qw.setText(label)
            parent_layout.addWidget(qw)
            return qw

        # Si el parámetro no es booleano se coloca la etiqueta a la izquierda
        lbl = QtWidgets.QLabel(label)
        lbl.setFixedWidth(128)
        parent_layout.addWidget(lbl)

        # Parámetro de tipo lista
        if param['type'] == 'list':
            qw = QtWidgets.QComboBox()
            for option in param.get('options', []):
                qw.addItem(*option)
            indice = qw.findData(param.get("default", None))
            if indice != -1:
                qw.setCurrentIndex(indice)
            qw.setEditable(True)

        # Parámetro de tipo texto
        else:
            qw = QtWidgets.QLineEdit()
            qw.setText(param.get("default", ""))
            parent_layout.addWidget(qw)

        parent_layout.addWidget(qw)
        return qw

    def _clean_layout(self):
        while self.layout_params.count():
            item = self.layout_params.takeAt(0)
            widget = item.widget()
            if widget is not None:
                for child in widget.findChildren(QtWidgets.QWidget):
                    child.setParent(None)
                    child.deleteLater()
                widget.setParent(None)
                widget.deleteLater()

    def _render_layout_params(self):
        """
            Renderiza los parámetros de consulta definidos en el archivo de configuración bajo la llave params.
        """

        self.container_params = QtWidgets.QWidget()

        self.layout_params.setAlignment(QtCore.Qt.AlignTop)

        self._clean_layout()

        self.param_widgets_dict.clear()
        self.param_dependencies_dict.clear()

        for param in self.endpoints_config[self.current_layer].get('params', []):
            container = QtWidgets.QWidget()
            parent_layout = QtWidgets.QHBoxLayout(container)
            parent_layout.setContentsMargins(5, 5, 5, 5)
            parent_layout.setSpacing(10)

            qw = self.build_param_widget(parent_layout, param)
            self.param_widgets_dict[param.get('name')] = qw
            self.layout_params.addWidget(container)

            if not param.get('visible', True):
                container.setVisible(False)

            if param.get('required', False):
                qw.setProperty("required", True)
                qw.setStyleSheet("QLineEdit[required='true'] { border: 1px solid #f07178; }")
                qw.setPlaceholderText(self.tr("Este campo es obligatorio..."))

        self._link_params()

        self.layout_params.addStretch()
        self.scrollAreaWidgetContents.adjustSize()

    def _get_extra_values(self, param):
        extras = param.get('extras', None)
        endpoint = extras.get('endpoint', None)
        # Lista de nombres de parámetros de los que depende este widget
        dependencies_names = extras.get('params', [])
        query_params_list = []

        for dependent_name in dependencies_names:

            if dependent_name in ['campos', 'max']:
                continue

            dependent_widget = self.param_widgets_dict.get(dependent_name)

            value = None
            if isinstance(dependent_widget, QtWidgets.QCheckBox):
                value = dependent_widget.isChecked()
            elif isinstance(dependent_widget, QtWidgets.QLineEdit):
                value = dependent_widget.text()
            elif isinstance(dependent_widget, QtWidgets.QComboBox):
                value = dependent_widget.currentData()

            if value:
                query_params_list.append(f"{dependent_name}={value}")

        query_params_list.append(f"campos=basico")
        query_params_list.append(f"max=529")
        return self._fetch_values(endpoint, query_params_list)

    def _link_params(self):
        """
            Analiza las dependencias declaradas en el archivo de configuración
            y conecta los eventos necesarios para actualizaciones en cascada.
        """

        params_config = self.endpoints_config[self.current_layer].get('params', [])

        for param in params_config:
            if param['type'] != 'list':
                continue

            name = param.get('name')
            qw = self.param_widgets_dict.get(name)

            # Desconectamos señales previas para evitar acumulaciones duplicadas
            try:
                qw.currentIndexChanged.disconnect()
            except TypeError:
                pass  # No tenía señales conectadas todavía
            qw.clear()

            # Agregamos los valores estáticos/predefinidos
            for option in param.get('options', []):
                qw.addItem(*option)

            # Buscamos valores dinámicos (extras)
            extras = param.get('extras', None)
            if isinstance(extras, dict) and (endpoint := extras.get('endpoint', None)):

                # Lista de nombres de parámetros de los que depende este widget
                dependencies_names = extras.get('params', [])

                for dependent_name in dependencies_names:
                    dependent_widget = self.param_widgets_dict.get(dependent_name)
                    # CONEXIÓN EN CASCADA: Si el padre cambia, el hijo se actualiza
                    if isinstance(dependent_widget, QtWidgets.QComboBox):
                        dependent_widget.currentIndexChanged.connect(
                            lambda pos, p=param: self._refresh_param(p)
                        )
                extra_options = self._get_extra_values(param)
                for extra_option in extra_options:
                    qw.addItem(*extra_option)

            indice = qw.findData(param.get("default", None))
            if indice != -1:
                qw.setCurrentIndex(indice)

    def _refresh_param(self, param):
        """
        Actualiza dinámicamente un QComboBox basándose en los valores
        seleccionados actualmente en sus widgets padres/dependencias.
        """

        qw = self.param_widgets_dict.get(param.get('name'))
        if not qw:
            return

        # 1. Bloquear señales para evitar bucles infinitos durante el vaciado/llenado
        qw.blockSignals(True)
        selected_backup = qw.currentData()
        qw.clear()

        for option in param.get('options', []):
            qw.addItem(*option)

        extra_options = self._get_extra_values(param)
        for extra_option in extra_options:
            qw.addItem(*extra_option)

        indice = qw.findData(selected_backup if selected_backup else param.get("default", None))
        if indice != -1:
            qw.setCurrentIndex(indice)

        # QtWidgets.QApplication.restoreOverrideCursor()
        qw.blockSignals(False)
        # qw.currentIndexChanged.emit(qw.currentIndex())

    def _fetch_values(self, endpoint, params):

        base_url = self.settings.value("GeorefAr/api_url", "https://apis.datos.gob.ar/georef/api").rstrip('/')
        url = f"{base_url}/{endpoint}"
        if params:
            url = f"{url}?{'&'.join(params)}"

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)

        try:
            r = self._query(url)
            data = json.loads(r.text)
            key = endpoint.replace("-", "_")
            items = data.get(key, [])

            unique_items = {}
            for item in items:
                nombre = item.get("nombre")
                id_val = item.get("id")
                if nombre and id_val:  # Nos aseguramos de que ambos existan
                    unique_items[nombre] = id_val

            sorted_data = sorted(list(unique_items.items()))

        except Exception as e:

            print(f"Error al buscar valores: {e}")
            sorted_data = []

        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        return sorted_data

    def _render_layout_response(self):
        pass

    def _render_layout_file(self):
        self.mFileWidget.setStorageMode(self.mFileWidget.SaveFile)
        self.mFileWidget.setFilter("GeoJSON (*.geojson);;CSV (*.csv);;JSON (*.json);;NDJSON (*.ndjson)")
        self.mFileWidget.lineEdit().setPlaceholderText(self.tr("[Create temporal layer]"))

        tmp_layer = self.endpoints_config.get(self.current_layer).get('tmp_layer', True)
        self.mFileWidget.setVisible(tmp_layer)
        self.label_out.setVisible(tmp_layer)

    @lru_cache(maxsize=32)
    def _query(self, url, timeout=5):
        logger.info(f"QUERY: {url}")
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response

    def _get_base_url(self):
        return self.settings.value("GeorefAr/api_url", "https://apis.datos.gob.ar/georef/api").rstrip('/')

    def _get_param_format(self):
        geom_qw = self.param_widgets_dict.get('geometria', None)
        if isinstance(geom_qw, QtWidgets.QComboBox):
            return geom_qw.currentData()
        return "json"

    def _build_endpoint_query(self, layer) -> str:
        """
            Construye en función de los parámetros actuales la url de consulta.

        :param layer: El nombre de la capa para la que se construirá la consulta
        :return: La url
        """
        base_url = self._get_base_url()
        endpoint = self.endpoints_config[layer]
        url = f"{base_url}{endpoint['url_path']}"

        query = []  # Default
        for name, widget in self.param_widgets_dict.items():

            val = None

            if isinstance(widget, QtWidgets.QCheckBox):
                val = widget.isChecked() or None

            elif isinstance(widget, QtWidgets.QComboBox):
                val = widget.currentData() or None

            elif isinstance(widget, QtWidgets.QLineEdit):
                val = widget.text()

            if val:
                query.append(f"{name}={val}")

        if query:
            url = f"{url}?{'&'.join(query)}"

        return url

    def _full_download(self, layer_name):
        """
            Descarga el archivo completo de la capa especificada en el formato especificado.
            Si no se indicó un path de descargará el archivo en formato geojson y se guardará en un archivo temporal.

        :return: el path del archivo descargado
        """
        base_url = self._get_base_url()
        endpoint = self.endpoints_config[layer_name]["url_path"]
        path = self.mFileWidget.filePath().strip()

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:

            if not path:
                path = os.path.join(tempfile.mkdtemp(), f"data.geojson")
                file_format = "geojson"
            else:
                file_format = path.split(".")[-1]

            if file_format not in FULL_DOWNLOAD_FORMATS:
                raise ValueError

            url = f"{base_url}{endpoint}.{file_format}"
            response = self._query(url, timeout=15)

            with open(path, 'wb') as f:
                f.write(response.content)

            self.load_layer(path, layer_name)

        except ValueError as e:
            self.iface.messageBar().pushMessage(
                        "Error", f"Especifique un formato válido: {FULL_DOWNLOAD_FORMATS}",
                        level=Qgis.Warning
                    )
        except HTTPError as e:
            self.iface.messageBar().pushMessage(
                        "Error", e.__str__(),
                        level=Qgis.Warning
                    )
        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Error", "Error desconocido",
                level=Qgis.Warning
            )
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def download(self, layer_name):
        """
            Descarga la capa especificada utilizando los parámetros indicados.
            Si no se indicó un archivo de descarga se guardará en un archivo temporal.

        :param layer_name: El nombre de la capa
        """

        path = self.mFileWidget.filePath().strip()

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:

            if not path:
                path = os.path.join(tempfile.mkdtemp(), f"data.{self._get_param_format()}")

            url = self._build_endpoint_query(layer_name)
            response = self._query(url, timeout=15)

            with open(path, 'wb') as f:
                f.write(response.content)

            check_layer = QgsVectorLayer(path, "check", "ogr")
            if not check_layer.isValid() or check_layer.featureCount() == 0:
                self.iface.messageBar().pushMessage(
                    "Consulta sin resultados",
                    "El archivo generado no contiene registros válidos.",
                    level=Qgis.Info,
                    duration=5
                )
                if os.path.exists(path):
                    os.remove(path)
                return

            self.load_layer(path, layer_name)

        except ValueError as e:
            self.iface.messageBar().pushMessage(
                        "Error", f"Especifique un formato válido: {FULL_DOWNLOAD_FORMATS}",
                        level=Qgis.Warning
                    )
        except HTTPError as e:
            self.iface.messageBar().pushMessage(
                        "Error", e.__str__(),
                        level=Qgis.Warning
                    )
        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Error", "Error desconocido",
                level=Qgis.Warning
            )
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def load_layer(self, path, layer_name):

        title = self.endpoints_config[layer_name]["title"]

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            vlayer = QgsVectorLayer(path, title, "ogr")
            if vlayer and vlayer.isValid():
                vlayer.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
                QgsProject.instance().addMapLayer(vlayer)
                self.iface.mapCanvas().setExtent(vlayer.extent())
            else:
                self.iface.messageBar().pushMessage(
                    "Error", "No se pudo crear una capa válida desde el recurso.",
                    level=Qgis.Warning
                )
        except Exception as e:
            self.iface.messageBar().pushMessage("Error Crítico", str(e), level=Qgis.Critical)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def validate_required_fields(self):
        """Devuelve True si todos los campos requeridos están completos."""
        for name, widget in self.param_widgets_dict.items():
            if widget.property("required") == True:
                if isinstance(widget, QtWidgets.QLineEdit):
                    if not widget.text().strip():
                        self.iface.messageBar().pushMessage(
                            "Datos faltantes",
                            f"El campo de texto '{name}' es obligatorio.",
                            level=Qgis.Warning,
                            duration=5
                        )
                        widget.setFocus()
                        return False

                elif isinstance(widget, QtWidgets.QComboBox):
                    if widget.currentData() is None and not widget.currentText().strip():
                        self.iface.messageBar().pushMessage(
                            "Selección faltante",
                            f"Debes seleccionar una opción para el campo '{name}'.",
                            level=Qgis.Warning,
                            duration=5
                        )
                        widget.setFocus()
                        return False
        return True

    def run_process(self):
        """
        Encapsula la lógica de descarga y carga.
        Retorna True si el proceso finalizó correctamente.
        """

        if not self.validate_required_fields():
            return False

        layer_name = self.comboBox_endpoints.currentData()

        try:
            if self.checkBox_full_download.isChecked():
                self._full_download(layer_name)
            else:
                self.download(layer_name)
            return True
        except Exception as e:
            self.iface.messageBar().pushMessage("Error Crítico", str(e), level=Qgis.Critical)
            return False

    def accept(self):
        """Ejecuta la acción y cierra el diálogo si tuvo éxito."""
        if self.run_process():
            # Importante: Quitamos el super().accept() de load_layer
            # para que sea esta función quien controle el cierre.
            super(EndpointDialog, self).accept()

    def tr(self, message):
        return QtCore.QCoreApplication.translate('EndpointDialogBase', message)
