# PLE 7 — dos variantes, una fuente de verdad

## Por qué hay dos módulos

Odoo **no admite `depends` alternativos**: un módulo depende de A o de B, no
de «A o B».

Y `solse_pe_activo_fijo` (Community) y `account_asset` (Enterprise) declaran
**el mismo modelo**, `account.asset`. Instalados juntos, Odoo **fusiona** las
dos definiciones: seis métodos coinciden en nombre
(`compute_depreciation_board`, `validate`, `set_to_draft`, `pause`, `resume`,
`set_to_close`) y el `Selection` de `method` se reemplaza entero por el del
módulo que cargue después.

Por eso el libro 7 existe en dos variantes:

| Módulo | Edición | Depende de |
|---|---|---|
| `solse_pe_ple_07` | **Community** | `solse_pe_activo_fijo` |
| `solse_pe_ple_07_ee` | **Enterprise** | `account_asset` |

## La duplicación es de dos líneas

Las 473 LOC del generador, los 141 de campos peruanos, las vistas del reporte
y la seguridad son **idénticos byte a byte**. Solo difieren:

| Archivo | Community | Enterprise |
|---|---|---|
| `__manifest__.py` | `'solse_pe_activo_fijo'` | `'account_asset'` |
| `views/account_asset_views.xml` | `ref="solse_pe_activo_fijo.view_activo_fijo_form"` | `ref="account_asset.view_account_asset_form"` |
| `reports/formato_7_1.xml` | `solse_pe_ple_07.formato_7_1_documento` | `solse_pe_ple_07_ee.formato_7_1_documento` |
| `reports/formato_7_3_7_4.xml` | `solse_pe_ple_07.formato_7_…` (report_name y t-call) | `solse_pe_ple_07_ee.formato_7_…` |
| `reports/formato_7_2.xml` | ídem | ídem |

El tercero existe desde 19.0.1.1.0: el `report_name` de un
`ir.actions.report` lleva el nombre técnico del módulo y no admite xmlid
relativo. El botón del formulario sí usa `%(action_reporte_formato_7_1)d`,
relativo, y funciona igual en las dos.

Esto es posible porque `ple_report_07.py` **no hereda** `account.asset`: lo
resuelve en tiempo de ejecución con `self.env['account.asset'].search(...)`
(línea 115). Y los 24 campos peruanos solo usan `original_move_line_ids`, que
existe igual en las dos ediciones.

## La fuente de verdad es `solse_pe_ple_07`

**La variante Enterprise se regenera; no se edita.**

```bash
python3 sincronizar_ple07.py              # regenera solse_pe_ple_07_ee
python3 sincronizar_ple07.py --verificar  # comprueba que no divergieron
```

`--verificar` falla si alguien tocó la variante Enterprise a mano, nombrando
el archivo. **Añádalo al protocolo previo al empaquetado**, junto a
`validar_modulo.py`: es el único punto donde estas dos copias pueden
divergir en silencio.

## Qué instalar en cada caso

**Odoo 19 Community**
```
solse_pe_activo_fijo     19.0.2.2.1
solse_pe_ple_07          19.0.1.4.0
```

**Odoo 19 Enterprise**
```
account_asset            (nativo)
solse_pe_ple_07_ee       19.0.1.4.1
```
**No instale `solse_pe_activo_fijo` en Enterprise.**

## ⚠ Y una tercera incompatibilidad

`base_accounting_kit` declara `account.asset.asset` — **no colisiona** con
`account.asset`, así que Odoo instala ambos sin quejarse, pero quedan dos
sistemas de activos fijos conviviendo y **el libro 7 solo lee uno**.

Ver `20-contabilidad/aviso-dos-sistemas-activos.md` de la biblia.

## 19.0.1.1.0 (L8.1) — el formato físico 7.1 y el TXT en ANSI

* **PDF del formato 7.1** (`models/formato_7_1.py`,
  `reports/formato_7_1.xml`, botón «PDF Formato 7.1» en el libro). Sigue la
  plantilla oficial de la R.S. 234-2006 (`234_formato71.xls`): 26 columnas,
  cabecera de período/RUC/razón social y fila de totales. **No es el TXT
  maquetado**: omite periodo, CUO, correlativo, catálogos, tipo y estado,
  las revaluaciones (son del formato 7.2) y el estado de la operación, y
  añade cuatro columnas derivadas (valor histórico y ajustado al 31.12,
  depreciación acumulada histórica y ajustada). Las fórmulas y su porqué
  están en la cabecera de `formato_7_1.py`, con un ⚠ sobre las bajas.
* **TXT en cp1252** con `_codificar_txt` de ple_pro, como el resto de
  libros. Con `latin-1` + `errors='replace'` los caracteres tipográficos
  salían como «?».
* `generate_report` ya no llama dos veces a `update_report`.
* Manifest: la descripción ya no dice «requiere Enterprise» en la variante
  Community.

## 19.0.1.1.1 (L8.1, AF7-02) — la moneda extranjera del 7.3 ya se puede informar

`moneda_adquisicion_id` y `valor_adquisicion_me` eran compute **readonly**
(el defecto de un compute sin inverse, `odoo/orm/fields.py:451` en 19.0), y
`create()` solo protege de la recomputación a los compute editables
(`odoo/orm/models.py:4691`). Resultado: lo que se pasaba al crear se
recalculaba desde `original_move_line_ids`; un activo **sin asiento de
origen** (importado, de apertura, migrado) quedaba con los dos campos vacíos
y **nunca entraba al 7.3**, y en el formulario tampoco se podían escribir.
Lo destapó el caso PLE-PDF (7.3 detalle: 0 de 2 filas).

Ahora son `readonly=False`: con apuntes de origen, ellos mandan; sin ellos,
el cálculo conserva lo informado a mano.

⚠ Los activos ya creados con los campos vacíos no se recuperan con `-u`:
hay que informarlos (en el laboratorio: Limpiar + resembrar, el limpiador
borra los activos).

## 19.0.1.2.0 (L9, B-9) — cómo presenta el físico 7.1 una baja

La norma no da fórmulas para las columnas derivadas; lo oficial es que C18,
C19 y C29-C32 admiten positivo o negativo (suma algebraica). Parámetro del
sistema `solse_pe_ple_07.dep_historica_bajas` (`data/parametros.xml`,
noupdate):

| Modo | Fila de un bien dado de baja en el ejercicio |
|---|---|
| `descontar` (**defecto**) | retiros −C18; dep. del ejercicio C30+C31; dep. de retiros −(C29+C31) ⇒ valor 0 y depreciación 0: la baja retira costo y acumulada (NIC 16 párr. 67-72), y los totales cuadran con la 33 y la 39 |
| `acumular` | la lectura literal de 19.0.1.1.0: el bien conserva su depreciación |

Los retiros se imprimen ahora en negativo en los dos modos (suma
algebraica visible). El TXT no cambia. El pie del PDF dice qué modo se usó.

## 19.0.1.2.1 (L9.1, B-10) — la baja no es depreciación

Desde `solse_pe_activo_fijo 19.0.2.2.0` la baja se contabiliza (D 39 / D
6551 / H 33). En Community ese asiento vive en `asiento_baja_id` y no entra
al cuadro de depreciación. En Enterprise el nativo sí enlaza la venta o la
baja al activo (`asset_move_type`); `_depreciacion_periodo` las excluye para
que su cargo a la 39 no reste la acumulada de la depreciación del ejercicio.
Guardia defensiva: no verificada contra el código EE.

## 19.0.1.3.0 — formatos físicos 7.3 y 7.4

Desde la plantilla oficial (`234_formato71.xls`, hojas «F 7.3» y «F 7.4»),
leyendo el TXT que se declara (`models/formato_7_3_7_4.py`,
`reports/formato_7_3_7_4.xml`, botones en el libro, paperformat del 7.1).

* **7.3** (12 columnas): lo del TXT (C05-C14) más dos derivadas —valor en
  M.N. al 31.12 = C09 + C11, y depreciación acumulada histórica—. La
  acumulada anterior no está en el 7.3: se toma del **C29 del 7.1** del
  mismo activo (cruce por código) y se aplica el mismo parámetro B-9 que en
  el 7.1. Totales solo en M.N. (sumar M.E. distintas o tipos de cambio no
  significa nada).
* **7.4** (5 columnas): contrato, número, inicio, cuotas y monto, con TOTAL.

## 19.0.1.3.1 (L9.4) — tildes en los PDF y descripción completa

* **Mojibake en los tres físicos** (vista por Gabriel en los PDF de 2025:
  «CÃ“DIGO», «virtualizaciÃ³n», «LÃNEA»). `ir.actions.report._prepare_html`
  (19.0) solo envuelve en el layout con `<meta charset="utf-8">` los nodos
  `div.article`; sin él pasa el cuerpo tal cual y wkhtmltopdf lo lee en
  latin-1. Cada documento va ahora en `div.article` (lo que hace
  `web.basic_layout`, sin anidar otro `html_container`).
* **7.1**: la descripción sale del nombre del activo (cruce por código),
  no del C11 del TXT, que la norma del PLE corta a 40 caracteres.

## 19.0.1.4.0 — formato físico 7.2: el libro 7 completo

* **7.2** («activos fijos revaluados», 32 columnas de la plantilla oficial
  `F 7.2 Det bs AF Revaluad`): sale del TXT 7.1 (no tiene TXT propio en el
  PLE), solo con los activos que tienen revaluación vigente. Las columnas
  comunes con el 7.1 se calculan con el mismo `_columnas_fisico` (retiros
  en negativo, B-9) y se les suman las revaluaciones (C20-C22) al valor y
  su depreciación (C33-C35) a la acumulada histórica.
* **`fecha_revaluacion`** en el activo: los importes de revaluación son
  acumulados al 31.12 (decisión de Gabriel, 2026-09-20) y solo rigen en
  los ejercicios que cierran desde esa fecha. Vacía = siempre (como antes).
