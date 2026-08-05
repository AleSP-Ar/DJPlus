# Componentes compartidos de prototipos DJPlus

Esta carpeta contiene estilos compartidos que normalizan la apariencia de los tres prototipos visuales:

- `tokens.css`: define colores, tipografía, radios y espaciado comunes.
- `components.css`: define la navegación lateral, los toolbars, botones, chips, estados, tarjetas y el preview player compartidos.

## Uso
Cada prototipo debe cargar los estilos compartidos antes de su CSS local:

```html
<link rel="stylesheet" href="../shared/tokens.css">
<link rel="stylesheet" href="../shared/components.css">
<link rel="stylesheet" href="styles.css">
```

## Alcance
- Normalización de tokens visuales comunes.
- Reutilización de clases de toolbar y controles.
- Estilos compartidos de estado hover, foco, seleccionado y deshabilitado.
- Soporte visual compartido para estado vacío, sin resultados y datos faltantes.
- Confirmación de que solo el estilo local permanece para comportamientos exclusivos de cada vista.

## Limitaciones
- No contiene lógica JS.
- No hay rutas absolutas.
- Solo funciona con los prototipos locales en `docs/ui/prototypes/`.
