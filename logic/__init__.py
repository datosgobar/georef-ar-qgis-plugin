import os

import yaml


def get_endpoints_config():
    yaml_path = os.path.join(os.path.dirname(__file__), '..', 'endpoints.yaml')
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)