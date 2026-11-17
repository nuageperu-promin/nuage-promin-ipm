# promin_cotizacion_formato

Reporte **Cotización PROMIN** en el menú Imprimir de la cotización, con el modelo entregado por Proveedores Mineros.

Contenido del PDF:
- Logo, sello ISO 9001 y direcciones (fijos en el reporte).
- Cliente (con correo y teléfono), número y fecha de cotización («12 de mayo del 2027»), referencia y «Elaborado por» (vendedor).
- Tabla: IT, Cant., UM, Producto Solicitado (descripción de la línea), Producto Ofertado (nombre del producto), Modelo (código interno), Precio Unit. e Importe. Sin columna Marca ni «Ver ficha».
- Si la cotización tiene el check «Se imprime Lista de Materiales», debajo de cada ítem se imprime su BoM (versión elegida en la línea).
- Plazo de entrega por ítem, agrupado por días (campo «Plazo de entrega» de la línea).
- Subtotal, IGV y TOTAL.
- Condiciones de venta: Moneda (lista de precios), Forma de pago (términos de pago), Validez (días hasta el vencimiento), y los textos editables Lugar de entrega, Tolerancia, Términos de venta e IMPORTANTE (pestaña «Otra información» > «Cotización PROMIN»), con el texto de PROMIN por defecto.
- Datos para emisión de OC: cuentas de la compañía de BCP, BBVA y Scotiabank (Soles y Dólares). Se reconocen por el nombre del banco; la cuenta sin moneda cuenta como Soles. Registrarlas en Contabilidad > Configuración > Cuentas bancarias.

El PDF estándar de Odoo no cambia.
