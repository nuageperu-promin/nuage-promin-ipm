# Estado del módulo solse_pe_accountant — Conocimiento acumulado

> **Odoo versión:** 19.0 Community  
> **Módulo:** solse_pe_accountant v19.0.0.1  
> **Última actualización de este archivo:** 2026-03-07  
> **Propósito:** Continuidad entre chats de desarrollo — leer ANTES de hacer cualquier cambio al módulo.

---

## 1. Arquitectura general

Módulo de contabilidad para localización peruana. Depende de:
- `account` (nativo Odoo)
- `solse_pe_rate_api` — tipo de cambio SUNAT/BCRP
- `solse_pe_edi` — facturación electrónica UBL 2.1
- `solse_pe_cpe` — gestión de CPE (contiene `tiene_detraccion`, `monto_detraccion`, `monto_retencion`, `tiene_retencion`, `monto_detraccion_base`, `monto_retencion_base`, `monto_neto_pagar`, `monto_neto_pagar_base`)

### Estructura de archivos
```
solse_pe_accountant/
├── models/
│   ├── account_move.py          ← núcleo: detracciones, retenciones, tipo de cambio, apertura, glosa
│   ├── res_company.py           ← cuentas configurables de detracción y retención
│   ├── res_config_settings.py   ← expone campos de company en Settings UI
│   ├── tipo_cambio_sunat.py     ← fecha_tipo_cambio, _compute_date override, cash rounding
│   └── account_payment_term.py  ← helpers (sin uso activo en producción aún)
├── wizard/
│   └── account_payment_register_min.py  ← wizard de pago con soporte detracciones/retenciones
├── views/
│   ├── account_move_view.xml
│   └── res_config_settings_view.xml
└── wizard/
    └── account_payment_register_views.xml
```

---

## 2. Cambios Odoo 19 aplicados (migración desde v17)

| v17 / anterior | v19 |
|---|---|
| `payment_id` en account.move | `origin_payment_id` |
| `to_check` field | `checked` field |
| `deprecated='f'` en account_account | `active='t'` |
| `_compute_terms()` sin cash_rounding | Requiere parámetro `cash_rounding` |
| `compute_all_tax` en move.line | **Eliminado** — usar `amount_tax` directamente |
| `account.payment` states: `posted` | `in_process` |
| `is_internal_transfer` en payment | **Eliminado** |
| `destination_journal_id` en payment | **Eliminado** |
| `ref` en payment | `memo` |
| `_get_batches()` en wizard | `self.batches` (campo binario computed) |
| `_get_total_amount_in_wizard_currency_to_full_reconcile()` | `_get_total_amounts_to_pay()` |
| `_get_batch_communication()` | `_get_communication()` |
| CTE `ir_property` en SQL | Acceso directo `partner.property_account_receivable_id` |
| `account_account_res_company_rel` via deprecated | via `account_account_res_company_rel.res_company_id` con `active='t'` |
| `line_subsection` no existía en display_type | Agregado en v19, incluir en exclusiones |

---

## 3. Bugs corregidos (todos aplicados al código actual)

### Bug 1 — write() dentro de _compute_glosa (AccountPayment)
- **Problema:** Se llamaba `reg.move_id.write({'glosa': ...})` dentro de un compute → recursión + error Odoo.
- **Solución:** `AccountMove.glosa` convertido a `compute='_compute_glosa_move', store=True, readonly=False`. El compute solo actúa cuando hay `origin_payment_id`. Facturas y asientos manuales conservan su valor.

### Bug 2+4 — Colisión de term_key entre línea normal y línea de detracción/retención
- **Problema:** En Odoo 19 el term_key nativo no incluye `account_id`, causando colisión cuando la línea de detracción tiene la misma fecha que una cuota de pago.
- **Solución:** `_compute_term_key` agrega `account_id` al frozendict SOLO para líneas cuya cuenta esté en el set de cuentas especiales (detracciones + retenciones). Las demás líneas mantienen el comportamiento nativo.

### Bug 3 — obtener_cuotas_pago no descontaba detracción
- **Problema:** Condición original solo descontaba si había `monto_retencion`, ignorando detracción sola.
- **Solución:** `if first_time and (invoice.monto_detraccion or invoice.monto_retencion):`

### Bug 5 — compute_all_tax eliminado en Odoo 19
- **Problema:** El bloque `is_draft` en `_compute_needed_terms` usaba `line.compute_all_tax` que no existe en v19.
- **Solución:** Eliminado el bloque. En v19 `amount_tax` y `amount_untaxed` están siempre disponibles.

### BUG-R1 — Retención no generaba línea en needed_terms
- **Solución:** Misma lógica que detracción. Ambos bloques de `_compute_needed_terms` (con y sin `invoice_payment_term_id`) ahora generan línea de retención con `account_id` en el key frozendict.

### BUG-R2 — Una sola cuenta de retenciones para compra y venta
- **Solución:** Dos cuentas separadas:
  - `cuenta_retenciones` → Compra (pasivo: IGV retenido por pagar a SUNAT)
  - `cuenta_retenciones_venta` → Venta (activo: IGV retenido por cobrar)

### BUG-R3 — obtener_cuotas_pago no filtraba línea de retención
- **Solución:** Ahora filtra tanto la línea de detracción como la de retención para que no aparezcan como cuotas cobrabres/pagables.

### BUG-R4/R5 — Wizard usaba pago_detraccion para bloquear retención, mensaje incorrecto
- **Solución:** Wizard usa `pago_retencion` (campo independiente) para validar retención. Mensaje: "Ya existe un pago por retención registrado en esta factura".

### BUG-R6 — Flujo de retención solo cubría in_invoice
- **Solución:** `_create_payment_vals_from_wizard` y `_cuenta_retencion_id()` cubren `out_invoice` con `cuenta_retenciones_venta` y `in_invoice` con `cuenta_retenciones`.

---

## 4. Feature: Fecha de vencimiento de detracción configurable

### Campos en res.company
```python
usar_fecha_vencimiento_detraccion = fields.Boolean(default=False)
dia_vencimiento_detraccion = fields.Integer(default=5)  # rango 1-28
```

### Helper _calcular_fecha_detraccion(self, fecha_base)
- Si `usar_fecha_vencimiento_detraccion = False` → retorna `fecha_base` sin cambios.
- Si activo → calcula día N del mes siguiente, con cap al último día del mes (maneja febrero correctamente con `relativedelta`).
- **Requiere:** `from dateutil.relativedelta import relativedelta` en account_move.py.

### Campo informativo
```python
fecha_vencimiento_detraccion = fields.Date(compute='_compute_fecha_vencimiento_detraccion', store=False)
```
Visible en formulario de factura cuando `tiene_detraccion = True`.

---

## 5. Campos clave en account.move (estado actual)

```python
# Trazabilidad de pagos especiales
pago_detraccion = fields.Many2one('account.payment', 'Pago de Detracción', copy=False)
pago_retencion  = fields.Many2one('account.payment', 'Pago de Retención',  copy=False)
asiento_det_ret = fields.Many2one('account.move', 'Asiento retención/detracción')

# Tipo de cambio
transaction_number = fields.Char(related='origin_payment_id.transaction_number', store=True)
tipo_cambio_dolar_sistema = fields.Float(compute='_compute_tipo_cambio_sistema', store=False, digits=(16, 3))

# Apertura
es_x_apertura = fields.Boolean("Movimiento por Apertura")
fecha_apertura = fields.Date("Fecha Apertura", default=fields.Date.context_today, readonly=True)

# Glosa
glosa = fields.Char(compute='_compute_glosa_move', store=True, readonly=False)

# Detracción
fecha_vencimiento_detraccion = fields.Date(compute='_compute_fecha_vencimiento_detraccion', store=False)
```

---

## 6. Campos clave en res.company (estado actual)

```python
cuenta_detracciones          # Many2one account.account — Venta
cuenta_detracciones_compra   # Many2one account.account — Compra
cuenta_detrac_ganancias      # Many2one account.account — diferencias +
cuenta_detrac_perdidas       # Many2one account.account — diferencias -
cuenta_retenciones           # Many2one account.account — Compra (pasivo)
cuenta_retenciones_venta     # Many2one account.account — Venta (activo)
usar_fecha_vencimiento_detraccion  # Boolean
dia_vencimiento_detraccion         # Integer 1-28
```

---

## 7. Wizard account.payment.register — estado actual

### Helpers
```python
def _cuenta_detraccion_id(self):
    # out_invoice → cuenta_detracciones
    # in_invoice  → cuenta_detracciones_compra

def _cuenta_retencion_id(self):
    # out_invoice → cuenta_retenciones_venta
    # in_invoice  → cuenta_retenciones
```

### Campos adicionales
```python
es_detraccion_retencion  # Boolean — activa el flujo especial
tipo                     # Selection: normal / detraccion / retencion
communication            # Char — computed desde facturas (override)
transaction_number       # Char — requerido si es_detraccion_retencion
mostrar_check            # Boolean computed — controla visibilidad del flujo
autodetraccion           # Boolean — para autodetracción
monto_autodetraccion     # Monetary
```

### Flujo _create_payments
1. Tipo `detraccion` → cuenta destino = `cuenta_det_id` según `move_type`
2. Tipo `retencion` → cuenta destino = `cuenta_ret_id` según `move_type`
3. Tipo `normal` → flujo estándar Odoo, excluye lotes de cuenta de detracción
4. Al confirmar: `factura.pago_detraccion = pago` o `factura.pago_retencion = pago`
5. Búsqueda de factura por `pago.memo` (en v19 `ref` → `memo`)

---

## 8. Tema pendiente: Asiento de apertura (mejora por hacer)

### Estado actual
El asiento de apertura funciona con:
- `es_x_apertura = True` → usa `fecha_apertura` como fecha contable (`date`)
- En `tipo_cambio_sunat.py`: `_compute_fecha_tipo_cambio` aplica `invoice_date` para `out_invoice + es_x_apertura`
- El campo `fecha_apertura` es `readonly=True` (solo se puede editar en borrador por el `states={'draft': [('readonly', False)]}` en `invoice_date`)

### Posibles mejoras a explorar en próximo chat
1. **¿`fecha_apertura` debería ser editable siempre en borrador?** Actualmente `readonly=True` puede impedir cambiarlo si ya se abrió el formulario.
2. **Asiento de apertura automático:** ¿generar el asiento de apertura desde el cierre de ejercicio? ¿o seguir siendo manual?
3. **Validación de fecha:** Verificar que `fecha_apertura` corresponda al primer día del ejercicio o primer día hábil.
4. **Wizard de apertura:** ¿conviene un wizard dedicado para configurar saldos iniciales en lote?
5. **Integración con fiscal year lock:** Asegurar que el asiento de apertura no quede bloqueado por el cierre del período anterior.
6. **Numeración:** El asiento de apertura suele llevar una secuencia propia (ej. "APER/2025/001"). ¿Agregar soporte para journal dedicado de apertura?

---

## 9. Pendientes futuros (no iniciados)

| Item | Prioridad | Notas |
|---|---|---|
| Validación mutua exclusión detracción-retención | Media | Normativamente no pueden coexistir |
| Umbral S/700 para retención | Media | No aplicar retención si total ≤ S/700 |
| Retención en pagos parciales | Baja | 3% sobre cada pago parcial |
| Tasa de retención configurable | Baja | Actualmente hardcodeada en solse_pe_cpe |
| Exportación FV-626 | Baja | En módulo separado (fuera de accountant) |
| Comprobante de retención XML | Baja | En solse_pe_cpe, no en este módulo |

---

## 10. Notas de desarrollo importantes

- **No usar `write()` dentro de `@api.depends` compute** — causa recursión. Usar `readonly=False` + `store=True` en el campo para permitir edición manual conservando el valor.
- **frozendict con `account_id`** — solo agregar en líneas de cuentas especiales, no en todas las `payment_term` lines. El term_key nativo de Odoo 19 no lo incluye.
- **`_compute_terms()` en Odoo 19** requiere el parámetro `cash_rounding=invoice.invoice_cash_rounding_id`.
- **`pago.memo`** en lugar de `pago.ref` para buscar facturas desde el pago en Odoo 19.
- **`account.payment` states en v19**: el estado `posted` pasó a `in_process`. Revisar cualquier filtro `('state', '=', 'posted')` en pagos.
- **Autodetracción** no soporta `group_payment = True` (lanza UserError explícito).
- El módulo solse_pe_cpe provee: `tiene_detraccion`, `monto_detraccion`, `monto_detraccion_base`, `tiene_retencion`, `monto_retencion`, `monto_retencion_base`, `monto_neto_pagar`, `monto_neto_pagar_base`.
