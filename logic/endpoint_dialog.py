import json
import os
import tempfile
from functools import lru_cache

import yaml
import requests
from qgis.PyQt import uic, QtWidgets, QtCore
from qgis.core import QgsSettings, QgsVectorLayer, Qgis
from requests import HTTPError

from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject

ui_path = os.path.join(os.path.dirname(__file__), '..', 'ui', 'endpoint_dialog.ui')
FORM_CLASS, _ = uic.loadUiType(ui_path)

FULL_DOWNLOAD_FORMATS = ['csv', 'geojson', 'json', 'ndjson']
API_FORMATS = {
    'puntos': 'geojson',
    'poligonos': 'gpkg',
    'lineas': 'gpkg'
}

from qgis.gui import QgsMapToolEmitPoint

class PointTool(QgsMapToolEmitPoint):
    def __init__(self, canvas, callback):
        super().__init__(canvas)
        self.callback = callback

    def canvasReleaseEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        self.callback(point)

class EndpointDialog(QtWidgets.QDialog, FORM_CLASS):

    def __init__(self, iface, parent=None):
        super(EndpointDialog, self).__init__(parent)
        self.setupUi(self)

        self.iface = iface
        self.settings = QgsSettings()
        self.param_widgets = {}

        self.api_config = {}
        self.load_api_config()

        # Selector del endpoint
        for key, info in self.api_config.items():
            self.comboBox_endpoints.addItem(info['titulo'], key)
        self.comboBox_endpoints.currentIndexChanged.connect(self.load_params)

        # Check para descarga completa
        self.check_full_download = QtWidgets.QCheckBox("Descargar el archivo completo (sin filtros)")
        self.check_full_download.setStyleSheet("margin-left: 5px; font-weight: bold;")
        self.verticalLayout.insertWidget(1, self.check_full_download)
        self.toggle_params_visibility(self.check_full_download.isChecked())
        self.check_full_download.stateChanged.connect(self.toggle_params_visibility)

        self.layout_params.setAlignment(QtCore.Qt.AlignTop)

        # Configuración del selector de archivos
        self.mFileWidget.setStorageMode(self.mFileWidget.SaveFile)
        self.mFileWidget.setFilter("GeoJSON (*.geojson);;CSV (*.csv);;JSON (*.json);;NDJSON (*.ndjson)")
        self.mFileWidget.lineEdit().setPlaceholderText("[Crear capa temporal]")

        # Botones de proceso
        self.buttonBox.setStandardButtons(
            QtWidgets.QDialogButtonBox.Ok |
            QtWidgets.QDialogButtonBox.Apply |
            QtWidgets.QDialogButtonBox.Cancel
        )
        btn_apply = self.buttonBox.button(QtWidgets.QDialogButtonBox.Apply)
        btn_apply.clicked.connect(self.apply_changes)

        self.load_params()

    def toggle_params_visibility(self, state):
        is_full = (state == QtCore.Qt.Checked)
        self.scrollArea.setEnabled(not is_full)
        if is_full:
            self.mFileWidget.setFilter("GeoJSON (*.geojson);;CSV (*.csv);;JSON (*.json);;NDJSON (*.ndjson)")
            self.iface.messageBar().pushMessage("Info", "Se descargará el recurso completo sin aplicar filtros.",
                                                level=Qgis.Info, duration=2)
        else:
            self.mFileWidget.setFilter("GeoJSON (*.geojson);;GeoPackage (*.gpkg)")

    def load_api_config(self):
        yaml_path = os.path.join(os.path.dirname(__file__), '..', 'endpoints.yaml')
        with open(yaml_path, 'r', encoding='utf-8') as f:
            self.api_config = yaml.safe_load(f)

    def activate_map_tool(self):
        """Activa la herramienta para capturar el clic en el lienzo."""
        self.setWindowState(QtCore.Qt.WindowMinimized)  # Minimizamos para ver el mapa
        self.map_tool = PointTool(self.iface.mapCanvas(), self.on_map_clicked)
        self.iface.mapCanvas().setMapTool(self.map_tool)

    def on_map_clicked(self, point):
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

            # 3. Cargar los valores transformados en los campos
            # Usamos punto_wgs84.y() para Latitud y .x() para Longitud
            if 'lat' in self.param_widgets:
                self.param_widgets['lat'].setText(f"{punto_wgs84.y():.6f}")
            if 'lon' in self.param_widgets:
                self.param_widgets['lon'].setText(f"{punto_wgs84.x():.6f}")

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

    def load_params(self):

        # Limpiar layout de forma agresiva
        while self.layout_params.count():
            item = self.layout_params.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)  # Lo desconecta visualmente ya
                widget.deleteLater()  # Libera la memoria luego

        self.param_widgets.clear()
        key = self.comboBox_endpoints.currentData()
        params = self.api_config[key].get('parametros', [])

        for p in params:
            container = QtWidgets.QWidget()
            # container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
            lyt = QtWidgets.QHBoxLayout(container)
            lyt.setContentsMargins(0, 5, 0, 5)
            lyt.setSpacing(10)

            lbl = QtWidgets.QLabel(p['label'])
            lbl.setFixedWidth(96)
            lyt.addWidget(lbl)

            # Contenedor para el widget de edición + botón opcional
            edit_layout = QtWidgets.QHBoxLayout()
            edit_layout.setContentsMargins(0, 0, 0, 0)
            edit_layout.setSpacing(2)

            opt_config = p.get('options')
            if opt_config:
                edit = QtWidgets.QComboBox()
                edit.setEditable(True)
                # Carga inicial (puede ser vacía o genérica)
                values = []
                if opt_config == "provincias":
                    values = self.fetch_values(opt_config, params)

                elif isinstance(opt_config, list):
                    values = opt_config

                edit.addItems(values)
                edit.setEditText(str(p.get('default', '')))
            else:
                edit = QtWidgets.QLineEdit(str(p.get('default', '')))

            edit_layout.addWidget(edit)

            # --- LÓGICA DE SELECCIÓN EN MAPA ---
            if p['name'] in ['lat', 'lon']:
                btn_map = QtWidgets.QPushButton()
                btn_map.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogHelpButton))
                btn_map.setFixedSize(28, 28)
                btn_map.setToolTip("Seleccionar punto en el mapa")
                btn_map.clicked.connect(self.activate_map_tool)
                edit_layout.addWidget(btn_map)

            # --- LÓGICA DE DEPENDENCIA ---
            if 'dependency' in p and isinstance(opt_config, str):
                btn_refresh = QtWidgets.QPushButton()
                # Usamos un icono estándar de sistema para "Refresh"
                icon = self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload)
                btn_refresh.setIcon(icon)
                btn_refresh.setFixedSize(28, 28)
                btn_refresh.setToolTip(f"Actualizar basado en: {', '.join(p['dependency'])}")

                # Conectamos el click usando una función lambda para pasarle el contexto
                btn_refresh.clicked.connect(
                    lambda chk=False, w=edit, target=opt_config, deps=p['dependency']:
                    self.refresh_dependent_combo(w, target, deps)
                )
                edit_layout.addWidget(btn_refresh)

            lyt.addLayout(edit_layout)
            self.param_widgets[p['name']] = edit
            self.layout_params.addWidget(container)

    def refresh_dependent_combo(self, combo_widget, layer, dependencies):
        """
        Actualiza un QComboBox basándose en el valor de otros widgets.
        """
        filters = []
        for dep_name in dependencies:
            dep_widget = self.param_widgets.get(dep_name)
            if dep_widget:
                # Obtenemos el texto sin importar si es combo o lineedit
                val = dep_widget.currentText().strip() if isinstance(dep_widget,
                                                                     QtWidgets.QComboBox) else dep_widget.text().strip()
                if val:
                    filters.append(f"{dep_name}={val}")

        if not filters:
            self.iface.messageBar().pushMessage("Aviso", "Complete los campos de dependencia primero", level=Qgis.Info)
            return

        base_url = self.settings.value("GeorefAr/api_url", "https://apis.datos.gob.ar/georef/api").rstrip('/')
        url = f"{base_url}/{layer}?{'&'.join(filters)}&campos=basico&max=500"

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            r = self.query(url)
            r.raise_for_status()
            data = r.json()

            # Extraemos los nombres
            key = layer.replace("-", "_")
            items = data.get(key, [])

            param_key = 'nombre'
            if key == 'fracciones_censales':
                param_key = 'id'

            new_values = sorted([item[param_key] for item in items])

            if new_values:
                combo_widget.clear()
                combo_widget.addItems(new_values)
                # Abrimos el desplegable automáticamente para mostrar los resultados
                combo_widget.showPopup()
            else:
                self.iface.messageBar().pushMessage("Georef", f"No se encontraron resultados para ese filtro: {url}",
                                                    level=Qgis.Warning)

        except Exception as e:
            self.iface.messageBar().pushMessage("Error", f"No se pudo actualizar: {str(e)}", level=Qgis.Critical)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def fill_param(self, param):
        pass

    def fetch_values(self, layer, params):

        base_url = self.settings.value("GeorefAr/api_url", "https://apis.datos.gob.ar/georef/api").rstrip('/')
        url = f"{base_url}/{layer}?campos=basico"

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)

        try:
            r = self.query(url)
            data = json.loads(r.text)
            key = layer.replace("-", "_")
            items = data.get(key, [])
            sorted_data = sorted([item["nombre"] for item in items])
        except:
            sorted_data = []
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        return sorted_data

    @lru_cache(maxsize=32)
    def query(self, url, timeout=5):
        print(url)
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response

    def update_file_filter(self, text):
        # Mapeo simple de formato a extensión
        ext_map = {
            'geojson': 'GeoJSON (*.geojson)',
            'gpkg': 'GeoPackage (*.gpkg)',
            'shp': 'ESRI Shapefile comprimido (*.zip)',
        }
        new_filter = ext_map.get(text.lower(), "Todos los archivos (*.*)")
        self.mFileWidget.setFilter(new_filter)

    def get_base_url(self):
        return self.settings.value("GeorefAr/api_url", "https://apis.datos.gob.ar/georef/api").rstrip('/')

    def _get_param_format(self):
        geometria = self.param_widgets['geometria'].currentText().strip()
        param_format = API_FORMATS[geometria]
        return param_format

    def get_selected_file(self):
        path = self.mFileWidget.filePath().strip()
        return path

    def build_endpoint_query(self, layer):
        base_url = self.get_base_url()
        endpoint = self.api_config[layer]
        url = f"{base_url}{endpoint['url_path']}"

        query = []  # Default
        for name, widget in self.param_widgets.items():
            val = widget.currentText().strip() if isinstance(widget, QtWidgets.QComboBox) else widget.text().strip()

            if not val:
                continue

            if name == "geometria":
                name = "formato"
                val = self._get_param_format()

            query.append(f"{name}={val}")

        if query:
            url = f"{url}?{'&'.join(query)}"

        return url

    def full_download(self, layer_name):
        """
            Descarga el archivo completo de la capa especificada en el formato especificado.
            Si no se indicó un path de descargará el archivo en formato geojson y se guardará en un archivo temporal.

        :return: el path del archivo descargado
        """
        base_url = self.get_base_url()
        endpoint = self.api_config[layer_name]["url_path"]
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
            response = self.query(url, timeout=15)

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


        :param layer_name:
        """

        path = self.mFileWidget.filePath().strip()

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:

            if not path:
                path = os.path.join(tempfile.mkdtemp(), f"data.{self._get_param_format()}")

            url = self.build_endpoint_query(layer_name)
            response = self.query(url, timeout=15)

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

    def load_layer(self, path, layer_name):

        title = self.api_config[layer_name]["titulo"]

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            vlayer = QgsVectorLayer(path, title, "ogr")
            if vlayer and vlayer.isValid():
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
            if self.check_full_download.isChecked():
                self.full_download(layer_name)
            else:
                self.download(layer_name)
            return True
        except Exception as e:
            return False

    def apply_changes(self):
        """Ejecuta la acción pero mantiene el diálogo abierto."""
        self.run_process()

    def accept(self):
        """Ejecuta la acción y cierra el diálogo si tuvo éxito."""
        if self.run_process():
            # Importante: Quitamos el super().accept() de load_layer
            # para que sea esta función quien controle el cierre.
            super(EndpointDialog, self).accept()
