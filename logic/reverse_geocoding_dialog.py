from .endpoint_dialog import EndpointDialog

class ReverseGeocoding(EndpointDialog):

    def __init__(self, iface, parent=None):
        super(ReverseGeocoding, self).__init__(iface, parent)
        self.setWindowTitle("GeorefAR | Georeferenciación inversa")
        self.groupBox_api.setVisible(False)

    def _get_enabled_endpoints(self):
        return ['ubicacion']


