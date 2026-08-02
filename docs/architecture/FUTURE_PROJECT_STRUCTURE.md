# Propuesta de estructura objetivo para DJPlus

## Objetivo

Esta propuesta prepara el crecimiento de DJPlus como una Biblioteca Profesional sin mover archivos ni cambiar el comportamiento actual. La reorganización se realizará por etapas y solo tras aprobación explícita.

## Estructura objetivo

```text
app/
├── core/
│   ├── database.py          # Motor, sesiones e inicialización de la base local.
│   ├── settings.py          # Configuración de la aplicación.
│   └── paths.py             # Rutas de datos y recursos.
├── models/
│   └── track.py             # Entidades SQLAlchemy del dominio.
├── repository/
│   └── track_repository.py  # Consultas y persistencia de pistas.
├── services/
│   ├── library_service.py   # Operaciones de biblioteca.
│   └── scanner_service.py   # Escaneo e importación de archivos.
├── plugins/
│   └── __init__.py          # Punto de extensión futuro, sin implementar plugins aún.
├── ui/
│   ├── views/               # Pantallas principales.
│   ├── widgets/             # Componentes visuales reutilizables.
│   ├── models/              # Modelos Qt, como TrackTableModel.
│   └── main_window.py       # Composición de la ventana principal.
├── resources/
│   ├── icons/
│   ├── images/
│   └── themes/
└── config/
    └── __init__.py          # Configuración distribuible de la aplicación.

docs/
├── ARCHITECTURE.md
├── FUTURE_PROJECT_STRUCTURE.md
└── ...
```

## Responsabilidades

- `core/` contiene infraestructura compartida y no depende de la interfaz.
- `models/` define las entidades del dominio y no incluye consultas ni widgets.
- `repository/` encapsula el acceso a datos.
- `services/` coordina casos de uso, sin acoplarse a Qt.
- `plugins/` queda reservado como frontera de extensión futura; no forma parte de v0.5.
- `ui/` presenta los datos mediante vistas, widgets y modelos Qt.
- `resources/` agrupa activos que hoy están en `assets/`.
- `config/` aloja configuración de aplicación separada de la infraestructura.
- `docs/` conserva la documentación funcional, técnica y de decisiones.

## Migración futura propuesta

1. Crear la estructura de destino sin mover lógica.
2. Mover un módulo por cambio y corregir sus imports.
3. Validar el arranque y la biblioteca después de cada movimiento.
4. Eliminar módulos heredados solo cuando no existan referencias.
5. Documentar cada decisión arquitectónica y crear un commit por hito aprobado.

## Estado

Este documento es una propuesta. No autoriza ni realiza refactorizaciones.
