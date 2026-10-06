# Changelog - solse_pe_accountant

Historial de cambios entre la versión `19.0.0.2` (base) y `19.0.0.12`.

Para detalle por versión, ver los archivos `CHANGELOG_19.0.0.X.md`
correspondientes.

---

## Resumen por área

### 1. Fix crítico: "El asiento no está balanceado" en facturas con detracción

Tres causas raíz corregidas:

- **`_compute_account_id`** (v19.0.0.7) sobreescribía la cuenta de la línea
  SPOT con la receivable del partner, desincronizando el `term_key`
  respecto del que armaba `_compute_needed_terms`.
- **`_compute_needed_terms` rama sin payment_term** (v19.0.0.9): el `else`
  final estaba colgado del `if tiene_retencion` cuando debía ser fallback
  general. En facturas con detracción y sin retención, sobreescribía la
  línea NETO con `amount_total_signed` completo, provocando descuadre por
  exactamente `monto_detraccion`.
- **`_compute_needed_terms` rama con payment_term** (v19.0.0.11): faltaba
  la distinción `is_draft` del nativo Odoo 19, necesaria durante onchange
  con `NewId`.

### 2. Feature: detracción en facturas de proveedor (cascada A+B) [v19.0.0.10]

En Odoo 19 las facturas de proveedor habitualmente no usan producto en
líneas. La detección de detracción heredada de `solse_pe_edi` (basada en
`product.aplica_detraccion`) no disparaba. Solución:

- `res.partner.aplica_detraccion` como default por proveedor.
- `account.move.aplica_detraccion` como override manual en cabecera.
- Cascada para compras: cabecera → producto en línea → partner.
- Ventas no cambian (delega al `super()`).
- Sub-bug heredado arreglado: el `for` sobre `invoice_line_ids` no tenía
  `break` y se quedaba con el código del último producto.

### 3. Feature: diagnóstico de configuración Tabla 34 (Estados Financieros)

> **Nota de autoría**: este bloque fue desarrollado por el equipo del
> proyecto en paralelo a las iteraciones de bugfix de Claude. No salió de
> las sesiones de diagnóstico documentadas en `CHANGELOG_19.0.0.7` a
> `CHANGELOG_19.0.0.12`.

- `account.account`: campos compute `pe_t34_estado` (na / completo /
  parcial / sin_config), `pe_t34_resumen`, `pe_t34_es_hoja`.
- Vista del plan de cuentas: page nueva con badge de estado.
- Vista lista: columna con widget badge + decoraciones.
- Vista search: filtros por estado + agrupación.
- Wizard `diagnostico_tabla34` con vista y permisos.

### 4. Limpieza y mantenimiento

#### Código muerto eliminado (v19.0.0.7)

- `models/account_payment_term.py` completo (143 líneas): 4 métodos
  huérfanos que además no compilaban (variables fuera de scope).
- `AccountMove.obtener_totales_linea_detraccion`: la única referencia
  estaba en el archivo de arriba.
- Docstring inerte de `_compute_partner_credit_warning` en
  `tipo_cambio_sunat.py` (indentación rota).

#### Bugs latentes corregidos (v19.0.0.11)

- `_compute_group_payment` del wizard de pagos: tenía `return False`
  dentro del `for`, dejaba `group_payment` como missing cached. Eliminado
  el override completo (el nativo lo hace bien).
- Falta de `_` (traducción) en imports de `account_move.py`: la línea 43
  usaba `_("...")` en un `raise`, `NameError` latente.

#### Refactor (v19.0.0.11)

- `_recompute_cash_rounding_lines`: antes era copia textual del nativo
  Odoo 19 con un solo cambio funcional (`fecha_tipo_cambio` vs `self.date`).
  Ahora delega al `super()` cuando `currency == company_currency` o
  `move_type` fuera de `INCLUIDOS`. Reduce la superficie de divergencia
  con futuras versiones de Odoo.

#### Limpieza de logs (v19.0.0.11)

Eliminados todos los `_logging.info("[SOLSE-ACCT]...")` sembrados entre
v19.0.0.7 y v19.0.0.10 como diagnóstico del bug del balance. Junto con
ellos, las declaraciones `_logging = logging.getLogger(...)` y los
`import logging` no usados en `account_move.py`, `tipo_cambio_sunat.py`
y `res_config_settings.py`.

#### Hotfix (v19.0.0.12)

`super(AccountMove, self)` → `super(AccountMoveSunat, self)` en
`tipo_cambio_sunat.py`. La clase en ese archivo no se llama `AccountMove`.

---

## Pendientes detectados durante el proceso (no aplicados)

1. **Migrar `super(Clase, self)` a `super()`** en todo el módulo. Forma
   idiomática en Python 3, evita errores como el del v19.0.0.12.
2. **Tests automatizados**: el módulo no tiene; sería un proyecto en sí
   mismo. Los casos de detracción venta/compra/draft/USD son los primeros
   candidatos.
3. **Falso positivo del análisis inicial**: el `cuenta_detraccion`
   (singular) que veía en el wizard de pagos NO era bug. Es un campo
   legítimo de `solse_pe_edi` (`Many2one('account.journal')`), distinto
   de `cuenta_detracciones`/`cuenta_detracciones_compra` que son cuentas
   contables. No se aplicó cambio.

---

## Índice de versiones

| Versión | Tema principal | Archivo |
|---|---|---|
| 19.0.0.7  | Fix `_compute_account_id` + limpieza código muerto | [CHANGELOG_19.0.0.7.md](CHANGELOG_19.0.0.7.md) |
| 19.0.0.8  | Iteración de logs diagnósticos | [CHANGELOG_19.0.0.8.md](CHANGELOG_19.0.0.8.md) |
| 19.0.0.9  | Fix definitivo balance (rama sin payment_term) | [CHANGELOG_19.0.0.9.md](CHANGELOG_19.0.0.9.md) |
| 19.0.0.10 | Cascada A+B detracción en compras | [CHANGELOG_19.0.0.10.md](CHANGELOG_19.0.0.10.md) |
| 19.0.0.11 | Limpieza logs + 4 mejoras técnicas | [CHANGELOG_19.0.0.11.md](CHANGELOG_19.0.0.11.md) |
| 19.0.0.12 | Hotfix `super(AccountMoveSunat)` | [CHANGELOG_19.0.0.12.md](CHANGELOG_19.0.0.12.md) |
