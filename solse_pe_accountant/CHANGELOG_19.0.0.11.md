# Changelog v19.0.0.11

## Limpieza de logs de diagnóstico + 4 mejoras técnicas

### A. Limpieza de logs

Eliminados **todos** los `_logging.info("[SOLSE-ACCT]...)` sembrados entre
v19.0.0.7 y v19.0.0.10 para depurar el bug "asiento no balanceado". El bug
está validado y resuelto, los logs ya no aportan información útil y sí
consumen I/O en producción (especialmente en cargas masivas).

| Hook | Logs eliminados |
|---|---|
| `_compute_term_key` | Rama PT y NO-PT |
| `_compute_account_id` | ENTRA, TERM-LINE, SET |
| `_compute_needed_terms` | Cabecera, NEEDED, FISICAS |
| `_post` | PRE, PRE-LINEA, PRE-SUMA |
| `_get_unbalanced_moves` | Método completo eliminado (era 100% diagnóstico) |

También se removieron las declaraciones `_logging = logging.getLogger(...)`
y los `import logging` no usados en `account_move.py`,
`tipo_cambio_sunat.py` y `res_config_settings.py`.

### B. Pendientes técnicos resueltos

#### 1. `_compute_group_payment` en wizard de pagos

El override original tenía `return False` dentro del `for wizard in self:`,
lo que dejaba `wizard.group_payment` como missing cached en lugar de
asignar Boolean. **Eliminado el override completo.** El nativo
(`account_payment_register.py:478`) hace el cálculo correctamente y no hay
razón en el módulo para sobrescribirlo.

#### 2. `cuenta_detraccion` (singular) en wizard — **REVISADO: no era bug**

Verificado contra `solse_pe_edi/models/res_company.py:10`: el campo
`cuenta_detraccion` (singular, sin "s") **sí existe** en `solse_pe_edi` y
es un `Many2one('account.journal')` distinto de los `cuenta_detracciones` /
`cuenta_detracciones_compra` (`Many2one('account.account')`) que define
`solse_pe_accountant`. El wizard usa el diario bancario para registrar
pagos de autodetracción, lo cual es correcto. **Falso positivo del análisis
anterior, no se aplica cambio.**

#### 3. Import de `_` (traducción) en `account_move.py`

Agregado `_` al import: `from odoo import models, fields, api, _`. Línea 43
ya usaba `_("...")` en un `raise ValidationError`, que iba a explotar con
`NameError` si se disparara la validación.

#### 4. Rama `is_draft` en `_compute_needed_terms`

Portada desde el nativo Odoo 19 (`account_move.py:1382-1402`). En registros
con `NewId` (durante onchange en formulario), `invoice.amount_tax` y
`invoice.amount_untaxed` pueden no reflejar los cambios pendientes. La rama
`is_draft` recalcula desde `_get_rounded_base_and_tax_lines` +
`_prepare_tax_lines` para tener montos coherentes.

También se añadió `with_context(bin_size=False)` al for principal (igual al
nativo) para que los campos `binary` no estén recortados durante el cálculo.

**Impacto esperado:** facturas con `invoice_payment_term_id` complejos
(múltiples cuotas, descuentos por pronto pago) durante onchange en la UI
ahora calculan las cuotas correctamente. Sin esta rama, en algunos
escenarios el total propuesto en la UI podría diferir del que finalmente
se guarda.

#### 5. Refactor de `_recompute_cash_rounding_lines`

Antes: copia textual del nativo Odoo 19 con un solo cambio funcional
(usar `fecha_tipo_cambio` en lugar de `self.date` en `_convert`). Riesgo
de divergencia silenciosa al actualizar Odoo.

Después: el método ahora **delega al super** en los dos casos donde la
divergencia no aplica:

  - Moneda del documento = moneda de la empresa (PEN→PEN): no hay
    conversión, super funciona idéntico.
  - `move_type` no en `INCLUIDOS` (no es factura ni nota de crédito):
    `fecha_tipo_cambio == self.date`, super funciona idéntico.

Solo se ejecuta el bloque custom cuando la factura está en moneda
extranjera Y es un documento incluido. La superficie de divergencia con
el nativo se redujo al mínimo y los demás flujos siempre usan el código
nativo más actualizado.

### Resultado neto

- **`account_move.py`**: ~125 líneas menos (logs eliminados).
- **`tipo_cambio_sunat.py`**: 2 líneas menos (logger) + early return en
  `_recompute_cash_rounding_lines` que delega al super en el 95% de casos.
- **`res_config_settings.py`**: 2 líneas menos.
- **`wizard/account_payment_register_min.py`**: 5 líneas menos.

Sin cambios de comportamiento esperados en flujos ya funcionando. Los
cambios 1, 3, 4 cierran riesgos latentes; el 5 reduce mantenimiento futuro.
