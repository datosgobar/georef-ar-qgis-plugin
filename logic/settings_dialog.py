import os
import requests
from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsSettings

ui_path = os.path.join(os.path.dirname(__file__), '..', 'ui', 'settings_dialog.ui')
FORM_CLASS, _ = uic.loadUiType(ui_path)


class SettingsDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super(SettingsDialog, self).__init__(parent)
        self.setupUi(self)
        self.settings = QgsSettings()

        # Carga inicial
        url = self.settings.value("GeorefAr/api_url", "https://apis.datos.gob.ar/georef/api/v2.0")
        self.lineEdit_url.setText(url)

        # Conexiones
        self.btn_test_api.clicked.connect(self.test_connection)
        # Limpiar el estado si el usuario vuelve a escribir
        self.lineEdit_url.textChanged.connect(lambda: self.label_status.setText(""))

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    def test_connection(self):
        url = self.lineEdit_url.text().strip().rstrip('/')
        if not url:
            self.show_status("Por favor, ingrese una URL", "orange")
            return

        test_url = f"{url}/provincias?max=1"
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        self.btn_test_api.setEnabled(False)

        try:
            # 5 segundos de timeout es lo ideal para redes de gobierno/oficina
            response = requests.get(test_url, timeout=5)

            if response.status_code == 200:
                self.show_status("✅ Conexión exitosa. La API responde correctamente.", "green")
            else:
                self.show_status(f"❌ Error: El servidor respondió con código {response.status_code}", "red")

        except Exception as e:
            self.show_status(f"❌ Error de red: {str(e)[:100]}...", "red")

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

    def reject(self):
        # Opcional: Si querés hacer algo al cancelar
        super(SettingsDialog, self).reject()