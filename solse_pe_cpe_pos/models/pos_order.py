# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_round
from datetime import datetime, timedelta
import pytz
import logging
from dateutil.parser import parse as parse_date
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DATE_FORMAT

tz = pytz.timezone('America/Lima')
_logging = logging.getLogger(__name__)

class PosOrder(models.Model):
	_inherit = "pos.order"

	refund_order_id = fields.Many2one('pos.order', string="POS para el que esta factura es el crédito")
	refund_invoice_id = fields.Many2one('account.move', string="Factura para la que esta factura es el crédito")
	
	partner_shipping_id = fields.Many2one('res.partner', string='Dirección de entrega', readonly=False, help="Delivery address for current sales order.")
	#payment_term_id = fields.Many2one('account.payment.term', string='Términos de pago')
	sale_order_id = fields.Many2one('sale.order', string='Referencia del pedido', copy=False)
	pos_user_id = fields.Many2one(comodel_name='res.users', string='Vendedor POS', help="Persona que utiliza la caja registradora. Puede ser un relevista, un estudiante o un empleado interino.", default=lambda self: self.env.uid)

	pe_credit_note_code = fields.Selection(selection="_get_pe_crebit_note_type", string="Código de nota de crédito")
	pe_invoice_type = fields.Selection([("annul", "Anular"), ("refund", "Nota de crédito")], "Tipo de factura")
	pe_motive = fields.Char("Razón de la nota de crédito")
	pe_invoice_date = fields.Datetime("Hora de la fecha de la factura", copy=False)

	l10n_latam_document_type_id = fields.Many2one('l10n_latam.document.type', string='Tipo de documento')
	invoice_sequence_number = fields.Integer(string='Secuencia de números de factura')
	date_invoice = fields.Date("Fecha de la factura")
	number = fields.Char(string='Número', related="account_move.l10n_latam_document_number", store=True)
	number_ref = fields.Char(string='Número Referencia', related="account_move.reversed_entry_id.l10n_latam_document_number")

	invoice_payment_term_id = fields.Many2one('account.payment.term', string='Plazos de pago', check_company=True, readonly=False)

	@api.constrains("sale_order_id")
	def check_sale_order_id(self):
		for order in self:
			if order.sale_order_id:
				if self.search_count([('sale_order_id','=', order.sale_order_id.id)])>1:
					raise ValidationError(_('La orden de venta ya existe y viola la restricción de campo único'))
	
	def invoice_print(self):
		return self.account_move.action_invoice_print()

	def action_invoice_sent(self):
		res = self.account_move.sudo().action_invoice_sent()
		res['context']['res_id'] = res['context'].pop('default_res_id', False)
		return res

	def _create_invoice(self, move_vals):
		res = super(PosOrder, self)._create_invoice(move_vals)
		res._compute_needed_terms()
		# Solo sumar 1 día si el pago fue "a cuenta de cliente":
		# se detecta porque al menos un método de pago tiene split_transactions=True.
		# Pagos normales (efectivo, tarjeta) NO tienen ese flag → no se tocan.
		es_cuenta_cliente = any(
			pago.payment_method_id.split_transactions
			for pago in self.payment_ids
			if pago.payment_method_id
		)
		if (es_cuenta_cliente
				and res.invoice_date
				and res.invoice_date_due
				and res.invoice_date_due <= res.invoice_date):
			res.write({'invoice_date_due': res.invoice_date + timedelta(days=1)})
		return res

	def _prepare_invoice_vals(self):
		self.ensure_one()
		res = super(PosOrder, self)._prepare_invoice_vals()
		timezone = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
		res['partner_shipping_id'] = self.partner_shipping_id.id
		
		# ✅ CORREGIDO: Pasar solo el ID, no el objeto
		res['fiscal_position_id'] = self.fiscal_position_id.id if self.fiscal_position_id else False
		
		res['invoice_date'] = self.date_invoice or self.date_order.astimezone(timezone).date()
		if not res.get('name') and res.get('type') == 'out_refund':
			res['name'] = '/'
		else:
			res['name'] = self.number

		res['pe_invoice_date'] = self.pe_invoice_date or False
		if self.l10n_latam_document_type_id.id:
			res['l10n_latam_document_type_id'] = self.l10n_latam_document_type_id.id

		if self.invoice_payment_term_id.id:
			res['invoice_payment_term_id'] = self.invoice_payment_term_id.id
			res['tipo_transaccion'] = 'credito'
		
		if res.get('move_type') == 'out_refund':
			orden_e = self.refunded_order_id
			res['reversed_entry_id'] = orden_e.account_move.id
			cod_nota = self.env['pe.datas'].search([('table_code', '=', 'PE.CPE.CATALOG9')], limit=1).code
			res['pe_credit_note_code'] = cod_nota

		if self.refunded_order_id.account_move:
			res['ref'] = _('Reversal of: %s', self.refunded_order_id.account_move.name)
			res['reversed_entry_id'] = self.refunded_order_id.account_move.id

		if self.pe_invoice_type == 'refund':
			res['ref'] = self.pe_motive or False

		return res

	def _prepare_invoice_line(self, line):
		line.set_pe_affectation_code();
		line._get_tax_ids_after_fiscal_position()
		res = super()._prepare_invoice_line(line)
		res.update({
			'pe_affectation_code': line.pe_affectation_code,
		})


	@api.model
	def _get_invoice_lines_values(self, line_values, pos_order_line, move_type):
		pos_order_line.set_pe_affectation_code();
		res = super(PosOrder, self)._get_invoice_lines_values(line_values, pos_order_line, move_type)
		res['pe_affectation_code'] = pos_order_line.pe_affectation_code
		
		return res

	@api.model
	def _order_fields(self, ui_order):
		res = super(PosOrder, self)._order_fields(ui_order)
		res['pe_invoice_date'] = ui_order.get('pe_invoice_date', False)
		res['number'] = ui_order.get('number', False)
		res['number_ref'] = ui_order.get('number_ref', False)
		tipo_doc_venta = ui_order.get('l10n_latam_document_type_id', False)
		plazo_pago = ui_order.get('invoice_payment_term_id', False)
		if tipo_doc_venta:
			res['l10n_latam_document_type_id'] = tipo_doc_venta
			if tipo_doc_venta != '00':
				res['to_invoice'] = True

		if plazo_pago:
			res['invoice_payment_term_id'] = int(plazo_pago)
		reg_datetime = datetime.now(tz)
		fecha = reg_datetime.strftime("%Y-%m-%d")
		res['date_invoice'] = parse_date(ui_order.get('date_invoice', fecha)).strftime(DATE_FORMAT)
		return res

	@api.model
	def _get_pe_crebit_note_type(self):
		return self.env['pe.datas'].get_selection("PE.CPE.CATALOG9")

	@api.onchange('partner_id')
	def _onchange_partner_id(self):
		super(PosOrder, self)._onchange_partner_id()
		self.ensure_one()
		if self.partner_id and self.env.context.get('force_pe_journal'):
			partner_id = self.partner_id.parent_id or self.partner_id
			tipo_documento = self.env['l10n_latam.document.type']
			if partner_id.doc_type in ["6"]:
				tipo_doc_id = tipo_documento.search([('code', '=', '01'), ('sub_type', '=', 'sale')], limit=1)
				if tipo_doc_id:
					self.l10n_latam_document_type_id = tipo_doc_id.id
			else:
				tipo_doc_id = tipo_documento.search([('code', '=', '03'), ('sub_type', '=', 'sale')], limit=1)
				if tipo_doc_id:
					self.l10n_latam_document_type_id = tipo_doc_id.id

	def action_pos_order_invoice(self):
		for order in self:
			if order.pe_invoice_type == 'annul':
				raise ValidationError(
					_("La factura fue cancelada, no puede crear una nota de crédito"))
		res = super(PosOrder, self).action_pos_order_invoice()
		for order_id in self.filtered(lambda x: x.account_move):
			if not order_id.number:
				order_id.number = order_id.account_move.name
		return res

	@api.model
	def _process_order(self, order, existing_order):
		res = super()._process_order(order, existing_order)
		if not res:
			return res
		order = self.browse(res)
		return res

	@api.model
	def generar_enviar_xml_cpe(self, datos):
		datos_rpt = []
		pos_order_id = datos.get('pos_order_id', False)
		for id_reg in pos_order_id:
			reg = self.env['pos.order'].search([('id', '=', id_reg)], limit=1)
			if reg.account_move.pe_cpe_id:
				reg.account_move.pe_cpe_id.generate_cpe()
				invoice_id = reg.account_move
				if reg.account_move.company_id.pe_is_sync and reg.account_move.l10n_latam_document_type_id.is_synchronous:
					reg.account_move.pe_cpe_id.action_send()
				elif (invoice_id.l10n_latam_document_type_id.code in ('07', '08') and invoice_id.origin_doc_code == '03' or invoice_id.l10n_latam_document_type_id.code == '03') and (not invoice_id.l10n_latam_document_type_id.is_synchronous):
					pe_summary_id = self.env['solse.cpe'].get_cpe_async('rc', reg.account_move)
					reg.account_move.pe_summary_id = pe_summary_id.id
			
			dato_respuesta = {
				'serie': reg.account_move.l10n_latam_document_number or reg.account_move.name, 'id_account_move': reg.account_move.id
			}
			if reg.account_move.reversed_entry_id:
				dato_respuesta['serie_referencia'] = reg.account_move.reversed_entry_id.l10n_latam_document_number or reg.account_move.reversed_entry_id.name
			datos_rpt.append(dato_respuesta)
		return datos_rpt

	def refund(self):
		res = super(PosOrder, self).refund()
		order_id = res.get("res_id", False)
		if not order_id:
			return res
		for order in self.browse([order_id]):
			order.refund_order_id = self.id
			order.refund_invoice_id = self.account_move.id
			order.pe_invoice_type = self.env.context.get("default_pe_invoice_type", False)
			if order.pe_invoice_type == 'annul' and order.refund_invoice_id:
				if order.refund_invoice_id.state == 'posted':
					#order.invoice_journal = order.session_id.config_id.journal_id.id
					_logging.info('anular la factura')
				else:
					raise ValidationError("No puedes cancelar la factura, debes crear una nota de crédito")
			else:
				"""invoice_journal = self.invoice_journal.credit_note_id or self.invoice_journal
				order.invoice_journal = invoice_journal.id or False"""
				_logging.info('crear nota de credito')
		return res

	def _prepare_refund_values(self, current_session):
		self.ensure_one()
		datos = {
			'name': self.name + _(' REFUND'),
			'session_id': current_session.id,
			'date_order': fields.Datetime.now(),
			'pos_reference': self.pos_reference,
			'lines': False,
			'amount_tax': -self.amount_tax,
			'amount_total': -self.amount_total,
			'amount_paid': 0,
			'is_total_cost_computed': False
		}
		return datos

	def _add_mail_attachment(self, name, ticket):
		filename = 'Receipt-' + name + '.jpg'
		receipt = self.env['ir.attachment'].create({
			'name': filename,
			'type': 'binary',
			'datas': ticket,
			'res_model': 'pos.order',
			'res_id': self.ids[0],
			'mimetype': 'image/jpeg',
		})
		attachment = [(4, receipt.id)]

		if self.mapped('account_move'):
			factura = self.account_move.ids[0]
			factura = self.env['account.move'].search([("id", "=", factura)])
			datos = factura.obtener_archivos_cpe()
			datos.append(receipt.id)
			return datos

		return attachment

	def action_receipt_to_customer(self, name, client, ticket):
		if not self:
			return False
		if not client.get('email'):
			return False

		message = _("<p>Dear %s,<br/>Here is your electronic ticket for the %s. </p>") % (client['name'], name)

		mail_values = {
			'subject': _('Receipt %s', name),
			'body_html': message,
			'author_id': self.env.user.partner_id.id,
			'email_from': self.env.company.email or self.env.user.email_formatted,
			'email_to': client['email'],
			'attachment_ids': self._add_mail_attachment(name, ticket),
		}

		mail = self.env['mail.mail'].sudo().create(mail_values)
		mail.send()

			

class PosOrderLine(models.Model):
	_inherit = "pos.order.line"
	
	tax_ids = fields.Many2many('account.tax', readonly=False)
	sequence = fields.Integer(string='Secuencia', default=10, readonly=True)
	origin = fields.Char(string='Documento fuente', readonly=True)
	#layout_category_id = fields.Many2one('sale.layout_category', string='Section', readonly=True)
	order_line_id = fields.Many2one('sale.order.line', string='Líneas de pedido', readonly=True)
	#analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')
	pe_affectation_code = fields.Selection(selection='_get_pe_reason_code', string='Tipo de afectación', default='10', help='Tipo de afectación al IGV')

	@api.model
	def _get_pe_reason_code(self):
		return self.env['pe.datas'].get_selection('PE.CPE.CATALOG7')

	def _set_free_tax(self):
		if self.pe_affectation_code not in ('10', '20', '30', '40'):
			ids = self.tax_ids.ids
			vat = self.env['account.tax'].search([('l10n_pe_edi_tax_code', '=', '9996'), ('id', 'in', ids)])
			self.discount = 100
			if not vat:
				res = self.env['account.tax'].search([('l10n_pe_edi_tax_code', '=', '9996')], limit=1)
				impuestos_total = [(6, 0, ids + res.ids)]
				self.tax_ids = impuestos_total
		else:
			if int(self.discount) == 100:
				self.discount = 0
			ids = self.tax_ids.ids
			vat = self.env['account.tax'].search([('l10n_pe_edi_tax_code', '=', '9996'), ('id', 'in', ids)])
		if vat:
			res = self.env['account.tax'].search([('id', 'in', ids), ('id', 'not in', vat.ids)]).ids
			self.tax_ids = [(6, 0, res)]

	def set_pe_affectation_code(self):
		igv = self.tax_ids.filtered(lambda tax: tax.l10n_pe_edi_tax_code == '1000')
		if self.tax_ids:
			if igv:
				if int(self.discount) == 100:
					self.pe_affectation_code = '11'
					self._set_free_tax()
				else:
					self.pe_affectation_code = '10'
		vat = self.tax_ids.filtered(lambda tax: tax.l10n_pe_edi_tax_code == '9997')
		if self.tax_ids:
			if vat:
				if int(self.discount) == 100:
					self.pe_affectation_code = '21'
					self._set_free_tax()
				else:
					self.pe_affectation_code = '20'
		vat = self.tax_ids.filtered(lambda tax: tax.l10n_pe_edi_tax_code == '9998')
		if self.tax_ids:
			if vat:
				if int(self.discount) == 100:
					self.pe_affectation_code = '31'
					self._set_free_tax()
				else:
					self.pe_affectation_code = '30'
		vat = self.tax_ids.filtered(lambda tax: tax.l10n_pe_edi_tax_code == '9995')
		if self.tax_ids:
			if vat:
				self.pe_affectation_code = '40'

	# =========================================================================
	# Nota: el código de gift cards en el ticket POS se maneja desde el frontend
	# (solse_pe_cpe_pos/static/src/app/overrides/models/pos_store.js) usando un
	# search_read estándar a loyalty.card en postProcessLoyalty. No tocamos
	# new_coupon_info nativo de pos_loyalty para evitar conflictos de render
	# en Owl. El bloque de impresión está en static/src/xml/OrderReceipt.xml,
	# leyendo de order.solse_gift_cards.
	#
	# Tampoco creamos un endpoint custom porque Odoo 19 requiere reinicio
	# completo de workers para registrar métodos RPC nuevos, y la GUI/CLI
	# 'update module' no siempre los reinicia. search_read es ORM estándar y
	# siempre está disponible.
	# =========================================================================
