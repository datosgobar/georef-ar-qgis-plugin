import json
import os
import tempfile
from functools import lru_cache

import requests
from PyQt5.QtWidgets import QVBoxLayout
from qgis.PyQt import uic, QtWidgets, QtCore
from qgis.core import QgsSettings, QgsVectorLayer, Qgis
from requests import HTTPError

from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject
from sphinx.environment.collectors import dependencies

from .utils import PointTool, get_endpoints_config
from .. import strings

ui_path = os.path.join(os.path.dirname(__file__), '..', 'ui', 'endpoint_dialog.ui')
FORM_CLASS, _ = uic.loadUiType(ui_path)

FULL_DOWNLOAD_FORMATS = ['csv', 'geojson', 'json', 'ndjson']
API_FORMATS = {
    'puntos': 'geojson',
    'poligonos': 'gpkg',
    'lineas': 'gpkg'
}

TRANSLATE = {
    "Autopista": "AUT",
    "Avenida": "AV",
    "Boulevard": "BV",
    "Calle": "CALLE",
    "Pasillo": "PASILLO",
    "Pasaje": "PASAJE",
    "Peatonal": "PEATONAL",
    "Ruta": "RUTA"
}

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

    def set_dialog_description(self, description):
        """
            Configura la descripción que tendrá el diálogo para informar al usuario.

        :param description: Un str con la descripción del diálogo
        """
        if hasattr(self, 'dialog_description') and description:
            self.dialog_description.setText(description)

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
        self._render_layout_buttons()

    def _render_layout_download(self):
        """
            Renderiza el layout que permite al usuario la descarga del recurso completo para el endpoint actual
        """
        key = self.comboBox_endpoints.currentData()
        self.checkBox_full_download.setVisible(self.endpoints_config.get(key).get('full_download', True))
        self.checkBox_full_download.stateChanged.connect(self._on_full_download_changed)

    def _on_full_download_changed(self, state):
        # Evaluamos el estado usando las constantes de Qt
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

    def _render_layout_params(self):
        """
            Renderiza los parámetros de consulta definidos en el archivo de configuración bajo la llave params.
        """

        self.container_params = QtWidgets.QWidget()

        self.layout_params.setAlignment(QtCore.Qt.AlignTop)

        # Limpiar layout de forma agresiva
        while self.layout_params.count():
            item = self.layout_params.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        self.param_widgets_dict.clear()
        self.param_dependencies_dict.clear()

        for param in self.endpoints_config[self.current_layer].get('params', []):
            name = param.get('name')
            options = param.get('options', None)
            default = param.get('default', None)
            visible = param.get('visible', True)
            dependencies = param.get('dependencies', [])
            label = self.tr(param['label'])

            container = QtWidgets.QWidget()
            parent_layout = QtWidgets.QHBoxLayout(container)
            parent_layout.setContentsMargins(5, 5, 5, 5)
            parent_layout.setSpacing(10)

            lbl = QtWidgets.QLabel(label)
            lbl.setFixedWidth(128)

            if isinstance(default, bool):
                qw = QtWidgets.QCheckBox()
                qw.setChecked(param.get('default', None))
                qw.setText(param['label'])
                parent_layout.addWidget(qw)

            elif options:
                parent_layout.addWidget(lbl)

                qw = QtWidgets.QComboBox()
                qw.setEditable(True)
                parent_layout.addWidget(qw)

            else:
                parent_layout.addWidget(lbl)

                qw = QtWidgets.QLineEdit()
                qw.setText(default)
                parent_layout.addWidget(qw)

            self.param_widgets_dict[name] = qw
            self.layout_params.addWidget(container)

            if not visible:
                container.setVisible(False)

        self._update_dependencies()

        self.layout_params.addStretch()
        self.scrollAreaWidgetContents.adjustSize()

    def _update_dependencies(self):
        """
        Analiza las dependencias declaradas en el archivo de configuración
        y conecta los eventos necesarios para actualizaciones en cascada.
        """
        for param in self.endpoints_config[self.current_layer].get('params', []):
            options = param.get('options', None)
            name = param.get('name')
            qw = self.param_widgets_dict.get(name)

            if not options or not isinstance(qw, QtWidgets.QComboBox):
                continue

            default = param.get('default', '')

            if isinstance(options, list):
                qw.addItems(options)
                qw.setEditText(default)
                continue

            dependencies = param.get('dependencies', [])
            if not dependencies:
                values = self._fetch_values(options, [])
                qw.clear()
                qw.addItems(values)
                qw.setEditText(default)
                continue

            for dep_name in dependencies:
                parent_qw = self.param_widgets_dict.get(dep_name)
                if parent_qw is not None:
                    parent_qw.currentIndexChanged.connect(
                        lambda _, h=qw, l=options, d=dependencies: self._refresh_dependent_combo(h, l, d)
                    )

    def _refresh_dependent_combo(self, combo_widget, endpoint, dependencies):
        """
        Actualiza dinámicamente un QComboBox basándose en los valores
        seleccionados actualmente en sus widgets padres/dependencias.
        """
        # 1. Bloquear señales para evitar bucles infinitos durante el vaciado/llenado
        combo_widget.blockSignals(True)
        combo_widget.clear()

        filters = ["max=500", "campos=basico"]
        for dep_name in dependencies or []:
            dep_widget = self.param_widgets_dict.get(dep_name)
            if dep_widget:
                val = dep_widget.currentText().strip() if isinstance(dep_widget,
                                                                     QtWidgets.QComboBox) else dep_widget.text().strip()
                if val:
                    filters.append(f"{dep_name}={val}")

        values = self._fetch_values(endpoint, filters)
        if values:
            combo_widget.addItems(values)
            combo_widget.setEditText("")

        QtWidgets.QApplication.restoreOverrideCursor()
        combo_widget.blockSignals(False)
        combo_widget.currentIndexChanged.emit(combo_widget.currentIndex())

    def _render_layout_response(self):
        pass

    def _render_layout_file(self):
        self.mFileWidget.setStorageMode(self.mFileWidget.SaveFile)
        self.mFileWidget.setFilter("GeoJSON (*.geojson);;CSV (*.csv);;JSON (*.json);;NDJSON (*.ndjson)")
        self.mFileWidget.lineEdit().setPlaceholderText(self.tr("[Create temporal layer]"))

        tmp_layer = self.endpoints_config.get(self.current_layer).get('tmp_layer', True)
        self.mFileWidget.setVisible(tmp_layer)
        self.label_out.setVisible(tmp_layer)

    def _render_layout_buttons(self):
        self.buttonBox.button(QtWidgets.QDialogButtonBox.Apply).clicked.connect(self.run_process)

    def _fetch_values(self, endpoint, params):

        base_url = self.settings.value("GeorefAr/api_url", "https://apis.datos.gob.ar/georef/api").rstrip('/')
        url = f"{base_url}/{endpoint}?{'&'.join(params)}"

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)

        try:
            print(url)
            r = self._query(url)
            data = json.loads(r.text)
            key = endpoint.replace("-", "_")
            items = data.get(key, [])
            # sorted_data = sorted([item["nombre"] for item in items])
            sorted_data = sorted(list(set(item["nombre"] for item in items if item.get("nombre"))))
        except:
            sorted_data = []
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        return sorted_data

    def _activate_map_tool(self):
        """Activa la herramienta para capturar el clic en el lienzo."""
        # self.setWindowState(QtCore.Qt.WindowMinimized)  # Minimizamos para ver el mapa
        self.hide()
        self.map_tool = PointTool(self.iface.mapCanvas(), self._on_map_clicked)
        self.iface.mapCanvas().setMapTool(self.map_tool)

    def _on_map_clicked(self, point):
        """Callback cuando el usuario hace clic en el mapa."""
        # 1. Restaurar la herramienta anterior
        self.iface.mapCanvas().unsetMapTool(self.map_tool)

        # 2. Configurar la transformación
        # SRC de origen: El que tenga el proyecto actualmente
        src_origen = self.iface.mapCanvas().mapSettings().destinationCrs()
        # SRC de destino: WGS84 (EPSG:4326)
        src_destino = QgsCoordinateReferenceSystem("EPSG:4326")

        # Crear el transformador
        transformacion = QgsCoordinateTransform(src_origen, src_destino, QgsProject.instance())

        try:
            # Transformar el punto capturado
            punto_wgs84 = transformacion.transform(point)

            if hasattr(self, 'res_widgets'):
                for widget in self.res_widgets.values():
                    widget.clear()

            # Buscamos en el diccionario general o en las variables específicas
            lat_w = self.param_widgets_dict.get('lat')
            lon_w = self.param_widgets_dict.get('lon')

            if lat_w: lat_w.setText(f"{punto_wgs84.y():.6f}")
            if lon_w: lon_w.setText(f"{punto_wgs84.x():.6f}")

        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Error de transformación",
                f"No se pudo convertir la coordenada: {str(e)}",
                level=Qgis.Warning
            )

        # 4. Volver a mostrar la ventana
        self.setWindowState(QtCore.Qt.WindowActive)
        self.show()
        self.raise_()
        self.activateWindow()

    @lru_cache(maxsize=32)
    def _query(self, url, timeout=5):
        print(f"[SERVER]: {url}")
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response

    def _get_base_url(self):
        return self.settings.value("GeorefAr/api_url", "https://apis.datos.gob.ar/georef/api").rstrip('/')

    def _get_param_format(self):
        geometria = self.param_widgets_dict['geometria'].currentText().strip()
        param_format = API_FORMATS[geometria]
        return param_format

    def _build_endpoint_query(self, layer) -> str:
        """
            Contruye en función de los parámetros actuales la url de consulta.

        :param layer: El nombre de la capa para la que se construirá la consulta
        :return: La url
        """
        base_url = self._get_base_url()
        endpoint = self.endpoints_config[layer]
        url = f"{base_url}{endpoint['url_path']}"

        query = []  # Default
        for name, widget in self.param_widgets_dict.items():

            val = None

            if isinstance(widget, QtWidgets.QCheckBox) and not (val := widget.isChecked()):
                continue

            val = val or widget.currentText().strip() if isinstance(widget, QtWidgets.QComboBox) else widget.text().strip()

            if not val:
                continue

            if name == "geometria":
                name = "formato"
                val = self._get_param_format()

            name = TRANSLATE.get(name, name)
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

    def run_process(self):
        """
        Encapsula la lógica de descarga y carga.
        Retorna True si el proceso finalizó correctamente.
        """
        layer_name = self.comboBox_endpoints.currentData()

        try:
            if self.checkBox_full_download.isChecked():
                self._full_download(layer_name)
            else:
                self.download(layer_name)
            return True
        except Exception as e:
            return False

    def accept(self):
        """Ejecuta la acción y cierra el diálogo si tuvo éxito."""
        if self.run_process():
            # Importante: Quitamos el super().accept() de load_layer
            # para que sea esta función quien controle el cierre.
            super(EndpointDialog, self).accept()

    def tr(self, message):
        return QtCore.QCoreApplication.translate('EndpointDialogBase', message)
