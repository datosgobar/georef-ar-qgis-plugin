from PyQt5.QtWidgets import QDialogButtonBox
from qgis.PyQt import QtWidgets, QtCore
from qgis._core import Qgis, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject

from .utils import PointTool
from .. import strings
from .endpoint_dialog import EndpointDialog

class ReverseGeocodingDialog(EndpointDialog):

    def __init__(self, iface, parent=None):
        super(ReverseGeocodingDialog, self).__init__(iface, parent)
        self.groupBox_api.setVisible(False)

        ok_button = self.buttonBox.button(QDialogButtonBox.Ok)
        if ok_button:
            ok_button.setVisible(False)

        self.set_dialog_description(self.tr(strings.MenuStrings.REVERSE_GEOCODING_DESCRIPTION))

    def tr(self, message):
        from qgis.PyQt import QtCore
        return QtCore.QCoreApplication.translate('ReverseGeocodingDialog', message)

    def setWindowTitle(self, a0):
        super().setWindowTitle(strings.MenuStrings.REVERSE_GEOCODING_TITLE)

    def set_note(self, note):
        super().set_note(self.tr(strings.MenuStrings.REVERSE_GEOCODING_NOTE))

    def get_enabled_endpoints(self):
        return {k: self.endpoints_config[k] for k in ['ubicacion'] if k in self.endpoints_config}

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

    def _render_layout_params(self):
        """Configura la interfaz específica para el endpoint de ubicación."""

        # 1. Dejar que la clase padre limpie el layout y cree los campos base según el YAML (lat, lon, campos)
        super()._render_layout_params()

        # 2. Extraer las referencias de los widgets generados automáticamente
        self.edit_lat = self.param_widgets_dict.get('lat')
        self.edit_lon = self.param_widgets_dict.get('lon')

        # Control de seguridad en caso de que cambie el YAML
        if not self.edit_lat or not self.edit_lon:
            return

        # 3. EXTRAERLOS DEL LAYOUT ORIGINAL DE FORMA SEGURA
        # Buscamos los contenedores intermedios que creó la clase padre para lat y lon
        parent_container_lat = self.edit_lat.parentWidget()
        parent_container_lon = self.edit_lon.parentWidget()

        if parent_container_lat and parent_container_lat.layout():
            # Extraemos el widget de su layout horizontal intermedio
            parent_container_lat.layout().removeWidget(self.edit_lat)
            # Removemos el contenedor intermedio del layout vertical principal del diálogo
            self.layout_params.removeWidget(parent_container_lat)
            parent_container_lat.hide()
            parent_container_lat.deleteLater()  # Borramos el contenedor vacío de forma segura

        if parent_container_lon and parent_container_lon.layout():
            parent_container_lon.layout().removeWidget(self.edit_lon)
            self.layout_params.removeWidget(parent_container_lon)
            parent_container_lon.hide()
            parent_container_lon.deleteLater()

        # 4. Configurar placeholders para la nueva fila compacta
        self.edit_lat.setPlaceholderText(self.tr("Latitude"))
        self.edit_lon.setPlaceholderText(self.tr("Longitude"))

        # --- FILA DE ENTRADA UNIFICADA (Lat/Lon + Botón) ---
        container_in = QtWidgets.QWidget()
        lyt_in = QtWidgets.QHBoxLayout(container_in)
        lyt_in.setContentsMargins(0, 5, 0, 5)

        lbl_in = QtWidgets.QLabel(self.tr("Coordinates:"))
        lbl_in.setFixedWidth(128)  # Alineado con el resto del formulario

        btn_map = QtWidgets.QPushButton()
        btn_map.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogHelpButton))
        btn_map.setFixedSize(28, 28)
        btn_map.clicked.connect(self._activate_map_tool)

        # 5. Inyectar los widgets originales reciclados en el nuevo layout horizontal
        lyt_in.addWidget(lbl_in)
        lyt_in.addWidget(self.edit_lat)
        lyt_in.addWidget(self.edit_lon)
        lyt_in.addWidget(btn_map)

        # Añadimos la fila unificada a la parte superior de los parámetros
        self.layout_params.insertWidget(0, container_in)

        # --- SEPARADOR ---
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.layout_params.insertWidget(1, line)

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
            edit.setStyleSheet("background-color: #f4f4f4; border: 1px solid #dcdcdc;")

            lyt_res.addWidget(lbl)
            lyt_res.addWidget(edit)
            self.res_widgets[key_res] = edit
            self.layout_params.addWidget(container_res)

        self.layout_params.addStretch()
        self.scrollAreaWidgetContents.adjustSize()

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

        self.query_location_info()
        return False
