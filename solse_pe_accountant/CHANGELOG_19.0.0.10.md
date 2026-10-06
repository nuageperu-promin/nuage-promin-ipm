# Changelog v19.0.0.10

## Detracción en facturas de proveedor (cascada A+B)

### Problema

En Odoo 19 el flujo habitual de facturas de proveedor no usa producto en
las líneas (el contador escribe descripción libre y elige cuenta contable).
La detección de `tiene_detraccion` en `solse_pe_edi` se hacía únicamente
mirando `invoice_line_ids.product_id.aplica_detraccion`, por lo que las
facturas de compra sin producto nunca disparaban la detracción aunque
correspondiera por giro del proveedor.

### Solución: cascada en 3 niveles para compras

Para facturas con `move_type in ('in_invoice', 'in_refund')`, el código
de detracción se resuelve en este orden:

1. **`account.move.aplica_detraccion`** (manual, en cabecera de factura).
2. **`product.template.aplica_detraccion`** de alguna línea (retrocompat).
3. **`res.partner.aplica_detraccion`** (default del proveedor).

El primero que tenga valor manda.

Para facturas de venta el comportamiento queda **idéntico** a
`solse_pe_edi`: el override de `_validar_detraccion_retencion` delega al
`super()` para `out_invoice` / `out_refund`.

### Cambios técnicos

| Archivo | Cambio |
|---|---|
| `models/res_partner.py` (nuevo) | Campos `aplica_detraccion` (Selection CATALOG54), `detraccion_id` (compute), `porc_detraccion` (compute). Mismo patrón que `product.template`. |
| `models/__init__.py` | Import del nuevo `res_partner`. |
| `models/account_move.py` | Campo `aplica_detraccion` en `account.move`. Override de `_validar_detraccion_retencion` para compras. Override de `_compute_detraccion_retencion` solo para extender `@api.depends` (delega al super). Onchange `partner_id` que precarga el código del proveedor en compras. |
| `views/account_move_view.xml` | Campo `aplica_detraccion` visible antes de `tiene_detraccion`, solo cuando `move_type in ('in_invoice', 'in_refund')`. |
| `views/res_partner_view.xml` (nuevo) | Campo `aplica_detraccion` en la pestaña Sales & Purchase del partner, después de `property_supplier_payment_term_id`. |
| `__manifest__.py` | Bump a `19.0.0.10`. Registro de `res_partner_view.xml`. |

### Comportamiento UX

1. **Configurar proveedor recurrente**: en la ficha del proveedor, campo
   "Aplicar detracción (default)" elegir el código del catálogo 54. Listo,
   todas las facturas de ese proveedor heredarán ese código.
2. **Factura puntual con detracción**: en la cabecera de la factura de
   proveedor, llenar el campo "Aplicar detracción" antes de confirmar.
   El sistema calcula `monto_detraccion`, `monto_detraccion_base` y al
   confirmar inyecta la línea SPOT con la cuenta `cuenta_detracciones_compra`
   de la empresa.
3. **Proveedor multi-rubro**: el código del partner sirve como default,
   y el contador puede editarlo en cabecera factura por factura.
4. **Retrocompat con productos**: si una factura ya usa producto con
   `aplica_detraccion`, sigue funcionando como antes (capa 2 de la cascada).

### Sub-bug arreglado de paso

El `for linea in self.invoice_line_ids` original de `solse_pe_edi` no
hacía `break`: si una factura tenía 2 productos con códigos de detracción
distintos (027 y 022), terminaba con el código del **último** producto en
iteración. El override usa `break` después del primer match, así que ahora
gana el primer producto con código.

Esto no afecta ventas (porque el super sigue siendo el código de EDI sin
cambiar). Sí mejora compras.

### Validaciones intactas heredadas de EDI

Estas validaciones siguen aplicándose **antes** de entrar a la cascada:

- `amount_total_signed >= company.monto_detraccion` (S/700 por defecto).
- `partner.doc_type == "6"` (solo RUC).

Si no se cumplen, devuelve dict vacío sin importar lo que se haya
configurado en cabecera o partner.

### Logs activos

Los logs `[SOLSE-ACCT]` siguen presentes desde v19.0.0.8 / v19.0.0.9.
Después de validar también compras se pueden retirar o bajar a
`_logger.debug`.

### Pendientes (sin tocar todavía)

Siguen vigentes los pendientes del CHANGELOG 19.0.0.7:

1. `_compute_group_payment` con `return False` dentro del for en el wizard.
2. `factura.company_id.cuenta_detraccion` (singular, inexistente) en wizard
   de autodetracción.
3. Falta `from odoo import _` en `account_move.py`.
4. La rama `is_draft` faltante en `_compute_needed_terms` (rama con
   payment_term).
5. Refactor de `_recompute_cash_rounding_lines` a override puntual.
