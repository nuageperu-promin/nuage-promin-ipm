# promin_cotizacion_lista_materiales

Lista de materiales (BoM) en la impresión de la cotización. Solicitado por el equipo de Ventas de PROMIN (tableros).

- Check **Se imprime Lista de Materiales** en la cotización (pestaña principal, junto a «Términos de pago»).
- Si está activo, el PDF de la cotización/pedido imprime, debajo de cada producto que tenga BoM, una tabla con **código, descripción, cantidad y unidad** de sus componentes.
- Primer nivel de la BoM; no despliega los subensambles. No muestra precios de componentes.
- La cantidad del componente = cantidad de la BoM × cantidad cotizada (convierte la unidad si la línea usa otra).
- Productos sin BoM se imprimen normal. Con el check apagado, el PDF no cambia.
- Imprime la **versión de lista de materiales elegida en la línea** (columna opcional «Lista de Materiales» de las líneas de la orden) y muestra su referencia en el encabezado de la tabla. Si la línea no tiene una elegida, usa la BoM por defecto del producto (menor secuencia; la propia de la variante tiene prioridad sobre la de la plantilla).
- Aplica al PDF estándar de Odoo (también el del portal y el adjunto del correo).

Depende de `sale` y `mrp` (Fabricación). El vendedor no necesita permisos de Fabricación: la BoM se lee internamente.

## Check «Imp. Cot» en la lista de materiales (1.2.0)

- En la BoM (Fabricación > Listas de materiales), pestaña **Componentes**, columna **Imp. Cot** (por defecto desactivada).
- La cotización con **Se imprime Lista de Materiales** imprime **solo** los componentes con «Imp. Cot» activo. Si ninguno lo tiene, no se imprime tabla para ese producto.
