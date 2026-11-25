# promin_bloqueo_credito

Bloquea la conversión de cotización a orden de venta de los clientes que llegaron a su límite de crédito. Solicitado por PROMIN.

- En el contacto, pestaña **Contabilidad**, al final del bloque **Límites de crédito**: check **Bloquear Orden de Venta**.
- Si el check está activo **y** el cliente llegó a su límite de crédito (el mismo cálculo del aviso naranja de Odoo: deuda + órdenes de venta + la cotización actual):
  - **La cotización sí se puede crear, editar, imprimir y enviar** (cambio 19.0.1.2.0, pedido del área de ventas).
  - **No se puede confirmar como orden de venta**: se oculta el botón **Confirmar**, aparece un aviso rojo en la cotización y la confirmación por otra vía (portal, acciones, importaciones) también se rechaza con un mensaje.
- Cancelar la cotización siempre está permitido. Las órdenes ya confirmadas no se tocan.
- El bloqueo se lee del contacto comercial: aplica también a los contactos hijos de la empresa.
- Requiere que el límite de crédito esté activado en Contabilidad > Configuración y en el contacto (casilla «Límite de crédito»). Sin límite activado no hay bloqueo.

## Compras (19.0.1.1.0)

- En el contacto, «Límite de crédito» se muestra como **Límite de Crédito Ventas**. Se agregan **Límite de Crédito Compras** (casilla + monto en moneda de la compañía, igual que ventas) y el check **Bloquear Cotización/Orden de Compra** (el de ventas se llama ahora **Bloquear Cotización/Orden de Venta**).
- Exposición del proveedor = saldo por pagar contabilizado + órdenes de compra confirmadas aún no facturadas + la cotización/orden que se digita.
- Si supera el límite: aviso amarillo en la cotización/orden de compra. Con el check activo: aviso rojo, no se puede grabar (crear o cambiar proveedor, líneas, moneda, términos), se ocultan **Enviar**, **Confirmar** y **Aprobar**, y esas acciones se rechazan por otra vía. Cancelar siempre se permite; las órdenes ya confirmadas no se tocan.
- Limitación: las facturas de proveedor en borrador no se cuentan en la deuda (solo las publicadas); las líneas de órdenes confirmadas se descuentan según la cantidad facturada.
