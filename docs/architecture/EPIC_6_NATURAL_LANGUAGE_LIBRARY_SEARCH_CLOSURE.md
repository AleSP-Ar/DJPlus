# Epic 6 - Cierre de búsqueda natural

Cada búsqueda interpretada devuelve `NaturalLibrarySearchResultDTO`: filtros interpretados, total de coincidencias, página actual, items resumidos inmutables y disponibilidad de más resultados. El texto de respuesta describe los criterios aplicados y distingue cero resultados, consulta ambigua y página adicional.

`LibraryQueryTool` conserva el último DTO interpretado sólo para paginación en memoria. Una consulta nueva llama a `LibraryService.query()` y reinicia la página; `load_more` llama exclusivamente a `LibraryService.load_more()`. No genera SQL ni accede a Repository.

El `AssistantPanel` muestra el resumen y los ítems de la página devueltos por la herramienta.

Prueba manual: realizar una búsqueda natural, comprobar criterios, total e ítems. Si hay más resultados, solicitar `library_query` con `{"load_more": true}` y verificar la siguiente página. Probar un filtro ambiguo y una búsqueda sin coincidencias: ambos deben devolver mensajes claros sin modificar la biblioteca.
