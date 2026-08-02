# Quality Guidelines

## Propósito

Estas guías orientan el crecimiento de DJPlus como producto profesional. Son criterios de revisión y mejora continua, no restricciones mecánicas que sustituyan el juicio técnico.

## Diseño y documentación

- Ninguna funcionalidad grande comienza sin un documento técnico revisado y aprobado.
- El flujo esperado es: idea → diseño → revisión → implementación → pruebas → commit → tag cuando corresponda.
- Las decisiones de arquitectura, datos, rendimiento e integraciones se documentan antes de su implementación.

## Tamaño y claridad del código

- Una clase no debería superar 500 líneas; si ocurre, se revisan responsabilidades y cohesión.
- Un método no debería superar 50 líneas salvo que exista una justificación clara y documentada.
- Los nombres deben expresar intención y las dependencias deben ser explícitas.
- La duplicación se elimina mediante responsabilidades compartidas, no mediante abstracciones prematuras.

## Capas y datos

- La UI no consulta la base de datos directamente.
- Toda consulta pasa por un servicio o repositorio.
- Los servicios no dependen de Qt y los repositorios no dependen de widgets.
- Las consultas son parametrizadas y las columnas de orden/filtro se validan contra listas permitidas.
- Las operaciones de biblioteca se diseñan para colecciones grandes y no asumen carga completa en memoria.
- Los cambios de rendimiento se comparan contra una medición de referencia y documentan los límites de la prueba.

## Pruebas y entrega

- Cada sprint define pruebas de aceptación antes de implementarse.
- Todo cambio importante incluye validación proporcional: unidad, integración, rendimiento o interfaz según corresponda.
- Cada sprint termina con pruebas, documentación actualizada y un commit cuando el alcance esté aprobado.
- Los tags se reservan para versiones o hitos estables acordados.

## Rendimiento y telemetría local futura

Hacia v0.8 se evaluará telemetría exclusivamente local, sin envío de datos a Internet. Medirá tiempo de apertura, consultas frecuentes, tiempos de búsqueda y ordenamiento, uso de memoria y tamaño de biblioteca. Su diseño deberá definir retención, privacidad, activación y acceso del usuario antes de implementarse.
