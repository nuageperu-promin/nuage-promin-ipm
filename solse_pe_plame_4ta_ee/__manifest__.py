# -*- coding: utf-8 -*-

{
	'maintainer': 'Nuage Peru S.A.C.',
	'name': 'Nómina Peruana - PLAME 4ta Categoría (Enterprise)',
	'version': '19.0.1.0.0',
	'category': 'Human Resources/Payroll',
	'summary': 'Añade los archivos .ps4 y .4ta de solse_pe_plame_rxh al ZIP del PLAME de la nómina Enterprise',
	'description': """
Puente entre la nómina ENTERPRISE (solse_pe_payroll) y el PLAME de 4ta
categoría. Gemelo de solse_pe_plame_4ta (Community): VARIANTES
EXCLUYENTES, se instala una u otra según la rama de nómina.

Agrega al ZIP del asistente PLAME los DOS archivos de Prestadores de
Servicios que genera solse_pe_plame_rxh:

  · .ps4 — estructura 7, maestro de prestadores
  · .4ta — estructura 20, detalle de comprobantes

El generador y su normativa viven en solse_pe_plame_rxh (neutro, sin
nómina), verificado contra archivos aceptados por el PDT y cubierto por el
caso PLAME-RXH del laboratorio. Este módulo solo lo engancha al ZIP.

A diferencia del gemelo Community no trae campos heredados de versiones
anteriores: nunca existió un puente de 4ta para Enterprise.
	""",
	'license': 'Other proprietary',
	'depends': [
		# Nómina Enterprise: dueña de solse.payroll.plame.wizard y de la
		# vista solse_pe_payroll.plame_wizard_view_form.
		'solse_pe_payroll',
		# El generador de .ps4/.4ta.
		'solse_pe_plame_rxh',
	],
	'data': [
		'views/plame_wizard_views.xml',
	],
	'installable': True,
	'application': False,
}
