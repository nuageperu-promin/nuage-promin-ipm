# -*- coding: utf-8 -*-

{
	'maintainer': 'Nuage Peru S.A.C.',
	'name': 'Nómina Peruana - Asistencias (Enterprise)',
	'version': '19.0.1.0.0',
	'category': 'Human Resources/Payroll',
	'summary': 'Concilia hr_attendance contra la boleta Enterprise: faltas, '
			   'medias jornadas y tardanzas',
	'description': """
Conciliación de asistencias (hr_attendance) contra la boleta de la nómina
peruana ENTERPRISE (solse_pe_payroll sobre hr_payroll).

Gemelo de solse_pe_payroll_asistencia (Community). Comparten el MOTOR de
conciliación (qué día es falta, tardanza o media jornada) y difieren en la
CAPA DE ESCRITURA, que en Enterprise no es portable:

  · la falta es una línea de días trabajados con un hr.work.entry.type
    propio (FALTA / FALTA_PARCIAL) declarado como NO PAGADO en las
    estructuras mensual y semanal; `is_paid` es un compute almacenado y
    no se escribe a mano;
  · la tardanza es un input TARDANZAS con su hr.payslip.input.type, que
    la regla TAR_001 descuenta a valor hora (sueldo/240) con signo
    POSITIVO, como todas las deducciones de solse_pe_payroll;
  · el estado editable es `draft` (Enterprise no tiene `verify`);
  · «Actualizar desde entradas de trabajo» regenera las líneas y borraría
    las faltas: se vuelve a conciliar detrás.

NO instalar junto a solse_pe_payroll_asistencia: la rama de nómina ya es
excluyente (guard en solse_pe_payroll / solse_pe_payroll_base).
	""",
	'license': 'Other proprietary',
	'depends': [
		'hr_payroll',
		'solse_pe_payroll',
		'hr_attendance',
	],
	'data': [
		'data/asistencia_data.xml',
		'views/hr_payslip_views.xml',
		'views/res_company_views.xml',
	],
	'installable': True,
	'application': False,
}
