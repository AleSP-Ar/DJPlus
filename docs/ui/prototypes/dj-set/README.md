# Prototipo de DJ Set de DJPlus

Este prototipo visual autónomo muestra la pantalla de DJ Set para la rama `release/v1.0.0-visual-polish`.

## Cómo usar

1. Abrir `docs/ui/prototypes/dj-set/index.html` en un navegador.
2. Revisar la curva de energía superior y los capítulos.
3. Alternar la curva objetivo con el checkbox `Curva objetivo`.
4. Cambiar el estado con el selector `Set normal`, `Set vacío` y `Sin resultados`.

## Características

- Misma base visual que Biblioteca y Playlist.
- Navegación lateral compacta.
- Título y métricas del DJ Set.
- Toolbar con búsqueda, edición, orden y acciones.
- Lista principal de tracks.
- Preview Player fijo inferior.
- Viaje superior de energía completo del set.
- Segmentos por track con ancho y altura proporcional.
- Transiciones visibles entre tracks.
- Track seleccionado marcado.
- Capítulos representados: Warm-up, Organic, Build, Peak Time, Closing.
- Etiquetas de inicio y fin de capítulo.
- Peak times destacados y saltos bruscos advertidos.
- Datos faltantes representados explícitamente.
- Tooltip con track, capítulo, BPM, tonalidad, energía y duración.
- Curva real del set y curva objetivo opcional con trazo diferenciado.

## Limitaciones

- No se muestra waveform individual fuera del Preview Player.
- Usa datos ficticios y recursos locales.
- No depende de frameworks ni CDNs.
