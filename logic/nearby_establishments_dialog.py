from .. import strings
from .endpoint_dialog import EndpointDialog


class NearbyEstablishmentsDialog(EndpointDialog):

    def __init__(self, iface, parent=None):
        super(NearbyEstablishmentsDialog, self).__init__(iface, parent)
        self.groupBox_api.setVisible(False)

        super().set_dialog_description(strings.MenuStrings.NEARBY_ESTABLISHMENT_DESCRIPTION)

    def setWindowTitle(self, a0):
        super().setWindowTitle(strings.MenuStrings.NEARBY_ESTABLISHMENT_TITLE)

    def get_enabled_endpoints(self):
        return {k: self.endpoints_config[k] for k in ['establecimientos-cercanos'] if k in self.endpoints_config}
