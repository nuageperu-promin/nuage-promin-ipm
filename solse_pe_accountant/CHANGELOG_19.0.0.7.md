# Changelog v19.0.0.7

## Limpieza de código muerto

| Eliminado | Razón |
|---|---|
| `models/account_payment_term.py` completo (143 líneas) | 4 métodos huérfanos sin invocadores externos; además no compilaban (variables `company_currency`, `total_amount`, `tax_amount_left`, `total_balance` sin definir) |
| `AccountMove.obtener_totales_linea_detraccion` | Zombie: única referencia estaba dentro del archivo anterior |
| Docstring de `_compute_partner_credit_warning` en `tipo_cambio_sunat.py` | Bloque inerte con indentación rota |

## Fix del bug "asiento no balanceado" en facturas con detracción

### Diagnóstico

El override de `_compute_account_id` (`models/account_move.py`) tenía dos defectos heredados:

1. Pasaba `current_ids = term_lines_filtro.ids` al SQL `previous` en lugar de
   `term_lines.ids` (que es lo que hace el nativo). Eso permitía que la propia
   línea SPOT figurara como "previous" para sí misma → la query devolvía
   `cuenta_detracciones` como cuenta candidata.
2. Iteraba sobre **todas** las term_lines (`for line in term_lines`) y, cuando
   detectaba que el `account_id` calculado era una cuenta especial, lo rebotaba
   a la cuenta receivable del partner. Resultado: la línea SPOT terminaba con
   cuenta de Clientes en lugar de cuenta de detracción.

Como `_compute_term_key` decide si incluir `account_id` en el key consultando
`line.account_id.id in [cuenta_det_id, cuenta_det_compra_id]`, una vez que la
cuenta cambiaba a receivable, el key quedaba sin `account_id`, mientras que
`_compute_needed_terms` había metido en `invoice.needed_terms` la entrada con
key CON `account_id`. La desincronización entre `inv_existing_after` y
`needed_after` en `_sync_dynamic_line` (`account.move._sync_dynamic_line`,
account_move.py:3551 del nativo v19) produce el desbalance.

### Solución aplicada

En `_compute_account_id`:
- `current_ids = term_lines.ids` (igual al nativo).
- `for line in term_lines_filtro` (no iteramos las líneas con cuenta especial).
- Eliminado el bloque de rebote `if cuentas_especiales and account_id in cuentas_especiales`.

Comportamiento esperado: la línea SPOT/retención conserva la cuenta que le
asignó `_compute_needed_terms` y `_compute_term_key` arma el key consistente
con la key que está en `needed_terms`.

## Logs sembrados para verificación

Todos con prefijo `[SOLSE-ACCT]` para grep rápido en `odoo.log`. Niveles `INFO`.

| Hook | Qué imprime |
|---|---|
| `_compute_term_key` | Por cada línea: `account_id`, flag `es_det`, dict `key` final |
| `_compute_account_id` | Resumen al iniciar (ids procesados, ids excluidos) + transición de `account_id` por línea |
| `_compute_needed_terms` | Resumen del move + dump completo de las entradas del dict `needed_terms` con sus balances |
| `_post` | Dump previo de líneas (cuenta, débito, crédito, balance, key, due) + ΣDébito ΣCrédito Δ |

Para correrlo:
```bash
./odoo-bin -c odoo.conf -u solse_pe_accountant --log-level=info 2>&1 | tee /tmp/post_fac06.log
grep "SOLSE-ACCT" /tmp/post_fac06.log
```

## Pendientes detectados (no aplicados aún)

Para una segunda iteración una vez que este fix se valide:

1. **`_compute_group_payment`** (`wizard/account_payment_register_min.py:59-61`):
   `return False` dentro del `for wizard in self`, nunca asigna el campo.
2. **`factura.company_id.cuenta_detraccion`** (singular, no existe) usado en
   `wizard/account_payment_register_min.py:285` y `:446`. Los campos reales son
   `cuenta_detracciones` / `cuenta_detracciones_compra`. AttributeError al
   activar autodetracción.
3. **Falta `_` (traducción) en imports** de `models/account_move.py` —
   `_prevent_automatic_line_deletion` lanza `NameError` si se dispara.
4. **`_compute_needed_terms` sin distinción `is_draft`**: el nativo v19
   (account_move.py:1382) recalcula `tax_amount` / `untaxed_amount` desde
   `_get_rounded_base_and_tax_lines` cuando es draft. El override actual usa
   `invoice.amount_tax` / `invoice.amount_untaxed` que en draft pueden estar
   desactualizados. No es la causa de este bug específico, pero sí riesgo para
   facturas con `invoice_payment_term_id` no trivial.
5. **`_recompute_cash_rounding_lines`** en `tipo_cambio_sunat.py` es copia
   textual del nativo con un solo cambio funcional. Conviene refactorizar a
   un super con override puntual del cálculo de moneda en `_compute_cash_rounding`.

Estos no se tocan en v19.0.0.7 para mantener el cambio acotado al bug del
balance.
