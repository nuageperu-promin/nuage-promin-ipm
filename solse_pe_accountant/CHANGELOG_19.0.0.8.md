# Changelog v19.0.0.8

## Iteración de logs diagnósticos

Esta versión NO trae cambio de lógica respecto a v19.0.0.7. Solo agrega logs
adicionales para diagnosticar por qué `_check_balanced` rechaza la factura
con detracción antes de llegar a `_post`.

### Hallazgo de v19.0.0.7

Los logs de v19.0.0.7 mostraron que:

- `_compute_needed_terms` arma correctamente el dict: 2 entradas (NETO=1770,
  SPOT=212 con `account_id=46`), suma 1982 = `amount_total`.
- `_compute_account_id` se ejecuta dos veces pero solo procesa una línea
  NewId (la NETO recibe `account_id=47` receivable). La SPOT no aparece en
  los logs porque o no se materializó, o ya estaba con `account_id=46` y mi
  filtro la excluyó (que es el comportamiento esperado).
- NO hay logs de `_compute_term_key`, NI logs de `_post`. El error sale antes.

### Por qué hace falta esta iteración

`_check_balanced` (nativo, `account_move.py:2749`) corre en cada `create`
y `write`, no solo en `_post`. Hace una query SQL directa
`SUM(debit) vs SUM(credit) GROUP BY move_id`. Si esa diferencia es != 0, lanza
`UserError("The entry is not balanced.")` — que en español es exactamente el
mensaje "El asiento no está balanceado." que estamos viendo.

Es decir, el descuadre se está midiendo sobre **líneas físicas en BD**, no
sobre `needed_terms`. Necesitamos ver qué líneas hay físicamente cuando el
check falla. Para eso, esta versión introduce:

### Logs agregados

| Hook nuevo o ampliado | Qué imprime |
|---|---|
| `_get_unbalanced_moves` (override nuevo, llama super) | Foto exacta de las líneas físicas con `debit/credit/balance/account_id/display_type` justo cuando el check_balanced las evalúa |
| `_compute_term_key` rama `else` (`NO-PT`) | Cada línea no-payment_term que pasa por el compute |
| `_compute_account_id` ENTRA + TERM-LINE | `len()` en lugar de `.ids` para detectar NewId; dump por término de su `display_type`, `account_id` y si está en el filtro |
| `_compute_needed_terms` `FISICAS` | Al final del compute, dump de `invoice.line_ids` reales (no solo el dict abstracto) |

### Cómo leer el log nuevo

Buscar `_get_unbalanced_moves][LINEA`. Esas líneas son la fuente de verdad
sobre lo que el SQL del check ve. Si ahí no aparece una línea con
`account_id=46` (cuenta_detracciones) y débito 212, la SPOT no se materializó
y el bug es del flujo de `_sync_dynamic_line`.

```bash
grep "SOLSE-ACCT" /tmp/post_fac06.log | grep -E "FISICAS|LINEA|MOVE|CHECK"
```
