# nuage_libros_electronicos_pe

Libros electrónicos PLE de SUNAT que `solse_pe_ple_pro` no trae. Se instala
**encima** de `solse_pe_ple_pro` y reutiliza sus campos y helpers.

**Versión:** 19.0.1.0.0 · **Estado:** Libro 1 listo para probar en *develop*.

| Libro | Estructuras | Estado |
|---|---|---|
| 1 — Caja y Bancos | 1.1 (010100) efectivo · 1.2 (010200) cuenta corriente | Hecho |
| 3 — Inventarios y Balances | 3.x | Pendiente |
| 12 / 13 — Inventario permanente | 12.1 (unidades) · 13.1 (valorizado) | Pendiente |
| Accionarial | 3.16.2 | Pendiente |

## Libro 1 — Caja y Bancos

Menú: **SUNAT → Libros electrónicos (PLE) → Estructura 01 - Libro Caja y Bancos**.
Se crea un registro por mes, **Generar Estructuras**, y se descargan los TXT y
Excel de 1.1 y 1.2. Si un mes no tiene movimientos de efectivo (o de banco), esa
estructura no se genera.

Qué entra en cada estructura (por las marcas de la cuenta contable que ya pone
`solse_pe_ple_pro`: 101–103 = efectivo, 104 = banco):

- **1.1** — líneas de cuentas marcadas *Es cuenta contable de efectivo*.
- **1.2** — líneas de cuentas marcadas *Es cuenta contable de banco*.

El CUO y el correlativo son los **mismos del Libro Diario y del Libro Mayor**
(SUNAT exige que el CUO del 1.2 coincida con el del Diario).

### Datos que deben estar configurados (1.2)

| Dato | Dónde | Si falta |
|---|---|---|
| Número de la cuenta bancaria | Diario de banco → *Número de cuenta* | **Bloquea** la generación y lista los diarios |
| Código SUNAT del banco (Tabla 3) | Bancos → *Banco* (`l10n_pe_bank_code`) | Se informa `99` (otros) y queda un aviso en el log |
| Medio de pago (Tabla 1) | En el pago (`l10n_pe_payment_method_code`) | Se informa `999` (otros) |
| Documento del girador/beneficiario | Contacto → tipo y número de documento | Se informa `-` / `-` / `varios` |
| N.º de transacción | Asiento o pago (`transaction_number`) | Se usa el nombre del asiento (últimos 20 caracteres) |

La cuenta bancaria se toma del **diario dueño de la cuenta contable**
(`default_account_id`), no del diario del asiento: un ajuste hecho en un diario
varios sobre la 104 sigue siendo del mismo banco.

### Reglas de formato aplicadas

Todas salen de la hoja oficial «1 Libro Caja y Bancos» y de «Reglas Generales»:

- Nombre `LE` + RUC + `AAAA` + `MM` + `00` + `010100`/`010200` + `00` + `1111`
  (`0` en el indicador de contenido si no hay datos).
- 1.1 con 19 campos, 1.2 con 15 campos, cada línea termina en `|`.
- **Una fila por llave única de SUNAT** — 1.1: (C1, C2, C3, C4, C10); 1.2:
  (C1, C2, C3, C4, C5). Las líneas que repiten la llave se **suman en neto**
  (debe − haber) y se vuelven a partir en debe/haber, porque esos campos son
  excluyentes. El movimiento neto del asiento no cambia.
- En 1.2, una fila con neto 0.00 se descarta (C13 y C14 no pueden ser ambos 0.00).
- Si dos líneas fusionadas en 1.2 tienen girador distinto → operación múltiple:
  documento `-` y razón social `varios`.
- Documento del girador validado con las reglas de tipo y longitud, y módulo 11
  para el RUC; si no cumple se informa `-`.
- Texto libre sin `|`, `/`, `\`; los números (C10 en 1.1, C12 en 1.2) cambian
  `/` por `-` (`BNK1/2026/00012` → `BNK1-2026-00012`).
- TXT en cp1252, igual que el resto de libros de `solse_pe_ple_pro`.

### Decisiones y puntos abiertos

- **Importes en soles** y moneda `1` en el nombre del archivo. En 1.1 el campo 7
  lleva la moneda de origen de la línea.
- **Dato estructurado (C18 de 1.1) vacío**, igual que en el 5.1 (ver
  `_dato_estructurado` en `solse_pe_ple_pro`).
- **Por validar con el PLE de SUNAT:** la observación del campo 16/17 de 1.1 dice
  que la suma del debe por CUO debe igualar la del haber. El libro 1.1 solo lleva
  las líneas de efectivo, así que por asiento no cuadra. Falta confirmar con el
  validador real si lo acepta o lo observa.
- No bloquea si la empresa está marcada como *eximida de presentar Caja y
  Bancos*: el libro se puede generar igual.

## Pruebas

La capa de formato (`models/ple_01_format.py`) son funciones puras y se prueba
sin Odoo:

```
python3 -m unittest discover -s nuage_libros_electronicos_pe/tests -v
```

El modelo (`models/ple_report_01.py`) hay que probarlo instalado, en *develop*,
con un mes que tenga cobros en efectivo y pagos bancarios.
