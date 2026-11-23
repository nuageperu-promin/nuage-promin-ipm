# promin_bloqueo_credito

Bloquea las cotizaciones y órdenes de venta de los clientes que llegaron a su límite de crédito. Solicitado por PROMIN.

- En el contacto, pestaña **Contabilidad**, al final del bloque **Límites de crédito**: check **Bloquear generación de Cotización/Orden de Venta**.
- Si el check está activo **y** el cliente llegó a su límite de crédito (el mismo cálculo del aviso naranja de Odoo: deuda + órdenes de venta + la cotización actual):
  - No se puede grabar la cotización/orden (error al guardar al crear o cambiar cliente, líneas, lista de precios, términos de pago).
  - Se ocultan los botones **Enviar** y **Confirmar** y aparece un aviso rojo en la cotización.
  - Confirmar o enviar por otra vía (portal, acciones) también se rechaza.
- Cancelar la cotización siempre está permitido. Las órdenes ya confirmadas no se tocan.
- El bloqueo se lee del contacto comercial: aplica también a los contactos hijos de la empresa.
- Requiere que el límite de crédito esté activado en Contabilidad > Configuración y en el contacto (casilla «Límite de crédito»). Sin límite activado no hay bloqueo.

## Compras (19.0.1.1.0)

- En el contacto, «Límite de crédito» se muestra como **Límite de Crédito Ventas**. Se agregan **Límite de Crédito Compras** (en moneda de la compañía; 0 = sin control) y el check **Bloquear generación de Cotización/Orden de Compra**.
- Exposición del proveedor = saldo por pagar contabilizado + órdenes de compra confirmadas aún no facturadas + la cotización/orden que se digita.
- Si supera el límite: aviso amarillo en la cotización/orden de compra. Con el check activo: aviso rojo, no se puede grabar (crear o cambiar proveedor, líneas, moneda, términos), se ocultan **Enviar**, **Confirmar** y **Aprobar**, y esas acciones se rechazan por otra vía. Cancelar siempre se permite; las órdenes ya confirmadas no se tocan.
- Limitación: las facturas de proveedor en borrador no se cuentan en la deuda (solo las publicadas); las líneas de órdenes confirmadas se descuentan según la cantidad facturada.
