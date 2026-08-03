# DJPlus v0.14.0 — Music Analysis Engine

## Release scope

- `MusicAnalysisService` y analizador WAV PCM determinista: duración, sample rate, canales y peak.
- RMS, energía normalizada y estimación BPM basada en envolvente/picos con confianza y explicación.
- Perfil cromático de doce notas y detección tonal mayor/menor con raíz, modo y confianza.
- `MusicAnalysisFacade` para análisis por lote obtenido exclusivamente mediante `LibraryService`.
- `MusicAnalysisWorker` con progreso, concurrencia acotada, cancelación y cierre cooperativos.
- `MusicAnalysisBatchTool` read-only, salida opcional en `AssistantPanel` y exportación de informe a texto.

## Limits and safety posture

El soporte de entrada actual se limita a WAV PCM local. BPM y key pueden ser `None` ante silencio, audio corto o baja confianza. La cancelación es cooperativa y se comprueba entre bloques PCM, por lo que un bloque en curso no se interrumpe por fuerza.

No hay persistencia de resultados ni actualización automática de metadata. La integración no accede directamente a Repository, SQLite u ORM, no usa red, IA generativa ni dependencias externas. Las modulaciones, mezclas complejas y la elección de nombres enarmónicos no están modeladas todavía.

## Release checks

La candidata requiere suite completa `unittest`, `compileall`, `git diff --check`, benchmark con WAV sintéticos, prueba headless de `AssistantPanel` y auditoría de los archivos incluidos. Commit y tag requieren aprobación separada.
