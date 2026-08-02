# Collection Engine

## Propósito futuro

El motor de colecciones administrará raíces locales de música, su estado de escaneo y la relación entre archivos y pistas.

## Responsabilidades previstas

- Registrar rutas de colección y opciones de escaneo.
- Coordinar importaciones mediante `CollectionService`.
- Persistir estado, errores y fecha de último escaneo con `CollectionRepository`.
- Notificar al Motor de Biblioteca para invalidar resultados afectados.

No contiene reproducción, análisis musical, lógica de UI ni conectores externos. No está implementado todavía.
