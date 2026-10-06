# -*- coding: utf-8 -*-

from . import models
from . import wizard
from .hooks import post_init_hook


def _verificar_variante_nomina(env, este, excluyente, nombre_excluyente):
	"""Las dos ramas de nómina son VARIANTES EXCLUYENTES (misma situación que
	solse_pe_ple_07 / _ee): siembran los mismos códigos de parámetros
	(pe_uit incluido) y tipos de entrada bajo xmlids de módulos distintos.
	Con la unicidad real de L2, instalar ambas fallaría con un error de
	constraint críptico a mitad de carga de datos; este guard lo convierte
	en un mensaje claro ANTES de tocar nada. Odoo no tiene mecanismo de
	conflictos declarativos en el manifest, así que se hace aquí.
	"""
	from odoo.exceptions import UserError
	instalado = env['ir.module.module'].search([
		('name', '=', excluyente),
		('state', 'in', ['installed', 'to install', 'to upgrade']),
	], limit=1)
	if instalado:
		raise UserError(
			'No se puede instalar %s: %s ya está instalado y son VARIANTES '
			'EXCLUYENTES de la nómina peruana (siembran los mismos códigos '
			'de parámetros, la UIT incluida). Community usa '
			'solse_pe_payroll_base + solse_pe_payroll_ce; Enterprise usa '
			'solse_pe_payroll. Desinstalar una rama antes de instalar la '
			'otra.' % (este, nombre_excluyente))


def _pre_init_payroll_ee(env):
	_verificar_variante_nomina(
		env, 'solse_pe_payroll', 'solse_pe_payroll_base',
		'solse_pe_payroll_base (rama Community)')
