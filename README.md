# Georef AR - QGIS Plugin

[![QGIS Version](https://img.shields.io/badge/QGIS-3.28%20%2B-green.svg)](https://qgis.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Complemento oficial para **QGIS** que permite consumir e integrar de forma directa los datos geoespaciales del **Sistema de Información Geográfica de Georef Argentina**. 

Con este plugin podés buscar, filtrar y cargar provincias, departamentos, localidades censales y asentamientos de toda la República Argentina como capas vectoriales nativas en tu proyecto, sin necesidad de descargar archivos externos manualmente.

---

## ✨ Características principales

* **Arquitectura Dinámica:** Interfaz construida a partir de configuraciones (`endpoints.yaml`), lo que permite que el plugin se adapte automáticamente a los parámetros de la API.
* **Filtros en Cascada:** Selección inteligente de departamentos y localidades basados en la provincia seleccionada previamente.
* **Formatos Flexibles:** Descarga datos en formato de geometría de **Puntos (GeoJSON)** o **Polígonos (GeoPackage)** según disponibilidad del endpoint.
* **Carga Nativa:** Agrega las capas automáticamente al panel de capas de QGIS con el Sistema de Referencia de Coordenadas correcto (**WGS 84 / EPSG:4326**).

---

## 🚀 Instalación

### Opción 1: Desde el Repositorio Oficial de QGIS (Recomendado)
1. En QGIS, ir al menú superior: **Complementos** -> **Administrar e instalar complementos...**
2. En la barra de búsqueda, escribir `Georef AR`.
3. Seleccionar el plugin y hacer clic en **Instalar complemento**.

### Opción 2: Instalación Manual (Desarrollo)
1. Descargá este repositorio como un archivo `.zip`.
2. Descomprimilo en la ruta de plugins de tu perfil de QGIS:
   * **Windows:** `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   * **Linux:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   * **macOS:** `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
3. Reiniciá QGIS y activalo desde el administrador de complementos.

---

## 🛠️ ¿Cómo se usa?

1. Hacé clic en el ícono de **Georef AR** en la barra de herramientas de QGIS (o buscalo en el menú *Web* / *Vectorial*).
2. Seleccioná el **Endpoint** que querés consultar (ej. *Asentamientos*).
3. Utilizá los desplegables dinámicos para acotar tu búsqueda (por ejemplo, filtrar por una Provincia específica).
4. *(Opcional)* Modificá la cantidad máxima de resultados o el tipo de geometría si el endpoint lo permite.
5. Hacé clic en **Buscar y Cargar**. ¡La capa se añadirá automáticamente a tu mapa!

---

## ⚙️ Estructura del Proyecto (Para Desarrolladores)

El plugin fue refactorizado para soportar adición de nuevos campos o endpoints modificando únicamente el archivo de configuración, sin tocar el código central de Python:

* `endpoints.yaml`: Define los endpoints de la API, los tipos de widgets de Qt (`list`, `text`), valores por defecto y lógicas de dependencia.
* `main_plugin.py`: Contiene el motor genérico que lee el YAML, genera la interfaz gráfica (UI) en caliente y gestiona las peticiones de red.
* `metadata.txt`: Metadatos requeridos por el ecosistema QGIS.

---

## 📄 Licencia

Este proyecto está bajo la Licencia **MIT**. Consultá el archivo [LICENSE](LICENSE) para más detalles.

---
Desarrollado y mantenido por **Datos Argentina** y la comunidad de software libre.