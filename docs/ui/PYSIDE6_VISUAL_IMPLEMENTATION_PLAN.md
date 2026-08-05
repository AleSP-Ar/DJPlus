# Plan de implementación visual PySide6 — DJPlus

## 1. Propósito

Trasladar a la aplicación PySide6 el sistema visual aprobado en los prototipos de Biblioteca, Playlist y DJ Set, preservando el comportamiento existente y evitando cambios de backend, base de datos o esquema.

Este documento distingue entre:

- **Existente:** clases y archivos ya presentes en el repositorio.
- **Propuesto:** archivos o componentes nuevos que se crearán durante los sprints visuales.
- **Diferido:** cambios funcionales, integraciones externas o ampliaciones fuera del alcance visual.

## 2. Estado verificado del repositorio

- Rama visual: `release/v1.0.0-visual-polish`.
- Último commit verificado: `2cecafc Unify shared UI prototype components`.
- Worktree verificado como limpio antes de redactar este plan.
- Los prototipos HTML/CSS comparten tokens y componentes visuales centralizados.
- No se detectaron archivos `.qss` en el relevamiento actual; el sistema QSS común deberá incorporarse como parte del Sprint 1.

## 3. Superficies PySide6 existentes

| Superficie | Archivo o clase existente | Estado para el trabajo visual |
|---|---|---|
| Composición principal | `app/ui/main_window.py` — `MainWindow` | Reutilizable; concentrará shell, navegación y workspace |
| Dependencias de ventana | `app/ui/main_window.py` — `MainWindowDependencies` | Preservar para inyección y tests |
| Biblioteca | `app/ui/library_view.py` — `LibraryView` | Base funcional existente; rediseño visual prioritario |
| Modelo de tabla | `app/ui/models/track_table_model.py` | Reutilizable; no mezclar cambios visuales con lógica de datos |
| Playlist | `app/ui/playlist_panel.py` — `PlaylistPanel` | Base funcional existente; requiere nueva composición visual |
| Colecciones | `app/ui/collection_panel.py` — `CollectionPanel` | Preservar y adaptar al shell común |
| Importación | `app/ui/import_manager_panel.py` — `ImportManagerPanel` | Preservar flujo funcional y aplicar tokens comunes |
| Metadata | `app/ui/track_metadata_panel.py` — `TrackMetadataPanel` | Preservar validaciones y adaptar estilos |
| Assistant | `app/ui/assistant_panel.py` — `AssistantPanel` | Preservar arquitectura actual; aplicar shell y estados |
| Diagnóstico | `app/ui/diagnostics_panel.py` — `DiagnosticsPanel` | Preservar contenido y adaptar jerarquía visual |
| Feedback común | `app/ui/feedback.py` | Reutilizable para mensajes, confirmaciones y estados |
| Preview Player | `app/ui/widgets/preview_player_bar.py` — `PreviewPlayerBar` | Reutilizable; rediseño visual sin autoplay |
| Servicio de Preview | `app/services/preview_player.py` — `PreviewPlayerService` | No modificar salvo corrección funcional separada y aprobada |
| DJ Set | No se detectó panel PySide6 específico en el relevamiento | Crear una superficie visual nueva apoyada en servicios existentes |
| Servicios de set | `app/services/set_builder_facade.py` y servicios relacionados | Reutilizables; no trasladar lógica a la UI |

## 4. Reglas contextuales obligatorias

1. **Biblioteca**
   - No tendrá barra superior de análisis.
   - Permitirá tabla y, cuando corresponda, vista de tarjetas.
   - La selección de una pista no mostrará waveform en el encabezado.

2. **Pista individual**
   - El waveform individual aparecerá únicamente dentro del `PreviewPlayerBar`.
   - Cargar una pista no iniciará reproducción automática.

3. **Playlist**
   - Mostrará una curva o secuencia de energía segmentada por pista.
   - El ancho de cada segmento representará duración relativa cuando haya datos.
   - Los estados de datos faltantes no deben romper el layout.

4. **DJ Set**
   - Mostrará viaje de energía, capítulos, transiciones y peak times.
   - Permitirá representar curva real y curva objetivo.
   - Conflictos o datos faltantes se mostrarán visualmente sin alterar la información persistida.

5. **Límites**
   - Sin cambios de backend, schema, migraciones o base de datos en los sprints visuales.
   - Sin integraciones con servicios externos.
   - Sin autoplay.
   - Sin eliminación de widgets existentes sin verificar dependencias y tests.

## 5. Arquitectura visual propuesta

### 5.1 Sistema de estilos

Crear durante el Sprint 1:

- `app/ui/styles/__init__.py`
- `app/ui/styles/tokens.py`
- `app/ui/styles/app.qss`
- `app/ui/styles/style_loader.py`

Responsabilidades:

- `tokens.py`: nombres semánticos para medidas y constantes que deban usarse desde Python.
- `app.qss`: paleta, tipografía, estados, bordes, radios, espaciado y componentes comunes.
- `style_loader.py`: carga controlada del QSS, validación de ruta y aplicación al `QApplication`.
- Los estilos específicos de una vista sólo deben añadirse cuando no puedan expresarse mediante `objectName`, propiedades dinámicas o componentes compartidos.

### 5.2 Componentes compartidos propuestos

Crear sólo cuando exista un uso real en más de una vista:

- `app/ui/widgets/navigation_sidebar.py`
- `app/ui/widgets/context_header.py`
- `app/ui/widgets/metric_card.py`
- `app/ui/widgets/action_toolbar.py`
- `app/ui/widgets/metadata_chip.py`
- `app/ui/widgets/state_panel.py`
- `app/ui/widgets/empty_state.py`
- `app/ui/widgets/loading_state.py`
- `app/ui/widgets/error_state.py`

Regla: no crear una abstracción compartida antes de confirmar al menos dos consumidores reales.

### 5.3 Responsive en PySide6

El comportamiento responsive se implementará con:

- tamaños mínimos y `QSizePolicy`;
- `QSplitter` cuando el usuario deba ajustar paneles;
- reorganización controlada en `resizeEvent`;
- ocultamiento progresivo de contenido secundario;
- textos elididos mediante métricas de fuente;
- barras con scroll sólo cuando sea necesario;
- nunca depender exclusivamente de un tamaño fijo de ventana.

Puntos de referencia:

- **1920×1080:** layout completo.
- **1366×768:** layout compacto sin pérdida de acciones primarias.
- **Ventana estrecha:** navegación compacta, métricas resumidas y controles secundarios reubicados.

## 6. Correspondencia prototipo → PySide6

| Elemento del prototipo | Archivo o clase actual | Cambio visual requerido | Componente compartido | Riesgo | Tests |
|---|---|---|---|---|---|
| Shell principal | `MainWindow` | Reorganizar navegación, workspace y jerarquía | `NavigationSidebar`, `ContextHeader` | Medio | `test_main_window_composition.py` |
| Navegación lateral | Navegación actual en `MainWindow` | Convertir a barra compacta con estados activo, hover y foco | `NavigationSidebar` | Medio | composición, foco, cambio de vista |
| Encabezados y métricas | Distribuidos por panel | Jerarquía común y tarjetas de métricas | `ContextHeader`, `MetricCard` | Bajo | tests focales por vista |
| Toolbar | Controles propios de cada panel | Orden, densidad y estilos consistentes | `ActionToolbar` | Medio | acciones existentes siguen conectadas |
| Biblioteca tabla | `LibraryView` + `TrackTableModel` | Densidad, columnas, selección, chips y estados | chips y estados comunes | Alto | `test_library_view_ui.py`, benchmark |
| Biblioteca tarjetas | No confirmada como componente actual | Crear vista opcional sin duplicar fuente de datos | widget específico de Biblioteca | Alto | selección, sincronización y memoria |
| Filtros de Biblioteca | `LibraryView` | Unificar chips, búsqueda y panel de filtros | `MetadataChip` / controles comunes | Medio | búsqueda, vacío y sin resultados |
| Playlist | `PlaylistPanel` | Nueva composición y curva de energía | widget específico de Playlist | Alto | `test_collection_playlist_panel_ui.py` |
| Curva de Playlist | No detectada como widget UI | Crear visual sólo de presentación | `PlaylistEnergyView` propuesto | Alto | datos completos, faltantes y extremos |
| DJ Set | No se detectó panel específico | Crear panel nuevo dentro del workspace | `DJSetPanel` propuesto | Alto | tests nuevos y servicios simulados |
| Viaje de energía | Servicios y tests de energía existentes | Visualizar sin mover cálculos a la UI | `EnergyJourneyView` propuesto | Alto | `test_energy_journey.py`, casos faltantes |
| Preview Player | `PreviewPlayerBar` | Rediseñar distribución, chips, waveform y responsive | componente existente | Alto | `test_preview_player_bar.py` |
| Estados de feedback | `app/ui/feedback.py` y estados locales | Presentación uniforme | `StatePanel` y derivados | Medio | error, carga, vacío, cancelado |
| Accesibilidad | Widgets actuales | nombres accesibles, orden de tabulación y foco visible | QSS y helpers | Medio | tests de accesibilidad focales |

## 7. Orden obligatorio de implementación

### Sprint 1 — Tokens, QSS y componentes compartidos

**Objetivo:** establecer la base visual sin cambiar la composición funcional.

Trabajo:

- crear `app/ui/styles/`;
- trasladar los tokens aprobados a QSS;
- definir estados `hover`, `focus`, `checked`, `selected`, `disabled`, `error`, `warning`, `success` y `missing`;
- crear únicamente componentes compartidos necesarios para shell y vistas existentes;
- incorporar pruebas de carga del QSS y nombres de objeto críticos.

Criterio de cierre:

- la aplicación inicia con QSS global;
- no se modifica lógica de servicios;
- los tests existentes permanecen verdes.

### Sprint 2 — Shell, navegación y workspace

**Objetivo:** implementar la estructura visual principal.

Trabajo:

- adaptar `MainWindow`;
- conservar `MainWindowDependencies`;
- implementar navegación lateral compacta;
- mantener accesibles Biblioteca, Colecciones, Playlists, Importar, Metadata, Assistant y Diagnóstico;
- reservar el punto de entrada para DJ Set sin romper la composición actual;
- preservar el `PreviewPlayerBar` fijo en la zona inferior.

Criterio de cierre:

- todas las vistas existentes siguen siendo accesibles;
- navegación por teclado correcta;
- no hay regresiones en composición.

### Sprint 3 — Biblioteca

**Objetivo:** trasladar el prototipo aprobado a `LibraryView`.

Trabajo:

- encabezado y métricas;
- toolbar compacta;
- búsqueda, filtros y selector de vista;
- tabla densa con chips;
- estados normal, vacío, sin resultados, carga y error;
- evaluar vista de tarjetas sobre la misma fuente de datos;
- preservar rendimiento con bibliotecas grandes.

Criterio de cierre:

- sin barra superior de análisis;
- waveform sólo en Preview Player;
- benchmark sin regresión significativa;
- selección y acciones existentes preservadas.

### Sprint 4 — Playlist

**Objetivo:** rediseñar `PlaylistPanel` y agregar la secuencia de energía.

Trabajo:

- encabezado, métricas y acciones;
- listado ordenado de pistas;
- curva segmentada por pista;
- marcador de selección;
- estados abruptos, vacíos y datos faltantes;
- preservar reordenamiento y compactación existentes.

Criterio de cierre:

- orden de membresía controlado por el servicio;
- curva visual desacoplada de persistencia;
- no se altera la lógica de playlists.

### Sprint 5 — DJ Set

**Objetivo:** crear la superficie visual de DJ Set.

Trabajo propuesto:

- crear `app/ui/dj_set_panel.py`;
- crear widgets visuales de capítulos, transiciones y viaje de energía;
- consumir resultados de servicios existentes mediante DTO o adaptador de UI;
- mostrar curva real y objetivo;
- representar peak times, conflictos y datos faltantes;
- integrar la vista al workspace sin modificar schema.

Criterio de cierre:

- ninguna lógica de cálculo vive en widgets;
- los servicios pueden simularse en tests;
- los estados del prototipo están cubiertos.

### Sprint 6 — Preview Player y responsive

**Objetivo:** completar el reproductor y comportamiento adaptativo.

Trabajo:

- rediseñar `PreviewPlayerBar`;
- integrar waveform individual sólo en esta superficie;
- mantener controles y estados actuales;
- conservar carga sin autoplay;
- adaptar volumen y salida a segunda línea cuando el ancho sea insuficiente;
- validar tamaños 1920×1080, 1366×768 y estrecho.

Criterio de cierre:

- todos los estados de `PreviewPlayerState` siguen representados;
- tests del servicio y barra permanecen verdes;
- controles nunca quedan inaccesibles.

### Sprint 7 — Accesibilidad, estados y auditoría visual

**Objetivo:** uniformar interacción y presentación.

Trabajo:

- foco visible;
- orden de tabulación;
- nombres y descripciones accesibles;
- tooltips;
- truncado y elisión;
- estados vacíos, carga, error, cancelado y faltante;
- auditoría comparativa contra los prototipos.

Criterio de cierre:

- navegación completa por teclado;
- contraste y foco visibles;
- no hay acciones críticas sólo disponibles por hover.

### Sprint 8 — Validación completa y preparación de release

**Objetivo:** cerrar la fase visual con evidencia reproducible.

Trabajo:

- tests focales por vista;
- suite completa;
- benchmark de Biblioteca;
- smoke manual;
- revisión de empaquetado;
- documentación de cambios;
- verificación de instalación;
- auditoría de regresiones funcionales.

Criterio de cierre:

- suite completa verde;
- build reproducible;
- worktree limpio;
- sin cambios de backend o schema mezclados con el cierre visual.

## 8. Estrategia de pruebas

### Tests existentes prioritarios

- `tests/test_main_window_composition.py`
- `tests/test_library_view_ui.py`
- `tests/test_collection_playlist_panel_ui.py`
- `tests/test_preview_player_bar.py`
- `tests/test_preview_player.py`
- `tests/test_preview_player_devices_history.py`
- `tests/test_qt_test_helpers.py`
- `tests/test_import_manager_ui.py`
- `tests/test_track_metadata_panel.py`
- `tests/test_packaging_configuration.py`
- `tests/test_installer_configuration.py`
- `tests/test_energy_journey.py`
- `tests/test_set_planning.py`

### Tests nuevos propuestos

Crear únicamente cuando comience el sprint correspondiente:

- `tests/test_ui_style_loader.py`
- `tests/test_navigation_sidebar.py`
- `tests/test_shared_ui_components.py`
- `tests/test_playlist_energy_view.py`
- `tests/test_dj_set_panel_ui.py`
- `tests/test_ui_responsive_layout.py`
- `tests/test_ui_accessibility.py`

### Secuencia de validación

1. `compileall` o validación sintáctica.
2. Tests focales del componente modificado.
3. Tests de composición.
4. Tests de servicios relacionados, aunque no se hayan modificado.
5. Suite completa al cerrar cada sprint.
6. Benchmark y smoke manual antes de release.

## 9. Riesgos principales

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Mezclar rediseño con cambios funcionales | Alto | commits separados y revisión de diff por sprint |
| QSS global afecta widgets no previstos | Alto | selectores por clase, `objectName` y propiedades dinámicas |
| Biblioteca pierde rendimiento | Alto | no duplicar consultas; benchmark antes y después |
| Vista de tarjetas duplica estado | Alto | un único modelo/fuente de selección |
| Curvas de energía trasladan lógica a UI | Alto | usar DTOs y servicios existentes |
| DJ Set no tiene panel UI existente | Alto | sprint separado y adaptador explícito |
| Responsive basado en tamaños fijos | Medio | `QSizePolicy`, splitters y pruebas por ancho |
| Preview Player introduce autoplay | Alto | conservar contrato actual y test específico |
| Accesibilidad se agrega al final | Medio | criterios obligatorios desde cada sprint |
| Empaquetado omite QSS o recursos | Alto | tests de packaging y rutas relativas |

## 10. Criterios de aceptación globales

### 1920×1080

- navegación, métricas, toolbar y contenido visibles;
- Preview Player fijo sin superposición;
- tabla y curvas aprovechan el ancho disponible;
- no aparecen espacios vacíos estructurales innecesarios.

### 1366×768

- acciones primarias visibles;
- métricas compactadas;
- toolbar refluye sin cortar controles;
- Preview Player conserva controles esenciales;
- no hay scroll horizontal global de la ventana.

### Ventana estrecha

- navegación pasa a modo compacto;
- contenido secundario se oculta o reubica;
- textos largos se eliden;
- volumen y salida pueden pasar a otra fila;
- las acciones críticas siguen accesibles por teclado.

### Accesibilidad

- foco visible en todos los controles interactivos;
- orden de tabulación lógico;
- nombres accesibles para iconos;
- tooltips en botones sin texto;
- estados no dependen exclusivamente del color.

### Rendimiento

- apertura de Biblioteca y ordenamiento sin regresiones significativas;
- scroll fluido con bibliotecas grandes;
- las tarjetas no cargan recursos pesados de forma anticipada;
- curvas de energía no bloquean el hilo de UI.

### Regresión funcional

- reordenamiento de Playlist preservado;
- selección de pistas preservada;
- importación y metadata mantienen validaciones;
- Preview Player mantiene todos sus estados;
- navegación y composición siguen pasando tests.

## 11. Política de commits y rollback

- Un commit por unidad visual verificable.
- No mezclar backend, schema o migraciones.
- Antes de cada commit:
  - tests focales;
  - `git diff --check`;
  - revisión de archivos incluidos.
- Al cerrar cada sprint:
  - suite completa;
  - commit de documentación si corresponde;
  - push sólo a `release/v1.0.0-visual-polish`.
- Rollback:
  - revertir el commit visual específico;
  - no usar `reset --hard`, `clean`, `restore` masivo ni force push;
  - conservar siempre el historial de la rama.

## 12. Tabla final de ejecución

| Orden | Sprint | Archivos previstos | Riesgo | Tests principales | Dependencia | Resultado esperado |
|---:|---|---|---|---|---|---|
| 1 | Tokens/QSS | `app/ui/styles/*`, widgets compartidos mínimos | Medio | style loader, composición | Prototipos aprobados | Base visual común |
| 2 | Shell | `main_window.py`, navegación compartida | Medio | main window, packaging | Sprint 1 | Workspace coherente |
| 3 | Biblioteca | `library_view.py`, modelo y widgets visuales | Alto | library UI, benchmark | Sprints 1–2 | Biblioteca aprobada |
| 4 | Playlist | `playlist_panel.py`, energía de Playlist | Alto | playlist UI y servicios | Sprints 1–2 | Playlist aprobada |
| 5 | DJ Set | panel y widgets nuevos de DJ Set | Alto | energía, set planning, UI nueva | Sprints 1–2 | DJ Set aprobado |
| 6 | Preview/responsive | `preview_player_bar.py`, helpers responsive | Alto | preview y responsive | Sprints 1–5 | Reproductor y layouts cerrados |
| 7 | Accesibilidad | QSS, widgets y tests de interacción | Medio | foco, teclado, estados | Sprints 1–6 | Auditoría visual aprobada |
| 8 | Release | tests, packaging y documentación | Alto | suite completa, installer | Todos | Candidato visual estable |

## 13. Primer paso de implementación autorizado

El primer cambio de código deberá limitarse al **Sprint 1: tokens, QSS y carga del estilo global**.

No se debe comenzar por Biblioteca, Playlist o DJ Set hasta que:

- el QSS global cargue correctamente;
- exista un conjunto mínimo de tokens;
- la aplicación inicie;
- los tests focales y de composición estén verdes;
- el cambio haya sido revisado y guardado en un commit independiente.
