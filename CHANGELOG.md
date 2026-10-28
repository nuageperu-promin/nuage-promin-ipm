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
