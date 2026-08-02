# UI Guidelines

## Principios

- La UI presenta estado y transmite intención del usuario; no contiene reglas de consulta ni acceso a base de datos.
- Las operaciones lentas deben ser cancelables y no bloquear la ventana.
- La tabla muestra solo las filas de la ventana cargada.
- Búsqueda, filtros y orden se expresan mediante contratos tipados hacia `LibraryService`.
- Los detalles de una pista se cargan por identificador.

## Biblioteca profesional

- Retroalimentación de carga y resultados claros.
- Orden determinista y consistente entre páginas.
- Debounce de búsqueda y cancelación de consultas obsoletas.
- Atajos y accesibilidad definidos antes de ampliar controles.
