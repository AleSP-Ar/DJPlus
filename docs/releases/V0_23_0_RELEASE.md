# DJPlus v0.23.0 — UI Freeze

Esta release cierra formalmente la Fase Gráfica. Los sprints UI 1–10 establecen un shell con navegación persistente, rediseño de Biblioteca, Preview Player adaptable, Colecciones, Playlists, Import Manager, Metadata, Assistant, Diagnóstico, feedback coherente y accesibilidad final.

El alcance es exclusivamente UI, pruebas UI y documentación. Se preservan backend, schema, servicios, scoring, consultas, reproducción, importación y contratos públicos de v0.22.0.

La validación de cierre usa unittest discovery completo, focales UI, compileall y diff check, en Qt offscreen. La auditoría confirma ausencia de procesos Python, locks y temporales del repositorio. FFmpeg permanece ignorado, local y fuera de Git LFS.
