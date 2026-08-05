# DJPlus Visual Polish Baseline — Parte 1

## Alcance

Esta etapa cubre exclusivamente:

- `app/ui/main_window.py`
- `app/ui/library_view.py`
- Navegación principal
- Estilos QSS compartidos en el shell
- Biblioteca y su tabla de pistas
No se incluyen aún: Colecciones, Playlists, Import Manager, Metadata, Assistant, Diagnóstico ni Preview Player.

---

## Archivos responsables

  - título de aplicación y subtítulo
  - estilo global del `QMainWindow` y navegación de esquema
  - `QStackedWidget` de contenido
- `app/ui/library_view.py`
  - encabezado y subtítulo de biblioteca
  - toolbar de búsqueda, filtros y acciones
  - `QTableView` principal de pista
  - estados de carga y error
  - barra de acciones de selección
---

## Estructura visual actual

### Shell principal
- Diseño de columna única con encabezado superior y después área de cuerpo en `HBoxLayout`.
- Navegación lateral fija a la izquierda con botones verticales de sección.
- Contenido principal en `QStackedWidget` con cada sección reemplazando el área central.
- Margen externo consistente: `16px` en todo el shell.

### Biblioteca

- Encabezado de pantalla: título grande, subtítulo descriptivo y contador alineado a la derecha.
- Panel de filtros colapsable debajo de la toolbar.
- Área central con `QTableView` para la lista de pistas.
- Mensajes de estado en un `QFrame` con relleno de `24px` cuando la tabla está vacía o cargando.
- Barra de selección/acción fija en el pie con contexto de pista seleccionada.


## Tipografía, colores, bordes y espaciado


- `QMainWindow` usa tamaño base de `13px`.
- `QLabel#appTitle`: `22px`, `font-weight: 600`.
- `QLabel#pageTitle`: `16px`, `font-weight: 600`.
- Texto secundario en etiquetas `#appSubtitle`, `#availabilityMessage`, `#libraryCounter` usa color gris claro.

### Colores
- Fondo principal: `#111827` (gris muy oscuro / casi negro).
- Contenedores y paneles: `#1f2937` (gris azulado oscuro).
- Bordes: `#374151` (gris medio-oscuro).
- Texto secundario y hints: `#9ca3af` (gris frío).
- Botones primarios: `#2563eb` (azul brillante).
- Hover de botones: `#374151`.
- Estados de error o degradado en Preview Player usan rojos/amarillos, aunque quedan fuera del alcance de esta etapa.

### Bordes y esquinas

- Radio de borde principal: `8px` para paneles y rail.
- Botones `QPushButton` tienen `border-radius: 4px`.
- Paneles interiores usan rellenos `10-12px` y márgenes `16px`.
### Espaciado

- `QVBoxLayout` entre secciones: `12px`.
- Toolbar y paneles usan `8px` de separación entre elementos.
- `QFrame` internos usan `12px` de relleno, `10px` en subpaneles.
- Estados de carga usan `24px` de margen interno para mayor respiración.

---
## Biblioteca — jerarquía y densidad

### Jerarquía
- Título "Biblioteca" es el elemento visual más fuerte dentro de la pantalla.
- El subtítulo y el contador secundario refuerzan el contexto.
- La toolbar de búsqueda aparece como la acción primaria siguiente.
- El `QTableView` es claramente la zona dominante.
- La barra de selección inferior es contextual y menos prominente.

### Densidad
- La tabla usa `QTableView` con filas claramente espaciadas y sin borde de cuadrícula.
- La fila de acciones en la parte inferior aporta densidad adicional si se habilita.
- El uso de `16px` de márgenes y `12px` de espaciado genera un balance medio entre contenido y respiración.

---


### Toolbar

- El campo de búsqueda se expande para ocupar el espacio disponible.
- Los botones están agrupados de forma lineal y se ven como controles secundarios.
- Ausencia de iconos; todo es texto plano.
### Búsqueda

- Clear button habilitado.
- No hay estilo de enfoque específico más allá del borde azul global.

### Filtros
- Panel de filtros encajado dentro de `QFrame` colapsable.
- Controles de filtros: `QLineEdit`, `QDoubleSpinBox`, `QSpinBox` y botones `Aplicar` / `Limpiar`.
- Los `SpinBox` muestran texto especial cuando están vacíos.
- El panel está inicialmente oculto y se revela por el toggle.

### Tabla
- `QTableView` con cabecera expandible en columnas clave y `ResizeToContents` en columnas secundarias.
- `verticalHeader` oculto y `grid` desactivado para apariencia minimalista.
- Alternating row colors habilitadas.
- Selección de filas completa, modo single selection.
- Encabezados se pueden clicar para ordenar, aunque la ordenación queda manejada en la lógica.
### Estados

- Estado de carga / vaciado en `QFrame` con `QLabel` de título y mensaje.
- Estado de selección en pie de página cambia según la pista seleccionada.
- El contenido alterna entre tabla y estado.


## Componentes que deben preservarse

- El título de aplicación y subtítulo en el encabezado.
- El esquema de colores oscuros con paneles contrastados en gris azulado.
- La separación clara entre toolbar, filtros y tabla.
- El foco azul uniforme para accesibilidad de teclado.
- La tabla como elemento central y principal de interacción.
- El patrón de filtro expandible como segunda capa de control.
---

## Inconsistencias visuales demostrables
- La navegación lateral fija usa botones sin iconos, mientras el resto de la app puede emplear componentes más compactos; esto puede bajar la consistencia si las demás pantallas usan botones distintos.
- El panel de filtros se siente visualmente separado del toolbar pero mantiene la misma jerarquía de espacio; podría necesitar una transición más clara entre estados abierto/cerrado.
- La toolbar y la tabla comparten poco lenguaje de diseño: el toolbar es muy plano y la tabla puede parecer demasiado densa frente a los paneles suavizados.
- El `QLabel#libraryCounter` derecho es informativo, pero su estilo no resalta tanto como para competir con el subtítulo.

---


- Cambiar la navegación principal puede afectar el flujo de acceso a toda la aplicación.
- Alterar el layout de `LibraryView` puede romper el comportamiento esperado de la tabla y los filtros.
- Ajustar los márgenes de la tabla sin verificar ventana estrecha puede causar truncamientos en ancho bajo.
- Cambios de color en botones primarios deben respetar contraste y estados de hover/focus para no degradar accesibilidad.

---
## Orden recomendado para el pulido

1. Biblioteca
3. Estilos QSS compartidos
4. Toolbar y búsqueda
5. Panel de filtros
6. Tabla de pistas
7. Estados y mensajes de carga/vacío


---


### Resoluciones de pantalla

- `1366×768`
- ventana estrecha (ancho menor a `1000px`)


1. Pantalla completa de `MainWindow` mostrando navegación lateral y área de contenido.
2. Biblioteca con toolbar de búsqueda visible y filtro cerrado.
4. Biblioteca con resultados de tabla cargados y fila seleccionada.
5. Estado de carga o vacío de la biblioteca.
6. Biblioteca en ventana estrecha, confirmando que el contenido se adapta sin perder funcionalidad.

---
## Clasificación de observaciones

- Claridad
  - El panel de filtros podría mejorar su transición para ser más explícito.

- Jerarquía
  - El contador derecho necesita más peso visual para equilibrar la cabecera.

- Densidad
  - El panel de filtros y la toolbar podrían usar espaciado más consistente.

- Consistencia
  - El toolbar plana y la tabla densa generan una pequeña ruptura visual.

- Accesibilidad
  - El contraste de texto y botones en paneles oscuros es adecuado.
  - Falta iconografía para reforzar acciones; la experiencia actual depende exclusivamente de texto.
- Identidad visual

---

## Parte 3 — Import Manager y Metadata

### Alcance
- Documentar exclusivamente las vistas de Import Manager y Metadata.
- No se revisó Assistant ni Diagnóstico.
- Se analizaron visualmente `app/ui/import_manager_panel.py`, `app/ui/import_manager_adapter.py` y `app/ui/track_metadata_panel.py`.

### Archivos responsables
- `app/ui/import_manager_panel.py`
- `app/ui/import_manager_adapter.py`
- `app/ui/track_metadata_panel.py`

---
## Import Manager

### Estructura visual y flujo
- Panel de columna única con título, hint de pasos y controles de carpeta arriba.
- Entrada de carpeta y botón de selección en una fila horizontal.
- Botones principales lineales: "Analizar e importar" y "Cancelar".
- Indicadores de estado, progreso y archivo actual apilados como información de proceso.
- Secciones claras para "Coincidencias y archivos procesados", "Conflictos y errores" y "Historial de importaciones".
- La lista de historial y el detalle de trabajo se muestran en el mismo panel sin pestañas.

### Origen
- La selección de carpeta se dicta con `QLineEdit` y `QPushButton` de exploración.
- El flujo comienza con elegir carpeta, luego iniciar importación.

---
## Parte 4 — Assistant y Diagnóstico

### Alcance
- Documentar exclusivamente la apariencia, jerarquía y estructura actuales de `AssistantPanel` y `DiagnosticsPanel`.
- Incluir los estados de superficie de fallback para ambas vistas.
- No se modifica código, comportamiento, tests ni estilos QSS.

### Archivos responsables
- `app/ui/assistant_panel.py`
- `app/ui/diagnostics_panel.py`

### Assistant — estructura visual actual
#### Composición
- `AssistantPanel` es una vista vertical de `QVBoxLayout` con márgenes `16px` y espaciado `12px`.
- Contiene un título principal, un hint de contexto, un bloque de conversación y un bloque de resultados.
- Las secciones clave están encerradas en `QFrame#assistantSection` con fondo `#1f2937`, borde `#374151` y radio `8px`.
- La entrada de texto y los botones están dispuestos en una fila `QHBoxLayout`.
- El resultado se muestra en un `QTextEdit` de sólo lectura.

#### Elementos visuales
- Título `Assistant local` con `font-size:18px; font-weight:600`.
- Hint secundario de color gris `#9ca3af`.
- Botón primario `Consultar` con fondo azul `#2563eb` y texto blanco.
- El estado actual se expresa mediante `QLabel` simples: `Listo`, `Procesando…`, `Error`, `Cancelada`.
- La etiqueta de diagnóstico en la parte inferior del bloque de conversación muestra contadores de errores/cancelaciones/timeouts.

#### Estados detectados
- Vacío / listo: `status_label` inicia en `Listo`, `response_view` vacío y la etiqueta de diagnóstico puede mostrar «Diagnostico: no disponible» si no hay servicio.
- Procesando: al enviar consulta, el botón `Consultar` se deshabilita, `Cancelar` se habilita y `status_label` pasa a `Procesando…`.
- Listo: tras resultado exitoso, el texto del `QTextEdit` se actualiza y el estado vuelve a `Listo`.
- Error: el panel muestra el mensaje de error en el `QTextEdit` y el `status_label` cambia a `Error`.
- Cancelado: si el usuario cancela, muestra `Consulta cancelada.` y el estado `Cancelada`.
- No configurado / fallback: cuando no se inyecta `DiagnosticsService`, el texto inferior queda en `Diagnostico: no disponible`.

#### Jerarquía y densidad
- La jerarquía principal es clara: título > hint > sección de conversación > resultados.
- El bloque de resultados carece de un subtítulo visual diferenciador más allá del `QLabel` interno, por lo que compite con la introducción.
- La densidad es media: dos paneles con borde, campo de entrada amplio y área de texto expandida ocupan la pantalla sin saturarla.
- La fila de botones tiene un peso visual mayor que el estado; el botón primario se distingue bien.

#### Claridad de herramientas disponibles
- El panel no presenta íconos ni labels secundarios para la acción `Cancelar` aparte del texto.
- El hint inicial comunica la naturaleza de sólo lectura, pero no hay un área dedicada de “acciones disponibles” más allá de la sección de resultados.
- La estructura sugiere conversacionalidad, pero los usuarios no tienen un indicador visual fuerte de la jerarquía entre preguntas, resultados y acciones de herramientas.

#### Riesgos visuales
- Uso exclusivo de etiquetas de texto para estados puede hacer que `Error` y `Cancelada` pasen desapercibidos en una vista con fondo oscuro.
- El `QTextEdit` de solo lectura podría parecer un campo de entrada si no hay borde o estilo adicional, lo que confunde jerarquía.
- La sección de diagnóstico puede parecer un mero metadato si no se refuerza su relación con el estado de la consulta.

### Diagnóstico — estructura visual actual
#### Composición
- `DiagnosticsPanel` usa un `QVBoxLayout` con márgenes `16px` y espaciado `12px`.
- Incluye título, estado, acciones en fila y un `QFrame` con `QTextEdit` de salida.
- Los botones `Actualizar` y `Exportar resumen` están alineados a la izquierda y se expande un `addStretch(1)` para separar.
- El área de resultados está dentro de `QFrame#diagnosticsResult`, lo que refuerza el contenedor visual.

#### Elementos visuales
- Título `Diagnóstico` sin estilo adicional visible en el código fuente, lo que deja su peso jerárquico dependiente del estilo global.
- `status_label` arriba comunica `Listo para actualizar`, `Actualizado · diagnóstico de sólo lectura` o `Error al actualizar diagnóstico`.
- `QTextEdit` usa placeholder `Sin diagnósticos disponibles.` para estado vacío.

#### Estados detectados
- Vacío / no configurado: `QTextEdit` muestra placeholder cuando no hay datos previos o si el servicio no puede generar un snapshot.
- Actualizado: después de `refresh()`, el texto se reemplaza con `snapshot.export_text()` y el estado indica éxito.
- Error: si la llamada falla, el output muestra el mensaje de excepción y el estado marca `Error al actualizar diagnóstico`.
- Exportación: presionar `Exportar resumen` refresca el contenido y cambia el estado a `Resumen diagnóstico listo para copiar`.

#### Legibilidad y densidad
- La vista es de baja densidad: una sola columna con grandes bloques de texto y dos botones.
- El `QTextEdit` de salida es el elemento dominante; su legibilidad depende casi totalmente de la forma en que el texto exportado se formatee.
- La sección de acciones tiene buena separación, pero el estado y el contenido del texto pueden quedar demasiado juntos si el texto es extenso.

#### Riesgos visuales
- Si el texto de diagnóstico es largo, el `QTextEdit` podría provocar desplazamiento sin una jerarquía clara entre encabezado y contenido.
- El placeholder `Sin diagnósticos disponibles.` es adecuado, pero no hay fallback visual alternativo más rico para cuando no hay información.
- La ausencia de estilos específicos para `diagnosticsTitle` y `diagnosticsResult` en el código sugiere dependencia de estilos globales que pueden variar.

### Elementos que deben preservarse
- El contenedor de conversación y resultados del Assistant en `AssistantPanel`.
- Los estados de botón `Consultar` / `Cancelar` con habilitado/deshabilitado dinámico.
- La etiqueta de diagnóstico de resumen en `AssistantPanel`.
- El flujo inmediato de `Actualizar` y `Exportar resumen` en `DiagnosticsPanel`.
- El placeholder de texto vacío en el panel de diagnóstico.
- El esquema de paneles y bordes para mantener continuidad visual con el resto de la aplicación.

### Inconsistencias demostrables
- `AssistantPanel` aplica estilos directos en `setStyleSheet`, mientras que `DiagnosticsPanel` no define estilos locales; esto rompe la consistencia de implementación.
- La etiqueta de título de `AssistantPanel` está explícitamente estilizada, pero la de `DiagnosticsPanel` no, lo que puede causar peso visual desigual.
- `AssistantPanel` usa un borde azul para el botón primario, pero `DiagnosticsPanel` no marca ningún botón como primario, reduciendo la claridad de acciones.
- El texto de fallback `Diagnostico: no disponible` es visible, pero no está alineado con el diseño de estados de `DiagnosticsPanel`.

### Accesibilidad
- Tanto `QTextEdit` como `QLineEdit` y `QPushButton` son controles estándar de Qt, lo cual es positivo.
- No hay evidencia de accesos directos o roles ARIA adicionales; la accesibilidad depende de los estilos y del foco del sistema Qt.
- El contraste entre fondo oscuro y texto blanco/gris es consistente con la línea general del producto.
- El botón `Cancelar` se habilita y deshabilita correctamente, reduciendo la posibilidad de acciones inválidas.

### Coherencia con el resto de DJPlus
- El uso del fondo oscuro `#1f2937` y el borde `#374151` encaja con el estilo de paneles descrito en la Parte 1.
- El azul primario `#2563eb` mantiene la identidad cromática de la aplicación.
- La separación en bloques tipo “panel + contenido” es coherente con la estructura de `LibraryView`.
- La falta de iconografía y la fuerte dependencia de texto coincide con la navegación y toolbar del baseline.

### Capturas necesarias
- Assistant en ventana normal: estado inicial listo, con `Conversación` y sección de resultados vacía.
- Assistant en ventana estrecha: comprobar si la fila de entrada y botones se conserva sin truncar.
- Assistant con resultado: mostrar texto cargado y estado `Listo`.
- Assistant cancelado/error: mostrar `Cancelada` o `Error` para validar estado visual.
- Diagnóstico en ventana normal: `Actualizado · diagnóstico de sólo lectura` con texto de exportación visible.
- Diagnóstico en ventana estrecha: validar que la barra de botones y el `QTextEdit` se adaptan.

### Prioridad visual recomendada
1. Assistant — prioridad alta
   - Porque es la interfaz interactiva más extensa y requiere estados claros de entrada, procesamiento y resultados.
2. Diagnóstico — prioridad media
   - Es una vista utilitaria de lectura y exportación, menos compleja visualmente, pero debe conservar legibilidad y fallback claros.

### Clasificación de observaciones
- Claridad
  - El Assistant comunica bien el propósito, pero el resultado y los estados pueden mezclarse visualmente.
- Jerarquía
  - La disposición vertical es correcta, aunque el panel de resultados necesita mayor distinción.
- Densidad
  - Assistant tiene densidad media; Diagnóstico es de baja densidad y podría beneficiarse de un espaciado mejor definido.
- Consistencia
  - Hay una inconsistencia de estilo entre los dos paneles y la aplicación general.
- Accesibilidad
  - Buen contraste general, pero la experiencia depende de Qt global y no hay indicadores locales para foco/estado.
- Identidad visual
  - Los colores y bordes siguen la identidad del producto, aunque la falta de iconografía reduce la sensación de pulido.


### Análisis
- El progreso se muestra con `QProgressBar` y `QLabel` que muestran procesados y estado.
- El estado del trabajo se actualiza con etiquetas textuales de estatus.
- No hay miniaturas ni indicadores de estado por archivo más allá de texto en listas.

### Progreso
- Barra de progreso simple con rango dinámico entre `0` y `total_items`.
- Etiqueta de archivos procesados y texto del archivo actual.
- Botón cancelar deshabilita la interacción de inicio y carpeta mientras corre.

### Coincidencias y conflictos
- `QListWidget` para archivos procesados con eventos tipo "Importado", "Omitido" y "Falló".
- `QListWidget` independiente para errores y conflictos.
- Las listas son de altura limitada (max 140px y 100px) para controlar la densidad.

### Errores y recuperación
- Panel de errores muestra entradas formateadas con nombre de archivo y mensaje.
- Botón "Recuperar trabajos incompletos" y lista de historial habilitan recuperación.
- El detalle de trabajo se actualiza al seleccionar un job.

### Resultado e historial
- Historial de importaciones usa `QListWidget` limitada a 120px.
- Cada ítem incluye ID, estado, procesados y contador de errores.
- El detalle de trabajo se resume en una sola etiqueta con texto envuelto.

### Jerarquía visual
- El encabezado y el hint de pasos son prominentes.
- Los controles de inicio/cancelación tienen peso visual medio.
- Las listas de progreso, errores e historial compiten con la información principal por espacio.
- El mensaje de estado actual puede perderse entre los múltiples labels similares.

### Densidad
- La pantalla es bastante compacta debido a contenedores limitados en altura.
- Las listas anidadas y el texto de estado ocupan mucho espacio vertical.
- La altura fija de listas reduce desplazamiento pero genera un panel con mucha información juntas.

### Claridad del flujo
- El orden 1→4 está indicado textualmente, pero no existen divisores visuales fuertes entre etapas.
- Las secciones están apiladas sin separación extra aparte de los `QLabel` y espaciado estándar.
- El botón cancelar y el botón recuperar son visibles, pero podrían no diferenciarse claramente en situación de error vs proceso normal.

### Coherencia con el resto de DJPlus
- Usa el mismo esquema de color oscuro, `QFrame` con borde redondeado y botones azules primarios.
- El texto de hint y pasos coincide con estilos de otros paneles.
- La mezcla de componentes de lista en forma de `QListWidget` es consistente con diseño de paneles sencillos.

### Estados clave
- Vacío: texto de estado inicial "Sin importación activa · esperando origen".
- Procesando: barra de progreso activa, botón cancelar habilitado, botón iniciar deshabilitado.
- Cancelado: el estado se establece a "Cancelación solicitada" y los controles vuelven a permitir selección de carpeta.
- Error: los errores se agregan al panel y el status label refleja el estado de trabajo.
- Completado: el status label cambia a "Completado" y la historia se recarga.

### Riesgos visuales
- El uso de múltiples `QListWidget` limita la diferenciación entre archivos procesados, errores e historial.
- El texto de estado actual y el mensaje de detalle de trabajo son similares, lo que puede causar confusión.
- La falta de una tarjeta o sección visual fuerte por cada etapa reduce la jerarquía.
- Altas densidades de información en ventanas estrechas pueden resultar en scroll vertical excesivo.

---
## Metadata

### Estructura visual y flujo
- Panel de columna única con título y hint de uso en la parte superior.
- Secciones definidas dentro de `QFrame#metadataSection` con heading y contenido encuadrado.
- Flujo lineal: selección → campos / cambio propuesto → vista previa / resultado.

### Selección de pistas
- Campo de texto libre para IDs de pistas con placeholder guía.
- Resumen dinámico muestra "Sin pistas seleccionadas", "Edición individual" o "Edición múltiple".
- No hay selección por lista de pistas ni elementos visuales de tabla dentro de este panel.

### Edición individual y múltiple
- El mismo control de campo se usa para edición individual y múltiple.
- El switch de contexto se infiere sólo por el resumen textual.
- Solo se muestra actualmente el campo "Título" como input editable.

### Campos mixtos
- Etiqueta de hint informa sobre valores mixtos, sin cambios y validaciones para varias pistas.
- No hay campos visibles que muestren los valores actuales de las pistas.

### Cambio propuesto
- Los cambios se introducen en el `QLineEdit` de título.
- Botón "Generar vista previa" lanza la generación del borrador.
- Botón "Confirmar y aplicar" permanece deshabilitado hasta que hay vista previa.

### Preview
- `QTextEdit` de resultado de preview es la única área de salida.
- Es de lectura y muestra texto plano con errores o el resumen de cambios.
- La vista previa carece de sección separada visualmente de la confirmación.

### Confirmación
- Botón de aplicación está ubicado junto al botón de preview en un `QHBoxLayout`.
- `Confirmar y aplicar` se habilita solo después de una preview exitosa.
- No hay indicador visual adicional de que la acción es irreversible o necesita doble confirmación.

### Resultado
- El `QTextEdit` también muestra el resultado final tras aplicar.
- El panel no diferencia claramente entre mensaje de preview y mensaje de resultado.

### Validaciones y errores
- Las excepciones se capturan y escriben en el `QTextEdit`.
- No hay un área de error separada ni estilo de error dedicado.
- La validación depende de los DTOs en backend; la UI solo muestra texto de excepción.

### Jerarquía de formularios
- Cada sección viene dentro de un `QFrame` con borde, lo que ayuda a separar bloques.
- El área de campos actuales aparece como la sección central más fuerte.
- El `QTextEdit` ocupa gran espacio y se siente visualmente dominante.

### Densidad y scannability
- El panel es de baja densidad: pocos inputs y mucho espacio.
- La información es fácil de escanear, pero la selección de IDs en un campo de texto libre puede confundir a usuarios.
- Los `QFrame` con relleno y separación de 6px hacen el formulario legible.

### Riesgos visuales
- El flujo basado en texto libre de IDs es propenso a errores de entrada sin validación visible.
- Falta una vista de las pistas seleccionadas o sus valores actuales, lo que reduce la confianza.
- El `QTextEdit` único como área de preview/resultado puede ser difícil de leer con muchos cambios.
- La ausencia de etiquetas de campo adicionales (artist, album, etc.) hace que la vista parezca incompleta y poco orientada.

---
## Elementos que deben preservarse
- Estilo oscuro y contenedores con bordes redondeados en ambos paneles.
- Botones primarios azules `#2563eb` con texto blanco.
- Separación clara de secciones en Metadata mediante `QFrame` de paso.
- El orden de pasos textual en Import Manager para guiar al usuario.
- El uso de QLists acotadas para limitar la altura de los listados.

## Inconsistencias demostrables
- Import Manager usa listas múltiples y etiquetas de estado sueltas; Metadata usa secciones encuadradas y un único resultado de texto.
- En Metadata el flujo de selección requiere IDs manuales; en Import Manager se espera interacción directa con carpeta y jobs.
- El panel de Import Manager tiene más elementos de control y densidad, mientras que Metadata se siente esqueleto y poco informativo.
- La información de estado en Import Manager no está jerarquizada con suficiente contraste entre etiquetas y listas.

## Capturas necesarias
- Import Manager en ventana normal mostrando carpeta, botones y progreso.
- Import Manager con listas de archivos procesados, errores y historial visibles.
- Import Manager en ventana estrecha para validar que no se pierda la fila de botones.
- Metadata en ventana normal mostrando selección, campos y vista previa.
- Metadata en ventana estrecha asegurando que los `QFrame` y el `QTextEdit` siguen legibles.

## Prioridad visual recomendada
1. Import Manager
2. Metadata

---
## Clasificación de observaciones

- Claridad
  - Import Manager necesita separación visual más clara entre etapas.
  - Metadata depende de texto libre para selección y no muestra valores actuales.

- Jerarquía
  - El estado y el detalle de trabajo compiten por atención en Import Manager.
  - Metadata requiere mejorar el peso relativo de la preview frente al formulario.

- Densidad
  - Import Manager es denso y puede saturar ventanas estrechas.
  - Metadata es ligera pero podría usar más contexto para mejorar su utilidad.

- Consistencia
  - Ambos paneles mantienen esquema de color y botones similares.
  - El tratamiento de listas y detalles difiere entre los dos paneles.

- Accesibilidad
  - El contraste es correcto en textos y botones principales.
  - La ausencia de una zona de error destacada en Metadata reduce la detección rápida de fallos.

- Identidad visual
  - El estilo oscuro y los bordes curvos son coherentes con la aplicación.
  - Falta iconografía y división de tarjetas para reforzar la identidad en estas vistas.

---
## Documento generado

- `docs/ui/VISUAL_POLISH_BASELINE.md`

---
## Cierre del Laboratorio Visual

### 1. Resumen ejecutivo visual
El baseline consolida las observaciones de las Partes 1 a 4 para el primer prototipo visual de Biblioteca. El proyecto se apoya en un esquema oscuro consistente, paneles con bordes redondeados y una jerarquía que prioriza la tabla central de la Biblioteca, el flujo de Import Manager, los estados de Assistant/Diagnóstico y la edición de Metadata. Los principales hallazgos se enfocan en mejorar la coherencia visual entre toolbar, filtros y tablas, reforzar la jerarquía de encabezados y estados, y preservar la legibilidad en ventanas estrechas sin alterar comportamiento ni layouts.

### 2. Hallazgos únicos
- El panel de filtros queda separable visualmente del toolbar y necesita transición más clara entre estados abierto/cerrado.
- La tabla de Biblioteca es dominante pero la toolbar es demasiado plana frente a la densidad de la lista.
- El contador de Biblioteca requiere mayor peso visual para equilibrar la cabecera.
- La navegación lateral sin iconos rompe la posible consistencia con otras pantallas.
- Assistant y Diagnóstico divergen en aplicación de estilos locales, generando inconsistencias de peso visual.
- El `QTextEdit` de resultados puede confundirse con un campo editable si no tiene un estilo de solo lectura más marcado.
- Import Manager agrupa demasiada información similar sin divisores visuales fuertes entre etapas.
- Metadata depende de entrada de IDs en texto libre y no comunica claramente la selección o valores actuales.
- El contraste general es adecuado para texto sobre fondo oscuro, pero estados de error y cancelación necesitan mayor distinción.
- El esquema de paneles oscuros con bordes `8px` y botones azules primarios es un elemento de identidad fuerte.

### 3. Prioridad global de pantallas
- Biblioteca: alta
- Assistant: alta
- Import Manager: media-alta
- Diagnóstico: media
- Metadata: media
- Navegación lateral / shell general: media

### 4. Elementos visuales que deben preservarse
- Esquema de color oscuro con paneles `#1f2937` y bordes `#374151`.
- Botones primarios azules `#2563eb` y foco azul uniforme.
- Estructura de paneles redondeados (`border-radius: 8px`) para contenedores.
- Separación clara entre toolbar, filtros y tabla en Biblioteca.
- Patrón de estados vacíos/normal/selección/error desplegados en marco fijo.
- Placeholder y estado de solo lectura en áreas de texto extensas.
- Flujo textual claro en Import Manager y Metadata sin alterar lógica.

### 5. Riesgos que pueden afectar comportamiento o accesibilidad
- Cambios visuales en la tabla de Biblioteca pueden alterar el manejo de selección y el ancho de columnas.
- Ajustes de espaciado o márgenes en ventana estrecha pueden causar truncamiento horizontal.
- Estilos de estado insuficientes para errores o cancelaciones pueden dificultar la detección de fallos.
- Reliance en texto en lugar de iconografía reduce la velocidad de reconocimiento de acciones.
- Dependencia del estilo global de Qt para títulos y botones puede provocar inconsistencias entre paneles.
- La edición de Metadata sin feedback de selección actual aumenta la probabilidad de errores de entrada.

### 6. Mejoras visuales diferibles
- Iconografía en la navegación lateral y la toolbar.
- Reforzar la jerarquía de subtítulos y contadores con peso tipográfico adicional.
- Separadores visuales más marcados en Import Manager entre etapas y listados.
- Área de error dedicada en Metadata en lugar de volcar todo en un `QTextEdit`.
- Transición animada o más clara para el panel de filtros colapsable.
- Estilos de enfoque más explícitos para inputs y botones en ventanas estrechas.

### 7. Orden recomendado de implementación
1. Biblioteca: reforzar jerarquía de toolbar, filtros y tabla.
2. Assistant: asegurar estados de entrada/resultado/cancelación claros.
3. Import Manager: mejorar separación entre etapas y densidad de información.
4. Diagnóstico: estabilizar legibilidad y fallback vacío.
5. Metadata: añadir mayor claridad en selección y flujo de preview.
6. Navegación lateral / shell: asegurar coherencia de iconos y botones con el resto de la app.

### 8. Plan de capturas
Capturar las siguientes pantallas en los tres tamaños solicitados, sin generar archivos todavía:
- `1366×768`
- `1920×1080`
- `ventana estrecha`

Estados a documentar cuando apliquen:
- Vacío
- Normal
- Selección
- Error
- Degradado

Pantallas a incluir en el plan:
- Biblioteca principal con toolbar y tabla normal.
- Biblioteca con filtro abierto y tabla cargada.
- Biblioteca con estado vacío o sin resultados.
- Biblioteca en ventana estrecha.
- Assistant listo, con resultado y con error/cancelación.
- Diagnóstico actualizado y vacío en ventana estrecha.
- Import Manager en proceso y con errores/conflictos visibles.
- Import Manager en ventana estrecha.
- Metadata con campo de edición y vista previa.
- Metadata en ventana estrecha.

### Tabla final de seguimiento
| Pantalla | Prioridad | Objetivo visual | Riesgo | Dependencia | Estado de capturas |
| --- | --- | --- | --- | --- | --- |
| Biblioteca | Alta | Equilibrar toolbar, filtros y tabla sin perder legibilidad | Truncado en ventanas estrechas | Navegación lateral / estilos globales | Planificada |
| Assistant | Alta | Claridad de estados y resultado de texto | Confusión de `QTextEdit` con campo editable | Estilos de panel y botones | Planificada |
| Import Manager | Media-Alta | Separar etapas y reducir densidad confusa | Sobrecarga de listas y scroll vertical | Datos de progreso / botones de acción | Planificada |
| Diagnóstico | Media | Mejorar legibilidad y fallback vacío | Texto largo sin jerarquía clara | Estilos globales de texto | Planificada |
| Metadata | Media | Añadir claridad de selección y preview | Input de IDs manuales mal interpretado | Lógica de selección / preview | Planificada |
| Shell / navegación | Media | Mantener coherencia de iconos y botonera | Inconsistencia visual con otras pantallas | Navegación común | Planificada |

---
