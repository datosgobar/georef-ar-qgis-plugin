import os
import tempfile
import zipfile

import requests


def get_shp_file(source, iface):
    try:
        # 2. Descargar el archivo ZIP temporalmente
        respuesta = requests.get(source)
        if respuesta.status_code == 200:
            # Creamos una carpeta temporal en /tmp/
            temp_dir = tempfile.mkdtemp()
            zip_path = os.path.join(temp_dir, "georef_data.zip")

            with open(zip_path, 'wb') as f:
                f.write(respuesta.content)

            # 3. Descomprimir el contenido
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # 4. Buscar el archivo .shp dentro de la carpeta extraída
            shp_file = None
            for file in os.listdir(temp_dir):
                if file.endswith(".shp"):
                    shp_file = os.path.join(temp_dir, file)
                    break

            return shp_file

        else:
            iface.messageBar().pushMessage("Error", f"Error de API: {respuesta.status_code}", level=3)

    except Exception as e:
        iface.messageBar().pushMessage("Error Crítico", str(e), level=3)