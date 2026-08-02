# LibraryService Design — Sprint 5.2.1

## Objetivo

Introducir `LibraryService` como única dependencia de biblioteca para la UI, preservando el comportamiento actual de la aplicación. La transición inicial no incorpora búsquedas SQL, ordenamiento SQL, filtros, caché, paginación ni carga incremental.

## Diseño aprobado

```text
LibraryView
    ▼
LibraryService
    ▼
TrackRepository
    ▼
SQLite
```

`LibraryView` no importará ni instanciará `TrackRepository`. `LibraryService` encapsulará el repositorio y expondrá operaciones de lectura de biblioteca.

## API inicial

| Método | Responsabilidad actual | Evolución posterior |
|---|---|---|
| `load_library()` | Cargar las pistas de la biblioteca con el comportamiento vigente | Recibirá `LibraryQuery` y devolverá `LibraryPage` en Sprint 5.2.2+ |
| `count_tracks()` | Obtener el total de pistas | Admitirá filtros cuando se implemente `FilterService` |
| `close()` | Liberar recursos del repositorio | Mantendrá el ciclo de vida de dependencias |

## Límites

- No importa Qt ni widgets.
- No construye SQL ni accede a sesiones de SQLAlchemy.
- No implementa reglas de búsqueda, ordenamiento, filtrado ni caché.
- No modifica los modelos de datos ni el esquema SQLite.
- No cambia los resultados que ve el usuario en la biblioteca actual.

## Pruebas de aceptación

1. La UI no tiene importaciones de `TrackRepository`.
2. La aplicación carga la misma cantidad de pistas que antes.
3. El contador de biblioteca sigue funcionando.
4. El filtro, ordenamiento y selección actuales conservan su comportamiento.
5. Las pruebas unitarias del servicio validan delegación y cierre de recursos.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Duplicar lógica del repositorio | El servicio delega sin transformar datos en esta fase |
| Sesión sin cierre | `LibraryView` cierra el servicio cuando se cierra la vista |
| Ampliar alcance | Search, sort, filter y cache quedan fuera de Sprint 5.2.1 |

## Decisión

Este diseño es deliberadamente pequeño. Establece la frontera de dependencias sin anticipar los contratos de paginación que se implementarán en los sprints posteriores.
