# Arquitectura DJPlus

## Visión general

DJPlus está organizado para separar claramente:
- la base de datos,
- la lógica de acceso a datos,
- los servicios,
- y la interfaz gráfica.

## Estructura propuesta

- app/database/: configuración de SQLAlchemy y modelos.
- app/repository/: acceso centralizado a las pistas.
- app/services/: lógica de negocio y procesamiento.
- app/ui/: vistas, widgets y diálogos.
- app/utils/: utilidades compartidas.

## Flujo de datos

1. El escáner lee archivos de audio.
2. Se almacenan en SQLite mediante los modelos.
3. La UI consulta los datos a través de repositories y servicios.
4. La biblioteca muestra los resultados en la interfaz.

## Base de datos

La base local se gestiona con SQLite y SQLAlchemy. La tabla principal es tracks.

## Repository

Los repositories encapsulan las consultas a la base de datos para evitar duplicar lógica.

## Servicios

Los servicios contienen operaciones más complejas como escaneo, análisis y preparación de datos.

## UI

La interfaz se organiza en vistas y widgets reutilizables. La idea es que la capa visual dependa de repositorios y servicios, no de consultas directas a la base.
