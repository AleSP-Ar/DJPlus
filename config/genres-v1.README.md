Formato de taxonomy `genres-v1.json`

- `version` (string): versión del seed. Cambiar cuando se actualice la estructura.
- `description` (string): texto descriptivo opcional.
- `genres` (object): mapa `canonical_id -> { label, aliases }`.
  - `canonical_id`: clave única del género (string).
  - `label`: human-readable label (string).
  - `aliases`: lista de strings que normalizan al mismo canonical_id.
- `ambiguous_terms` (object) (opcional): mapa `term -> [canonical_id, ...]` para declarar términos que deben considerarse explícitamente ambiguos.

Reglas de validación implementadas (loader):
- El JSON es validado sin dependencias externas; claves duplicadas en cualquier objeto causan error de carga.
- `version` debe ser una cadena no vacía.
- `genres` debe ser un objeto; cada entrada requiere `label` (string) y `aliases` (lista de strings).
- `ambiguous_terms` debe mapear términos (string) a listas no vacías de `canonical_id` existentes.
- Aliases que normalizan al mismo token entre diferentes `canonical_id` son rechazados como conflicto, salvo que el token esté declarado en `ambiguous_terms` con el conjunto exacto de candidatos.

Versión: 1
