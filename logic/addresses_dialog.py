from .. import strings
from .endpoint_dialog import EndpointDialog


class AddressesDialog(EndpointDialog):

    def __init__(self, iface, parent=None):
        super(AddressesDialog, self).__init__(iface, parent)
        self.groupBox_api.setVisible(False)

        super().set_dialog_description(strings.MenuStrings.ADDRESSES_DESCRIPTION)

    def setWindowTitle(self, a0):
        super().setWindowTitle(strings.MenuStrings.ADDRESSES_TITLE)

    def get_enabled_endpoints(self):
        return {k: self.endpoints_config[k] for k in ['direcciones'] if k in self.endpoints_config}
