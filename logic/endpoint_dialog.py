import json
import os
import tempfile
from functools import lru_cache

import requests
from qgis.PyQt import uic, QtWidgets, QtCore
from qgis.core import QgsSettings, QgsVectorLayer, Qgis
from requests import HTTPError

from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject

from .utils import PointTool, get_endpoints_config

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

        self.endpoints_config = get_endpoints_config()

        for key, info in self.endpoints_config.items():
            if key in self._get_enabled_endpoints():
                self.comboBox_endpoints.addItem(self.tr(info['title']), key)
        self.comboBox_endpoints.currentIndexChanged.connect(self._load_endpoint_params)

        self.checkBox_full_download = QtWidgets.QCheckBox(self.tr("Download complete file (without filters)"))
        self.checkBox_full_download.setStyleSheet("margin-left: 5px; font-weight: bold;")
        self.verticalLayout.insertWidget(1, self.checkBox_full_download)

        self.layout_params.setAlignment(QtCore.Qt.AlignTop)

        self.mFileWidget.setStorageMode(self.mFileWidget.SaveFile)
        self.mFileWidget.setFilter("GeoJSON (*.geojson);;CSV (*.csv);;JSON (*.json);;NDJSON (*.ndjson)")
        self.mFileWidget.lineEdit().setPlaceholderText(self.tr("[Create temporal layer]"))

        self.buttonBox.button(QtWidgets.QDialogButtonBox.Apply).clicked.connect(self.run_process)

        self._load_endpoint_params()

    def _get_enabled_endpoints(self):
        return ENDPOINTS

    def _load_endpoint_params(self):
        """
            Método para generar y cargar los parámetros de la capa cada vez que se selecciona un nuevo endpoint.

        :return:
        """

        # Limpiar layout de forma agresiva
        while self.layout_params.count():
            item = self.layout_params.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        self.param_widgets_dict.clear()
        key = self.comboBox_endpoints.currentData()
        self.checkBox_full_download.setVisible(self.endpoints_config.get(key).get('full_download', True))

        tmp_layer = self.endpoints_config.get(key).get('tmp_layer', True)
        self.mFileWidget.setVisible(tmp_layer)
        self.label_out.setVisible(tmp_layer)

        params = self.endpoints_config[key].get('params', [])

        for param in params:
            options = param.get('options', None)

            is_boolean = isinstance(param.get('default', None), bool)
            if is_boolean:
                qw = QtWidgets.QCheckBox()
                qw.setChecked(param.get('default'))
            elif options:
                qw = QtWidgets.QComboBox()
                qw.setEditable(True)
                values = []
                if options == "provincias":
                    values = self._fetch_values(options, params)
                elif isinstance(options, list):
                    values = options
                qw.addItems(values)
                qw.setEditText(str(param.get('default', '')))
            else:
                qw = QtWidgets.QLineEdit(str(param.get('default', '')))

            self.param_widgets_dict[param['name']] = qw

            if key in ['ubicacion', 'establecimientos-cercanos']:
                continue

            if not param.get('visible', True):
                qw.setVisible(False)
                continue

            container = QtWidgets.QWidget()
            lyt = QtWidgets.QHBoxLayout(container)
            lyt.setContentsMargins(0, 5, 0, 5)
            lyt.setSpacing(10)

            lbl = QtWidgets.QLabel(self.tr(param['label']))
            lbl.setFixedWidth(128)
            lyt.addWidget(lbl)

            edit_layout = QtWidgets.QHBoxLayout()
            edit_layout.setContentsMargins(0, 0, 0, 0)
            edit_layout.setSpacing(2)
            edit_layout.addWidget(qw)

            if is_boolean:
                qw.setText(param['label'])
                lbl.setVisible(False)

            if 'dependency' in param and isinstance(options, str):
                btn_refresh = QtWidgets.QPushButton()
                icon = self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload)
                btn_refresh.setIcon(icon)
                btn_refresh.setFixedSize(28, 28)
                btn_refresh.setToolTip(f"Actualizar basado en: {', '.join(param['dependency'])}")
                btn_refresh.clicked.connect(
                    lambda chk=False, w=qw, target=options, deps=param['dependency']:
                    self._refresh_dependent_combo(w, target, deps)
                )
                edit_layout.addWidget(btn_refresh)

            lyt.addLayout(edit_layout)
            self.layout_params.addWidget(container)

        if self.endpoints_config.get(key).get('reverse_georef', False):
            self._setup_location_ui()

        self.layout_params.addStretch()
        self.scrollAreaWidgetContents.adjustSize()

    def _setup_location_ui(self):
        """Configura la interfaz específica para el endpoint de ubicación."""
        # --- FILA DE ENTRADA (Lat/Lon + Botón) ---
        container_in = QtWidgets.QWidget()
        lyt_in = QtWidgets.QHBoxLayout(container_in)
        lyt_in.setContentsMargins(0, 5, 0, 5)

        lbl_in = QtWidgets.QLabel(self.tr("Coordinates:"))
        lbl_in.setFixedWidth(128)  # Alineado con el resto del formulario

        self.edit_lat = QtWidgets.QLineEdit()
        self.edit_lat.setPlaceholderText(self.tr("Latitude"))
        self.edit_lon = QtWidgets.QLineEdit()
        self.edit_lon.setPlaceholderText(self.tr("Longitude"))

        self.param_widgets_dict['lat'] = self.edit_lat
        self.param_widgets_dict['lon'] = self.edit_lon

        btn_map = QtWidgets.QPushButton()
        btn_map.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogHelpButton))
        btn_map.setFixedSize(28, 28)
        btn_map.clicked.connect(self._activate_map_tool)

        lyt_in.addWidget(lbl_in)
        lyt_in.addWidget(self.edit_lat)
        lyt_in.addWidget(self.edit_lon)
        lyt_in.addWidget(btn_map)

        self.layout_params.addWidget(container_in)

        # --- SEPARADOR ---
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.layout_params.addWidget(line)

        # --- SECCIÓN DE RESULTADOS ---
        self.res_widgets = {}
        campos_res = [
            ('calle', self.tr('Street:')),
            ('numero', self.tr('Number:')),
            ('gobierno_local', self.tr('Local Government:')),
            ('departamento', self.tr('Department:')),
            ('provincia', self.tr('Province:')),
            ('nomenclatura', self.tr('Nomenclature:'))
        ]

        for key_res, label_text in campos_res:
            container_res = QtWidgets.QWidget()
            lyt_res = QtWidgets.QHBoxLayout(container_res)
            lyt_res.setContentsMargins(0, 2, 0, 2)

            lbl = QtWidgets.QLabel(label_text)
            lbl.setFixedWidth(128)

            edit = QtWidgets.QLineEdit()
            edit.setReadOnly(True)
            # Estilo visual para indicar que es solo lectura
            edit.setStyleSheet("background-color: #f4f4f4; border: 1px solid #dcdcdc;")

            lyt_res.addWidget(lbl)
            lyt_res.addWidget(edit)
            self.res_widgets[key_res] = edit
            self.layout_params.addWidget(container_res)

        self.layout_params.addStretch()
        self.scrollAreaWidgetContents.adjustSize()


    def _fetch_values(self, layer, params):

        base_url = self.settings.value("GeorefAr/api_url", "https://apis.datos.gob.ar/georef/api").rstrip('/')
        url = f"{base_url}/{layer}?campos=basico"

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)

        try:
            r = self._query(url)
            data = json.loads(r.text)
            key = layer.replace("-", "_")
            items = data.get(key, [])
            sorted_data = sorted([item["nombre"] for item in items])
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

    def _refresh_dependent_combo(self, combo_widget, layer, dependencies):
        """
        Actualiza un QComboBox basándose en el valor de otros widgets.
        """
        filters = []
        for dep_name in dependencies:
            dep_widget = self.param_widgets_dict.get(dep_name)
            if dep_widget:
                # Obtenemos el texto sin importar si es combo o lineedit
                val = dep_widget.currentText().strip() if isinstance(dep_widget,
                                                                     QtWidgets.QComboBox) else dep_widget.text().strip()
                if val:
                    filters.append(f"{dep_name}={val}")

        if not filters:
            self.iface.messageBar().pushMessage("Aviso", "Complete los campos de dependencia primero", level=Qgis.Info)
            return

        base_url = self.settings.value("GeorefAr/api_url", "https://apis.datos.gob.ar/georef/api/v2.1").rstrip('/')
        url = f"{base_url}/{layer}?{'&'.join(filters)}&campos=basico&max=500"

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            r = self._query(url)
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

    @lru_cache(maxsize=32)
    def _query(self, url, timeout=5):
        print(url)
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

    def query_location_info(self):
        """Consulta la API y llena los campos de resultados."""
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            url = self._build_endpoint_query('ubicacion')
            response = self._query(url, timeout=10)
            data = response.json()

            res = data.get('ubicacion', {})

            # Limpiamos resultados previos
            for w in self.res_widgets.values(): w.clear()

            # Mapeo de la respuesta al widget
            # La API de Georef devuelve objetos para prov/depto/etc.
            if res:
                self.res_widgets['calle'].setText(res.get('calle', {}).get('nombre', ''))
                self.res_widgets['numero'].setText(str(res.get('calle', {}).get('altura', '')))
                self.res_widgets['gobierno_local'].setText(res.get('gobierno_local', {}).get('nombre', ''))
                self.res_widgets['departamento'].setText(res.get('departamento', {}).get('nombre', ''))
                self.res_widgets['provincia'].setText(res.get('provincia', {}).get('nombre', ''))
                self.res_widgets['nomenclatura'].setText(res.get('nomenclatura', ''))
            else:
                self.iface.messageBar().pushMessage("Georef", "Sin datos en esa coordenada", level=Qgis.Info)

        except Exception as e:
            self.iface.messageBar().pushMessage("Error", str(e), level=Qgis.Critical)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def run_process(self):
        """
        Encapsula la lógica de descarga y carga.
        Retorna True si el proceso finalizó correctamente.
        """
        layer_name = self.comboBox_endpoints.currentData()

        if layer_name == 'ubicacion':
            self.query_location_info()
            return False

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
        """Fuerza el contexto exacto para coincidir con el archivo .ts/.qm de la UI"""
        return QtCore.QCoreApplication.translate('EndpointDialogBase', message)
