# Prototipo de Biblioteca de DJPlus

Este prototipo visual autónomo es una demostración local de la pantalla de Biblioteca de DJPlus para la rama `release/v1.0.0-visual-polish`.

## Cómo usar

1. Abrir `docs/ui/prototypes/library/index.html` en un navegador moderno.
2. Usar el selector de vista `Portadas` / `Tabla`.
3. Cambiar el estado con el menú `Estado` para ver los modos `Normal`, `Vacío` y `Sin resultados`.

## Contenido

- Navegación lateral estrecha con íconos y tooltips.
- Encabezado con título `Biblioteca` y métricas destacadas.
- Toolbar compacta con búsqueda, filtros y selector de vista.
- Vista de portadas de tracks con tarjetas y chips de BPM, tonalidad, energía y rating.
- Selección clara de track activo.
- Estado vacío y estado sin resultados.
- Preview Player fijo inferior con controles, tiempo y chips de metadatos.

## Limitaciones

- Este prototipo usa datos ficticios.
- No utiliza waveform ni espectro en el encabezado de Biblioteca.
- La waveform solo aparece dentro del Preview Player inferior en el diseño.
- Solo usa HTML, CSS y JavaScript locales sin recursos externos.
