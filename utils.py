import os
import tempfile
import zipfile
import requests


def get_local_resource(url, formato, iface):
    try:
        respuesta = requests.get(url, timeout=30)
        if respuesta.status_code == 200:
            temp_dir = tempfile.mkdtemp()

            if formato == 'shp':
                # Lógica para ZIP/SHP que ya tenías
                zip_path = os.path.join(temp_dir, "data.zip")
                with open(zip_path, 'wb') as f:
                    f.write(respuesta.content)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                for file in os.listdir(temp_dir):
                    if file.endswith(".shp"):
                        return os.path.join(temp_dir, file)
            else:
                # Lógica para archivos planos (GPKG, GeoJSON, CSV)
                file_path = os.path.join(temp_dir, f"data.{formato}")
                with open(file_path, 'wb') as f:
                    f.write(respuesta.content)
                return file_path
        else:
            iface.messageBar().pushMessage("Error", f"API: {respuesta.status_code} en URL: {url}", level=2)
    except Exception as e:
        iface.messageBar().pushMessage("Error Utils", str(e), level=3)
    return None