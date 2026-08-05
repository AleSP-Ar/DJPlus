# DJPlus Visual Specification

## 1. Introducción

Documento de especificación visual aprobada para DJPlus que describe la apariencia, la estructura y los comportamientos de las tres pantallas principales: Biblioteca, Playlist y DJ Set. Se basa en los diseños aprobados y define tokens de estilo, jerarquía, estados, comportamientos responsivos y criterios de implementación.

Esta especificación se entrega como documento de diseño y no modifica ningún código, QSS, test, backend, esquema ni versión.

## 2. Paleta de tokens

### Colores principales
- `background`: #0F1116
- `surface`: #131821
- `surface-raised`: #1E2531
- `border`: #2E3748
- `text-primary`: #F5F7FA
- `text-secondary`: #A8B0C2
- `accent`: #5E8CFF
- `accent-hover`: #80A9FF
- `energy-low`: #30D3A6
- `energy-medium`: #F0C03D
- `energy-high`: #F85A3D
- `peak-time`: #E66CFF
- `warning`: #FFB25A
- `error`: #F75454
- `success`: #4CC67D

### Uso de tokens
- `background` para el fondo general de la aplicación.
- `surface` para paneles secundarios y áreas escalonadas.
- `surface-raised` para tarjetas, filas seleccionadas y controles elevados.
- `border` para divisores, outlines de inputs y contenedores de chips.
- `text-primary` para títulos, etiquetas principales y datos legibles.
- `text-secondary` para metadata, subtítulos y estados secundarios.
- `accent` para acciones principales, estados activos y navegación seleccionada.
- `accent-hover` para estados hover de botones y elementos interactivos.
- `energy-*` para visualización de energía, curvas y chips de energía.
- `peak-time` para marcar la sección de Peak Time en DJ Set.
- `warning`, `error`, `success` para mensajes de estado y feedback.

## 3. Fundamentos visuales

### Tipografía
- Familia: sistema UI sans serif consistente.
- Título de pantalla: 22 px, semibold, `text-primary`.
- Subtítulos de sección: 15 px, semibold, `text-primary`.
- Texto de cuerpo y controles: 13 px, regular, `text-primary`.
- Texto secundario: 12 px, regular, `text-secondary`.
- Numerales tabulares para duración/BPM/tiempo cuando el sistema lo soporte.

### Espaciados y radii
- `space-1`: 4 px
- `space-2`: 8 px
- `space-3`: 12 px
- `space-4`: 16 px
- `space-5`: 24 px
- `space-6`: 32 px
- `radius-sm`: 4 px
- `radius-md`: 8 px
- `radius-lg`: 12 px

### Bordes y sombras
- Bordes suaves de 1 px con `border` para tarjetas, inputs y separadores.
- Radio `radius-md` en tarjetas y paneles elevados.
- Radio `radius-sm` en botones y chips.
- Sombras muy suaves solo en paneles flotantes o overlays; la mayoría de la interfaz mantiene un aspecto plano y oscuro.

### Iconografía
- Estilo lineal simple, contornos suaves, peso medio.
- Íconos en toolbar, navegación y estado deben ser consistentes en tamaño.
- Tamaños: 20 px para iconos pequeños, 24 px para acciones principales, 28 px para grupo de reproducción.

## 4. Comportamiento general

### Navegación lateral
- Compacta, vertical y persistente en pantallas de escritorio.
- Ancho estándar: 240 px en modo normal, 80 px en modo compacto.
- Contiene íconos + etiquetas en modo completo; solo íconos en modo compacto.
- Estados: normal, hover, activo.
- Accesibilidad: foco visible en cada elemento, etiqueta accesible en modo compacto.

### Encabezados y toolbar
- Toda pantalla tiene header superior con título y subtítulo.
- Toolbar secundaria con acciones principales y controles de filtro.
- En Biblioteca, toolbar incluye búsqueda, filtros, contador de resultados y botón de acción principal.
- En Playlist y DJ Set, toolbar incluye acciones de orden, modo de vista y acción de exportar/guardar.

### Búsqueda y filtros
- Campo de búsqueda con ícono de lupa y placeholder `Buscar tracks...`.
- Filtros en línea como chips o botones de menú desplegable.
- Filtros principales: género, BPM, tonalidad, energía, estado.
- Clear all visible cuando hay filtros activos.
- En vista compacta puede colapsar a un botón `Filtros`.

### Estados globales
- Hover: fondo `surface-raised` suave y cambio de texto/ícono a `accent-hover` cuando aplica.
- Seleccionado: fondo `accent` con opacidad baja o borde 2 px `accent` dependiendo del componente.
- Foco: outline brillante de 2 px `accent` o `surface-raised` con sombra tenue.
- Deshabilitado: opacidad 40%, texto `text-secondary`, cursor no permitido.
- Vacío: tarjeta/panel con icono ilustrativo, título y acción sugerida.
- Carga: skeletons de bloques con gradiente suave en `surface-raised` y animación lenta.
- Error: banner con color `error`, ícono de alerta y mensaje específico.
- Degradado: se usa solo en overlays no funcionales y estados inactivos de waveform preview.

## 5. Componentes compartidos

- Panel lateral `NavigationRail`.
- Toolbar superior reutilizable con espacio entre grupo izquierdo/derecho.
- Chips de filtro de BPM, tonalidad y energía.
- Tarjetas de track con carátula, metadata y badges.
- Tabla de tracks con filas seleccionables.
- Preview Player fijo inferior.
- Curva de energía en Playlist y DJ Set.
- Tags de capítulo del DJ Set.

## 6. Biblioteca

### Estructura de pantalla
- Barra lateral compacta izquierda.
- Contenido principal dividido en:
  - Header superior con título `Biblioteca` y contador de tracks.
  - Toolbar con búsqueda, filtros, métricas resumidas y control de vista.
  - Área de contenido principal con alternancia entre:
    - Vista Tabla
    - Vista Portadas
  - Preview Player fijo en la parte inferior.

### Jerarquía visual
- Título `Biblioteca` en la parte superior.
- Toolbar visible inmediatamente debajo del título.
- Métricas y controles de vista agrupados a la derecha.
- Contenido principal dominante: tabla o tarjetas.
- Preview Player en el borde inferior, siempre visible y separado por un divisor.

### Dimensiones aproximadas
- Contenedor principal: 1920×1080 utiliza sidebar 240 px y contenido 1680 px.
- Toolbar: altura 64 px.
- Área de contenido: min-height 720 px.
- Preview Player: altura 120 px fijo.
- Vista Portadas: tarjetas de 220×260 px con 24 px de separación.

### Navegación lateral
- Íconos: Biblioteca, Playlist, DJ Set, Colecciones, Importar, Ajustes.
- Texto visible en ancho completo.
- Modo compacto oculta el texto y mantiene tooltips.

### Toolbar
- Grupo izquierdo: búsqueda, filtro rápido, botón `Limpiar`.
- Grupo derecho: métricas de resultados, selector `Tabla` / `Portadas`, botón `Nuevo` o `Importar`.
- Distancia interna: `space-4` entre controles.

### Búsqueda y filtros
- Input principal con borde redondeado `radius-md`, fondo `surface`, texto `text-primary`.
- Icono de búsqueda integrado.
- Filtros activos representados como chips con borde `border` y fondo `surface-raised`.
- Chip `BPM`, `Tonalidad` y `Energía` visibles en el toolbar cuando están aplicados.

### Tabla
- Columnas: selección, título, artista, BPM, tonalidad, energía, duración, fecha/estado.
- Ancho: texto flexible, numéricos fijos 96 px a 120 px.
- Filas: altura 50 px.
- Separadores: línea 1 px `border` entre filas.
- Selección: fondo `accent` con baja opacidad si está seleccionado.
- Hover: fondo `surface-raised`, texto primario más brillante.
- Thumbnail opcional en la primera columna en modo compacta.

### Tarjetas
- Contenido: carátula cuadrada, título, artista, chips de BPM/tonalidad/energía.
- Altura: 260 px.
- Fondo: `surface-raised` con `radius-md` y bordes `border`.
- Acción seleccionable en toda la tarjeta.
- Badge de `En reproducción` o `Seleccionado` en la esquina superior.

### Preview Player
- Ubicado en el footer, persistente en todas las pantallas.
- Controles: título/artist, play/pause, stop, tiempo actual/duración, slider de seek, volumen, dispositivo salida.
- Waveform: solo en el Preview Player.
- Estado: muestra `Sin salida de audio` en degradado si no hay pista cargada.
- Altura: 120 px.
- Panel de fondo: `surface-raised` con borde superior `border`.
- En ventana estrecha, el control de volumen y la selección de salida pueden colapsar en un botón de menú.

### Curvas de energía y visualización de waveform
- No se muestran curvas ni waveform en la Biblioteca.
- La waveform del track aparece únicamente en el Preview Player inferior y no en listado ni tarjetas.

## 7. Playlist

### Estructura de pantalla
- Barra lateral compacta.
- Header con título `Playlist` y subtítulo dinámico.
- Toolbar con acciones de orden, guardar, compartir y filtros.
- Área principal con visualización superior de curva de energía de la secuencia.
- Lista/tabla de tracks debajo de la curva.
- Preview Player fijo inferior.

### Jerarquía visual
- Curva superior de energía es la pieza visual más prominente.
- Lista de tracks es secundaria pero sigue claramente visible.
- Control de selección y estado de track destacado se muestra en la lista.

### Dimensiones aproximadas
- Curva de energía: altura 200 px en 1920×1080, 150 px en 1366×768.
- Ancho total: usa el ancho de contenido completo.
- Pistas segmentadas en proporción a la duración.
- Espacio entre curva y tabla: `space-5`.

### Barra lateral
- Igual que Biblioteca, con Playlist activo.

### Toolbar
- Botones: `Guardar`, `Exportar`, `Reordenar`, `Vista Detallada`.
- Filtros: `Mostrar solo pistas activas`, `Filtrar por energía`.
- Acción de orden: menú desplegable `Ordenar por` BPM / Duración / Energía.

### Búsqueda y filtros
- Busca dentro de los tracks de la playlist.
- Filtros visibles en toolbar o panel lateral según ancho.
- Chips de energía y BPM se representan como indicadores de estado de los tracks.

### Curva de energía
- Representa energía total de la secuencia.
- Cada segmento es un track.
- Ancho del segmento proporcional a la duración del track.
- Altura del segmento proporcional a la energía media del track.
- Límite de altura: valores con `energy-low`, `energy-medium`, `energy-high`.
- Picos: marcadores visibles con `peak-time` cuando superan el umbral alto.
- Transiciones: líneas de separación suaves entre segmentos.
- Orden: se muestra el índice del track sobre cada segmento o en un label adhesivo.
- Track seleccionado: destacado con un borde `accent` y opacidad elevada.
- Hover en segmento: resalta el track correspondiente en la lista.

### Tabla/Lista de tracks
- Similar a Biblioteca pero optimizada para contenido playlist.
- Columnas principales: orden, título, artista, duración, energía, BPM, transición.
- Selección de fila actual sincronizada con el segmento de la curva.
- Picos y transiciones pueden mostrarse con íconos en una columna `Eventos`.

### Preview Player
- Igual que Biblioteca: waveform individual solo en el Preview Player.
- El panel inferior permanece fijo y visible.
- Para playlist con track cargado, muestra título y progreso.
- En carga o sin pista, muestra estado `Preview no cargado`.

## 8. DJ Set

### Estructura de pantalla
- Barra lateral compacta.
- Header con título `DJ Set` y subtítulo `Viaje de energía`.
- Toolbar con acciones de capítulos, exportación y filtros de set.
- Visualización principal de la curva de energía del set.
- Capítulos marcados en la zona de curva.
- Lista de tracks / secuencia debajo.
- Preview Player fijo inferior.

### Jerarquía visual
- Viaje superior de energía es el foco principal.
- Capítulos y transiciones aparecen encima de la lista.
- Track seleccionado y picos son acentos críticos.

### Dimensiones aproximadas
- Curva de energía: 220 px de altura en desktop grande.
- Capítulos: panel horizontal de 60 px sobre la curva.
- Secciones verticales de capítulo ocupan el ancho proporcional a su duración.

### Navegación lateral y toolbar
- Mismos patrones que Biblioteca y Playlist.
- Toolbar puede incluir `Mostrar capítulos`, `Editar set`, `Vista de timecode`.

### Curva de energía del set
- Viaje de energía superior muestra la evolución de todo el set.
- Control de altura fluida con picos y valles claramente destacados.
- Transiciones entre tracks indicadas por líneas verticales finas `border`.
- Picos: marcadores con `peak-time` en el borde superior.
- Track seleccionado: segmento resaltado con `accent` y sombra suave.

### Capítulos del DJ Set
- Capítulos definidos: Warm-up, Organic, Build, Peak Time, Closing.
- Cada capítulo debe tener una etiqueta visible sobre su área.
- Colores de capítulo: tonos suaves derivados de la paleta, con mayor saturación en `Peak Time`.
- División de capítulos: líneas verticales y fondo ligero en la zona correspondiente.
- Iconografía de capítulo: pequeños indicadores circulares junto al nombre.
- El capítulo activo en pantalla puede mostrar un badge con nombre y rango de tiempo.

### Track seleccionado y picos
- Al seleccionar un track, se resalta la fila y el segmento en la curva.
- Picos se muestran con un punto/flecha `peak-time` y un tooltip al hover.
- Transiciones se representan como cortes de color o separadores entre barras.

### Preview Player
- Igual que las demás pantallas: waveform individual solamente en el reproductor inferior.
- Mantiene el mismo diseño fijo inferior y comportamiento responsive.
- El panel no desplaza la curva ni la lista cuando se oculta parcialmente.

## 9. Dimensiones y comportamiento responsivo

### Comportamiento en 1920×1080
- Sidebar fijo a 240 px.
- Área de contenido amplia con cards y tabla horizontales.
- Playlist/DJ Set muestran la curva completa sin scroll horizontal urgente.
- Preview Player fijo inferior con ancho completo.

### Comportamiento en 1366×768
- Sidebar sigue visible, pero la interfaz puede usar 80 px en modo compacto si es necesario.
- El contenido principal adapta las tarjetas a 2 columnas en Vista Portadas.
- Curva de energía reduce altura a 150–180 px.
- Toolbar puede mostrar menos botones y agrupar acciones en un menú.
- Tabla mantiene scroll vertical y columnas prioritarias.

### Comportamiento en ventana estrecha
- Sidebar colapsa a iconos o drawer lateral.
- Header y toolbar se vuelven de una sola columna.
- Búsqueda, filtros y acciones principales se pueden ocultar detrás de un menú `Más`.
- Vista de tabla cambia a compacta y prioriza columnas: título, duración, energía.
- Tarjetas en Vista Portadas se reducen a una sola columna o fila.
- Preview Player permanece fijo y usa controles simplificados.
- No debe requerir horizontal scroll para las áreas primarias en anchos ≥ 1000 px.

## 10. Accesibilidad

- Todos los controles deben tener focus visible claro.
- Navegación lateral, toolbar, tabla, tarjetas y Preview Player accesibles con teclado.
- Labels accesibles para campos de búsqueda y botones.
- Contraste mínimo 4.5:1 para texto principal y 3:1 para texto secundario.
- Estados hover y seleccionado no dependen solo del color.
- Foco en inputs y botones con outline `accent`.
- Estados vacíos y error describen la acción siguiente.
- Los chips deben ser seleccionables mediante teclado y tener un propósito claro.
- El Preview Player debe mantener tab-order lógico: prioridad de reproducción, seek, volumen.

## 11. Diferencias funcionales entre Biblioteca, Playlist y DJ Set

- Biblioteca
  - No muestra curva ni waveform de lista.
  - Permite alternar entre Vista Tabla y Vista Portadas.
  - Contiene búsqueda y filtros detallados de biblioteca.
  - Incluye métricas y selección rápida de tracks.
  - Reproductor fijo inferior con waveform individual.

- Playlist
  - Muestra curva de energía de toda la secuencia.
  - Cada segmento corresponde a un track, ancho según duración, altura según energía.
  - Marca track seleccionado, transiciones y picos.
  - Mantiene waveform solo en Preview Player.
  - Enfocado en orden y secuencia de lista.

- DJ Set
  - Muestra viaje superior de energía completo.
  - Incluye capítulos: Warm-up, Organic, Build, Peak Time, Closing.
  - Marca transiciones, cambios de capítulo, picos y track seleccionado.
  - Más énfasis en narrativa de set que en lista.
  - Waveform individual únicamente en el Preview Player.

## 12. Componentes detallados

### Chips de BPM, tonalidad y energía
- Forma: rectángulo con `radius-sm`.
- Fondo: `surface-raised`.
- Texto: `text-primary`.
- Border: 1 px `border`.
- Estado activo: fondo `accent` ligero, texto `text-primary`.
- Hover: fondo `accent-hover` tenue.
- Deshabilitado: opacidad 40%.

### Tabla
- Filas con altura 50 px.
- Columnas con alineación: texto izquierda, numéricos derecha.
- Encabezado de columna: `text-secondary`, tamaño 12 px.
- Fila seleccionada: fondo `accent` opaco 10% y borde izquierdo `accent` 4 px.
- Hover de fila: fondo `surface-raised`.
- Sin datos: fila completa con mensaje centrado y acción sugerida.

### Tarjetas de portada
- Espaciado interior: `space-3`.
- Carátula: altura 140 px, ancho completo.
- Metadata: título, artista y chips alineados.
- Interacción: escala 1.02 en hover y sombra suave.
- Estado seleccionado: borde `accent` 2 px y overlay tenue.

### Preview Player
- Columnas: metadata + transporte, seek + tiempo, volumen + salida.
- Botón de play/pause central grande.
- Slider de seek con thumb visible y barra de progreso en `accent`.
- Waveform: fondo `surface`, forma de onda `accent` / `accent-hover`.
- Texto de tiempo: `text-secondary`.
- Estados inactivos: icono y mensaje en `text-secondary`.

### Curva de energía
- Base: área de gráfico con fondo `surface`.
- Línea principal: color `energy-medium` con gradiente a `energy-high` en picos.
- Segmentos: barras suaves con borde sutil.
- Picos: puntos `peak-time` sobre la línea.
- Transiciones: líneas verticales `border` en el área.
- Etiquetas de track: texto `text-secondary` pequeño en la base del segmento.

### Capítulos del DJ Set
- Barra superior con cinco secciones.
- Cada capítulo: label semibold, color de fondo ligero.
- `Warm-up`: fondo tenue verde / `energy-low`.
- `Organic`: fondo suave azul.
- `Build`: fondo naranja claro / `energy-medium`.
- `Peak Time`: fondo magenta claro / `peak-time`.
- `Closing`: fondo gris azulado.
- Separadores de capítulo: línea vertical 2 px con opacidad 20%.
- Capítulo activo: resaltado con borde inferior `accent` y label `text-primary`.

## 13. Comportamientos de estado específicos

### Hover
- Elemento eleva su fondo a `surface-raised`.
- Iconos cambian a `accent-hover`.
- En zonas de lista, el texto principal se vuelve `text-primary` más brillante.

### Seleccionado
- Fondo `accent` suave o borde `accent` definido.
- Texto principal se mantiene `text-primary` y el icono de selección aparece.
- En la curva de energía, el segmento aparece con mayor contraste.

### Foco
- Outline de 2 px `accent` o `surface-raised` en controles.
- Focus ring debe ser visible sobre fondos oscuros y claros.

### Deshabilitado
- Opacidad 40% o `text-secondary`.
- Cursor no-allowed.
- No se permite hover activo.

### Vacío
- Card/panel central con icono ilustrativo, título y acción.
- Mensaje secundario para guiar al usuario.

### Carga
- Skeleton de líneas en tablas y cards.
- Animación de gradiente horizontal suave.
- Placeholder de botón inactivo.

### Error
- Banner rojo con texto `error`.
- Si el error ocurre en el Preview Player, el texto aparece en la zona de waveform.
- Si ocurre en la pantalla principal, se muestra un banner superior persistente.

### Degradado
- Único en overlays de waveform no activos o en paneles de estado inactivo.
- No debe usarse como fondo principal para texto.

## 14. Orden de implementación en PySide6

1. Definir los tokens de color y espaciado en un módulo central de estilo.
2. Implementar la estructura del shell con NavigationRail, header y footer fijo.
3. Construir el Preview Player persistente con controls y waveform.
4. Desarrollar la pantalla de Biblioteca con toolbar, búsqueda, filtros y alternancia de vista.
5. Añadir la tabla de tracks y el modo Portadas.
6. Implementar la pantalla Playlist con curva de energía y sincronización de lista.
7. Implementar la pantalla DJ Set con viaje de energía y capítulos.
8. Añadir comportamientos responsive para 1920×1080, 1366×768 y ventanas estrechas.
9. Integrar estados vacíos, carga y error en cada pantalla.
10. Validar accesibilidad de foco, labels y contraste.

## 15. Riesgos técnicos

- Falta de un sistema de tokens centralizado en PySide6 puede llevar a inconsistencias de color y espaciado.
- La curva de energía puede requerir un widget de gráfico personalizado que no existe aún.
- Sin un modelo de datos consistente para capítulos y energía, la sincronización entre gráfico y lista puede ser frágil.
- La performance de listas grandes en la Biblioteca con tablas y tarjetas puede degradar la UI.
- El Preview Player fijo puede chocar con layouts responsivos si no se maneja correctamente en anchos estrechos.

## 16. Funciones que requieren backend adicional

- Cálculo de energía de playlist y DJ Set.
- Datos de capítulos de DJ Set: Warm-up, Organic, Build, Peak Time, Closing.
- Metadatos de BPM, tonalidad y energía para chips y filtros.
- Estados de transición y picos para la curva de energía.
- Conteos de métricas y resultados en la Biblioteca.

## 17. Criterios de aprobación visual

- La Biblioteca respeta la jerarquía: sidebar, toolbar, contenido principal y preview fixed.
- La Playlist muestra una curva de energía segmentada correcta y sincronizada con la lista.
- El DJ Set presenta capítulos claramente marcados y un viaje de energía legible.
- Los estados hover, seleccionado, foco, deshabilitado, vacío, carga y error son visibles y consistentes.
- La paleta de tokens se aplica correctamente en todos los componentes.
- El comportamiento en 1920×1080, 1366×768 y ventana estrecha es estable.
- Accesibilidad de teclado y contraste valida las principales áreas.
- No se muestra waveform fuera del Preview Player.

## 18. Checklist de implementación

- [ ] Definir tokens de color y espaciado en PySide6.
- [ ] Crear sidebar de navegación compacta.
- [ ] Implementar header y toolbar comunes.
- [ ] Construir Preview Player fijo con waveform.
- [ ] Implementar Biblioteca con vista Tabla y Portadas.
- [ ] Añadir búsqueda, filtros y chips funcionales.
- [ ] Crear tabla con selección y estados.
- [ ] Crear tarjetas de portada con badges.
- [ ] Implementar Playlist con curva de energía segmentada.
- [ ] Sincronizar selección de curva y lista en Playlist.
- [ ] Implementar DJ Set con capítulos.
- [ ] Marcar picos, transiciones y track seleccionado en DJ Set.
- [ ] Definir estados visuales hover/selected/focus/disabled.
- [ ] Agregar estados vacíos, carga y error en cada pantalla.
- [ ] Validar comportamiento en 1920×1080, 1366×768 y ancho estrecho.
- [ ] Probar accesibilidad de foco y labels.
- [ ] Revisar el documento final y confirmar consistencia.
