# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_round
from datetime import datetime
from collections import defaultdict
from odoo.tools.misc import formatLang
from pytz import timezone
from . import constantes
import logging

_logging = logging.getLogger(__name__)


READONLY_FIELD_STATES = {
	state: [('readonly', True)]
	for state in {'sale', 'done', 'cancel'}
}

LOCKED_FIELD_STATES = {
	state: [('readonly', True)]
	for state in {'done', 'cancel'}
}

INVOICE_STATUS = [
	('upselling', 'Upselling Opportunity'),
	('invoiced', 'Fully Invoiced'),
	('to invoice', 'To Invoice'),
	('no', 'Nothing to Invoice')
]

class ResPartner(models.Model):
	_inherit = "res.partner"


	def _get_name(self):
		""" Utility method to allow name_get to be overrided without re-browse the partner """
		partner = self
		name = partner.name or ''

		if partner.company_name or partner.parent_id:
			if not name and partner.type in ['invoice', 'delivery', 'other']:
				name = dict(self.fields_get(['type'])['type']['selection'])[partner.type]
			if not partner.is_company:
				name = self._get_contact_name(partner, name)
		if self.env.context.get('show_address_only'):
			name = partner._display_address(without_company=True)
		if self.env.context.get('show_address'):
			name = name + "\n" + partner._display_address(without_company=True)
		name = name.replace('\n\n', '\n')
		name = name.replace('\n\n', '\n')
		if self.env.context.get('partner_show_db_id'):
			name = "%s (%s)" % (name, partner.id)
		if self.env.context.get('address_inline'):
			splitted_names = name.split("\n")
			name = ", ".join([n for n in splitted_names if n.strip()])
		if self.env.context.get('show_email') and partner.email:
			name = "%s <%s>" % (name, partner.email)
		if self.env.context.get('html_format'):
			name = name.replace('\n', '<br/>')
		if self.env.context.get('show_vat') and partner.vat:
			name = "%s ‒ %s" % (name, partner.vat)
		return name

class SaleOrder(models.Model):
	_inherit = "sale.order"

	factura_ids = fields.One2many('account.move', 'venta_id', 'Facturas')
	nro_factura = fields.Char("Nro Factura", compute="_get_invoiced", store=False)
	orden_compra = fields.Char("Orden de compra")

	amount_text = fields.Char("Monto en letras", compute="_get_amount_text")
	#diario = fields.Many2one("account.journal", string="Diario")
	fecha_pedido_date = fields.Date("Fecha Pedido (b)", compute="_compute_fecha_date", store=True)

	@api.depends('date_order')
	def _compute_fecha_date(self):
		tz_peru = timezone('America/Lima')
		for reg in self:
			if reg.date_order:
				# Convertir el datetime UTC a la zona horaria de Perú
				fecha_peru = reg.date_order.astimezone(tz_peru)
				# Extraer solo la fecha
				reg.fecha_pedido_date = fecha_peru.date()
			else:
				reg.fecha_pedido_date = False

	@api.depends('amount_total')
	def _get_amount_text(self):
		for invoice in self:
			if invoice.amount_total<2 and invoice.amount_total>=1:
				currency_name = invoice.currency_id.singular_name or invoice.currency_id.plural_name or invoice.currency_id.name or ""
			else:
				currency_name = invoice.currency_id.plural_name or invoice.currency_id.name or ""
			fraction_name = invoice.currency_id.fraction_name or ""
			amount_text = invoice.currency_id.amount_to_text(invoice.amount_total)
			invoice.amount_text= amount_text


	@api.depends('partner_id')
	def _compute_partner_shipping_id(self):
		for order in self:
			order.partner_shipping_id = order.partner_id.address_get(['delivery'])['delivery'] if order.partner_id else False

	def es_valido(self):
		for linea in self.order_line:
			if linea.pe_affectation_code in ['11', '12', '13', '14', '15', '16', '17']:
				if not 'discount' in linea or int(linea.discount) != 100:
					raise UserError("El descuento no es valido, para este tipo de operaciones verifique que tiene activo la opción de descuentos")


	def action_confirm(self):
		valido = self.es_valido()
		res = super(SaleOrder, self).action_confirm()
		return res

	@api.depends('order_line.invoice_lines', 'factura_ids', 'factura_ids.state', 'factura_ids.name')
	def _get_invoiced(self):
		for order in self:
			invoices = order.order_line.invoice_lines.move_id.filtered(lambda r: r.move_type in ('out_invoice', 'out_refund'))
			#invoices = order.factura_ids.filtered(lambda r: r.move_type in ('out_invoice', 'out_refund'))
			#if not invoices:
			#	invoices = order.order_line.invoice_lines.move_id.filtered(lambda r: r.move_type in ('out_invoice', 'out_refund'))

			order.invoice_ids = invoices
			if invoices:
				order.nro_factura = invoices[0].l10n_latam_document_number
			else:
				order.nro_factura = ""
			order.invoice_count = len(invoices)

	def recalcular_nro_factura(self):
		lista = self.env['sale.order'].search([('nro_factura', 'in', [False, ''])])
		for order in lista:
			invoices = order.order_line.invoice_lines.move_id.filtered(lambda r: r.move_type in ('out_invoice', 'out_refund'))
			if invoices:
				order.nro_factura = invoices[0].l10n_latam_document_number
			else:
				order.nro_factura = ""
	
	def _prepare_invoice(self):
		self.ensure_one()
		res = super(SaleOrder, self)._prepare_invoice()
		res['venta_id'] = self.id
		res['orden_compra'] = self.orden_compra
		tipo_documento = self.env['l10n_latam.document.type']
		l10n_latam_document_type_id = False
		partner_id = self.partner_id.parent_id or self.partner_id
		doc_type = partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code
		if not doc_type:
			return res
		
		tipo_doc_id = False
		if doc_type in '6':
			dominio = [('code', '=', '01'), ('sub_type', '=', 'sale'), ('company_id', '=', self.company_id.id)]
			"""if self.diario and self.diario.tipo_doc_permitidos:
				dominio.append(('id', 'in', self.diario.tipo_doc_permitidos.ids))"""
			tipo_doc_id = tipo_documento.search(dominio, limit=1)
			_logging.info(tipo_doc_id)
			if tipo_doc_id:
				l10n_latam_document_type_id = tipo_doc_id.id

		elif doc_type in '1':
			dominio = [('code', '=', '03'), ('sub_type', '=', 'sale'), ('company_id', '=', self.company_id.id)]
			"""if self.diario and self.diario.tipo_doc_permitidos:
				dominio.append(('id', 'in', self.diario.tipo_doc_permitidos.ids))"""
			tipo_doc_id = tipo_documento.search(dominio, limit=1)
			if tipo_doc_id:
				l10n_latam_document_type_id = tipo_doc_id.id
		else:
			dominio = [('code', '=', '03'), ('sub_type', '=', 'sale'), ('company_id', '=', self.company_id.id)]
			"""if self.diario and self.diario.tipo_doc_permitidos:
				dominio.append(('id', 'in', self.diario.tipo_doc_permitidos.ids))"""
			tipo_doc_id = tipo_documento.search(dominio, limit=1)
			if tipo_doc_id:
				l10n_latam_document_type_id = tipo_doc_id.id

		if not tipo_doc_id:
			dominio = [('code', '=', '00'), ('sub_type', '=', 'sale'), ('company_id', '=', self.company_id.id)]
			"""if self.diario and self.diario.tipo_doc_permitidos:
				dominio.append(('id', 'in', self.diario.tipo_doc_permitidos.ids))"""
			tipo_doc_id = tipo_documento.search(dominio, limit=1)
			if tipo_doc_id:
				l10n_latam_document_type_id = tipo_doc_id.id
		
		if l10n_latam_document_type_id:
			res['l10n_latam_document_type_id'] = l10n_latam_document_type_id

		reg = self
		tipo_transaccion = 'contado'
		if reg.payment_term_id:
			tipo_transaccion = reg.payment_term_id.tipo_transaccion or 'contado'

		res['tipo_transaccion'] = tipo_transaccion
		return res

class SaleOrderLine(models.Model):
	_inherit = "sale.order.line"

	pe_affectation_code = fields.Selection(selection='_get_pe_reason_code', string='Tipo de afectación', default='10', help='Tipo de afectación al IGV')

	nro_ov = fields.Char("Nro OV", related="order_id.name", store=True)
	nro_comprobante = fields.Char("Nro Comprobante", related="order_id.nro_factura", store=True)
	cliente = fields.Many2one('res.partner',string='Cliente', related='order_id.partner_id', store=True)
	nro_ruc_dni = fields.Char(related="order_id.partner_id.vat", store=True)
	fecha_pedido = fields.Datetime("Fecha Pedido", related="order_id.date_order", store=True)
	#uom_po_id = fields.Many2one('uom.uom', related="product_id.uom_id")
	#campaign_id = fields.Many2one("utm.campaign", related="order_id.campaign_id", store=True)
	medium_id = fields.Many2one("utm.medium", related="order_id.medium_id", store=True)
	source_id = fields.Many2one("utm.source", related="order_id.source_id", store=True)

	state_id = fields.Many2one("res.country.state", related="order_id.partner_id.state_id", store=True)
	city_id = fields.Many2one("res.city", related="order_id.partner_id.city_id", store=True)
	l10n_pe_district = fields.Many2one("l10n_pe.res.city.district", related="order_id.partner_id.l10n_pe_district", store=True)

	"""@api.depends('invoice_lines.move_id.state', 'invoice_lines.quantity')
	def _compute_qty_invoiced(self):
		for line in self:
			qty_invoiced = 0.0
			for invoice_line in line._get_invoice_lines():
				if invoice_line.move_id.state not in ['cancel', 'annul'] or invoice_line.move_id.payment_state == 'invoicing_legacy':
					if invoice_line.move_id.move_type == 'out_invoice':
						qty_invoiced += invoice_line.product_uom_id._compute_quantity(invoice_line.quantity, line.product_uom)
					elif invoice_line.move_id.move_type == 'out_refund':
						qty_invoiced -= invoice_line.product_uom_id._compute_quantity(invoice_line.quantity, line.product_uom)
			line.qty_invoiced = qty_invoiced

		for sale_line in self:
			if 'pos_order_line_ids' not in sale_line:
				continue
			pos_lines = sale_line.pos_order_line_ids.filtered(lambda order_line: order_line.order_id.state not in ['cancel', 'draft'])
			sale_line.qty_invoiced += sum([self._convert_qty(sale_line, pos_line.qty, 'p2s') for pos_line in pos_lines], 0)"""

	def _prepare_invoice_line(self, **optional_values):
		self.ensure_one()
		res = super(SaleOrderLine, self)._prepare_invoice_line(**optional_values)
		res['pe_affectation_code'] = self.pe_affectation_code
		return res

	@api.model
	def _get_pe_reason_code(self):
		return self.env['pe.datas'].get_selection('PE.CPE.CATALOG7')

	@api.model
	def _get_pe_tier_range(self):
		return self.env['pe.datas'].get_selection('PE.CPE.CATALOG8')

	def _set_free_tax(self):
		if self.pe_affectation_code not in ('10', '20', '30', '40'):
			ids = self.tax_ids.ids
			vat = self.env['account.tax'].search([('l10n_pe_edi_tax_code', '=', constantes.IMPUESTO['gratuito']), ('id', 'in', ids)])
			self.discount = 100
			if not vat:
				res = self.env['account.tax'].search([('l10n_pe_edi_tax_code', '=', constantes.IMPUESTO['gratuito'])], limit=1)
				self.tax_ids = [(6, 0, ids + res.ids)]
		else:
			if int(self.discount) == 100:
				self.discount = 0
			ids = self.tax_ids.ids
			vat = self.env['account.tax'].search([('l10n_pe_edi_tax_code', '=', constantes.IMPUESTO['gratuito']), ('id', 'in', ids)])
		if vat:
			res = self.env['account.tax'].search([('id', 'in', ids), ('id', 'not in', vat.ids)]).ids
			self.tax_ids = [(6, 0, res)]

	@api.onchange('discount')
	def onchange_affectation_code_discount(self):
		for rec in self:
			if rec.discount != 100:
				pass
			elif rec.pe_affectation_code not in ['11', '12', '13', '14', '15', '16', '17', '21', '31', '32', '33', '34', '35', '36']:
				rec.pe_affectation_code = '11'

	@api.onchange('pe_affectation_code')
	def onchange_pe_affectation_code(self):
		# Catalogo 7
		# (10) Gravado - Operación Onerosa; ​(11) Gravado - Retiro por premio; ​(12) Gravado - Retiro por donación; ​ ​ 
		# (13) Gravado - Retiro;​ (14)​ Gravado - Retiro por publicidad; ​ (15) Gravado - Bonificaciones; ​(16)​ Gravado - Retiro por entrega a trabajadores
		if self.pe_affectation_code in ('10'):
			ids = self.tax_ids.filtered(lambda tax: tax.l10n_pe_edi_tax_code == constantes.IMPUESTO['igv']).ids
			res = self.env['account.tax'].search([('l10n_pe_edi_tax_code', '=', constantes.IMPUESTO['igv']), ('id', 'in', ids)])
			if not res:
				res = self.env['account.tax'].search([('l10n_pe_edi_tax_code', '=', constantes.IMPUESTO['igv'])], limit=1)
			self.tax_ids = [(6, 0, ids + res.ids)]
			self._set_free_tax()

		elif self.pe_affectation_code in ('11', '12', '13', '14', '15', '16', '17'):
			self.tax_ids = [(6, 0, [])]
			self._set_free_tax()
		
		# (20) Exonerado - Operación Onerosa;
		elif self.pe_affectation_code in ('20'):
			ids = self.tax_ids.filtered(lambda tax: tax.l10n_pe_edi_tax_code == constantes.IMPUESTO['exonerado']).ids
			res = self.env['account.tax'].search([('l10n_pe_edi_tax_code', '=', constantes.IMPUESTO['exonerado']), ('id', 'in', ids)])
			if not res:
				res = self.env['account.tax'].search([('l10n_pe_edi_tax_code', '=', constantes.IMPUESTO['exonerado'])], limit=1)
			self.tax_ids = [(6, 0, ids + res.ids)]
			self._set_free_tax()
		# (21) Exonerado – Transferencia gratuita
		elif self.pe_affectation_code in ('21'):
			self.tax_ids = [(6, 0, [])]
			self._set_free_tax()
		# (30) Inafecto - Operación Onerosa; ​ ​ 
		elif self.pe_affectation_code in ('30'):
			ids = self.tax_ids.filtered(lambda tax: tax.l10n_pe_edi_tax_code == constantes.IMPUESTO['inafecto']).ids
			res = self.env['account.tax'].search([('l10n_pe_edi_tax_code', '=', constantes.IMPUESTO['inafecto']), ('id', 'in', ids)])
			if not res:
				res = self.env['account.tax'].search([('l10n_pe_edi_tax_code', '=', constantes.IMPUESTO['inafecto'])], limit=1)
			self.tax_ids = [(6, 0, ids + res.ids)]
			#self.discount = 100
		# (31) Inafecto - Retiro por bonificación; ​ ​ (32) Inafecto - Retiro; ​ ​ 
		# (33) Inafecto - Retiro por muestras médicas; ​ ​ (34) Inafecto - Retiro por convenio colectivo; ​ ​ (35) Inafecto - Retiro por premio; ​ ​ 
		# (36) Inafecto - Retiro por publicidad
		elif self.pe_affectation_code in ('31', '32', '33', '34', '35', '36'):
			self.tax_ids = [(6, 0, [])]
			self._set_free_tax()
			#self._set_free_tax()
		# (40) Exportación
		elif self.pe_affectation_code in ('40', ):
			ids = self.tax_ids.filtered(lambda tax: tax.l10n_pe_edi_tax_code == constantes.IMPUESTO['exportacion']).ids
			res = self.env['account.tax'].search([('l10n_pe_edi_tax_code', '=', constantes.IMPUESTO['exportacion']), ('id', 'in', ids)])
			if not res:
				res = self.env['account.tax'].search([('l10n_pe_edi_tax_code', '=', constantes.IMPUESTO['exportacion'])], limit=1)
			self.tax_ids = [(6, 0, ids + res.ids)]
			self._set_free_tax()

	def set_pe_affectation_code(self):
		igv = self.tax_ids.filtered(lambda tax: tax.l10n_pe_edi_tax_code == constantes.IMPUESTO['igv'])
		if self.tax_ids:
			if igv:
				if int(self.discount) == 100:
					self.pe_affectation_code = '11'
					self._set_free_tax()
				else:
					self.pe_affectation_code = '10'
		vat = self.tax_ids.filtered(lambda tax: tax.l10n_pe_edi_tax_code == constantes.IMPUESTO['exonerado'])
		if self.tax_ids:
			if vat:
				if int(self.discount) == 100:
					self.pe_affectation_code = '21'
					self._set_free_tax()
				else:
					self.pe_affectation_code = '20'
		vat = self.tax_ids.filtered(lambda tax: tax.l10n_pe_edi_tax_code == constantes.IMPUESTO['inafecto'])
		if self.tax_ids:
			if vat:
				if int(self.discount) == 100:
					self.pe_affectation_code = '31'
					self._set_free_tax()
				else:
					self.pe_affectation_code = '30'
		vat = self.tax_ids.filtered(lambda tax: tax.l10n_pe_edi_tax_code == constantes.IMPUESTO['exportacion'])
		if self.tax_ids:
			if vat:
				self.pe_affectation_code = '40'

	@api.onchange('product_id', 'tax_ids')
	def _onchange_product_id(self):
		for rec in self.filtered(lambda x: x.product_id):
			rec.set_pe_affectation_code()

		self = self.with_context(check_move_validity=False)

	def get_price_unit(self, all=False):
		self.ensure_one()
		price_unit = self.price_unit
		if all:
			price_unit = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
			tax_id = self.tax_ids
		else:
			tax_id = self.tax_ids.filtered(lambda tax: tax.l10n_pe_edi_tax_code != constantes.IMPUESTO['gratuito'])
		res = tax_id.with_context(round=False).compute_all(price_unit, self.move_id.currency_id, 1, self.product_id, self.move_id.partner_id)
		return res

	def get_price_unit_sunat(self, all=False):
		self.ensure_one()
		price_unit = self.price_unit
		if all:
			price_unit = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
			tax_id = self.tax_ids
		else:
			tax_id = self.tax_ids.filtered(lambda tax: tax.l10n_pe_edi_tax_code != constantes.IMPUESTO['gratuito'])
			
		res = tax_id.with_context(round=False).compute_all_sunat(price_unit, self.move_id.currency_id, 1, self.product_id, self.move_id.partner_id)
		return res
