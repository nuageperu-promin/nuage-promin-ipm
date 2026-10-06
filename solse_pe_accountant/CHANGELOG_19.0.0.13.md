# CHANGELOG v19.0.0.13

## Fix: cuenta de inventario no se aplicaba en facturas de compra (anglo-saxon)

### Problema

En bases con `stock_account` instalado (Community o Enterprise) y productos
almacenables con `valuation = 'real_time'`, las facturas de compra generadas
con el módulo `solse_pe_accountant` instalado usaban la cuenta **expense** del
producto en lugar de la cuenta de **inventario / stock_valuation** que asigna
Odoo nativo para anglo-saxon accounting.

Al desinstalar `solse_pe_accountant`, el comportamiento volvía a ser correcto.

### Causa raíz

El método `AccountMoveLine._compute_account_id` en `models/account_move.py`
era una **copia casi exacta** del método nativo de Odoo 19 sobreescribiéndolo
**sin llamar a `super()`**. Esto rompía la cadena de herencia y anulaba la
extensión que hace `stock_account/models/account_move_line.py`:

```python
# stock_account – Odoo 19 nativo
def _compute_account_id(self):
    super()._compute_account_id()
    for line in self:
        if not line.move_id.is_purchase_document():
            continue
        if not line._eligible_for_stock_account():
            continue
        ...
        if line.product_id.valuation == 'real_time' and accounts['stock_valuation']:
            line.account_id = accounts['stock_valuation']
```

Como el override no encadenaba con `super()`, esa reasignación jamás se
ejecutaba y la línea quedaba en `expense`.

### Solución

Refactor de `_compute_account_id` en tres bloques:

1. **`term_lines` (lógica custom)**: se mantiene el fix v19.0.0.7 que protege
   las líneas de detracción / retención del recompute, evitando el desbalance
   del asiento.
2. **Resto de líneas (`product_lines` + fallback)**: se delega al
   `super()._compute_account_id()` pasando `self - term_lines`. Esto permite
   que `stock_account` (y cualquier otro módulo que extienda el compute
   nativo) aplique su lógica normalmente.
3. **Fallback final para `term_lines`**: se replica el fallback nativo solo
   sobre las term_lines, ya que el super() del paso 2 solo lo aplica al
   subset que recibe.

### Compatibilidad

- **No introduce dependencia con módulos Enterprise**. La asignación de la
  cuenta de inventario vive en `stock_account`, que es Community.
- En bases sin `stock_account`: comportamiento idéntico al anterior.
- En bases con `stock_account` y productos con valoración en tiempo real:
  ahora la línea de compra usa la cuenta de inventario configurada en la
  categoría del producto.

### Archivos modificados

- `models/account_move.py` – refactor de `AccountMoveLine._compute_account_id`
- `__manifest__.py` – versión `19.0.0.12` → `19.0.0.13`
