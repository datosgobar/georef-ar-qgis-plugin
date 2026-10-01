import os
import csv
import json
import urllib.request
import urllib.error

from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal, QVariant
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QComboBox, QTableWidget,
    QTableWidgetItem, QProgressBar, QFileDialog, QMessageBox, QHeaderView
)
from qgis.core import (
    QgsVectorLayer, QgsField, QgsFeature, QgsGeometry,
    QgsPointXY, QgsProject, QgsSettings
)


class BatchGeocodingWorker(QThread):
    progress_changed = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    finished_success = pyqtSignal(list, list, int, int)
    finished_error = pyqtSignal(str)

    def __init__(self, file_path, delimiter, encoding, mappings, parent=None, base_url="https://apis.datos.gob.ar/georef/api"):
        super().__init__(parent)
        self.file_path = file_path
        self.delimiter = delimiter
        self.encoding = encoding
        self.mappings = mappings
        self._is_cancelled = False
        self.base_url = base_url

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        def clean_text(text):
            if not text:
                return ""
            return " ".join(text.split())

        try:
            rows = []
            headers = []
            with open(self.file_path, mode='r', encoding=self.encoding, errors='replace') as f:
                reader = csv.reader(f, delimiter=self.delimiter)
                headers = next(reader, None)
                if not headers:
                    self.finished_error.emit("El archivo CSV está vacío.")
                    return
                for row in reader:
                    if row:
                        rows.append(row)

            total_rows = len(rows)
            if total_rows == 0:
                self.finished_error.emit("No se encontraron registros en el archivo.")
                return

            batch_size = 100
            processed_results = []
            found_count = 0
            not_found_count = 0

            col_dir = self.mappings.get('direccion')
            col_alt = self.mappings.get('altura')
            col_prov = self.mappings.get('provincia')
            col_dept = self.mappings.get('departamento')
            # col_census_loc = self.mappings.get('localidad_censal')
            col_loc = self.mappings.get('localidad')

            for i in range(0, total_rows, batch_size):
                if self._is_cancelled:
                    return

                batch_rows = rows[i:i + batch_size]
                payload_direcciones = []
                valid_indices = []

                for idx, row in enumerate(batch_rows):

                    dir_val = clean_text(row[col_dir]) if col_dir is not None and col_dir < len(row) else ""

                    if col_alt is not None and col_alt < len(row):
                        alt_val = clean_text(row[col_alt])
                        if alt_val:
                            dir_val = f"{dir_val} {alt_val}".strip()

                    if not dir_val:
                        continue

                    item = {"direccion": dir_val, "desplazar": True}

                    if col_prov is not None and col_prov < len(row):
                        prov_val = clean_text(row[col_prov])
                        if prov_val:
                            item["provincia"] = prov_val

                    if col_dept is not None and col_dept < len(row):
                        dept_val = clean_text(row[col_dept])
                        if dept_val:
                            item["departamento"] = dept_val

                    # if col_census_loc is not None and col_census_loc < len(row):
                    #     census_loc_val = clean_text(row[col_census_loc])
                    #     if census_loc_val:
                    #         item["localidad_censal"] = census_loc_val

                    if col_loc is not None and col_loc < len(row):
                        loc_val = clean_text(row[col_loc])
                        if loc_val:
                            item["localidad"] = loc_val

                    payload_direcciones.append(item)
                    valid_indices.append(idx)

                resultados = []
                if payload_direcciones:
                    req_data = json.dumps({"direcciones": payload_direcciones}).encode('utf-8')
                    req = urllib.request.Request(
                        f"{self.base_url}/direcciones",
                        data=req_data,
                        headers={"Content-Type": "application/json", "User-Agent": "GeorefQGISPlugin/1.0"}
                    )

                    try:
                        with urllib.request.urlopen(req, timeout=30) as resp:
                            res_json = json.loads(resp.read().decode('utf-8'))
                            resultados = res_json.get("resultados", [])
                    except Exception as e:
                        print(e)
                        self.finished_error.emit(f"Error de conexión con la API Georef: {str(e)}")
                        return

                api_res_map = {valid_indices[k]: res for k, res in enumerate(resultados)}

                for idx, orig_row in enumerate(batch_rows):
                    rec_data = {
                        "orig_row": orig_row,
                        "estado": "NO_ENCONTRADO",
                        "calle": "",
                        "altura": None,
                        "provincia": "",
                        "departamento": "",
                        "localidad_censal": "",
                        "localidad": "",
                        "nomenclatura": "",
                        "lat": None,
                        "lon": None
                    }

                    if idx in api_res_map:
                        res_item = api_res_map[idx]
                        matches = res_item.get("direcciones", [])
                        if matches:
                            match = matches[0]
                            ubicacion = match.get("ubicacion", {})
                            lat = ubicacion.get("lat")
                            lon = ubicacion.get("lon")

                            if lat and lon:
                                rec_data["estado"] = "ENCONTRADO"
                                found_count += 1
                            else:
                                rec_data["estado"] = "SIN_GEOMETRIA"
                                not_found_count += 1

                            rec_data["calle"] = match.get("calle", {}).get("nombre", "")
                            rec_data["altura"] = match.get("altura", {}).get("valor", None) or None
                            rec_data["provincia"] = match.get("provincia", {}).get("nombre", "")
                            rec_data["departamento"] = match.get("departamento", {}).get("nombre", "")
                            rec_data["localidad_censal"] = match.get("localidad_censal", {}).get("nombre", "")
                            rec_data["localidad"] = match.get("localidad", {}).get("nombre", "")
                            rec_data["nomenclatura"] = match.get("nomenclatura", "")
                            rec_data["lat"] = lat if lat else None
                            rec_data["lon"] = lon if lon else None
                        else:
                            not_found_count += 1
                    else:
                        not_found_count += 1

                    processed_results.append(rec_data)

                processed = min(i + batch_size, total_rows)
                progress_percent = int((processed / total_rows) * 100)
                self.progress_changed.emit(progress_percent)
                self.status_changed.emit(f"Procesando {processed} de {total_rows} registros...")

            self.finished_success.emit(processed_results, headers, found_count, not_found_count)

        except Exception as e:
            self.finished_error.emit(f"Error inesperado al procesar el lote: {str(e)}")


class BatchGeocodingDialog(QDialog):

    def __init__(self, parent=None):

        if hasattr(parent, 'mainWindow'):
            parent = parent.mainWindow()

        super().__init__(parent)
        self.setWindowTitle("Geocodificación por Lotes - Georef AR")
        self.resize(750, 650)

        self.worker = None
        self.headers = []

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 0. Leyenda / Encabezado
        lbl_info = QLabel(
            "<b>Geocodificación por Lotes (API Georef AR)</b><br>"
            "<span style='color: #4f4f4f; font-size: 11px;'>"
            "Permite geocodificar múltiples direcciones a partir de un archivo CSV. "
            "Seleccione el archivo, su delimitador y asocie sus campos con los parámetros de Georef AR.<br><br>"
            "<i>Para obtener resultados más precisos, se recomienda completar la mayor cantidad posible de datos de ubicación "
            "(provincia, departamento y localidad), además de la dirección y la altura.</i>"
            "</span>"
        )
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("""
                    QLabel {
                        background-color: #f0f4f8;
                        border: 1px solid #cbd5e1;
                        border-radius: 5px;
                        padding: 10px;
                        margin-bottom: 4px;
                    }
                """)
        layout.addWidget(lbl_info)

        # 1. Selección de Archivo
        file_group = QGroupBox("Archivo de Entrada")
        file_layout = QHBoxLayout()
        self.txt_file = QLineEdit()
        self.txt_file.setReadOnly(True)
        btn_browse = QPushButton("Explorar...")
        btn_browse.clicked.connect(self._select_file)
        file_layout.addWidget(self.txt_file)
        file_layout.addWidget(btn_browse)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # 2. Formato del Archivo
        fmt_group = QGroupBox("Opciones de Formato")
        fmt_layout = QHBoxLayout()

        fmt_layout.addWidget(QLabel("Delimitador:"))
        self.combo_delimiter = QComboBox()
        self.combo_delimiter.addItems([", (Coma)", "; (Punto y coma)", "\\t (Tabulaciones)", "| (Barra vertical)"])
        self.combo_delimiter.currentIndexChanged.connect(self._reload_csv_preview)
        fmt_layout.addWidget(self.combo_delimiter)

        fmt_layout.addWidget(QLabel("Codificación:"))
        self.combo_encoding = QComboBox()
        self.combo_encoding.addItems(["utf-8", "latin-1", "cp1252", "iso-8859-1"])
        self.combo_encoding.currentIndexChanged.connect(self._reload_csv_preview)
        fmt_layout.addWidget(self.combo_encoding)

        fmt_group.setLayout(fmt_layout)
        layout.addWidget(fmt_group)

        # 3. Mapeo de Columnas
        mapping_group = QGroupBox("Mapeo de Campos a la API Georef AR")
        map_layout = QFormLayout()

        self.combo_dir = QComboBox()
        self.combo_alt = QComboBox()
        self.combo_prov = QComboBox()
        self.combo_dept = QComboBox()
        # self.combo_census_loc = QComboBox()
        self.combo_loc = QComboBox()

        map_layout.addRow("Calle / Dirección (*):", self.combo_dir)
        map_layout.addRow("Número / Altura (Opcional):", self.combo_alt)
        map_layout.addRow("Provincia (Opcional):", self.combo_prov)
        map_layout.addRow("Departamento (Opcional):", self.combo_dept)
        # map_layout.addRow("Localidad Censal (Opcional):", self.combo_census_loc)
        map_layout.addRow("Localidad (Opcional):", self.combo_loc)

        mapping_group.setLayout(map_layout)
        layout.addWidget(mapping_group)

        # 4. Vista previa de datos
        preview_group = QGroupBox("Vista Previa (Primeros 5 registros)")
        preview_layout = QVBoxLayout()
        self.table_preview = QTableWidget()
        self.table_preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        preview_layout.addWidget(self.table_preview)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        # 5. Barra de Progreso y Estado
        self.lbl_status = QLabel("Seleccione un archivo CSV para comenzar.")
        layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 6. Botones de Acción
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("Ejecutar Geocodificación")
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self._start_batch_geocoding)

        self.btn_close = QPushButton("Cerrar")
        self.btn_close.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_run)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

    def _get_selected_delimiter(self):
        text = self.combo_delimiter.currentText()
        if ";" in text:
            return ";"
        elif "\\t" in text:
            return "\t"
        elif "|" in text:
            return "|"
        return ","

    def _select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo CSV", "", "Archivos CSV (*.csv *.txt);;Todos los archivos (*)"
        )
        if file_path:
            self.txt_file.setText(file_path)
            self._reload_csv_preview()

    def _reload_csv_preview(self):
        file_path = self.txt_file.text()
        if not file_path or not os.path.exists(file_path):
            return

        delimiter = self._get_selected_delimiter()
        encoding = self.combo_encoding.currentText()

        try:
            with open(file_path, mode='r', encoding=encoding, errors='replace') as f:
                reader = csv.reader(f, delimiter=delimiter)
                self.headers = next(reader, None)

                if not self.headers:
                    self.lbl_status.setText("Error: El archivo CSV está vacío.")
                    return

                for combo in [self.combo_dir, self.combo_alt, self.combo_prov, self.combo_loc]:
                    combo.clear()

                self.combo_alt.addItem("-- Ninguno (incluido en campo Dirección) --", None)
                self.combo_prov.addItem("-- Ninguno --", None)
                self.combo_dept.addItem("-- Ninguno --", None)
                self.combo_loc.addItem("-- Ninguno --", None)

                for idx, h in enumerate(self.headers):
                    self.combo_dir.addItem(f"{h} (Col {idx+1})", idx)
                    self.combo_alt.addItem(f"{h} (Col {idx+1})", idx)
                    self.combo_prov.addItem(f"{h} (Col {idx+1})", idx)
                    self.combo_dept.addItem(f"{h} (Col {idx+1})", idx)
                    self.combo_loc.addItem(f"{h} (Col {idx+1})", idx)

                for idx, h in enumerate(self.headers):
                    h_lower = h.lower()
                    if any(k in h_lower for k in ["direccion", "calle", "domicilio", "address"]):
                        self.combo_dir.setCurrentIndex(idx)
                    elif any(k in h_lower for k in ["altura", "numero", "nro", "number"]):
                        self.combo_alt.setCurrentIndex(idx + 1)
                    elif any(k in h_lower for k in ["provincia", "prov"]):
                        self.combo_prov.setCurrentIndex(idx + 1)
                    elif any(k in h_lower for k in ["departamento", "dept", "depto"]):
                        self.combo_dept.setCurrentIndex(idx + 1)
                    elif any(k in h_lower for k in ["localidad", "municipio", "departamento"]):
                        self.combo_loc.setCurrentIndex(idx + 1)

                rows = []
                for _ in range(5):
                    row = next(reader, None)
                    if row:
                        rows.append(row)

                self.table_preview.setColumnCount(len(self.headers))
                self.table_preview.setRowCount(len(rows))
                self.table_preview.setHorizontalHeaderLabels(self.headers)

                for r_idx, r_data in enumerate(rows):
                    for c_idx, val in enumerate(r_data):
                        if c_idx < len(self.headers):
                            self.table_preview.setItem(r_idx, c_idx, QTableWidgetItem(val))

            self.btn_run.setEnabled(True)
            self.lbl_status.setText("Archivo cargado correctamente. Verifique el mapeo de columnas.")

        except Exception as e:
            self.lbl_status.setText(f"Error al leer el archivo: {str(e)}")
            self.btn_run.setEnabled(False)

    def _start_batch_geocoding(self):
        file_path = self.txt_file.text()
        if not file_path:
            return

        mappings = {
            'direccion': self.combo_dir.currentData(),
            'altura': self.combo_alt.currentData(),
            'provincia': self.combo_prov.currentData(),
            'departamento': self.combo_dept.currentData(),
            # 'localidad_censal': self.combo_census_loc.currentData(),
            'localidad': self.combo_loc.currentData()
        }

        if mappings['direccion'] is None:
            QMessageBox.warning(self, "Atención", "Debe seleccionar la columna correspondiente a la Dirección.")
            return

        self.btn_run.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        self.worker = BatchGeocodingWorker(
            file_path=file_path,
            delimiter=self._get_selected_delimiter(),
            encoding=self.combo_encoding.currentText(),
            mappings=mappings,
            base_url=QgsSettings().value("GeorefAr/api_url", "https://apis.datos.gob.ar/georef/api").rstrip('/')
        )

        self.worker.progress_changed.connect(self.progress_bar.setValue)
        self.worker.status_changed.connect(self.lbl_status.setText)
        self.worker.finished_success.connect(self._on_geocoding_success)
        self.worker.finished_error.connect(self._on_geocoding_error)

        self.worker.run()

    def _on_geocoding_success(self, results, headers, found_count, not_found_count):
        self.progress_bar.setVisible(False)
        self.btn_run.setEnabled(True)

        layer = QgsVectorLayer("Point?crs=EPSG:4326", "Geocodificación Georef", "memory")
        provider = layer.dataProvider()

        fields = [QgsField(h, QVariant.String) for h in headers]
        fields.extend([
            QgsField("georef_estado", QVariant.String),
            QgsField("georef_calle", QVariant.String),
            QgsField("georef_altura", QVariant.Int),
            QgsField("georef_provincia", QVariant.String),
            QgsField("georef_departamento", QVariant.String),
            QgsField("georef_localidad_censal", QVariant.String),
            QgsField("georef_localidad", QVariant.String),
            QgsField("georef_nomenclatura", QVariant.String),
            QgsField("georef_lat", QVariant.Double),
            QgsField("georef_lon", QVariant.Double)
        ])
        provider.addAttributes(fields)
        layer.updateFields()

        features = []
        for rec in results:
            feat = QgsFeature(layer.fields())

            lat = rec.get("lat")
            lon = rec.get("lon")
            if lat and lon:
                feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))

            attrs = list(rec.get("orig_row", [])) + [
                rec.get("estado", ""),
                rec.get("calle", ""),
                rec.get("altura", None),
                rec.get("provincia", ""),
                rec.get("departamento", ""),
                rec.get("localidad_censal", ""),
                rec.get("localidad", ""),
                rec.get("nomenclatura", ""),
                lat,
                lon
            ]
            feat.setAttributes(attrs)
            features.append(feat)

        provider.addFeatures(features)
        layer.updateExtents()

        QgsProject.instance().addMapLayer(layer)

        QMessageBox.information(
            self,
            "Proceso Finalizado",
            f"Geocodificación completada exitosamente.\n\n"
            f"- Registros georreferenciados: {found_count}\n"
            f"- Registros sin coincidencia: {not_found_count}\n\n"
            f"La capa '{layer.name()}' se ha agregado al proyecto."
        )
        self.accept()

    def _on_geocoding_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.btn_run.setEnabled(True)
        QMessageBox.critical(self, "Error en Geocodificación", error_msg)
        self.lbl_status.setText("Proceso cancelado debido a un error.")