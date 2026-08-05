# Prototipo de Playlist de DJPlus

Este prototipo visual autónomo muestra la pantalla de Playlist para la rama `release/v1.0.0-visual-polish`.

## Cómo usar

1. Abrir `docs/ui/prototypes/playlist/index.html` en un navegador.
2. Explorar la curva de energía y la lista de tracks.
3. Cambiar el estado con el selector `Playlist normal`, `Playlist vacía` y `Sin resultados`.

## Características

- Misma base visual de Biblioteca, con interfaz oscura y profesional.
- Navegación lateral compacta.
- Título y métricas de la playlist.
- Toolbar con búsqueda, orden y acciones.
- Curva superior de energía con un segmento por track.
- Ancho aproximado según duración y altura según energía.
- Separadores entre tracks y marcador de track seleccionado.
- Estados de energía baja, media, alta y peak.
- Tooltip visual con datos de cada segmento.
- Tabla/lista principal de tracks con selección clara.
- Preview Player fijo inferior.

## Limitaciones

- No se representa waveform individual fuera del Preview Player.
- Usa datos ficticios y recursos locales.
- No depende de frameworks ni CDNs.
