# Development Log

## 2026-08-01

- Se creó la interfaz PySide6.
- Se implementó la biblioteca visual.
- Se agregó ordenamiento por columnas.
- Se incorporó el panel de información de la biblioteca.
- Se reorganizó la arquitectura interna con TrackRepository y TrackTableModel.
- Se integró QTableView + QSortFilterProxyModel.
- Se dejó la vista preparada para una versión estable v0.4.

### Próximo objetivo

- Cerrar la versión v0.4 con un commit y tag finales.
- Iniciar el desarrollo del Editor de Track en v0.5.

## 2026-08-02 — Motor de Biblioteca

- Se incorporaron LibraryService, SearchEngine, SortEngine y FilterEngine.
- La UI delega consultas de biblioteca a LibraryService; SQLite ejecuta búsqueda y ordenamiento.
- Se añadieron pruebas unitarias para la capa de servicio y los motores.
- En 8.529 pistas: apertura 7,758 s → 2,183 s; filtro 1,074 s → 0,027 s; ordenamiento 11,262 s → 3,349 s.
- No se añadieron índices porque la siguiente limitación es materializar todas las filas Qt.

## 2026-08-02 — Sprint 5.3: Virtual Library

- `TrackTableModel` carga 200 pistas inicialmente y solicita páginas adicionales mediante `canFetchMore()` y `fetchMore()`.
- `LibraryService` conserva el estado de la consulta y reinicia la paginación al buscar, filtrar u ordenar.
- `TrackRepository` ejecuta páginas SQLite con `LIMIT/OFFSET`; no se mantienen cursores abiertos entre lotes.
- El contador muestra pistas cargadas frente al total de resultados sin repetir el `COUNT` durante el scroll.

## 2026-08-02 — Sprint 5.4: Collection Engine

- Se añadieron colecciones manuales persistentes y su relación muchos-a-muchos con pistas.
- La UI usa exclusivamente `CollectionService`; `CollectionRepository` concentra la persistencia SQLite.
- El panel de Colecciones permite crear, renombrar, eliminar y seleccionar colecciones.
- El tipo `smart` queda reservado en el modelo de datos para la próxima etapa, sin lógica de Smart Collections implementada.

## 2026-08-02 — Sprint 5.5: Playlist Engine

- Se añadieron playlists separadas de Collections, con orden manual persistente de pistas.
- `PlaylistRepository` evita duplicados y mantiene posiciones contiguas al mover o quitar una pista.
- La UI usa exclusivamente `PlaylistService` mediante un panel básico de administración.
- Se dejó documentada la futura integración de Set Builder, sin implementar reproducción ni drag and drop.

## 2026-08-02 — Sprint 5.6: Favorites + History Engine

- Se añadió el estado persistente de favorito por pista, accesible mediante `FavoriteService`.
- Se incorporó `track_history` con eventos de selección, reproducción, alta y uso en playlist.
- La selección en la biblioteca, el escáner y el agregado a playlists registran los eventos disponibles.
- Se documentó el uso futuro de historial por Smart Collections e IA, sin implementar esas funciones.

## 2026-08-02 — Sprint 5.7: Smart Collections Engine

- Se añadieron reglas persistentes para colecciones de tipo `smart`, manteniendo intactas las colecciones manuales.
- `SmartRuleEngine` traduce reglas soportadas a `FilterCriteria` con semántica AND.
- `SmartCollectionService` evalúa mediante `LibraryService`, manteniendo la consulta SQLite y la carga incremental.
- El panel permite crear una colección smart y visualizar sus reglas; no se añadió editor avanzado, IA ni recomendaciones.

## 2026-08-02 — Sprint 5.8: Stabilization & Release Candidate

- Se centralizó la versión v0.5.0 en `app.version.VERSION`.
- Se reemplazó la inicialización ad hoc por migraciones SQLite registradas e idempotentes.
- Se añadieron pruebas de integración para importación, biblioteca, favoritos, playlists, historial y Smart Collections.
- Se documentaron arquitectura, módulos legacy, deuda técnica, riesgos y recomendaciones para v0.6.
- Validación RC: 35 pruebas automatizadas correctas; benchmark visual sobre 8.529 pistas correcto.
- El cierre y cualquier commit/tag de v0.5.0 quedan pendientes de aprobación explícita.

## 2026-08-02 — Sprint 6.1: Import Engine

- Se incorporaron ScannerService, MetadataService, ImportQueue, ImportService, ImportWorker y TrackImportService.
- Las migraciones 0002 y 0003 agregan trabajos persistentes y snapshots de archivo.
- Cada alta o actualización de pista se coordina con historial e ImportItem dentro de un Unit of Work.
- El motor conserva rating, favoritos, playlists, collections e historial existentes.

## 2026-08-02 — Sprint 6.1.7A: Release Hardening

- Se centralizó la versión objetivo 0.6.1 y se actualizó la documentación de cierre.
- El arranque de base usa exclusivamente migraciones versionadas.
- Se normalizan filepaths para compatibilidad entre rutas relativas heredadas y rutas absolutas de importación.
- Los errores persistidos se acotan a 500 caracteres y se agregó un benchmark reproducible del motor.
