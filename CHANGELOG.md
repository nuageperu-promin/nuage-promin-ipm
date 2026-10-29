# Changelog — nuage-promin-ipm

Registro de versiones y actualizaciones recibidas o desarrolladas para cada módulo.
Formato por entrada: fecha, módulo(s), motivo, acción.

---

## Cómo agregar una entrada nueva

Cuando se reciba una corrección de un módulo de terceros, o se complete una
versión de un desarrollo propio:

## AAAA-MM-DD — <nombre técnico del módulo>

- **Motivo:** <qué se corrigió, mejoró o desarrolló>
- **Acción:** <qué se hizo: código actualizado, "Actualizar" ejecutado en Aplicaciones, etc.>

---

## 2026-10-28 — Paquete: estados financieros en bimoneda + cierre y apertura contable

- **promin_bimoneda_pen_usd 19.0.1.2.2** (actualización): agrega el Balance de Comprobación en dos variantes, «(SOL)» y «(USD)». El saldo USD de cada apunte se guarda con 6 decimales y sin redondeo por línea, para que la balanza en dólares cuadre en 0.00. Al actualizar, un script de migración recalcula el USD de los apuntes existentes (puede tardar en bases grandes: actualizar fuera de horario).
- **promin_bimoneda_flujo 19.0.1.0.1** (nuevo): Estado de Flujos de Efectivo en dos variantes «(SOL)» y «(USD)». En USD, la línea de diferencia se rotula «Diferencia por tipo de cambio» (efecto de convertir con el tipo de cambio de la factura y del pago). Instalar después de la bimoneda.
- **promin_estado_patrimonio 19.0.1.0.1** (nuevo): Estado de Cambios en el Patrimonio en soles y dólares (columnas del PCGE: capital, acciones de inversión, capital adicional, resultados no realizados, excedente de revaluación, reservas, resultados acumulados). Excluye los asientos generados por el cierre y apertura. Depende de la bimoneda y del cierre y apertura.
- **promin_asiento_cierre_contable 19.0.1.0.1** (nuevo, prototipo): genera, por compañía y año, el cierre de resultados, el cierre de balance y la apertura del ejercicio siguiente (detalle por tercero y moneda en cuentas por cobrar/pagar). Menú: Contabilidad > Asientos > Cierre y apertura contable. Pendiente de validación del contador de PROMIN: traslado del resultado a la cuenta 59, diario y numeración.
- **nuage_pe_oc 19.0.1.1.2 y nuage_pe_factura_pdf 19.0.1.1.1**: solo cambian los títulos de la pestaña en la compañía («Órdenes Compra» y «Facturas»).
- **Acción:** actualizar el submódulo al commit indicado en el correo, y en este orden: actualizar `nuage_pe_oc` y `nuage_pe_factura_pdf`; actualizar `promin_bimoneda_pen_usd`; instalar `promin_asiento_cierre_contable`, `promin_bimoneda_flujo` y por último `promin_estado_patrimonio`. Requiere tipos de cambio PEN/USD cargados.

---

## 2026-10-28 — promin_bimoneda_pen_usd (nuevo, 19.0.1.1.1, prototipo)

- **Motivo:** desarrollo "Bimoneda (PEN/USD)": estados financieros valorizados en soles y dólares.
- **Acción:** módulo nuevo. Agrega el campo almacenado `nuage_balance_usd` en los apuntes (conversión con el tipo de cambio de la tabla de Odoo) y habilita las columnas PEN y USD en el Balance General (PE) y el Estado de Resultados (PE), en pantalla, PDF y XLSX. Al instalar, Odoo calcula el campo para todos los apuntes existentes: instalar fuera de horario. Requiere cotizaciones PEN/USD cargadas en `res.currency`. Alcance actual: solo conversión; pendientes la moneda de transacción original con diferencia de cambio, la valuación de Inventario, balanza de comprobación, estado de cambios en el patrimonio y flujo de efectivo.

---

## 2026-10-28 — solse_pe_* (mantenimiento: warnings del build)

- **Motivo:** el build del staging salía en naranja por warnings del log: falta de `author` en los manifests y el import obsoleto `odoo.osv`.
- **Acción:** se agrega `'author': 'Nuage Peru SAC'` en los 23 manifests de `solse_pe_*` y se elimina el import sin uso `from odoo.osv import expression` en `solse_pe_cpe/models/account_tax.py` y `solse_pe_edi/models/res_partner.py`. Sin cambios de lógica ni de versión: no requiere actualizar módulos. Quedan pendientes los warnings de `origin_doc_*` (compute_sudo/store) y `nombre_producto`, que requieren pruebas de notas de crédito/débito.

---

## 2026-10-28 — nuage_pe_retencion (nuevo, 19.0.1.1.3)

- **Motivo:** PROMIN, como agente de retención, retendrá el IGV al pagar a proveedores. Se toma como modelo el comprobante RT08-00002911 (factura en dólares).
- **Acción:** módulo nuevo. La retención se decide al registrar el pago (suma de facturas del mismo proveedor; umbral de S/ 700 en soles; tasa 3%) y reemplaza, por compañía, la retención que Solse calcula al validar la factura de compra. Soporta facturas en USD: tipo de cambio de la tabla de Odoo a la fecha de pago, retención registrada en soles. Genera el comprobante de retención con serie y correlativo propios (estado borrador/emitido/cancelado) y su PDF con el formato de PROMIN, más el reporte "Retenciones por proveedor". Instalar (depende de `solse_pe_edi` y `solse_pe_accountant`). Después, en Ajustes > Compañías > pestaña "Retenciones": activar "Retener IGV al pagar", tasa, umbral, serie y correlativo inicial (confirmar con PROMIN: RT08 desde 2912 u otra serie) y la cuenta de IGV retenido por pagar (confirmar con el contador). No envía el comprobante a SUNAT: la emisión electrónica por Nubefact/Bizlinks queda para una segunda etapa. Probado en promindemo con facturas en soles y en dólares.

---

## 2026-10-28 — nuage_pe_guia_pdf (corrección, 19.0.1.0.2)

- **Motivo:** Odoo.sh rechazó el módulo ("manifest has an invalid syntax"): el `__manifest__.py` se subió vacío en el commit anterior.
- **Acción:** manifest restaurado. Actualizar el submódulo y luego instalar `nuage_pe_guia_pdf`. `nuage_pe_oc` no cambia.

---

## 2026-10-27 — nuage_pe_oc (19.0.1.1.1) y nuage_pe_guia_pdf (nuevo, 19.0.1.0.2)

- **Motivo:** observaciones de PROMIN tras la demostración. (1) El "Tipo de OC" pasa a 7 tipos con numeración propia: PMA Activo, PMC Consumibles, PMI Importación, PML Local, PMS Stock, PMT Tableros, SRV Servicios. (2) El PDF se separa en dos formatos independientes del tipo: "Orden de Compra Local (PROMIN)" y "Orden de Compra Importación (PROMIN)". (3) Columna, filtros y agrupación por Tipo de OC en la lista y búsqueda. (4) Nuevo módulo con el formato PDF de la guía de remisión remitente (transporte privado y público).
- **Acción:** `nuage_pe_oc` incluye migración: las OC con tipo "local" pasan a PMS y las de "importación" a PMI, conservando secuencias y contadores. Las secuencias nuevas (PMA, PMC, PML, PMT, SRV) empiezan en 1: ajustar el número inicial con PROMIN en Ajustes > Técnico > Secuencias. Para `nuage_pe_oc` usar **Actualizar** y para `nuage_pe_guia_pdf` **Instalar** (depende de `solse_pe_cpe_guias`). Probado en promindemo.

---

## 2026-10-23 — nuage_pe_oc y nuage_pe_factura_pdf (nuevos, 19.0.1.0.0 y 19.0.1.1.0)

- **Motivo:** formatos PDF de PROMIN enviados por Alicia Quispe: orden de compra local (PMS) e importación (PMI), factura electrónica y notas de crédito/débito.
- **Acción:** módulos nuevos en rama `feature/oc-factura-pdf`, probados en promindemo (factura y notas confirmadas; OC revisadas contra los PDF originales). Instalar primero en *develop*. `nuage_pe_oc` agrega el campo "Tipo de OC" y las secuencias PMS/PMI (ajustar el número inicial con PROMIN); ambos módulos añaden una pestaña en la compañía con los textos fijos editables. Dependen de `purchase` y de `solse_pe_cpe_pdf_ee`.

---

## 2026-10-22 — nuage_zk_attendance

- **Motivo:** probado en promindemo (handshake, entrada/salida, duplicado). El formulario mostraba puerto 80 y sin HTTPS porque `web.base.url` queda en http detrás del proxy.
- **Acción:** la pestaña "Configurar el reloj" ahora indica HTTPS/443 para cualquier servidor no local.

---

## 2026-10-21 — nuage_zk_attendance (nuevo, 19.0.1.0.0)

- **Motivo:** integrar los 2 relojes ZKTeco de PROMIN (MB20-VL/ID y SenseFace
  M2F-LR, ADMS) con Asistencias de Odoo 19 en Odoo.sh.
- **Acción:** módulo nuevo en rama `feature/zk-attendance` (no está en `main`).
  Instalar primero en el entorno *develop*; ver `nuage_zk_attendance/README.md`.
  Antes de apuntar los relojes a Odoo, confirmar con PROMIN quién administra el
  servidor actual (18.209.x.x:8538).
