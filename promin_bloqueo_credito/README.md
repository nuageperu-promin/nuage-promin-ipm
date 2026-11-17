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
