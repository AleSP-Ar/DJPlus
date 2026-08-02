# DJPlus Documentation

DJPlus es una herramienta local de biblioteca musical orientada a DJs. Esta carpeta reúne la documentación técnica, de roadmap y de desarrollo del producto.

## Estructura

- [architecture/](architecture/): decisiones de arquitectura y diseños de motores futuros.
- [roadmap/](roadmap/): roadmap, hitos e historial de versiones.
- [development/](development/): registro de desarrollo y estándares de contribución.
- [diagrams/](diagrams/): diagramas de clases, secuencia y base de datos.

## Inicio rápido

```bash
pip install -r requirements.txt
python -m app.main
```

## Tecnología actual

- Python
- PySide6
- SQLAlchemy
- SQLite
- Mutagen

## Release candidate v0.5.0

- [Arquitectura actual](architecture/DJPLUS_ARCHITECTURE.md)
- [Diseño de migraciones y datos](architecture/DATABASE_DESIGN.md)
- [Historial de desarrollo](development/DEVELOPMENT_LOG.md)
