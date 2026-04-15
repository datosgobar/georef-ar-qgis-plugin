import os
import tempfile
import zipfile

def get_local_resource(response, formato, iface):
    try:
        temp_dir = tempfile.mkdtemp()

        if formato == 'shp':
            # Lógica para ZIP/SHP que ya tenías
            zip_path = os.path.join(temp_dir, "data.zip")
            with open(zip_path, 'wb') as f:
                f.write(response.content)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            for file in os.listdir(temp_dir):
                if file.endswith(".shp"):
                    return os.path.join(temp_dir, file)
        else:
            # Lógica para archivos planos (GPKG, GeoJSON, CSV)
            file_path = os.path.join(temp_dir, f"data.{formato}")
            with open(file_path, 'wb') as f:
                f.write(response.content)
            return file_path
    except Exception as e:
        iface.messageBar().pushMessage("Error Utils", str(e), level=3)
    return None