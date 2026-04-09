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

        # --- NUEVO: Check para descarga completa ---
        self.check_full_download = QtWidgets.QCheckBox("Descargar el archivo completo (sin filtros)")
        self.check_full_download.setStyleSheet("margin-left: 5px; font-weight: bold;")

        # Insertarlo en el layout principal (índice 1, después del GroupBox)
        self.verticalLayout.insertWidget(1, self.check_full_download)

        # Conectar el evento para habilitar/deshabilitar parámetros
        self.check_full_download.stateChanged.connect(self.toggle_params_visibility)

        # Asegura que los widgets se peguen arriba y se estiren a lo ancho
        self.layout_params.setAlignment(QtCore.Qt.AlignTop)
        # Opcional: Si el mFileWidget también se ve corto
        self.mFileWidget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        self.iface = iface
        self.settings = QgsSettings()

        self.param_widgets = {}

        # Configuración del selector de archivos
        self.mFileWidget.setStorageMode(self.mFileWidget.SaveFile)
        self.mFileWidget.setFilter("GeoJSON (*.geojson);;GeoPackage (*.gpkg);;ESRI Shapefile comprimido (*.zip)")
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

    def toggle_params_visibility(self, state):
        # Si está chequeado, desactivamos el ScrollArea donde están los campos dinámicos
        is_full = (state == QtCore.Qt.Checked)
        self.scrollArea.setEnabled(not is_full)

        if is_full:
            # Opcional: poner un mensaje en la barra de mensajes para aclarar
            self.iface.messageBar().pushMessage("Info", "Se descargará el recurso completo sin aplicar filtros.",
                                                level=Qgis.Info, duration=2)

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
                if isinstance(opt_config, str):
                    values = self.fetch_values(opt_config, params)
                else:
                    values = opt_config or []
                edit.addItems(values)
                edit.setEditText(str(p.get('default', '')))
            else:
                edit = QtWidgets.QLineEdit(str(p.get('default', '')))

            edit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            edit_layout.addWidget(edit)

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

        self.layout_params.addStretch()

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
        # Construimos la URL de filtrado (ej: /departamentos?provincia=Salta&campos=basico)
        url = f"{base_url}/{layer}?{'&'.join(filters)}&campos=basico&max=500"

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            r = self.query(url)
            r.raise_for_status()
            data = r.json()

            # Extraemos los nombres
            new_values = sorted([item["nombre"] for item in data.get(layer, [])])

            if new_values:
                combo_widget.clear()
                combo_widget.addItems(new_values)
                # Abrimos el desplegable automáticamente para mostrar los resultados
                combo_widget.showPopup()
            else:
                self.iface.messageBar().pushMessage("Georef", "No se encontraron resultados para ese filtro",
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
        formato = "gpkg"

        for name, widget in self.param_widgets.items():
            val = widget.currentText().strip() if isinstance(widget, QtWidgets.QComboBox) else widget.text().strip()
            if not val:
                continue
            if name == "geometría":
                formato = "gpkg" if val == "poligonos" else "geojson"
                query.append(f"formato={formato}")

        # if self.check_full_download.isChecked():
        #     full_url = f"{base_url}{endpoint['url_path']}{endpoint['url_path']}.geojson"
        # else:
        #     full_url = f"{base_url}{endpoint['url_path']}?{'&'.join(query)}"
        full_url = f"{base_url}{endpoint['url_path']}?{'&'.join(query)}"
        path_usuario = self.mFileWidget.filePath().strip()

        # 3. Procesamiento de la Capa
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:

            if not path_usuario:
                # --- CAPA TEMPORAL ---
                uri = get_local_resource(full_url, formato, self.iface)

            else:
                # --- GUARDADO MANUAL ---
                if formato == 'shp' and not path_usuario.lower().endswith('.zip'):
                    path_usuario += ".zip"

                r = requests.get(full_url, timeout=30)
                r.raise_for_status()
                with open(path_usuario, 'wb') as f:
                    f.write(r.content)

                # Si es un ZIP (SHP), usamos el driver /vsizip/ para que QGIS entre al archivo
                uri = f"/vsizip/{path_usuario}" if formato == 'shp' else path_usuario

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