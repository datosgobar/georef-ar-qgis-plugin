from PyQt5.QtWidgets import QDialogButtonBox

from .. import strings
from .endpoint_dialog import EndpointDialog, MixinCoordinates, MixinFields


class ReverseGeocodingDialog(MixinCoordinates, MixinFields, EndpointDialog):

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

    def _render_layout_params(self):
        """Configura la interfaz específica para el endpoint de ubicación."""

        # 1. Dejar que la clase padre limpie el layout y cree los campos base según el YAML (lat, lon, campos)
        super()._render_layout_params()
        self.group_coordinates()
        self.render_fields()

    def run_process(self):
        """
        Encapsula la lógica de descarga y carga.
        Retorna True si el proceso finalizó correctamente.
        """
        if self.validate_required_fields():
            self.show_response()
        return False
