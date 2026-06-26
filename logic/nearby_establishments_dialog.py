from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from .. import strings
from .endpoint_dialog import EndpointDialog, MixinCoordinates


class NearbyEstablishmentsDialog(MixinCoordinates, EndpointDialog):

    def __init__(self, iface, parent=None):
        super(NearbyEstablishmentsDialog, self).__init__(iface, parent)
        self.groupBox_api.setVisible(False)

        super().set_dialog_description(self.tr(strings.MenuStrings.NEARBY_ESTABLISHMENT_DESCRIPTION))

    def tr(self, message):
        from qgis.PyQt import QtCore
        return QtCore.QCoreApplication.translate('NearbyEstablishmentsDialog', message)

    def setWindowTitle(self, a0):
        super().setWindowTitle(strings.MenuStrings.NEARBY_ESTABLISHMENT_TITLE)

    def get_enabled_endpoints(self):
        return {k: self.endpoints_config[k] for k in ['establecimientos-cercanos'] if k in self.endpoints_config}

    def _build_endpoint_query(self, layer) -> str:
        """Construye la URL y convierte el parámetro 'distancia' de Km a Metros."""
        url_string = super()._build_endpoint_query(layer)
        parsed_url = urlparse(url_string)
        query_params = dict(parse_qsl(parsed_url.query))

        # 3. Si el parámetro 'distancia' está presente, hacemos la conversión
        if 'distancia' in query_params:
            try:
                distancia_km = float(query_params['distancia'])
                distancia_m = int(distancia_km * 1000)
                query_params['distancia'] = str(distancia_m)
            except ValueError:
                pass

        new_query = urlencode(query_params)
        new_url = parsed_url._replace(query=new_query)

        return urlunparse(new_url)

    def _render_layout_params(self):
        super()._render_layout_params()
        self.group_coordinates()


