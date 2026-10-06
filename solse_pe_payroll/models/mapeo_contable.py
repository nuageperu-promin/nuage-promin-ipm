# -*- coding: utf-8 -*-

# Mapeo contable por prefijo PCGE.
#
# Principio de diseño: las reglas salariales NUNCA se distribuyen con cuentas
# contables fijas, porque cada implementación tiene un plan con longitudes de
# sufijo distintas (6211000, 621100, 62111...). El PCGE es estable en sus
# primeros dígitos, así que el mapeo guarda PREFIJOS y un resolutor los
# aplica por compañía sobre los campos company_dependent account_debit /
# account_credit de hr.salary.rule (nativos de hr_payroll_account v19).
#
# Idempotencia: solo completa cuentas vacías; jamás pisa una asignación manual.

from odoo import api, fields, models, _


class SolsePayrollMapeoContable(models.Model):
	_name = 'solse.payroll.mapeo.contable'
	_description = 'Mapeo PCGE por prefijo para reglas de nómina'
	_order = 'regla_id'

	regla_id = fields.Many2one(
		comodel_name='hr.salary.rule',
		string='Regla salarial',
		required=True,
		ondelete='cascade',
		index=True,
	)
	codigo_regla = fields.Char(
		related='regla_id.code', string='Código', store=True)
	prefijo_debito = fields.Char(
		string='Prefijo débito (PCGE)',
		help='Prefijo de cuenta de gasto. Ej.: 6211 para "Sueldos y salarios". '
			 'El resolutor busca la cuenta hoja cuyo código empiece por este prefijo.'
	)
	estructura_id = fields.Many2one(
		comodel_name='hr.payroll.structure',
		string='Solo para la estructura',
		help='Vacío: el mapeo aplica a la regla en todas las estructuras '
			 'SOLSE. Con valor: solo a la regla de esa estructura (p. ej. el '
			 'NET de Gratificaciones acredita 4114 mientras el NET general '
			 'acredita 4111). Los mapeos específicos se aplican antes que '
			 'los genéricos.'
	)
	prefijo_credito = fields.Char(
		string='Prefijo crédito (PCGE)',
		help='Prefijo de cuenta de pasivo/tributo. Ej.: 4017 para renta de 5ta, '
			 '4111 para remuneraciones por pagar.'
	)
	nota = fields.Char(string='Nota')

	_regla_unica = models.Constraint(
		'unique (regla_id, estructura_id)',
		'Ya existe un mapeo contable para esta regla y estructura.',
	)

	def _buscar_cuenta(self, prefijo, compania):
		"""Busca la cuenta del plan de la compañía que matchee el prefijo PCGE.

		Toma la de código más corto (la más cercana al nivel del prefijo),
		lo que resuelve indistintamente planes con 5, 6 o 7 dígitos.
		"""
		if not prefijo:
			return self.env['account.account']
		# Nota v19: account.account ya no tiene 'deprecated'; las cuentas
		# fuera de uso se archivan y search() las excluye por defecto.
		return self.env['account.account'].with_company(compania).search([
			('code', '=like', prefijo.strip() + '%'),
			('company_ids', 'in', compania.id),
		], order='code asc', limit=1)

	def aplicar_a_compania(self, compania):
		"""Aplica los mapeos sobre las reglas para la compañía indicada.

		Devuelve (aplicados, sin_match) donde sin_match es una lista de
		tuplas (codigo_regla, campo, prefijo) para reporte al usuario.
		"""
		aplicados = 0
		sin_match = []
		estructuras = self.env['solse.payroll.inicializador'].estructuras_solse()
		Regla = self.env['hr.salary.rule']
		# Específicos por estructura primero; los genéricos solo completan
		# lo que quede vacío.
		mapeos_ordenados = sorted(self, key=lambda m: 0 if m.estructura_id else 1)
		for mapeo in mapeos_ordenados:
			# El mapeo alcanza a la regla de la estructura base Y a sus
			# copias en las estructuras operativas (mismo código). Las
			# cuentas son company_dependent y las copias no las heredan.
			dominio_estructuras = (
				mapeo.estructura_id.ids if mapeo.estructura_id else estructuras.ids)
			regla_ids = Regla.with_company(compania).search([
				('code', '=', mapeo.codigo_regla),
				('struct_id', 'in', dominio_estructuras),
			])
			for regla_id in regla_ids:
				for campo, prefijo in (
					('account_debit', mapeo.prefijo_debito),
					('account_credit', mapeo.prefijo_credito),
				):
					if not prefijo or regla_id[campo]:
						# Sin prefijo definido, o ya asignada (manual o
						# corrida previa): no tocar.
						continue
					cuenta_id = mapeo._buscar_cuenta(prefijo, compania)
					if cuenta_id:
						regla_id[campo] = cuenta_id
						aplicados += 1
					else:
						sin_match.append((mapeo.codigo_regla, campo, prefijo))
		return aplicados, sin_match

	@api.model
	def aplicar_todas_las_companias(self):
		"""Punto de entrada del post_init_hook: aplica el mapeo en cada
		compañía peruana existente. Silencioso ante faltantes (el wizard es
		el canal para el reporte detallado)."""
		mapeos = self.search([])
		if not mapeos:
			return
		# res.company.country_id no es almacenado en v19: filtrar en Python
		pe_id = self.env.ref('base.pe')
		companias = self.env['res.company'].search([]).filtered(
			lambda c: c.country_id == pe_id)
		for compania in companias:
			mapeos.aplicar_a_compania(compania)
