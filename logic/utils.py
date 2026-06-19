import os

import yaml
from qgis._gui import QgsMapToolEmitPoint


class PointTool(QgsMapToolEmitPoint):
    def __init__(self, canvas, callback):
        super().__init__(canvas)
        self.callback = callback

    def canvasReleaseEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        self.callback(point)


def get_endpoints_config():
    yaml_path = os.path.join(os.path.dirname(__file__), '..', 'endpoints.yaml')
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)
