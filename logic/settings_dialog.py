import os
import requests
from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsSettings
from urllib.parse import urlparse

ui_path = os.path.join(os.path.dirname(__file__), '..', 'ui', 'settings_dialog.ui')
FORM_CLASS, _ = uic.loadUiType(ui_path)


class SettingsDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super(SettingsDialog, self).__init__(parent)
        self.setupUi(self)
        self.settings = QgsSettings()

        url = self.settings.value("GeorefAr/api_url", "https://apis.datos.gob.ar/georef/api/v2.1")
        self.lineEdit_url.setText(url)

        self.btn_test_api.clicked.connect(self.test_connection)
        self.lineEdit_url.textChanged.connect(lambda: self.label_status.setText(""))

    def test_connection(self):

        url_raw = self.lineEdit_url.text().strip()

        if not url_raw:
            self.show_status("Por favor, ingrese una URL", "orange")
            return

        try:
            result = urlparse(url_raw)
            is_valid = all([result.scheme, result.netloc])
            if not is_valid:
                raise ValueError("URL malformada")
        except Exception:
            self.show_status("❌ Error: Ingrese una URL válida (ej: https://apis.datos.gob.ar/georef/api)", "orange")
            return

        # 2. Limpieza para la petición
        url = url_raw.rstrip('/')

        test_url = f"{url}/provincias?max=1"
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        self.btn_test_api.setEnabled(False)

        try:
            response = requests.get(test_url, timeout=5)

            if response.status_code == 200:
                self.show_status("✅ Conexión exitosa. La API responde correctamente.", "green")
            else:
                self.show_status(f"❌ Error: El servidor respondió con código {response.status_code}", "red")

        except requests.exceptions.Timeout:
            self.show_status("❌ Error: Tiempo de espera agotado (Timeout).", "red")

        except requests.exceptions.ConnectionError:
            self.show_status("❌ Error: No se pudo establecer conexión con el servidor.", "red")

        except Exception as e:
            self.show_status(f"❌ Error inesperado: {str(e)[:50]}", "red")

        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            self.btn_test_api.setEnabled(True)

    def show_status(self, message, color):
        """Metodo auxiliar para mostrar mensajes de estado con color."""
        self.label_status.setText(message)
        self.label_status.setStyleSheet(f"color: {color}; font-weight: bold;")

    def accept(self):
        new_url = self.lineEdit_url.text().strip().rstrip('/')
        self.settings.setValue("GeorefAr/api_url", new_url)
        super(SettingsDialog, self).accept()
