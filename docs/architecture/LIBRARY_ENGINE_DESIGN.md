# DJPlus Library Engine Design

## Estado y alcance

Este documento diseña el Motor de Biblioteca de DJPlus para bibliotecas de 10.000 a 250.000 pistas. No implementa cambios de código, migraciones, índices ni movimientos de archivos.

El objetivo es que la interfaz visual sea una consumidora pasiva de resultados y no conozca detalles de búsqueda, filtros, ordenamiento, carga, caché u optimizaciones.

## Arquitectura objetivo

```text
PySide6 UI
    │  LibraryQuery / comandos de usuario
    ▼
LibraryService
    │  casos de uso, estado de consulta, caché y coordinación
    ▼
TrackRepository
    │  consultas seguras, cursor, límites e hidratación mínima
    ▼
SQLite
    │  tablas, índices, FTS opcional y planes de consulta
    ▼
Archivo de biblioteca local
```

La dirección de dependencias debe ser siempre hacia abajo. La UI no importará `SessionLocal`, modelos SQLAlchemy ni reglas SQL. Los repositorios no importarán Qt. Los servicios no dependerán de widgets.

## Fase 1 — Análisis actual

### 1. Cuellos de botella actuales

1. `LibraryView.load_tracks()` consulta directamente al repositorio y conserva todas las entidades `Track` en `TrackTableModel`.
2. `QSortFilterProxyModel` filtra y ordena en el cliente, solicitando repetidamente valores al modelo Python. En la medición de 8.529 pistas, la apertura tomó 8,112 s y el ordenamiento 11,540 s.
3. La carga completa materializa entidades ORM aunque la tabla solo necesita campos de resumen.
4. El filtrado actual del proxy recorre filas y columnas en memoria, en lugar de permitir que SQLite use índices o una estrategia de búsqueda especializada.
5. `TrackRepository` mantiene una sesión de larga vida por instancia. Para operaciones de biblioteca futuras debe existir una política explícita de ciclo de vida y liberación de recursos.
6. No hay índices de consulta declarados para los campos que se mostrarán, filtrarán u ordenarán con frecuencia.

### 2. Responsabilidades mezcladas

| Componente actual | Responsabilidad válida | Responsabilidad que debe trasladarse |
|---|---|---|
| `LibraryView` | Renderizar controles, enviar intención del usuario y mostrar resultados | Decidir límite, cargar pistas, filtrar globalmente, ordenar globalmente y contar la biblioteca |
| `TrackTableModel` | Presentar una ventana de filas ya resueltas | Conservar toda la colección y servir como fuente de operaciones globales |
| `QSortFilterProxyModel` | Orden o filtro local de conjuntos pequeños y temporales | Ordenamiento y búsqueda de toda la biblioteca |
| `TrackRepository` | Ejecutar consultas de persistencia | Hoy expone consultas muy genéricas; debe recibir contratos de consulta ya validados por un servicio |
| `scanner.py` | Importar archivos y metadatos | Debe notificar cambios para invalidar cachés, no forzar decisiones de UI |

### 3. Responsabilidad exacta de `LibraryService`

`LibraryService` será la fachada del Motor de Biblioteca. Debe:

- validar y normalizar una consulta de biblioteca;
- definir valores por defecto, tamaño de lote máximo y columnas/órdenes permitidos;
- decidir si puede responder desde caché o si debe consultar al repositorio;
- coordinar filtrado, ordenamiento, cursores y carga incremental;
- devolver DTOs o proyecciones de fila, no entidades ORM expuestas a la UI;
- obtener el detalle de una pista por identificador;
- invalidar o actualizar cachés tras escaneos, edición de metadatos o eliminación;
- ofrecer una API estable a la UI aunque cambie SQLite, los índices o la estrategia de búsqueda;
- medir o registrar métricas técnicas de consulta cuando sea habilitado para desarrollo.

No debe:

- importar widgets o tipos de Qt;
- implementar reproducción, análisis musical, IA o sincronización;
- aceptar SQL, nombres de columna arbitrarios ni expresiones de orden desde la UI;
- asumir que la biblioteca completa cabe en memoria.

### 4. Contrato público propuesto

Los nombres definitivos se aprobarán antes de implementar. La interfaz debería depender de un contrato equivalente al siguiente:

| Método | Propósito | Resultado esperado |
|---|---|---|
| `load_library(query)` | Obtiene la primera ventana ordenada y filtrada | `LibraryPage` con filas, total opcional y cursor siguiente |
| `load_more(query, cursor)` | Obtiene el siguiente lote de la misma consulta | `LibraryPage` |
| `search(text, query=None)` | Crea o actualiza una consulta textual normalizada | `LibraryPage` |
| `filter(query, filters)` | Aplica filtros estructurados (BPM, key, rating, etc.) | `LibraryPage` |
| `sort(query, sort_spec)` | Reemplaza el orden de una consulta | `LibraryPage` |
| `refresh(query)` | Invalida resultados de esa consulta y recarga la primera ventana | `LibraryPage` |
| `count_tracks(filters=None)` | Cuenta pistas sin cargarlas | entero o `LibraryCount` |
| `get_track(track_id)` | Obtiene el detalle completo de una pista | `TrackDetail` o ausencia |
| `invalidate_cache(reason)` | Invalida entradas afectadas por cambios de biblioteca | sin resultado de UI |

Tipos de apoyo propuestos:

- `LibraryQuery`: texto, filtros estructurados, `SortSpec`, tamaño de lote y versión de consulta.
- `SortSpec`: columna permitida, dirección y desempate determinista por `id`.
- `LibraryPage`: `rows`, `next_cursor`, `has_more`, `total` opcional y metadatos de consulta.
- `TrackRow`: proyección liviana para tabla (`id`, artista, título, álbum, BPM, key, duración, rating).
- `TrackDetail`: información completa para inspector/editor futuro.

La UI conserva el cursor de la consulta actual como estado de presentación; el servicio conserva la política, validación y caché. El cursor debe ser opaco para la UI.

## Flujo de datos

```text
Usuario cambia búsqueda, filtro u orden
    │
    ▼
LibraryView emite una intención tipada
    │
    ▼
LibraryService normaliza, aplica debounce externo o coordinado y valida
    │
    ├── respuesta válida en caché ────────────────► LibraryPage
    │
    └── consulta necesaria
           │
           ▼
      TrackRepository ejecuta SQL parametrizado
           │
           ▼
      SQLite usa índice / FTS / cursor
           │
           ▼
      LibraryPage con proyección de columnas
           │
           ▼
      TrackTableModel reemplaza o agrega solo el lote recibido
```

Al editar, escanear o eliminar una pista:

```text
Servicio de escritura o escáner
    ▼
Transacción SQLite confirmada
    ▼
Evento interno de cambio de biblioteca
    ▼
LibraryService invalida caché y marca consultas afectadas para refresh
```

## Fase 2 — Diseño de índices SQLite

### Estado del modelo actual

`tracks` tiene `title`, `artist`, `album`, `bpm`, `key`, `rating` y `created_at`. No tiene `genre` ni `date_added` como columnas independientes. Para la propuesta:

- `genre` requerirá una migración futura y una decisión de normalización antes de indexarse.
- `created_at` puede servir temporalmente como fecha de alta técnica.
- `date_added` debe definirse como fecha de incorporación a la biblioteca si su semántica difiere de `created_at`.

No se deben crear índices hasta medir consultas reales con `EXPLAIN QUERY PLAN` y acordar las combinaciones de filtros/orden principales.

| Índice propuesto | Beneficio esperado | Costo | Cuándo conviene |
|---|---|---|---|
| `title COLLATE NOCASE, id` | Orden de títulos y búsqueda por prefijo (`titulo%`) sin ordenar todo en memoria | Espacio en disco y coste al insertar/editar título | Columna visible y orden frecuente |
| `artist COLLATE NOCASE, title COLLATE NOCASE, id` | Orden principal de DJ: artista y título; permite cursor estable | Más espacio que un índice simple; coste de escritura | Debe ser el índice inicial prioritario |
| `album COLLATE NOCASE, artist COLLATE NOCASE, title COLLATE NOCASE, id` | Navegación por álbum y orden coherente dentro del álbum | Índice compuesto más grande | Conviene si álbum es una navegación habitual |
| `bpm, id` | Rangos BPM y orden por BPM | Coste moderado de escritura; baja selectividad en colecciones homogéneas | Filtros de rango o preparación de sets futuros |
| `key COLLATE NOCASE, id` | Filtro y orden por tonalidad | Baja selectividad; beneficio limitado sin combinación | Conviene si key se usa activamente en biblioteca |
| `rating DESC, artist COLLATE NOCASE, title COLLATE NOCASE, id` | Favoritos y orden por valoración con desempate estable | Índice compuesto adicional | Conviene si rating se usa para navegar, no solo mostrar |
| `genre COLLATE NOCASE, artist COLLATE NOCASE, title COLLATE NOCASE, id` | Filtro/navegación por género | Requiere columna y taxonomía consistentes; coste de actualización | Solo tras definir `genre` y su calidad de datos |
| `date_added DESC, id` o `created_at DESC, id` | Vistas de añadidos recientes y cursor descendente | Espacio y escritura en cada inserción | Recomendable para importaciones y biblioteca reciente |

### Índices y búsqueda textual

Los índices B-tree anteriores no aceleran consultas con forma `LIKE '%texto%'`. Para búsqueda libre por artista, título y álbum a gran escala se recomienda evaluar, en una fase separada, una tabla virtual FTS5 sincronizada con `tracks`.

FTS5 aporta búsqueda de tokens y prefijos; implica tamaño extra, mantenimiento al cambiar metadatos y una política de normalización. No sustituye los índices de ordenamiento o de filtros numéricos.

### Política de índices

- Empezar con el índice de orden predeterminado y los índices ligados a filtros medidos.
- Preferir índices compuestos que cubran una consulta real a múltiples índices simples redundantes.
- Añadir `id` como desempate para que los cursores sean estables.
- Revisar tamaño de base, tiempos de escaneo/importación y planes de consulta tras cada índice.
- No indexar cada campo por defecto: cada índice acelera lectura y penaliza inserción, actualización y almacenamiento.

## Fase 3 — Comparación de rendimiento

Las estimaciones suponen un SSD, SQLite local con índices correctos y lotes de 100 a 500 filas. Deben validarse con benchmarks de 10.000, 50.000, 100.000 y 250.000 pistas con datos representativos.

| Estrategia | Ventajas | Desventajas | Complejidad | 10.000 | 50.000 | 100.000 | 250.000 |
|---|---|---|---|---|---|---|---|
| A. `QSortFilterProxyModel` global | Simple y ya integrado | Carga/ordena todo en memoria Python; bloquea UI | Baja | Límite práctico | Degradado | No viable | No viable |
| B. SQLite `ORDER BY` | Usa índices; orden global consistente; poca memoria si hay límite | Exige órdenes permitidos e índices; no resuelve por sí solo el scroll | Media | Muy bueno | Muy bueno | Bueno | Bueno con índices |
| C. Lazy loading | Apertura inmediata; solo obtiene lo visto | Requiere coordinación de estado; necesita orden global en BD | Media-alta | Muy bueno | Muy bueno | Muy bueno | Muy bueno |
| D. Carga incremental | Scroll natural y memoria acotada | Manejo de lotes, reset, cancelación y cursores | Media-alta | Muy bueno | Muy bueno | Muy bueno | Muy bueno |
| E. Caché | Reduce consultas repetidas y mejora navegación de vuelta | Invalidez, límites de memoria y métricas más complejas | Media | Complemento útil | Complemento útil | Necesaria con límites | Necesaria con límites |

### Estrategia recomendada

La estrategia de DJPlus debe ser B + C + D + E:

1. SQLite filtra y ordena; el repositorio usa solo SQL parametrizado y órdenes permitidos.
2. La primera ventana se carga mediante `LIMIT` y un orden determinista.
3. El scroll solicita lotes posteriores por cursor (`keyset pagination`), no por `OFFSET` profundo.
4. `TrackTableModel` mantiene únicamente las filas cargadas de la consulta vigente.
5. `LibraryService` mantiene una caché LRU acotada de páginas y de detalles, invalidada por cambios de biblioteca.
6. La búsqueda textual usa índices de prefijo inicialmente y evalúa FTS5 cuando el benchmark y los requisitos de búsqueda libre lo justifiquen.

`OFFSET` puede aceptarse en prototipos o saltos de página pequeños, pero no es la base para 100.000 o 250.000 pistas. `QSortFilterProxyModel` puede conservarse para vistas locales muy pequeñas, nunca para la tabla global.

### Objetivos de rendimiento propuestos

| Escala | Primera ventana | Cambio de filtro u orden | Memoria de filas en UI |
|---:|---:|---:|---:|
| 10.000 | < 250 ms | < 250 ms | Un lote, no la colección |
| 50.000 | < 350 ms | < 350 ms | Un lote, no la colección |
| 100.000 | < 500 ms | < 500 ms | Un lote, no la colección |
| 250.000 | < 750 ms | < 750 ms | Un lote, no la colección |

Estos objetivos excluyen el arranque completo del proceso y miden desde una solicitud ya recibida hasta que la primera página está lista para la UI. Deben incluir telemetría local de desarrollo y pruebas automatizadas de regresión.

## Fase 4 — Arquitectura de repositorios y servicios futuros

```text
                        ┌────────────────────────┐
                        │      LibraryService    │
                        │ consultas y caché      │
                        └───────┬────────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
  TrackRepository       CollectionRepository   PlaylistRepository
  pistas y proyecciones colecciones físicas     playlists y orden
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                ▼
                           SQLite / ORM

     SearchService       MetadataService       AnalysisRepository
     búsqueda/FTS        lectura y edición     resultados de análisis
          │                     │                     │
          └─────────────────────┴─────────────────────┘
                        servicios de aplicación

                       HistoryRepository
                       historial de reproducción
```

### Repositorios

| Componente | Responsabilidad futura | Límite explícito |
|---|---|---|
| `TrackRepository` | Proyecciones, detalle de pista, filtros/orden permitidos, cursor y conteos | No coordina caché ni decide experiencia de UI |
| `CollectionRepository` | Raíces escaneadas, estado de colección, configuración de importación | No lee archivos de audio directamente |
| `PlaylistRepository` | Playlists, posiciones y relaciones con pistas | No reproduce ni analiza |
| `HistoryRepository` | Eventos de reproducción y consultas históricas | No define la lógica del reproductor |
| `AnalysisRepository` | Persistencia de BPM, key, waveform y resultados futuros | No ejecuta análisis musical |

### Servicios

| Componente | Responsabilidad futura | Dependencias permitidas |
|---|---|---|
| `LibraryService` | Consulta de biblioteca, páginas, filtros, orden, caché e invalidación | Repositorios y configuración |
| `CollectionService` | Casos de uso de colecciones e importaciones | Collection/Track repositories y scanner futuro |
| `SearchService` | Normalización de texto, estrategia FTS/prefijo y ranking | TrackRepository o adaptador de búsqueda |
| `MetadataService` | Lectura, validación y escritura de metadatos de pista | TrackRepository y lector de archivos futuro |

Los servicios se comunicarán mediante contratos de dominio y eventos internos simples, no por acceso directo a widgets. La creación concreta de dependencias debe residir en el punto de arranque de la aplicación hasta que exista un contenedor de composición justificado.

## Fase 5 — Plugin ready

La arquitectura propuesta permite integrar futuras fuentes sin modificar el núcleo si se añaden adaptadores en los bordes del sistema.

| Integración futura | Tipo de adaptador | Núcleo que no debe cambiar |
|---|---|---|
| Traktor, Rekordbox, Serato | Importador/exportador de colecciones y playlists | `LibraryService`, repositorios y modelo de dominio base |
| Beatport, Discogs, MusicBrainz | Proveedor de enriquecimiento de metadatos | Contrato de `MetadataService` y validación de cambios |
| IA | Proveedor de sugerencias o clasificación asíncrona | Persistencia mediante `AnalysisRepository`, sin acoplar la consulta de biblioteca |
| Cloud | Sincronizador de eventos/estado o backend alternativo | Contratos de repositorio y servicios, no widgets |

Principios para preservar esta extensibilidad:

1. Los conectores implementan interfaces de entrada/salida y se registran fuera del dominio central.
2. Un plugin nunca recibe una sesión SQLite ni modifica tablas directamente.
3. Los plugins producen comandos, DTOs o eventos que los servicios validan.
4. La interfaz gráfica consulta el mismo `LibraryService` independientemente del origen de datos.
5. Las operaciones lentas de conectores se ejecutarán fuera del hilo de UI en una fase futura, con progreso y cancelación explícitos.

No se crea todavía una carpeta de plugins, SDK, registro dinámico ni integración externa.

## Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación propuesta |
|---|---|---|
| Índices excesivos | Importaciones y ediciones lentas; base más grande | Medir planes y añadir solo índices justificados |
| Cursores inestables | Duplicados o huecos al cargar más | Orden determinista con `id` y versión de consulta |
| Caché desactualizada | La UI muestra datos obsoletos | Invalidación por eventos de escritura y TTL/límite LRU acotado |
| Consultas de texto lentas | Mala percepción en bibliotecas grandes | Debounce, normalización, índices adecuados y evaluación de FTS5 |
| SQL dinámico inseguro | Consulta incorrecta o inyección lógica | Mapa cerrado de columnas y direcciones permitidas |
| Trabajo en hilo UI | Congelamientos | Mantener lotes pequeños y diseñar ejecución asíncrona en fase posterior |
| Refactorización amplia | Regresiones y pérdida de control | Implementar por verticales pequeños, sin mover archivos inicialmente |

## Roadmap técnico

### Sprint 5.2A — Contratos y consultas básicas

- Definir `LibraryQuery`, `SortSpec`, `TrackRow` y `LibraryPage`.
- Añadir consultas de primera página en `TrackRepository` con columnas permitidas, orden determinista y `LIMIT`.
- Añadir los índices mínimos aprobados y medir con `EXPLAIN QUERY PLAN`.
- Mantener el código existente hasta validar la nueva ruta en pruebas aisladas.

### Sprint 5.2B — `LibraryService`

- Crear `LibraryService` sin mover módulos existentes.
- Exponer carga inicial, búsqueda, filtro, orden, conteo y detalle.
- Centralizar límites de lote, validación y normalización.
- Añadir pruebas unitarias de contrato y consultas.

### Sprint 5.2C — Integración de UI incremental

- Sustituir la carga completa de `LibraryView` por la primera página de `LibraryService`.
- Reemplazar filtro/orden global del proxy por recargas consultadas a SQLite.
- Implementar scroll incremental a través de cursor.
- Medir apertura, orden, filtro, memoria y selección.

### Sprint 5.2D — Caché y búsqueda escalable

- Añadir caché LRU acotada por consultas y detalles.
- Definir invalidación tras escaneo y edición.
- Evaluar FTS5 con un corpus de 10.000 a 250.000 pistas.

### Sprint 5.2E — Validación y estabilización

- Construir bases de benchmark reproducibles para las cuatro escalas objetivo.
- Añadir regresiones de cursor, orden, filtros combinados y cambios de datos.
- Documentar límites, índices aprobados y decisiones de compatibilidad futura.

## Decisión requerida

La siguiente implementación debe comenzar por el Sprint 5.2A. Antes de escribir código se debe aprobar este diseño, especialmente:

- contratos de consulta y paginación por cursor;
- índices iniciales;
- objetivo de rendimiento;
- límites y política de caché;
- separación de responsabilidades entre `LibraryService` y `TrackRepository`.

## Implementación inicial — Sprint 5.2

Se incorporaron `LibraryService`, `SearchEngine`, `SortEngine` y `FilterEngine`. La UI delega carga, búsqueda y ordenamiento a `LibraryService`; `TrackRepository` ejecuta consultas SQLite con contratos validados. No se añadieron caché, paginación, Smart Collections ni cambios de esquema.

Con 8.529 pistas, la referencia anterior midió 7,758 s de apertura, 1,074 s de filtro y 11,262 s de ordenamiento. La nueva ruta SQLite midió 2,183 s, 0,027 s y 3,349 s. El orden restante incluye reconstruir la tabla Qt completa. No se añadieron índices: se medirán con páginas limitadas y `EXPLAIN QUERY PLAN` antes de justificarlos.
