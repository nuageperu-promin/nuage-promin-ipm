# solse_pe_plame_rxh

Genera los archivos de importación de **Prestadores de Servicios de 4ta
Categoría** al PDT Planilla Electrónica – PLAME (Formulario Virtual 0601).

- **Estructura 7** → archivo `.ps4` (maestro de prestadores)
- **Estructura 20** → archivo `.4ta` (detalle de comprobantes)

Base normativa: Anexo 3 de la R.M. N.° 121-2011-TR, modificado por la
R.S. N.° 028-2018/SUNAT. Tablas paramétricas del Anexo 2 (Tablas 3, 23 y 25).
Verificado contra el PDT PLAME versión 4.6 (R.S. N.° 000016-2026/SUNAT).

## Criterio de selección

Los comprobantes entran al periodo por **percepción**: se declara todo recibo
cuyo *pago* se produjo dentro del mes, sin importar su fecha de emisión. Un
recibo emitido en mayo y pagado en junio se declara en el periodo de junio.

Si un recibo se paga parcialmente en varios meses, cada periodo declara la
parte proporcional del importe bruto, con la fecha del último pago del mes.

## Configuración

1. **Ajustes → Contabilidad → PLAME - Recibos por Honorarios**
   - Régimen pensionario (campo 10): dejar **vacío** salvo que algún prestador
     tenga aporte pensionario retenido.
   - Rellenar número con ceros: dejar **desactivado**.

2. **Impuesto de retención de 4ta**: en el impuesto de compra que representa
   la retención del 8%, marcar *Retención de renta de 4ta categoría*. El campo 9
   del archivo se deriva de ahí.

3. **Ficha del prestador → pestaña PLAME 4ta categoría**:
   apellido paterno, apellido materno, nombres, tipo de documento (Tabla 3),
   condición de domiciliado y, para no domiciliados, el convenio (Tabla 25).
   Las constancias de suspensión se registran con su ejercicio y vigencia.

## Uso

**Contabilidad → Reportes → PLAME - Recibos por Honorarios**

*Revisar periodo* lista los comprobantes y muestra errores y advertencias sin
generar nada. *Generar archivos* produce ambos ficheros solo si no hay errores.

En el PDT se importa **primero el `.ps4`** y luego el `.4ta`, desde
*Detalle de Declaración / PS 4ta Categoría*.

## Formato de los archivos

Verificado byte a byte contra archivos reales aceptados por el PDT:

- Cada campo termina con `|`, **incluido el último de la línea**.
- Fin de línea `CRLF`, codificación ASCII, texto en mayúsculas sin tildes.
- Montos con punto decimal y **sin decimales cuando son cero** (`750`, no `750.00`).
- Número de comprobante **sin ceros a la izquierda** (`75`, no `00000075`).
- Campos 10 y 11 del `.4ta` vacíos por defecto.
- Nombre: `0601<aaaa><mm><RUC>.ps4` / `.4ta`.

## Versión 19.0 (port desde 17.0.1.1.0)

El formato de los archivos NO cambia respecto de la v17 (verificado contra
el PDT). Cambios del port:

- **Pagos sin asiento (Odoo 18+)**. Un pago cuyo método no tiene cuenta
  pendiente (*outstanding*) no genera asiento
  (`account/models/account_payment.py:997` en 19.0) y se enlaza al recibo
  por `matched_payment_ids`, no por conciliación. El criterio de percepción
  ahora los suma también (`_pagos_sin_asiento_v19`); los pagos con asiento
  se siguen leyendo por conciliación, sin contarse dos veces.
- Vistas `<tree>` → `<list>`.
- Demo: el impuesto se crea con `price_include_override` (en 19.0
  `price_include` es un compute sin inverse).
- `herramientas/prueba_formato.py`: prueba dorada estructural, sin Odoo,
  contra la FORMA de archivos reales aceptados por el PDT (sin sus datos).

Independiente de la nómina: para quien solo declara 4ta. Con la nómina
instalada, el puente `solse_pe_plame_4ta` (PL-1 paso 2) reutiliza este
generador en el ZIP del asistente PLAME.
