import json
import os
from functools import lru_cache

import yaml
import requests
from qgis.PyQt import uic, QtWidgets, QtCore
from qgis.core import QgsSettings, QgsProject, QgsVectorLayer, Qgis

from ..utils import get_local_resource

ui_path = os.path.join(os.path.dirname(__file__), '..', 'ui', 'endpoint_dialog.ui')
FORM_CLASS, _ = uic.loadUiType(ui_path)


class EndpointDialog(QtWidgets.QDialog, FORM_CLASS):

    def __init__(self, iface, parent=None):
        super(EndpointDialog, self).__init__(parent)
        self.setupUi(self)

        # Asegura que los widgets se peguen arriba y se estiren a lo ancho
        self.layout_params.setAlignment(QtCore.Qt.AlignTop)
        # Opcional: Si el mFileWidget también se ve corto
        self.mFileWidget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        self.iface = iface
        self.settings = QgsSettings()

        self.param_widgets = {}

        # Configuración del selector de archivos
        self.mFileWidget.setStorageMode(self.mFileWidget.SaveFile)
        self.mFileWidget.setFilter("GeoJSON (*.geojson);;GeoPackage (*.gpkg)")
        self.mFileWidget.lineEdit().setPlaceholderText("[Crear capa temporal]")
        self.mFileWidget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        self.api_config = {}
        self.load_api_config()
        self.comboBox_endpoints.currentIndexChanged.connect(self.load_params)

        # Cargar combo de endpoints
        self.comboBox_endpoints.blockSignals(True)  # Silenciar mientras cargamos
        for key, info in self.api_config.get('endpoints', {}).items():
            self.comboBox_endpoints.addItem(info['titulo'], key)
        self.comboBox_endpoints.blockSignals(False)  # Reactivar

        self.load_params()

    def load_api_config(self):
        yaml_path = os.path.join(os.path.dirname(__file__), '..', 'endpoints.yaml')
        with open(yaml_path, 'r', encoding='utf-8') as f:
            self.api_config = yaml.safe_load(f)

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
        params = self.api_config['endpoints'][key].get('parametros', [])

        self.scrollAreaWidgetContents.setMinimumWidth(self.scrollArea.viewport().width())

        for p in params:
            container = QtWidgets.QWidget()
            container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

            lyt = QtWidgets.QHBoxLayout(container)
            lyt.setContentsMargins(0, 5, 0, 5)
            lyt.setSpacing(10)

            lbl = QtWidgets.QLabel(p['label'])
            lbl.setFixedWidth(150)

            options = p.get('options')
            if options:
                edit = QtWidgets.QComboBox()
                edit.setEditable(True)

                if isinstance(options, str):
                    values = self.fetch_values(options, params)
                elif isinstance(options, list):
                    values = options
                else:
                    values = []

                edit.addItems(values)
                edit.setEditText(str(p.get('default', '')))
            else:
                # Campo de texto normal
                edit = QtWidgets.QLineEdit(str(p.get('default', '')))

            edit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

            if p['name'] == 'formato' and isinstance(edit, QtWidgets.QComboBox):
                edit.currentTextChanged.connect(self.update_file_filter)

            self.param_widgets[p['name']] = edit
            lyt.addWidget(lbl)
            lyt.addWidget(edit)
            self.layout_params.addWidget(container)

        self.layout_params.addStretch()


    def fetch_values(self, layer, params):

        base_url = self.settings.value("GeorefAr/api_url", "https://apis.datos.gob.ar/georef/api").rstrip('/')
        url = f"{base_url}/{layer}?campos=basico"
        # url = '&'.join([url] + params)
        try:
            r = self.query(url)
            data = json.loads(r.text)
            sorted_data = sorted([item["nombre"] for item in data[layer]])
        except:
            sorted_data = []

        return sorted_data

    @lru_cache(maxsize=32)
    def query(self, url):
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response
        raise Exception


    def update_file_filter(self, text):
        # Mapeo simple de formato a extensión
        ext_map = {
            'geojson': 'GeoJSON (*.geojson)',
            'gpkg': 'GeoPackage (*.gpkg)',
            'shp': 'ESRI Shapefile comprimido (*.zip)',
        }
        new_filter = ext_map.get(text.lower(), "Todos los archivos (*.*)")
        self.mFileWidget.setFilter(new_filter)

    def accept(self):

        # 1. Configuración inicial
        base_url = self.settings.value("GeorefAr/api_url", "https://apis.datos.gob.ar/georef/api").rstrip('/')
        key = self.comboBox_endpoints.currentData()
        endpoint = self.api_config['endpoints'][key]

        # 2. Construir Query y detectar formato
        query = []  # Default
        formato_elegido = "geojson"

        for name, widget in self.param_widgets.items():
            val = widget.currentText().strip() if isinstance(widget, QtWidgets.QComboBox) else widget.text().strip()
            if val:
                query.append(f"{name}={val}")
                if name == "formato":
                    formato_elegido = val.lower()

        full_url = f"{base_url}{endpoint['url_path']}?{'&'.join(query)}"
        path_usuario = self.mFileWidget.filePath().strip()

        # 3. Procesamiento de la Capa
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:

            if not path_usuario:
                # --- CAPA TEMPORAL ---
                uri = get_local_resource(full_url, formato_elegido, self.iface)
            else:
                # --- GUARDADO MANUAL ---
                if formato_elegido == 'shp' and not path_usuario.lower().endswith('.zip'):
                    path_usuario += ".zip"

                r = requests.get(full_url, timeout=30)
                r.raise_for_status()
                with open(path_usuario, 'wb') as f:
                    f.write(r.content)

                # Si es un ZIP (SHP), usamos el driver /vsizip/ para que QGIS entre al archivo
                uri = f"/vsizip/{path_usuario}" if formato_elegido == 'shp' else path_usuario

            # 4. Carga en QGIS
            if uri:
                vlayer = QgsVectorLayer(uri, endpoint['titulo'], "ogr")
                if vlayer and vlayer.isValid():
                    QgsProject.instance().addMapLayer(vlayer)
                    self.iface.mapCanvas().setExtent(vlayer.extent())
                    super(EndpointDialog, self).accept()  # Cerramos el diálogo con éxito
                else:
                    self.iface.messageBar().pushMessage(
                        "Error", "No se pudo crear una capa válida desde el recurso.",
                        level=Qgis.Warning
                    )

        except Exception as e:
            self.iface.messageBar().pushMessage("Error Crítico", str(e), level=Qgis.Critical)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()