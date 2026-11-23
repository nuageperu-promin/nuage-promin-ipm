# promin_portal_empleado — Portal del Empleado (1.ª entrega)

Odoo 19. Depende de `hr`, `hr_payroll`, `portal`, `mail`.

## Qué hace
- **Acceso**: RRHH crea un usuario Portal vinculado al empleado (acción "Crear acceso al Portal del Empleado" en Empleados, o menú *Portal del Empleado > Accesos al portal*). El empleado no necesita ser usuario interno.
- **Mis datos** (el empleado registra; RRHH aprueba o rechaza con motivo): DNI, derechohabientes, estudios, experiencia laboral y CUL, con adjuntos PDF/JPG/PNG (5 MB). Los datos aprobados solo cambian mediante una solicitud de cambio, que también se aprueba. Al aprobar un DNI se actualiza el N.° de identificación del empleado.
- **Mis documentos**: contratos y otros documentos que RRHH publica (solo ver/descargar) y boletas de pago (PDF de la boleta PE) con **registro de lectura** (primera apertura y n.° de veces), visible en *Lectura de boletas*.

## Menú (RRHH)
Portal del Empleado: Datos por aprobar · Contratos y documentos · Lectura de boletas · Accesos al portal.

## Próximas entregas
Renta de 5.ª categoría (2 planillas), vacaciones por periodos, encuestas en el portal.
