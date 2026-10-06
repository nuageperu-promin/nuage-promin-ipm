# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AccountAccount(models.Model):
	_inherit = 'account.account'

	# ── Tabla 34 SUNAT — Rubros de Estados Financieros ──────────────────────
	# Cada campo cubre los sub-libros indicados.
	# El wizard "Asignar Rubros EEFF (Tabla 34)" llena estos campos automáticamente.

	pe_t34_esf = fields.Many2one(
		comodel_name='pe.datas',
		string='Rubro Situación Financiera (3.1)',
		domain=[('table_code', '=', 'PE.TABLA34')],
		ondelete='set null',
		help=(
			'Rubro para el Estado de Situación Financiera (3.1). '
			'Aplica a cuentas de Activo (1x-3x) y Pasivo/Patrimonio (4x-5x).'
		),
	)
	pe_t34_resultado = fields.Many2one(
		comodel_name='pe.datas',
		string='Rubro Estado de Resultados (3.20/3.24)',
		domain=[('table_code', '=', 'PE.TABLA34')],
		ondelete='set null',
		help=(
			'Rubro para el Estado de Resultados (3.20) y el Estado de '
			'Resultados Integrales (3.24). '
			'Aplica a cuentas de Ingresos (7x) y Gastos (6x).'
		),
	)
	pe_t34_flujos = fields.Many2one(
		comodel_name='pe.datas',
		string='Rubro Flujos de Efectivo (3.18/3.25)',
		domain=[('table_code', '=', 'PE.TABLA34')],
		ondelete='set null',
		help=(
			'Rubro para Flujos de Efectivo Método Directo (3.18) e Indirecto (3.25). '
			'El sistema detecta el sub-libro correcto según el rubro asignado. '
			'Aplica principalmente a cuentas de tesorería y operaciones.'
		),
	)
	pe_t34_patrimonio = fields.Many2one(
		comodel_name='pe.datas',
		string='Rubro Cambios en Patrimonio (3.19)',
		domain=[('table_code', '=', 'PE.TABLA34')],
		ondelete='set null',
		help=(
			'Rubro para el Estado de Cambios en el Patrimonio Neto (3.19). '
			'Aplica a cuentas de Patrimonio (5x).'
		),
	)

	# Campo legacy mantenido para compatibilidad con instalaciones anteriores.
	# Equivale a pe_t34_esf. Usar el wizard para migrar los datos.
	pe_tabla34_id = fields.Many2one(
		comodel_name='pe.datas',
		string='Rubro EEFF Tabla 34 (legado)',
		domain=[('table_code', '=', 'PE.TABLA34')],
		ondelete='set null',
	)

	# ── Campos de diagnostico (computados) ───────────────────────────────────
	# Permiten filtrar, agrupar y detectar cuentas que requieren configuracion
	# manual sin necesidad de consultar SQL o revisar cada pestana.

	pe_t34_estado = fields.Selection(
		selection=[
			('na',       'No aplica'),
			('completo', 'Completo'),
			('parcial',  'Parcial'),
			('sin_config', 'Sin configurar'),
		],
		string='Estado Rubros EEFF',
		compute='_compute_pe_t34_estado',
		store=True,
		help=(
			'Estado global de configuracion de rubros Tabla 34 en esta cuenta:\n'
			'- No aplica: cuenta de orden o fuera de balance (no requiere rubros).\n'
			'- Completo: tiene todos los rubros esperados para su tipo de cuenta.\n'
			'- Parcial: le falta algun rubro esperado (revisar manualmente).\n'
			'- Sin configurar: le falta al menos un rubro obligatorio.'
		),
	)
	pe_t34_resumen = fields.Char(
		string='Resumen Rubros Tabla 34',
		compute='_compute_pe_t34_resumen',
		help=(
			'Muestra en una sola linea que rubros Tabla 34 tiene configurada '
			'esta cuenta. Util para ver de un vistazo el estado completo sin '
			'entrar a la pestana de rubros.'
		),
	)

	# ── Campos auxiliares para diagnostico (no almacenados) ──────────────────
	# Se exponen en la vista lista del wizard de diagnostico para dar contexto
	# al contador sin obligarle a abrir cada cuenta.

	pe_t34_es_hoja = fields.Boolean(
		string='Es Cuenta Hoja',
		compute='_compute_pe_t34_es_hoja',
		store=True,
		help='Indica si la cuenta tiene codigo de 6-8 digitos (nivel de detalle).',
	)

	# ── Computes ─────────────────────────────────────────────────────────────

	def _pe_t34_rubros_esperados(self):
		"""
		Devuelve un set con los nombres de los campos pe_t34_* que se esperan
		tener configurados en esta cuenta, segun su account_type.
		Retorna set() si la cuenta no aplica a ningun rubro Tabla 34.
		"""
		self.ensure_one()
		atype = self.account_type or ''
		# Cuentas de orden / fuera de balance: no aplica
		if atype in ('off_balance', False, '') or not atype:
			return set()
		# Ingresos y gastos: solo resultado (y eventualmente flujos)
		if atype.startswith('income') or atype.startswith('expense'):
			return {'pe_t34_resultado'}
		# Patrimonio: ESF + Cambios en patrimonio
		if atype in ('equity', 'equity_unaffected'):
			return {'pe_t34_esf', 'pe_t34_patrimonio'}
		# Resto (activos, pasivos): al menos ESF
		if atype.startswith('asset') or atype.startswith('liability'):
			return {'pe_t34_esf'}
		# Cualquier otro caso: sin expectativas
		return set()

	@api.depends('account_type', 'pe_t34_esf', 'pe_t34_resultado',
	             'pe_t34_flujos', 'pe_t34_patrimonio')
	def _compute_pe_t34_estado(self):
		"""
		Clasifica cada cuenta en uno de los 4 estados segun si tiene
		configurados los rubros esperados para su account_type.
		"""
		for cuenta in self:
			esperados = cuenta._pe_t34_rubros_esperados()
			if not esperados:
				cuenta.pe_t34_estado = 'na'
				continue
			configurados = set()
			if cuenta.pe_t34_esf:
				configurados.add('pe_t34_esf')
			if cuenta.pe_t34_resultado:
				configurados.add('pe_t34_resultado')
			if cuenta.pe_t34_flujos:
				configurados.add('pe_t34_flujos')
			if cuenta.pe_t34_patrimonio:
				configurados.add('pe_t34_patrimonio')

			faltantes = esperados - configurados
			if not faltantes:
				cuenta.pe_t34_estado = 'completo'
			elif faltantes == esperados:
				# No tiene ninguno de los esperados
				cuenta.pe_t34_estado = 'sin_config'
			else:
				cuenta.pe_t34_estado = 'parcial'

	@api.depends('pe_t34_esf', 'pe_t34_resultado', 'pe_t34_flujos',
	             'pe_t34_patrimonio', 'account_type')
	def _compute_pe_t34_resumen(self):
		"""
		Genera un string compacto con los rubros configurados.
		Ejemplo: "ESF: Efectivo | FLU: Operacion"
		"""
		for cuenta in self:
			partes = []
			if cuenta.pe_t34_esf:
				partes.append(f'ESF: {cuenta.pe_t34_esf.name or cuenta.pe_t34_esf.code}')
			if cuenta.pe_t34_resultado:
				partes.append(f'RES: {cuenta.pe_t34_resultado.name or cuenta.pe_t34_resultado.code}')
			if cuenta.pe_t34_flujos:
				partes.append(f'FLU: {cuenta.pe_t34_flujos.name or cuenta.pe_t34_flujos.code}')
			if cuenta.pe_t34_patrimonio:
				partes.append(f'PAT: {cuenta.pe_t34_patrimonio.name or cuenta.pe_t34_patrimonio.code}')
			if partes:
				cuenta.pe_t34_resumen = ' | '.join(partes)
			elif cuenta._pe_t34_rubros_esperados():
				cuenta.pe_t34_resumen = _('(sin configurar)')
			else:
				cuenta.pe_t34_resumen = _('(no aplica)')

	@api.depends('code')
	def _compute_pe_t34_es_hoja(self):
		"""
		Heuristica simple: cuentas con codigo >= 6 digitos son de detalle
		(cuentas hoja). Las cuentas padre/agrupadoras tienen menos digitos.
		"""
		for cuenta in self:
			codigo = (cuenta.code or '').strip()
			cuenta.pe_t34_es_hoja = len(codigo) >= 6
