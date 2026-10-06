# Changelog v19.0.0.9

## Fix definitivo del bug "El asiento no está balanceado"

### Causa raíz identificada

Los logs de v19.0.0.8 mostraron la verdad:

```
[NEEDED]   key={...date_mat:2026-05-13...} | balance=1770.0
[NEEDED]   key={...date_mat:2026-06-05, account_id:46} | balance=212.0

[LINEA] product | cuenta=7012100 | C=1500
[LINEA] tax     | cuenta=4011100 | C=270
[LINEA] PT      | cuenta=1213000(47) | D=1770
[LINEA] PT      | cuenta=1212000(46) | D=212

ΣD=1982 | ΣC=1770 | Δ=+212
```

La línea SPOT estaba bien creada. La que estaba mal era la línea NETO, que
tenía balance 1770 cuando debía tener 1558 (1770 − 212).

### El bug exacto

En `_compute_needed_terms`, rama "sin `invoice_payment_term_id`", la estructura
de `if/else` estaba malformada:

```python
if invoice.tiene_detraccion:
    # ...
    invoice.needed_terms[key_neto] = {'balance': untaxed_amount - monto_det, ...}
    invoice.needed_terms[key_spot] = {'balance': monto_det, ...}

if invoice.tiene_retencion:
    # ...
    invoice.needed_terms[key_retencion] = {...}

else:                          # ← ESTE else estaba colgado de tiene_retencion
    invoice.needed_terms[key_neto] = {'balance': amount_total_signed, ...}  # 1770
```

El `else` final, intentado como fallback general "si no hay det ni ret, una
sola línea con el total", quedó atado al `if tiene_retencion`. Resultado:
para una factura con detracción y sin retención (FAC-06), después de meter
correctamente la línea NETO con 1558 y la SPOT con 212, **el `else` se
ejecutaba** porque `tiene_retencion` era False, y sobrescribía la línea NETO
con el `amount_total_signed` completo (1770).

Como Python dicts mantienen la entrada al re-asignar con la misma key, la
línea NETO terminaba con balance 1770 en lugar de 1558. La SPOT seguía ahí
con 212 → ΣD = 1770 + 212 = 1982 ≠ ΣC = 1770 → descuadre +212 = monto SPOT.

### Solución aplicada

Refactor de la rama "sin payment_term" en `_compute_needed_terms` con
estructura plana, sin anidamientos engañosos:

```python
# 1) calcular descuento base
untaxed_amount = invoice.amount_total_signed
if invoice.tiene_detraccion:
    untaxed_amount -= monto_detraccion
if invoice.tiene_retencion:
    untaxed_amount -= monto_retencion

# 2) si hay det o ret, meter la línea NETO (con el saldo descontado)
if invoice.tiene_detraccion or invoice.tiene_retencion:
    invoice.needed_terms[key_neto] = {'balance': untaxed_amount, ...}

# 3) meter línea SPOT si aplica
if invoice.tiene_detraccion:
    invoice.needed_terms[key_spot] = {...}

# 4) meter línea retención si aplica
if invoice.tiene_retencion:
    invoice.needed_terms[key_retencion] = {...}

# 5) fallback: ni det ni ret → una sola línea con el total
if not invoice.tiene_detraccion and not invoice.tiene_retencion:
    invoice.needed_terms[key_total] = {'balance': amount_total_signed, ...}
```

Bonus: en la versión anterior, las facturas que tuvieran AMBOS detracción
y retención simultáneamente también fallaban (la línea NETO se mete dentro
del bloque `if tiene_detraccion:` calculada como `total - monto_det`, sin
restar también la retención). Ahora ese caso queda correcto porque ambas
restas se aplican antes de meter la línea NETO.

### Pendientes que NO se aplicaron (siguen vigentes desde v19.0.0.7)

1. `_compute_group_payment` con `return False` dentro del for en el wizard.
2. `factura.company_id.cuenta_detraccion` (singular, inexistente) en wizard.
3. Falta `from odoo import _` en `account_move.py`.
4. La rama `is_draft` faltante en `_compute_needed_terms` (rama con
   payment_term).
5. Refactor de `_recompute_cash_rounding_lines` a override puntual.

### Logs

Los logs `[SOLSE-ACCT]` siguen activos. Una vez confirmado que FAC-06 postea
sin error, en la próxima iteración los retiramos o los convertimos en
`_logger.debug` para que no aparezcan en producción.
