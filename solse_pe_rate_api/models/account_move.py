# -*- coding: utf-8 -*-

from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError
import logging
_logging = logging.getLogger(__name__)

class AccountMove(models.Model):
	_inherit = 'account.move'

	tipo_cambio = fields.Monetary('Tipo de cambio', compute="_compute_tipo_cambio", currency_field='company_currency_id')
	tipo_cambio_dolar = fields.Float("Tipo de cambio (Dolar)", compute="_compute_tipo_cambio", digits=(16, 3), readonly=True)
	currency_available_ids = fields.Many2many('res.currency', compute='_compute_currency_available_ids')
	tipo_cambio_dolar_sistema = fields.Float("Tipo Cambio ($)", compute="_compute_tipo_cambio_sistema", store=False, digits=(16, 3))


	@api.depends('invoice_date')
	def _compute_tipo_cambio_sistema(self):
		for reg in self:
			tipo = 'venta'
			if reg.move_type in ['out_invoice', 'out_refund']:
				tipo = 'venta'
			if reg.move_type in ['in_invoice', 'in_refund']:
				tipo = 'compra'
			moneda_dolar = self.env["res.currency"].search([("name", "=", "USD"), ("rate_type", "=", tipo)], limit=1)
			if not moneda_dolar:
				moneda_dolar = self.env["res.currency"].search([("name", "=", "USD")], limit=1)

			tipo_cambio = 1.0
			if moneda_dolar and reg.invoice_date:
				tipo_cambio = moneda_dolar._convert(1.000, reg.company_id.currency_id, reg.company_id, reg.invoice_date, round=False)
			reg.tipo_cambio_dolar_sistema = tipo_cambio

	@api.depends('move_type')
	def _compute_currency_available_ids(self):
		for record in self:
			if record.move_type in ['out_invoice', 'out_refund', 'out_receipt']:
				currencies = self.env['res.currency']
				currency_available_ids = currencies.search([('rate_type', 'in', ['venta', False])])
			elif record.move_type in ['in_invoice', 'in_refund', 'in_receipt']:
				currency_available_ids = self.env['res.currency'].search(['|', ('rate_type', '=', False), ('rate_type', 'in', ['compra', 'venta'])])
			else:
				currencies = self.env['res.currency'].search([('rate_type', 'in', ['compra', 'venta', False])])
				currency_available_ids = currencies
			record.currency_available_ids = currency_available_ids

	@api.depends('currency_id', 'date', 'company_id')
	def _compute_tipo_cambio(self):
		for reg in self:
			if not reg.date or not reg.currency_id or not reg.company_id:
				reg.tipo_cambio = 1
				continue
			fecha_busqueda = reg.obtener_fecha_tipo_cambio()

			if not fecha_busqueda or fecha_busqueda == False:
				reg.tipo_cambio = 1.000
				reg.tipo_cambio_dolar = 1.000
				continue

			fecha_busqueda = str(fecha_busqueda)

			# TC-02 (L9.1): se leía `rate_pe`, un campo que no declara ningún
			# módulo de la suite ni el nativo — Gabriel confirmó en su base
			# que `res.currency.rate._fields.get('rate_pe')` es None. Toda
			# factura en moneda extranjera con tasa del día reventaba este
			# compute con AttributeError. El nativo `inverse_company_rate`
			# (base/models/res_currency.py:364) es la tasa en soles por
			# unidad, que es lo que este campo muestra; limit=1 porque dos
			# tasas del mismo día no deben tumbar la factura.

			currency_rate_id = [
				('name', '=', fecha_busqueda),
				('company_id','=',reg.company_id.id),
				('currency_id','=',reg.currency_id.id),
			]
			currency_rate_id = self.env['res.currency.rate'].sudo().search(currency_rate_id, limit=1)

			if currency_rate_id:
				reg.tipo_cambio = currency_rate_id.inverse_company_rate
			else:
				reg.tipo_cambio = 1.000
				reg.tipo_cambio_dolar = 1.000

			if reg.currency_id.name != "USD":
				moneda_dolar = self.env["res.currency"].search([("name", "=", "USD")], limit=1)
				dolar_rate_parm = [
					('name','=', fecha_busqueda),
					('company_id','=',reg.company_id.id),
					('currency_id','=', moneda_dolar.id),
				]
				dolar_rate_id = self.env['res.currency.rate'].sudo().search(dolar_rate_parm, limit=1)
				if dolar_rate_id:
					reg.tipo_cambio_dolar = dolar_rate_id.inverse_company_rate
				else:
					reg.tipo_cambio_dolar = 1.000
			else:
				reg.tipo_cambio_dolar = currency_rate_id.inverse_company_rate

	def obtener_fecha_tipo_cambio_anterior(self):
		fecha = self.invoice_date
		if self.move_type == 'out_invoice': # Facturas de cliente
			fecha = self.invoice_date
		elif self.move_type == 'out_refund': # Notas de credito cliente
			fecha = self.reversed_entry_id.invoice_date
		elif self.move_type == 'in_invoice': # Facturas proveedor
			fecha = self.invoice_date
		elif self.move_type == 'in_refund': # Notas de credito proveedor
			fecha = self.reversed_entry_id.invoice_date

		return fecha

	def obtener_fecha_tipo_cambio(self):
		fecha = self.invoice_date
		if self.move_type == 'in_invoice': # Facturas proveedor
			fecha = self.invoice_date
		elif self.move_type == 'in_refund': # Notas de credito proveedor
			fecha = self.reversed_entry_id.invoice_date
		else:
			fecha = self.date

		return fecha



