# DJPlus

DJPlus es una herramienta local para gestionar una biblioteca musical de forma simple, rápida y pensada para DJs.

## ¿Qué es DJPlus?

DJPlus permite:
- escanear carpetas de música,
- almacenar metadatos en SQLite,
- explorar pistas desde una interfaz visual,
- preparar la base para futuras funciones como edición de tracks, análisis BPM/Key, crates y preview player.

## Objetivos

- Organizar bibliotecas musicales locales.
- Mantener una estructura clara y escalable.
- Preparar el proyecto para evolucionar hacia un flujo DJ más completo.

## Tecnologías

- Python
- PySide6 para la interfaz gráfica
- SQLAlchemy para la base de datos
- SQLite como motor local
- Mutagen para leer metadatos de audio

## Instalación

1. Crear un entorno virtual.
2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

## Ejecución

```bash
python app/main.py
```
