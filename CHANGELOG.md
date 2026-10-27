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
