# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class LineaAfectacionCompra(models.Model):
	_name = 'solse.pe.afectacion.compra'
	_description = 'Linea Afectación compra'

	name = fields.Char('Nombre')
	active = fields.Boolean(default=True)
	sequence = fields.Integer(default=10)
	impuesto_afect_ids = fields.One2many(
		comodel_name='solse.pe.impuesto.afectacion.compra',
		inverse_name='linea_afectacion_id',
		string='Impuesto',
	)
	impuesto_defecto = fields.Many2one(
		'solse.pe.impuesto.afectacion.compra',
		domain="[('id', 'in', impuesto_afect_ids)]",
		string='Impuesto por defecto',
	)
	nro_col_importe_afectacion = fields.Integer('Columna Importe Afectación')
	toma_para_calculo = fields.Selection(
		[('total', 'Total'), ('impuesto', 'Impuesto'), ('base', 'Base')],
		default='base',
		string='Valor para Cálculo',
	)


class ImpuestoAfectacionCompra(models.Model):
	_name = 'solse.pe.impuesto.afectacion.compra'
	_description = 'Impuesto Afectación compra'

	active = fields.Boolean(default=True)
	linea_afectacion_id = fields.Many2one('solse.pe.afectacion.compra', string='Afectación compra')
	impuesto_id = fields.Many2one('account.tax', string='Impuesto')
	name = fields.Char('Nombre', related='impuesto_id.name')
	nro_col_importe_impuesto = fields.Integer('Columna Importe Impuesto')
	toma_para_calculo = fields.Selection(
		[('total', 'Total'), ('impuesto', 'Impuesto'), ('base', 'Base')],
		default='base',
		string='Valor para Cálculo',
	)


class AccountMove(models.Model):
	_inherit = 'account.move'

	def _get_view(self, view_id=None, view_type='form', **options):
		arch, view = super()._get_view(view_id, view_type, **options)
		if view_type != 'form':
			return arch, view

		paso_validacion = False
		ctx = self.env.context

		if ctx.get('params') and 'action' in ctx['params']:
			accion = self.env['ir.actions.act_window'].sudo().search(
				[('id', '=', ctx['params']['action'])], limit=1
			)
			if accion and accion.domain and (
				'in_invoice' in accion.domain or 'in_refund' in accion.domain
			):
				paso_validacion = True
		elif options and 'action_id' in options:
			accion = self.env['ir.actions.act_window'].sudo().search(
				[('id', '=', options['action_id'])], limit=1
			)
			if accion and accion.domain and (
				'in_invoice' in accion.domain or 'in_refund' in accion.domain
			):
				paso_validacion = True
		elif ctx.get('default_move_type') in ['in_invoice', 'in_refund']:
			paso_validacion = True

		if paso_validacion:
			for node in arch.xpath("//field[@name='tipo_afectacion_compra']"):
				node.set('invisible', '0')
				node.set('column_invisible', '0')

		return arch, view


class AccountMoveLine(models.Model):
	_inherit = 'account.move.line'

	tipo_afectacion_compra = fields.Many2one(
		'solse.pe.afectacion.compra',
		string='Tipo de afectación',
		help='Tipo de afectación Compra',
		store=True,
	)

	@api.onchange('tipo_afectacion_compra')
	def onchange_tipo_afectacion_compra(self):
		if self.move_id.move_type not in ['in_invoice', 'in_refund']:
			return
		if not self.tipo_afectacion_compra or not self.tax_ids:
			return

		impuesto_ids_afect = self.tipo_afectacion_compra.impuesto_afect_ids.mapped('impuesto_id').ids
		if self.tax_ids[0]._origin.id in impuesto_ids_afect:
			return

		# A-12 (L3): las líneas de la afectación mezclan impuestos de todas
		# las compañías — el defecto se toma solo de la compañía de la línea.
		compania = self.company_id or self.move_id.company_id
		defecto_m2o = self.tipo_afectacion_compra.impuesto_defecto.impuesto_id
		if defecto_m2o and defecto_m2o.company_id != compania:
			defecto_m2o = False
		por_defecto = defecto_m2o or self.tipo_afectacion_compra.impuesto_afect_ids.mapped(
			'impuesto_id').filtered(lambda t: t.company_id == compania)[:1]
		if por_defecto:
			self.tax_ids = [(6, 0, [por_defecto.id])]

	def _asignar_afectacion_por_impuesto(self):
		"""Asigna tipo_afectacion_compra buscando qué afectación contiene el impuesto."""
		if not self.tax_ids:
			return
		impuesto = self.tax_ids[0]
		for afectacion in self.env['solse.pe.afectacion.compra'].search([]):
			if impuesto._origin.id in afectacion.impuesto_afect_ids.mapped('impuesto_id').ids:
				self.tipo_afectacion_compra = afectacion
				return

	@api.onchange('tax_ids')
	def _onchange_impuesto_compra(self):
		self._asignar_afectacion_por_impuesto()

	@api.onchange('product_id')
	def _onchange_purchase_product_id(self):
		for rec in self.filtered(lambda x: x.product_id):
			rec._asignar_afectacion_por_impuesto()
