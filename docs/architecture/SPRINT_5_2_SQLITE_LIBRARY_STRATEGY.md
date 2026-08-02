# Sprint 5.2 — Estrategia de filtrado y ordenamiento escalable

## Contexto

La carga completa actual de 8.529 pistas funciona, pero el ordenamiento en `QSortFilterProxyModel` tardó aproximadamente 11,5 segundos y la apertura entre 8 y 16 segundos. La causa principal es que Qt debe pedir datos al modelo Python repetidamente, conservar todas las filas en memoria y ordenar en la capa visual.

Este documento compara alternativas para trasladar trabajo a SQLite sin implementar cambios todavía.

## Criterios de comparación

- Los tiempos son estimaciones para una base SQLite local, con índices adecuados, SSD y una interfaz que muestra solo una ventana de resultados. No sustituyen benchmarks en el equipo objetivo.
- El rendimiento de búsqueda depende de la consulta. `LIKE '%texto%'` no aprovecha un índice B-tree convencional; para búsqueda libre a escala se debe evaluar SQLite FTS5.
- Las cifras expresan el tiempo percibido para obtener y mostrar la primera página, no el tiempo de recorrer todas las pistas.

## 1. Ordenamiento en `QSortFilterProxyModel`

La aplicación carga todas las pistas en `TrackTableModel` y `QSortFilterProxyModel` filtra y ordena en memoria.

### Ventajas

- Implementación directa y ya disponible en la interfaz actual.
- Ordenamiento y filtrado inmediatos para conjuntos pequeños ya cargados.
- No requiere ampliar el repositorio ni diseñar contratos de consulta.

### Desventajas

- Carga y retiene todas las entidades SQLAlchemy en memoria.
- El proxy solicita datos al modelo Python muchas veces durante el ordenamiento.
- El coste aumenta con el número total de pistas, aunque el usuario solo vea unas pocas filas.
- El filtrado actual recorre las columnas de todas las filas en el cliente.

### Complejidad

Baja. No requiere cambios estructurales, pero no resuelve la escalabilidad.

### Impacto arquitectónico

Mantiene la consulta dentro de la vista y acopla el rendimiento de biblioteca a Qt y a entidades ORM materializadas.

### Rendimiento esperado

| Biblioteca | Apertura / primera vista | Filtro y ordenamiento | Evaluación |
|---:|---|---|---|
| 10.000 | Segundos; cercano a la medición actual | Varios segundos | Límite práctico |
| 50.000 | Decenas de segundos y alto uso de memoria | Decenas de segundos | No recomendable |
| 100.000 | Muy alto riesgo de bloqueo o experiencia degradada | Muy lento | No viable |

## 2. Ordenamiento mediante `ORDER BY` en SQLite

El repositorio recibe el criterio de ordenamiento y solicita a SQLite solo las filas necesarias, por ejemplo: `ORDER BY artist COLLATE NOCASE, title COLLATE NOCASE, id LIMIT :limit`.

### Ventajas

- SQLite ordena datos cerca del almacenamiento y evita ordenar objetos Python en Qt.
- Permite índices por los órdenes más usados: artista, título, álbum, BPM, rating y fecha.
- Reduce memoria y tiempo de apertura al traer una cantidad acotada de filas.
- Centraliza consultas en `TrackRepository` y conserva la UI como consumidora de resultados.

### Desventajas

- Requiere definir una lista permitida de columnas y direcciones; no se deben interpolar valores libres en SQL.
- Cada orden frecuente puede necesitar un índice compuesto distinto.
- Un `ORDER BY` sin índice apropiado puede crear tablas temporales y perder parte de la mejora.
- La búsqueda parcial con comodín inicial requiere una estrategia adicional.

### Complejidad

Media. Deben evolucionar repositorio, modelo de tabla y contrato de carga.

### Impacto arquitectónico

Positivo. El repositorio pasa a exponer consultas de biblioteca y la UI deja de decidir cómo se ordenan todos los datos en memoria.

### Rendimiento esperado

| Biblioteca | Primera página con índice | Cambio de orden | Evaluación |
|---:|---|---|---|
| 10.000 | Decenas de milisegundos a menos de 0,2 s | Habitualmente < 0,2 s | Muy bueno |
| 50.000 | Habitualmente < 0,3 s | Habitualmente < 0,3 s | Bueno |
| 100.000 | Habitualmente < 0,5 s | Habitualmente < 0,5 s | Viable |

## 3. Carga incremental (lazy loading)

El modelo Qt solicita más filas cuando el usuario se aproxima al final de las filas ya cargadas. La primera carga contiene una ventana pequeña y las siguientes se agregan bajo demanda.

### Ventajas

- Apertura rápida y memoria estable.
- El usuario no espera a que se materialice la biblioteca completa.
- Encaja con `QAbstractTableModel` mediante `canFetchMore()` y `fetchMore()`.

### Desventajas

- Mayor complejidad de estado: lote actual, fin de resultados, reinicio por filtro y cancelación de consultas antiguas.
- Si el ordenamiento es local, deja de ser correcto cuando llegan filas posteriores; por ello debe combinarse con `ORDER BY` en SQLite.
- Requiere tratar correctamente desplazamientos rápidos y cambios de filtro.

### Complejidad

Media-alta. Es una mejora de experiencia, no una sustitución del ordenamiento en base de datos.

### Impacto arquitectónico

Introduce un modelo de consulta paginado entre UI y repositorio. Conviene que `LibraryService` coordine la solicitud y que `TrackTableModel` solo mantenga la ventana cargada.

### Rendimiento esperado

| Biblioteca | Primera página | Desplazamiento | Evaluación |
|---:|---|---|---|
| 10.000 | Muy rápido | Fluido con lotes apropiados | Muy bueno |
| 50.000 | Muy rápido | Fluido si SQLite ordena | Muy bueno |
| 100.000 | Muy rápido | Fluido con cursores estables | Viable |

## 4. Paginación

La interfaz solicita páginas explícitas de resultados. Puede implementarse con `LIMIT/OFFSET` o, preferentemente para navegación secuencial, con paginación por cursor (keyset pagination).

### Ventajas

- Límite claro de memoria, transferencia y trabajo de UI.
- Simplifica la medición y el control de carga.
- Funciona naturalmente con filtrado y ordenamiento delegados a SQLite.

### Desventajas

- Una interfaz de páginas explícitas es menos natural para una biblioteca musical que el scroll continuo.
- `OFFSET` se degrada a medida que aumenta el número de página, especialmente con 100.000 pistas.
- La paginación por cursor requiere un orden determinista: añadir `id` como desempate y conservar el último valor visto.

### Complejidad

Media con `LIMIT/OFFSET`; media-alta con cursor, que es la opción escalable.

### Impacto arquitectónico

El repositorio debe devolver resultados y metadatos de navegación. La UI puede representarlo como botones de página o como fuente para carga incremental.

### Rendimiento esperado

| Biblioteca | `LIMIT/OFFSET` inicial | Páginas profundas con `OFFSET` | Cursor (keyset) |
|---:|---|---|---|
| 10.000 | Rápido | Aceptable | Rápido |
| 50.000 | Rápido | Variable, puede degradarse | Rápido |
| 100.000 | Rápido | No recomendable | Rápido y estable |

## 5. Combinación de técnicas

La solución combina filtrado y ordenamiento en SQLite, índices alineados con las consultas, búsqueda escalable, y carga incremental alimentada por páginas con cursor.

### Ventajas

- Mantiene una apertura rápida sin limitar artificialmente el tamaño real de la biblioteca.
- El orden es global y consistente porque se calcula antes de que Qt reciba cada lote.
- Escala en memoria y tiempo para colecciones mayores.
- Separa responsabilidades: repositorio consulta, servicio coordina, modelo Qt presenta.

### Desventajas

- Es la alternativa de mayor diseño e implementación inicial.
- Exige pruebas de consistencia al cambiar filtros, orden, datos y tamaño de lote.
- Requiere definir índices y revisar el plan de consultas con `EXPLAIN QUERY PLAN`.

### Complejidad

Alta, pero incremental y justificable para una Biblioteca Profesional.

### Impacto arquitectónico

Muy positivo. Formaliza una API de consulta de biblioteca y reduce la dependencia de `QSortFilterProxyModel` para operaciones globales.

### Rendimiento esperado

| Biblioteca | Apertura / primera página | Filtro y orden | Memoria de UI | Evaluación |
|---:|---|---|---|---|
| 10.000 | < 0,2 s objetivo | < 0,2 s objetivo | Acotada al lote | Excelente |
| 50.000 | < 0,3 s objetivo | < 0,3 s objetivo | Acotada al lote | Excelente |
| 100.000 | < 0,5 s objetivo | < 0,5 s objetivo | Acotada al lote | Recomendada |

## Recomendación para DJPlus v1.0

Adoptar la combinación de `ORDER BY` y filtrado en SQLite, índices específicos, carga incremental con scroll y paginación por cursor interna. La UI no debe usar `QSortFilterProxyModel` para ordenar o filtrar toda la biblioteca.

### Arquitectura propuesta

```text
LibraryView
  -> LibraryService (estado de consulta, debounce y cancelación)
    -> TrackRepository (filtros permitidos, ORDER BY seguro, cursor y LIMIT)
      -> SQLite (índices y, si corresponde, FTS5)
  <- TrackTableModel (solo las filas cargadas)
```

### Fases recomendadas

1. Definir un objeto inmutable de consulta: texto, orden, dirección, tamaño de lote y cursor.
2. Implementar en el repositorio la primera página ordenada mediante `ORDER BY`, `LIMIT` e índices.
3. Mover el filtrado textual a SQLite; evaluar FTS5 cuando la búsqueda parcial actual no alcance.
4. Reemplazar el ordenamiento y filtro global de Qt por recargas de consulta con debounce.
5. Añadir `fetchMore()` con cursor estable y pruebas en bibliotecas de 10.000, 50.000 y 100.000 pistas.
6. Medir apertura, consulta, desplazamiento, memoria y planes de ejecución antes de declarar el hito terminado.

## Decisión pendiente

No se propone implementar esta arquitectura en Sprint 5.2. Este documento debe aprobarse antes de modificar repositorios, servicios, modelos Qt, índices o interfaz.
