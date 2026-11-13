# promin_cotizacion_lista_materiales

Lista de materiales (BoM) en la impresión de la cotización. Solicitado por el equipo de Ventas de PROMIN (tableros).

- Check **Se imprime Lista de Materiales** en la cotización (pestaña principal, junto a «Términos de pago»).
- Si está activo, el PDF de la cotización/pedido imprime, debajo de cada producto que tenga BoM, una tabla con **código, descripción, cantidad y unidad** de sus componentes.
- Primer nivel de la BoM; no despliega los subensambles. No muestra precios de componentes.
- La cantidad del componente = cantidad de la BoM × cantidad cotizada (convierte la unidad si la línea usa otra).
- Productos sin BoM se imprimen normal. Con el check apagado, el PDF no cambia.
- Si el producto tiene varias BoM, usa la de menor secuencia (la propia de la variante tiene prioridad sobre la de la plantilla).
- Aplica al PDF estándar de Odoo (también el del portal y el adjunto del correo).

Depende de `sale` y `mrp` (Fabricación). El vendedor no necesita permisos de Fabricación: la BoM se lee internamente.
