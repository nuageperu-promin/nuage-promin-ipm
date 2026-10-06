# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging
_logging = logging.getLogger(__name__)


class AccountAsset(models.Model):
	_inherit = 'account.asset'

	# ── Identificación SUNAT ─────────────────────────────────────────────
	codigo_af = fields.Char(
		string='Código del activo (PLE C5)',
		help='Código propio del activo fijo (campo 5 de la estructura 7.1). '
			'Hasta 24 caracteres alfanuméricos. Si se deja vacío se usa AF + ID.',
		size=24,
	)
	codigo_catalogo_af = fields.Selection(
		string='Catálogo (Tabla 13)',
		selection=[
			('1', '1 - Naciones Unidas (UNSPSC)'),
			('3', '3 - GS1 (EAN-UCC / GTIN)'),
			('9', '9 - Otros'),
		],
		default='9',
		help='Campo 4 de la estructura 7.1. Catálogo al que corresponde el '
			'código propio del activo.',
	)
	codigo_existencia_af = fields.Char(
		string='Código UNSPSC/GTIN (PLE C7)',
		help='Campo 7 de la estructura 7.1. Opcional salvo que el CPE de '
			'compra haya consignado UNSPSC o GTIN. No aplica catálogo 9.',
		size=128,
	)
	tipo_af = fields.Selection(
		string='Tipo de activo (Tabla 18)',
		selection=[
			('1', '1 - No revaluado o revaluado sin efecto tributario'),
			('2', '2 - Revaluado con efecto tributario'),
		],
		default='1',
		help='Campo 8 de la estructura 7.1.',
	)
	estado_af = fields.Selection(
		string='Estado del activo (Tabla 19)',
		selection=[
			('1', '1 - Activo en desuso'),
			('2', '2 - Activo obsoleto'),
			('9', '9 - Resto de activos'),
		],
		default='9',
		help='Campo 10 de la estructura 7.1.',
	)
	marca_af = fields.Char(string='Marca', size=20)
	modelo_af = fields.Char(string='Modelo', size=20)
	serie_placa_af = fields.Char(string='N° serie / placa', size=30)
	num_autorizacion_metodo = fields.Char(
		string='N° autorización cambio de método',
		size=20,
		default='-',
		help='Campo 27 de la estructura 7.1. Documento de autorización para '
			"cambiar el método de depreciación. Si no existe, '-'.",
	)
	porcentaje_dep_tributaria = fields.Float(
		string='% depreciación tributaria',
		digits=(5, 2),
		help='Campo 28 de la estructura 7.1. Solo obligatorio con método '
			'línea recta (Tabla 20 = 1). Si se deja en 0 se calcula desde '
			'la duración configurada en el activo (100 / años).',
	)

	# ── Revaluaciones y ajustes (captura manual, no existen en Odoo) ─────
	#
	# Los importes son ACUMULADOS al 31.12 (decisión de Gabriel,
	# 2026-09-20): el valor revaluado vigente y la depreciación acumulada
	# de la revaluación. `fecha_revaluacion` los ancla en el tiempo: el 7.1
	# de un ejercicio que cierra ANTES de esa fecha los informa en cero (sin
	# ella, un 7.1 regenerado de un año anterior mostraría una revaluación
	# que aún no existía). Vacía = siempre vigentes (comportamiento previo).
	fecha_revaluacion = fields.Date(
		string='Fecha de la revaluación',
		help='Desde qué fecha rigen los importes de revaluación (C20-C22, '
			'C33-C35). Los ejercicios que cierran antes la informan en cero.')
	valor_revaluacion_voluntaria = fields.Monetary(
		string='Revaluación voluntaria (C20)', currency_field='currency_id')
	valor_revaluacion_reorganizacion = fields.Monetary(
		string='Revaluación por reorganización (C21)', currency_field='currency_id')
	valor_otras_revaluaciones = fields.Monetary(
		string='Otras revaluaciones (C22)', currency_field='currency_id')
	dep_revaluacion_voluntaria = fields.Monetary(
		string='Dep. revaluación voluntaria (C33)', currency_field='currency_id')
	dep_revaluacion_reorganizacion = fields.Monetary(
		string='Dep. revaluación reorganización (C34)', currency_field='currency_id')
	dep_otras_revaluaciones = fields.Monetary(
		string='Dep. otras revaluaciones (C35)', currency_field='currency_id')

	# ── Arrendamiento financiero (estructura 7.4) ────────────────────────
	es_leasing = fields.Boolean(
		string='Arrendamiento financiero',
		help='Marcar si el activo se adquirió bajo leasing. Habilita su '
			'inclusión en la estructura 7.4.',
	)
	numero_contrato_leasing = fields.Char(string='N° contrato leasing', size=20)
	fecha_contrato_leasing = fields.Date(string='Fecha del contrato')
	fecha_inicio_leasing = fields.Date(string='Fecha inicio del leasing')
	numero_cuotas_leasing = fields.Integer(string='N° cuotas pactadas')
	monto_total_leasing = fields.Monetary(
		string='Monto total del contrato', currency_field='currency_id')

	# ── Moneda extranjera (estructura 7.3) ───────────────────────────────
	#
	# AF7-02 (L8.1): compute EDITABLE (readonly=False). Un compute sin
	# inverse es readonly por defecto (odoo/orm/fields.py:451 en 19.0) y
	# `create()` solo protege de la recomputación a los compute editables
	# (odoo/orm/models.py:4691): el valor que se pasaba al crear se
	# recalculaba desde original_move_line_ids, y un activo SIN asiento de
	# origen —importado, de apertura, migrado— nunca podía entrar al 7.3.
	moneda_adquisicion_id = fields.Many2one(
		comodel_name='res.currency',
		string='Moneda de adquisición',
		compute='_compute_datos_adquisicion_me',
		store=True,
		readonly=False,
		help='Moneda del comprobante de compra origen. Si es distinta de '
			'PEN el activo se incluye en la estructura 7.3. Se detecta de los '
			'apuntes de origen; sin ellos (activo importado) se informa a mano.',
	)
	valor_adquisicion_me = fields.Float(
		string='Valor adquisición M.E.',
		digits=(14, 2),
		compute='_compute_datos_adquisicion_me',
		store=True,
		readonly=False,
	)

	def _get_codigo_af(self):
		self.ensure_one()
		return (self.codigo_af or ('AF%s' % self.id))[:24]

	@api.depends('original_move_line_ids', 'original_move_line_ids.currency_id',
		'original_move_line_ids.amount_currency')
	def _compute_datos_adquisicion_me(self):
		"""Moneda y valor de adquisición en M.E. desde los apuntes de origen.

		Con apuntes de origen, ellos mandan: moneda extranjera si alguno la
		tiene, PEN (campos vacíos) si no. SIN apuntes de origen el cálculo
		no tiene de dónde leer y CONSERVA lo informado a mano — es el
		fallback que el docstring anterior prometía y que el campo readonly
		hacía imposible (AF7-02).
		"""
		pen = self.env.ref('base.PEN', raise_if_not_found=False)
		for registro in self:
			if not registro.original_move_line_ids:
				registro.moneda_adquisicion_id = registro.moneda_adquisicion_id
				registro.valor_adquisicion_me = registro.valor_adquisicion_me
				continue
			moneda = False
			valor_me = 0.0
			for linea in registro.original_move_line_ids:
				if linea.currency_id and (not pen or linea.currency_id != pen) \
						and linea.currency_id != linea.company_currency_id:
					moneda = linea.currency_id
					valor_me += abs(linea.amount_currency)
			registro.moneda_adquisicion_id = moneda
			registro.valor_adquisicion_me = valor_me
