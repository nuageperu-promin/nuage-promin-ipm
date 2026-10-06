# -*- coding: utf-8 -*-

"""
Wizard de diagnostico de configuracion de Rubros EEFF (Tabla 34).

Proporciona al contador una vista grafica del estado de configuracion
del plan de cuentas frente a los requerimientos de la Tabla 34 SUNAT,
sin necesidad de ejecutar queries SQL ni conocer los nombres tecnicos
de los campos.

Flujo tipico:
 1. El contador abre el wizard.
 2. Pulsa "Calcular Diagnostico" — se contabilizan las cuentas por estado.
 3. Pulsa uno de los botones ("Ver sin configurar", "Ver parcial", etc.)
    para abrir la vista lista del plan filtrada a esas cuentas.
 4. Corrige manualmente o vuelve a correr el wizard de asignacion masiva.
"""

from odoo import models, fields, api, _


class WizardDiagnosticoTabla34(models.TransientModel):
	_name = 'solse.wizard.diagnostico.tabla34'
	_description = 'Diagnostico Rubros EEFF (Tabla 34)'

	def _compute_display_name(self):
		for reg in self:
			reg.display_name = _('Diagnostico Rubros EEFF (Tabla 34)')

	company_id = fields.Many2one(
		comodel_name='res.company',
		string='Empresa',
		default=lambda self: self.env.company,
		required=True,
	)

	# ── Contadores de diagnostico (computados al abrir el wizard) ────────────
	# Estan como readonly en la vista para que el contador vea los numeros
	# pero no los pueda editar.

	total_cuentas = fields.Integer(
		string='Total de cuentas',
		readonly=True,
	)
	cuentas_completo = fields.Integer(
		string='Cuentas Completo',
		readonly=True,
		help='Cuentas con todos los rubros esperados configurados.',
	)
	cuentas_parcial = fields.Integer(
		string='Cuentas Parcial',
		readonly=True,
		help='Cuentas con algunos rubros esperados pero no todos.',
	)
	cuentas_sin_config = fields.Integer(
		string='Cuentas Sin Configurar',
		readonly=True,
		help='Cuentas que deberian tener rubros pero no tienen ninguno.',
	)
	cuentas_na = fields.Integer(
		string='Cuentas No Aplica',
		readonly=True,
		help='Cuentas de orden o fuera de balance que no requieren rubros.',
	)

	# Desglose del estado "Sin Configurar" por tipo de cuenta, util para
	# entender si las cuentas problematicas son activos, pasivos o resultados.
	desglose_activos_sin = fields.Integer(
		string='Activos sin configurar',
		readonly=True,
	)
	desglose_pasivos_sin = fields.Integer(
		string='Pasivos sin configurar',
		readonly=True,
	)
	desglose_patrimonio_sin = fields.Integer(
		string='Patrimonio sin configurar',
		readonly=True,
	)
	desglose_resultados_sin = fields.Integer(
		string='Ingresos/Gastos sin configurar',
		readonly=True,
	)

	# Separacion entre hojas (realmente problematicas) vs agrupadoras
	# (probablemente ignorables) para el estado "Sin Configurar".
	sin_config_hojas = fields.Integer(
		string='Sin Configurar — Cuentas Hoja',
		readonly=True,
		help='Cuentas de detalle (6+ digitos) sin rubro. Estas son las '
		     'que realmente requieren atencion del contador.',
	)
	sin_config_agrupadoras = fields.Integer(
		string='Sin Configurar — Cuentas Padre',
		readonly=True,
		help='Cuentas agrupadoras de menos de 6 digitos. Normalmente no '
		     'necesitan rubro porque no reciben movimientos directos.',
	)

	diagnostico_calculado = fields.Boolean(
		string='Diagnostico calculado',
		default=False,
	)

	# ── Logica de diagnostico ────────────────────────────────────────────────

	def _dominio_cuentas_empresa(self):
		"""Dominio base: cuentas activas de la empresa."""
		return [
			('company_ids', 'in', [self.company_id.id]),
			('active', '=', True),
		]

	def action_calcular(self):
		"""
		Recorre todas las cuentas de la empresa y contabiliza por estado.
		Se apoya en el campo computado almacenado pe_t34_estado, que ya
		evalua la logica "cuales rubros se esperan por account_type".
		"""
		self.ensure_one()
		Account = self.env['account.account']
		domain_base = self._dominio_cuentas_empresa()

		def _contar(estado_extra=None):
			d = list(domain_base)
			if estado_extra:
				d += estado_extra
			return Account.search_count(d)

		# Totales por estado
		self.total_cuentas       = _contar()
		self.cuentas_completo    = _contar([('pe_t34_estado', '=', 'completo')])
		self.cuentas_parcial     = _contar([('pe_t34_estado', '=', 'parcial')])
		self.cuentas_sin_config  = _contar([('pe_t34_estado', '=', 'sin_config')])
		self.cuentas_na          = _contar([('pe_t34_estado', '=', 'na')])

		# Desglose por familia contable — solo para "sin_config"
		dom_sin = [('pe_t34_estado', '=', 'sin_config')]
		self.desglose_activos_sin = _contar(
			dom_sin + [('account_type', 'like', 'asset%')]
		)
		self.desglose_pasivos_sin = _contar(
			dom_sin + [('account_type', 'like', 'liability%')]
		)
		self.desglose_patrimonio_sin = _contar(
			dom_sin + [('account_type', 'in', ('equity', 'equity_unaffected'))]
		)
		self.desglose_resultados_sin = _contar(
			dom_sin + ['|', ('account_type', 'like', 'income%'),
			               ('account_type', 'like', 'expense%')]
		)

		# Hojas vs agrupadoras para "sin_config"
		self.sin_config_hojas = _contar(
			dom_sin + [('pe_t34_es_hoja', '=', True)]
		)
		self.sin_config_agrupadoras = _contar(
			dom_sin + [('pe_t34_es_hoja', '=', False)]
		)

		self.diagnostico_calculado = True
		return {
			'type': 'ir.actions.act_window',
			'res_model': self._name,
			'res_id': self.id,
			'view_mode': 'form',
			'target': 'new',
		}

	# ── Acciones para abrir listas filtradas ────────────────────────────────
	# Cada boton abre la vista lista del plan de cuentas con el filtro
	# correspondiente. Asi el contador ve exactamente que cuentas necesitan
	# atencion y puede corregirlas in-situ (o ejecutar el wizard de
	# asignacion masiva).

	def _action_listar(self, dominio_extra, nombre):
		"""Helper: abre account.account con un dominio fijo."""
		self.ensure_one()
		dominio = self._dominio_cuentas_empresa() + dominio_extra
		return {
			'type': 'ir.actions.act_window',
			'name': nombre,
			'res_model': 'account.account',
			'view_mode': 'list,form',
			'domain': dominio,
			'context': {
				'search_default_group_t34_estado': 0,
				'create': False,
			},
			'target': 'current',
		}

	def action_ver_sin_configurar(self):
		return self._action_listar(
			[('pe_t34_estado', '=', 'sin_config')],
			_('Cuentas sin Rubros EEFF configurados'),
		)

	def action_ver_sin_config_hojas(self):
		"""Solo las hojas sin configurar — las que REALMENTE importan."""
		return self._action_listar(
			[('pe_t34_estado', '=', 'sin_config'),
			 ('pe_t34_es_hoja', '=', True)],
			_('Cuentas Hoja sin Rubros EEFF (requieren atencion)'),
		)

	def action_ver_parcial(self):
		return self._action_listar(
			[('pe_t34_estado', '=', 'parcial')],
			_('Cuentas con Rubros EEFF parciales'),
		)

	def action_ver_completo(self):
		return self._action_listar(
			[('pe_t34_estado', '=', 'completo')],
			_('Cuentas con Rubros EEFF completos'),
		)

	# Accesos directos a los wizards de asignacion masiva, para que el
	# contador no tenga que salir del flujo de diagnostico.
	def action_ir_wizard_asignacion(self):
		"""Abre el wizard de asignacion masiva de Tabla 34."""
		self.ensure_one()
		return {
			'type': 'ir.actions.act_window',
			'name': _('Asignar Rubros EEFF (Tabla 34)'),
			'res_model': 'solse.wizard.asignar.tabla34',
			'view_mode': 'form',
			'target': 'new',
			'context': {'default_company_id': self.company_id.id},
		}
