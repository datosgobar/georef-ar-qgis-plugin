#!/bin/bash

set -e

echo "=== 1. Escaneando código y UIs (lupdate) ==="
#lupdate -extensions py,ui ./*.py ./logic/*.py ./ui/*.ui -ts ./i18n/GeorefArApi_es.ts -target-language es

echo "=== 2. Compilando diccionario binario (lrelease) ==="
lrelease ./i18n/GeorefArApi_es.ts -qm ./i18n/GeorefArApi_es.qm

echo "=== 3. Compilando recursos de Qt (iconos) ==="
pyrcc5 resources.qrc -o resources.py

echo "✅ ¡Todo compilado con éxito! Reiniciá QGIS para ver los cambios."