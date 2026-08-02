# AI Architecture

## Estado

La IA no forma parte de v0.5. Este documento reserva una dirección arquitectónica sin implementar modelos, proveedores ni flujos automáticos.

## Dirección futura

- Las sugerencias serán opcionales, explicables y ejecutadas fuera del hilo de UI.
- Los resultados persistentes se guardarán mediante `AnalysisRepository` o servicios específicos aprobados.
- El Motor de Biblioteca funcionará sin IA ni conectividad.
- La IA consumirá DTOs y contratos de servicio; no accederá directamente a SQLite ni modificará widgets.

Los posibles casos de uso incluyen clasificación, sugerencias de playlists, etiquetado asistido y detección de duplicados.
