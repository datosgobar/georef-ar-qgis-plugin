import os
import yaml
import requests
from qgis.PyQt import uic, QtWidgets, QtCore
from qgis.core import QgsSettings, QgsProject, QgsVectorLayer, Qgis
from qgis.gui import QgsFileWidget

ui_path = os.path.join(os.path.dirname(__file__), '..', 'ui', 'endpoint_dialog.ui')
FORM_CLASS, _ = uic.loadUiType(ui_path)


class EndpointDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, iface, parent=None):
        super(EndpointDialog, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.settings = QgsSettings()

        # --- Configuración Estilo QuickOSM ---
        self.mFileWidget.setStorageMode(QgsFileWidget.SaveFile)
        self.mFileWidget.setFilter("GeoJSON (*.geojson);;GeoPackage (*.gpkg)")

        # Permitimos que el usuario limpie el campo con una 'X'
        # para volver a modo temporal fácilmente
        self.mFileWidget.setFullUrl(True)

        # Texto por defecto (Placeholder)
        self.line_edit_file = self.mFileWidget.lineEdit()
        self.line_edit_file.setPlaceholderText("[Crear capa temporal]")

        # Carga de datos
        self.load_api_config()
        self.comboBox_endpoints.currentIndexChanged.connect(self.render_dynamic_ui)

        for key, info in self.api_config.get('endpoints', {}).items():
            self.comboBox_endpoints.addItem(info['titulo'], key)
        self.render_dynamic_ui()

    def load_api_config(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'endpoints.yaml')
        with open(path, 'r', encoding='utf-8') as f:
            self.api_config = yaml.safe_load(f)

    def render_dynamic_ui(self):
        """Genera los widgets del YAML en el scrollArea."""
        while self.layout_params.count():
            child = self.layout_params.takeAt(0)
            if child.widget(): child.widget().deleteLater()

        self.param_widgets = {}
        key = self.comboBox_endpoints.currentData()
        params = self.api_config['endpoints'][key].get('parametros', [])

        for p in params:
            container = QtWidgets.QWidget()
            lyt = QtWidgets.QHBoxLayout(container)
            lbl = QtWidgets.QLabel(p['label'])
            lbl.setFixedWidth(120)
            edit = QtWidgets.QLineEdit(str(p.get('default', '')))
            self.param_widgets[p['nombre']] = edit
            lyt.addWidget(lbl);
            lyt.addWidget(edit)
            self.layout_params.addWidget(container)
        self.layout_params.addStretch()

    def accept(self):
        """Lógica de ejecución final."""
        base_url = self.settings.value("GeorefAr/api_url", "https://apis.datos.gob.ar/georef/api").rstrip('/')
        key = self.comboBox_endpoints.currentData()
        endpoint = self.api_config['endpoints'][key]

        # Construcción de la Query
        query = ["formato=geojson"]
        for name, widget in self.param_widgets.items():
            val = widget.text().strip()
            if val: query.append(f"{name}={val}")

        full_url = f"{base_url}{endpoint['url_path']}?{'&'.join(query)}"
        path = self.mFileWidget.filePath().strip()

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            # Si el path está vacío, QGIS entiende que es temporal
            if not path:
                # Usamos el prefijo 'url=' para que QGIS sepa que debe descargar
                vlayer = QgsVectorLayer(full_url, endpoint['titulo'], "ogr")
            else:
                # Guardamos el archivo físico
                r = requests.get(full_url, timeout=15)
                if r.status_code == 200:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(r.text)
                    vlayer = QgsVectorLayer(path, endpoint['titulo'], "ogr")
                else:
                    vlayer = None

            if vlayer and vlayer.isValid():
                QgsProject.instance().addMapLayer(vlayer)
                self.iface.mapCanvas().setExtent(vlayer.extent())
                super().accept()
            else:
                self.iface.messageBar().pushMessage("Georef", "Error al cargar datos", level=Qgis.Warning)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()