# Plugin Architecture

## Estado

No existe un sistema de plugins implementado en v0.5. Este documento fija sus límites para evitar acoplar el núcleo a integraciones futuras.

## Principios

- Los plugins viven en los bordes y dependen de contratos públicos, no de tablas SQLite ni widgets.
- Un plugin entrega DTOs, comandos o eventos; los servicios centrales validan y persisten cambios.
- La UI consulta los mismos servicios con independencia del origen de datos.
- Las operaciones de red, importación y análisis futuro no se ejecutarán en el hilo de interfaz.

## Integraciones previstas

- Importación/exportación: Traktor, Rekordbox y Serato.
- Metadatos: Beatport, Discogs y MusicBrainz.
- Servicios futuros: IA y Cloud.

No se crean todavía SDK, registro dinámico ni conectores.
