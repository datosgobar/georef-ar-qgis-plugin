from .endpoint_dialog import EndpointDialog


class NearbyEstablishments(EndpointDialog):

    def __init__(self, iface, parent=None):
        super(NearbyEstablishments, self).__init__(iface, parent)
        self.setWindowTitle("GeorefAR | Establecimientos cercanos")
        self.groupBox_api.setVisible(False)

    def _get_enabled_endpoints(self):
        return ['establecimientos-cercanos']
