# -*- coding: utf-8 -*-
# Copyright (c) 2026
# 
# 

{
	'support': '',
	'maintainer': 'NUAGE',
	'name': 'Nómina Peruana - Detalle de Renta de 5ta (Enterprise)',
	'summary': 'Muestra paso a paso cómo se calculó la retención de renta de '
			   '5ta categoría de cada recibo: pestaña en el recibo, lista y PDF.',
	'description': """
Detalle de la retención mensual de renta de 5ta categoría (art. 40 del
Reglamento de la LIR) calculada por la regla R5TA_001 de solse_pe_payroll.

- Al calcular la hoja guarda el desglose: proyección anual de
  remuneraciones y gratificaciones, percibido acumulado, deducción de
  7 UIT, impuesto por tramos, retenciones previas y dozavo del mes.
- Compara la retención reconstruida con la línea R5TA_001 del recibo y
  avisa si no coinciden (por ejemplo, si la regla fue modificada).
- Pestaña «Renta de 5ta» en el recibo, lista «Detalle de Renta de 5ta» en
  Nómina PE y reporte PDF para entregar al trabajador o al contador.

No modifica la regla ni el cálculo de la nómina.
	""",
	'author': 'NUAGE PERU SAC',
	'website': '',
	'category': 'Human Resources/Payroll',
	'version': '19.0.1.0.0',
	'license': 'LGPL-3',
	'depends': [
		'solse_pe_payroll',
	],
	'data': [
		'security/ir.model.access.csv',
		'report/detalle_renta5_report.xml',
		'views/hr_payslip_views.xml',
	],
	'installable': True,
	'application': False,
}
