# Plan de trabajo para DJPlus v0.4

## Objetivo
Mejorar la estructura interna del proyecto sin agregar nuevas funciones, preparando la base para un desarrollo más mantenible.

## Pasos

### Paso 1 - Reorganizar la estructura
- Crear nuevas carpetas y mover archivos poco a poco.
- Verificar que la aplicación siga arrancando después de cada cambio.

### Paso 2 - Crear TrackRepository
- Centralizar las consultas a SQLite en una clase repository.
- Reemplazar las consultas dispersas por llamadas al repository.

### Paso 3 - Migrar a QTableView
- Reemplazar QTableWidget por QTableView + QAbstractTableModel.
- Mejorar rendimiento y facilitar futuras extensiones.

### Paso 4 - Integrar y probar
- Probar inicio de la app.
- Probar carga de la biblioteca.
- Probar búsqueda.
- Probar selección de pistas.

## Limpieza de nombres recomendada
- library.py → track_repository.py
- scanner.py → scanner_service.py
- library_view.py → library_view.py (ubicado en ui/views/)
- track_info.py → track_info_panel.py

## Criterio de aceptación
- La aplicación sigue funcionando tras cada movimiento.
- La arquitectura queda más clara y preparada para los próximos hitos.
- Se realiza un único commit al finalizar la versión v0.4.
