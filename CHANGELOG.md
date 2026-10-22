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

## 2026-10-21 — nuage_zk_attendance (nuevo, 19.0.1.0.0)

- **Motivo:** integrar los 2 relojes ZKTeco de PROMIN (MB20-VL/ID y SenseFace
  M2F-LR, ADMS) con Asistencias de Odoo 19 en Odoo.sh.
- **Acción:** módulo nuevo en rama `feature/zk-attendance` (no está en `main`).
  Instalar primero en el entorno *develop*; ver `nuage_zk_attendance/README.md`.
  Antes de apuntar los relojes a Odoo, confirmar con PROMIN quién administra el
  servidor actual (18.209.x.x:8538).
