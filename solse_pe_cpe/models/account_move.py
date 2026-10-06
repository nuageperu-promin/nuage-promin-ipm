# -*- coding: utf-8 -*-

from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import tempfile
import base64
import re
from datetime import datetime, date, timedelta
from odoo.tools import (
	date_utils,
	email_normalize,
	email_split,
	float_compare,
	float_is_zero,
	float_repr,
	format_amount,
	format_date,
	formatLang,
	frozendict,
	get_lang,
	index_exists,
	is_html_empty,
)
from io import StringIO, BytesIO
from collections import defaultdict
from importlib import reload
import xml.etree.cElementTree as ET
from lxml import etree
import json
import sys
import time

import logging
_logging = logging.getLogger(__name__)

try:
	import qrcode
	qr_mod = True
except:
	qr_mod = False

from ast import literal_eval
import socket
from binascii import hexlify
from functools import partial

TYPE2JOURNAL = {
	'out_invoice': 'sale',
	'in_invoice': 'purchase',
	'out_refund': 'sale',
	'in_refund': 'purchase'
}

CODIGOS_IGV_VALIDAR = ('1000', '1016')

def encodestring(datos):
	respuesta = datos
	if not respuesta:
		return respuesta
	if sys.version_info >= (3, 9):
		respuesta = base64.b64encode(datos)
	else:
		respuesta = base64.encodestring(datos)
	return respuesta


class AccountPaymentRegister(models.TransientModel):
	_inherit = 'account.payment.register'

	transaction_number = fields.Char(string='Número de operación')


class AccountPayment(models.Model):
	_inherit = 'account.payment'

	transaction_number = fields.Char(string='Número de operación')


class AccountMove(models.Model):
	_inherit = 'account.move'

	glosa = fields.Char("Glosa")
	pe_additional_total_ids = fields.One2many(
		'account.move.additional.total',
		'invoice_id',
		string='Montos adicionales',
		readonly=True,
		copy=False
	)
	pe_additional_property_ids = fields.One2many(
		'account.move.additional.property',
		'invoice_id',
		string='Propiedad adicional',
		readonly=True,
		copy=False
	)
	pe_taxable_amount = fields.Monetary('Operaciones gravadas', compute='_pe_compute_operations')
	pe_exonerated_amount = fields.Monetary('Operaciones exoneradas', compute='_pe_compute_operations')
	pe_unaffected_amount = fields.Monetary('Operaciones no afectadas', compute='_pe_compute_operations')
	pe_free_amount = fields.Monetary('Operaciones gratuitas', compute='_pe_compute_operations')

	pe_cpe_id = fields.Many2one('solse.cpe', 'SUNAT CPE', copy=False)
	pe_voided_id = fields.Many2one('solse.cpe', 'Documento anulado', copy=False)
	pe_summary_id = fields.Many2one('solse.cpe', 'Resumen del documento', copy=False)

	pe_digest = fields.Char('Digest', related='pe_cpe_id.digest')
	pe_signature = fields.Text('Firma', related='pe_cpe_id.signature')
	pe_response = fields.Char('Respuesta', related='pe_cpe_id.response')
	pe_note = fields.Text('Notas SUNAT', related='pe_cpe_id.note')
	pe_error_code = fields.Selection(string='Error Code', related='pe_cpe_id.error_code', readonly=True)
	
	pe_invoice_code = fields.Char("Codigo comprobante", related="l10n_latam_document_type_id.code", store=True)
	pe_doc_name = fields.Char('Nombre del documento', compute='_get_peruvian_doc_name')
	pe_invoice_state = fields.Selection(string='Estado cpe', related='pe_cpe_id.state', copy=False)
	estado_sunat = fields.Selection(string='Estado Sunat', related='pe_cpe_id.estado_sunat')
	pe_debit_note_code = fields.Selection(selection='_get_pe_debit_note_type', string='Código de nota de debito')
	pe_credit_note_code = fields.Selection(selection='_get_pe_credit_note_type', string='Código de nota de crédito')
	
	# NC/ND con factura de origen EXTERNA a Odoo (migraciones parciales de
	# saldos): con la factura vinculada en `pe_related_ids`, el compute
	# autollena; sin ella, el usuario ingresa serie/número y tipo a mano y
	# el valor PERSISTE (store + readonly=False). El builder del XML ya
	# resuelve ambas ramas. Port del commit v17 7336d2b (+3475fa0),
	# aplicado en v18 (18.0.0.3) y aquí completado para v19: las ramas del
	# XML ya estaban, faltaba la persistencia de los campos.
	origin_doc_code = fields.Selection(
		'_get_origin_doc_code', 'Código de documento de origen',
		compute='_compute_origin_doc', store=True, readonly=False)
	origin_doc_number = fields.Char(
		'Número de documento de origen',
		compute='_compute_origin_doc', store=True, readonly=False)
	origin_doc_id = fields.Many2one(
		'account.move', 'CPE de origen', compute='_compute_origin_doc')

	pe_additional_type = fields.Selection(
		'_get_pe_additional_document',
		string='Documento adicional',
		readonly=True
	)
	pe_additional_number = fields.Char(string='Número adicional', readonly=True)
	pe_export_amount = fields.Monetary('Monto de exportación', compute='_pe_compute_operations')
	pe_sunat_transaction = fields.Selection(
		'_get_pe_pe_sunat_transaction',
		string='Transacción SUNAT',
		default='01',
		readonly=True
	)
	pe_invoice_date = fields.Datetime('Hora/fecha de la factura', copy=False)
	sunat_qr_code = fields.Binary('QR Code', compute='_compute_get_qr_code')
	pe_amount_tax = fields.Monetary('Importe de impuestos', compute='_pe_compute_operations')
	pe_license_plate = fields.Char('Placa', size=10, readonly=True, copy=False)
	pe_condition_code = fields.Selection('_get_pe_condition_code', 'Código de condición', copy=False)
	pe_total_discount = fields.Float('Descuento total', compute='_compute_discount')
	pe_amount_discount = fields.Monetary(string='Descuento (PE)', compute='_compute_discount')
	pe_total_discount_tax = fields.Monetary(string='Impuesto de descuento', compute='_compute_discount')
	pe_charge_total = fields.Monetary(
		'Cargo total',
		compute='get_pe_charge_amount',
		currency_field='company_currency_id'
	)
	# ✅ CORREGIDO: digits como tuple en vez de dp.get_precision
	pe_icbper_amount = fields.Float('ICBPER', compute='_compute_pe_icbper_amount', digits=(16, 2))
	pe_sunat_transaction51 = fields.Selection('_get_pe_sunat_transaction51', string='Tipo de transacción de Sunat', default='0101', readonly=False)

	total_operaciones_gravadas = fields.Monetary(store=False, readonly=True, compute='_compute_amount_reporte')
	total_operaciones_gravadas_dolar = fields.Monetary(store=False, readonly=True, compute='_compute_amount_reporte')
	total_operaciones_exoneradas = fields.Monetary(store=False, readonly=True, compute='_compute_amount_reporte')
	total_operaciones_exoneradas_dolar = fields.Monetary(store=False, readonly=True, compute='_compute_amount_reporte')
	total_operaciones_gratuitas = fields.Monetary(store=False, readonly=True, compute='_compute_amount_reporte')
	total_operaciones_gratuitas_dolar = fields.Monetary(store=False, readonly=True, compute='_compute_amount_reporte')
	total_operaciones_inafectas = fields.Monetary(store=False, readonly=True, compute='_compute_amount_reporte')
	total_operaciones_inafectas_dolar = fields.Monetary(store=False, readonly=True, compute='_compute_amount_reporte')
	total_operaciones_exportadas = fields.Monetary(store=False, readonly=True, compute='_compute_amount_reporte')
	total_operaciones_exportadas_dolar = fields.Monetary(store=False, readonly=True, compute='_compute_amount_reporte')

	sunat_estado_manual = fields.Char('Estado SUNAT')

	pe_related_ids = fields.Many2many("account.move", string="Facturas relacionadas", compute="_get_related_ids")
	no_enviar_rnoaceptados = fields.Boolean("No enviar en Reporte de No Aceptados")

	# ✅ CORREGIDO: digits como tuple
	tipo_cambio_dolar_sistema = fields.Float(
		"Tipo Cambio ($)",
		compute="_compute_tipo_cambio_sistema",
		store=False,
		digits=(16, 3)
	)

	fecha_nota_credito_proveedor = fields.Date("Fecha emisión del Proveedor")
	fue_offline = fields.Boolean("Fue offiline")

	tax_totals_pe = fields.Binary(
		string="Totales Impuestos (PE)",
		compute='_compute_tax_totals_pe',
		inverse='_inverse_tax_totals_pe',
		exportable=False,
	)

	forzar_resumen = fields.Boolean("Forzar resumen")

	


	def obtener_guia(self):
		dato = ""
		if 'guide_number' in self:
			dato = self.guide_number
		if not dato and 'pe_stock_name' in self:
			dato = self.pe_stock_name
		return dato


	def get_order_compra(self):
		oc_compra = self.ref
		if not oc_compra:
			sale_ids = self.invoice_line_ids.mapped('sale_line_ids').mapped('order_id')
			for sale in sale_ids:
				oc_compra = sale.origin or sale.client_order_ref or sale.name
				break

		return oc_compra or ""

	def _get_l10n_latam_documents_domain(self):
		self.ensure_one()
		sub_type = False
		if self.move_type in ['in_invoice', 'in_refund']:
			sub_type = "purchase"
		elif self.move_type in ['out_invoice', 'out_refund']:
			sub_type = "sale"
		internal_types = []
		invoice_type = self.move_type
		if invoice_type in ['out_refund', 'in_refund']:
			internal_types = ['credit_note']
		elif invoice_type in ['out_invoice', 'in_invoice']:
			internal_types = ['invoice', 'debit_note']
		if self.debit_origin_id:
			internal_types = ['debit_note']
		internal_types += ['all']
		dominio = [('internal_type', 'in', internal_types), ('country_id', '=', self.company_id.account_fiscal_country_id.id)]
		if sub_type:
			dominio.append(("sub_type", "=", sub_type))

		if self.company_id:
			dominio.append(("company_id", "=", self.company_id.id))

		if self.journal_id.tipo_doc_permitidos:
			dominio.append(("id", "in", self.journal_id.tipo_doc_permitidos.ids))
		return dominio


	def _inverse_tax_totals_pe(self):
		if self.env.context.get('skip_invoice_sync'):
			return
		with self._sync_dynamic_line(
			existing_key_fname='term_key',
			needed_vals_fname='needed_terms',
			needed_dirty_fname='needed_terms_dirty',
			line_type='payment_term',
			container={'records': self},
		):
			for move in self:
				if not move.is_invoice(include_receipts=True):
					continue
				invoice_totals = move.tax_totals

				for amount_by_group_list in invoice_totals['groups_by_subtotal'].values():
					for amount_by_group in amount_by_group_list:
						tax_lines = move.line_ids.filtered(lambda line: line.tax_group_id.id == amount_by_group['tax_group_id'])

						if tax_lines:
							first_tax_line = tax_lines[0]
							tax_group_old_amount = sum(tax_lines.mapped('amount_currency'))
							sign = -1 if move.is_inbound() else 1
							delta_amount = tax_group_old_amount * sign - amount_by_group['tax_group_amount']

							if not move.currency_id.is_zero(delta_amount):
								first_tax_line.amount_currency -= delta_amount * sign
			self._compute_amount()

	@api.depends(
		'invoice_line_ids.currency_rate',
		'invoice_line_ids.tax_base_amount',
		'invoice_line_ids.tax_line_id',
		'invoice_line_ids.price_total',
		'invoice_line_ids.price_subtotal',
		'invoice_payment_term_id',
		'partner_id',
		'currency_id',
	)
	def _compute_tax_totals_pe(self):
		""" Computed field used for custom widget's rendering.
			Only set on invoices.
		"""
		for move in self:
			if move.is_invoice(include_receipts=True):
				base_lines, _tax_lines = move._get_rounded_base_and_tax_lines()
				move.tax_totals_pe = self.env['account.tax']._get_tax_totals_summary(
					base_lines=base_lines,
					currency=move.currency_id,
					company=move.company_id,
					cash_rounding=move.invoice_cash_rounding_id,
				)
				move.tax_totals_pe['display_in_company_currency'] = (
					move.company_id.display_invoice_tax_company_currency
					and move.company_currency_id != move.currency_id
					and move.tax_totals_pe['has_tax_groups']
					and move.is_sale_document(include_receipts=True)
				)
			else:
				# Non-invoice moves don't support that field (because of multicurrency: all lines of the invoice share the same currency)
				move.tax_totals_pe = None


	def procesar_respuesta_impuestos(self, datos):
		"""
		{'amount_untaxed': 122.4, 'amount_total': 133.63, 'formatted_amount_total': 'S/\xa0133.63', 'formatted_amount_untaxed': 'S/\xa0122.40', 'groups_by_subtotal': defaultdict(<class 'list'>, {'Op. Gravadas': [{'group_key': 2, 'tax_group_id': 2, 'tax_group_name': 'IGV', 'tax_group_amount': 11.23, 'tax_group_base_amount': 62.4, 'formatted_tax_group_amount': 'S/\xa011.23', 'formatted_tax_group_base_amount': 'S/\xa062.40'}, {'group_key': 8, 'tax_group_id': 8, 'tax_group_name': 'INA', 'tax_group_amount': 60.0, 'tax_group_base_amount': 60.0, 'formatted_tax_group_amount': 'S/\xa060.00', 'formatted_tax_group_base_amount': 'S/\xa060.00'}]}), 'subtotals': [{'name': 'Op. Gravadas', 'amount': 62.400000000000006, 'formatted_amount': 'S/\xa062.40'}], 'subtotals_order': ['Op. Gravadas'], 'display_tax_base': True}
		"""

		json_valores = {
			"INA": False,
			"EXO": False,
			"GRA": False,
			"OTR": False,
			"DES": False,
			"IGV": False,
		}
		json_nombres = {
			"INA": "Op. Inafectas",
			"EXO": "Op. Exoneradas",
			"GRA": "Op. Gratuitas",
			"OTR": "Otros Cargos",
			"DES": "Descuentos",
			"IGV": "IGV",
		}
		monto_gratuito = 0
		monto_descuento = 0
		grupos = datos['groups_by_subtotal']
		for item in grupos:
			datos_grupo = grupos[item]
			for reg in datos_grupo:
				if reg['tax_group_name'] == 'INA':
					reg['tax_group_name'] = "Op. Inafectas"
					json_valores["INA"] = True

				if reg['tax_group_name'] == 'EXO':
					reg['tax_group_name'] = "Op. Exoneradas"
					json_valores["EXO"] = True

				if reg['tax_group_name'] == 'GRA':
					json_valores["GRA"] = True
					monto_gratuito = abs(sum(line.price_unit * line.quantity for line in self.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '9996'))
					#reg['tax_group_base_amount'] = monto_gratuito * -1
					reg['tax_group_name'] = "Op. Gratuitas"
					reg['tax_group_amount'] = monto_gratuito
					reg['formatted_tax_group_amount'] = formatLang(self.env, monto_gratuito, currency_obj=self.currency_id) or ''
					reg['formatted_tax_group_base_amount'] = formatLang(self.env, monto_gratuito, currency_obj=self.currency_id) or ''

				if reg['tax_group_name'] == 'OTR':
					reg['tax_group_name'] = "Otros Cargos"
					json_valores["OTR"] = True

				if reg['tax_group_name'] == 'DES':
					reg['tax_group_name'] = "Descuentos"
					json_valores["DES"] = True

				if reg['tax_group_name'] == 'IGV':
					json_valores["IGV"] = True


		contador = 100
		for value in json_valores:
			contador = contador + 1
			if json_valores[value]:
				continue

			if not self.journal_id.mostrar_impuestos_en_cero:
				continue

			monto_grupo = 0
			if value == "DES":
				monto_grupo = total_operaciones_gratuitas = abs(sum((line.price_unit * line.quantity) - line.price_subtotal for line in self.invoice_line_ids if line.discount and line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code != '9996'))
				monto_descuento = monto_grupo
				
			for item in grupos:
				datos_grupo = grupos[item]
				clave_grupo = self.env['account.tax.group'].search([("name", "=", value)], limit=1)
				if not clave_grupo:
					clave_grupo = contador
				else:
					clave_grupo = clave_grupo.id

				monto_texto = formatLang(self.env, monto_grupo, currency_obj=self.currency_id) or ''
				datos_nuevos = {
					'group_key': clave_grupo, 
					'tax_group_id': clave_grupo, 
					'tax_group_name': json_nombres[value], 
					'tax_group_amount': monto_grupo, 
					'tax_group_base_amount': 0, 
					'formatted_tax_group_amount': monto_texto, 
					'formatted_tax_group_base_amount': monto_texto
				}
				datos_grupo.append(datos_nuevos)

		amount_total = datos['amount_total'] #- monto_gratuito
		datos['monto_gratuito'] = monto_gratuito
		datos['monto_descuento'] = monto_descuento


		return datos

	@api.onchange('pe_credit_note_code')
	def _onchange_pe_credit_note_code(self):
		if self.pe_credit_note_code == '13':
			for linea in self.invoice_line_ids:
				linea.price_unit = 0.0

	@api.model
	def get_view(self, view_id=None, view_type='form', **options):
		res = super(AccountMove, self).get_view(view_id, view_type, **options)
		if view_type in ['form']:
			type = self.env.context.get('default_move_type')
			if type == 'in_refund':
				root = etree.fromstring(res['arch'])
				for el in root.iter('field'):
					if el.attrib.get('name') in ['payment_reference']:
						el.attrib.update({'string': 'Nota de crédito del proveedor'})
						break
				res.update({'arch': etree.tostring(root, encoding='utf8')})

			paso_validacion = False
			if self.env.context.get('params') and 'action' in self.env.context['params']:
				parametros = self.env.context['params']
				accion = self.env['ir.actions.act_window'].sudo().search([('id', '=', parametros['action'])])
				if accion and accion.domain and ('out_invoice' in accion.domain or 'out_refund' in accion.domain):
					paso_validacion = True

			elif options and 'action_id' in options:
				accion = self.env['ir.actions.act_window'].sudo().search([('id', '=', options['action_id'])])
				if accion and accion.domain and ('out_invoice' in accion.domain or 'out_refund' in accion.domain):
					paso_validacion = True

			elif self.env.context.get('default_move_type'):
				move_type = self.env.context.get('default_move_type')
				if move_type in ['out_invoice', 'out_refund']:
					paso_validacion = True

			#{'action': 198, 'cids': 1, 'id': '', 'menu_id': 101, 'model': 'account.move', 'view_type': 'form'}
			if paso_validacion:
				root = etree.fromstring(res['arch'])
				for el in root.iter('field'):
					if el.attrib.get('name') in ['pe_affectation_code']:
						json_mod = {
							'column_invisible': False,
						}
						el.attrib.update({'column_invisible': '0', 'invisible': '0', 'modifiers': json.dumps(json_mod)})
						break

				res.update({'arch': etree.tostring(root, encoding='utf8')})

		return res

	@api.depends('invoice_date')
	def _compute_tipo_cambio_sistema(self):
		for reg in self:
			moneda_dolar = self.env["res.currency"].search([("name", "=", "USD")], limit=1)
			tipo_cambio = 1.0
			if reg.invoice_date:
				tipo_cambio = moneda_dolar._convert(1.000, reg.company_id.currency_id, reg.company_id, reg.invoice_date, round=False)
			reg.tipo_cambio_dolar_sistema = tipo_cambio


	@api.depends('invoice_line_ids', 'invoice_line_ids.price_subtotal', 'invoice_line_ids.tax_ids.amount', 'currency_id', 'company_id', 'invoice_date', 'move_type')
	def _compute_amount_reporte(self,detener=False):	
		#salida = super(AccountMove, self)._compute_amount_reporte()
		"""
			1000 Total valor de venta – operaciones exportadas
			1001 Total valor de venta - operaciones gravadas
			1002 Total valor de venta - operaciones inafectas
			1003 Total valor de venta - operaciones exoneradas
			1004 Total valor de venta – Operaciones gratuitas
			1005 Sub total de venta
			2001 Percepciones
			2002 Retenciones
			2003 Detracciones
			2004 Bonificaciones
			2005 Total descuentos
			3001 FISE (Ley 29852) Fondo Inclusión Social Energético
		"""
		for reg in self:
			if reg.move_type in ['out_invoice', 'in_refund']:
				total_operaciones_gravadas = abs(sum(line.credit for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '1000'))
				total_operaciones_gravadas_dolar = abs(sum(line.amount_currency for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '1000'))

				total_operaciones_gravadas_descontar = abs(sum(line.debit for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '1000' and line.debit))
				total_operaciones_gravadas_dolar_descontar = abs(sum(line.amount_currency for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '1000' and line.debit))
				total_operaciones_gravadas = total_operaciones_gravadas - total_operaciones_gravadas_descontar
				total_operaciones_gravadas_dolar = total_operaciones_gravadas_dolar - total_operaciones_gravadas_dolar_descontar

				total_operaciones_exoneradas = abs(sum(line.credit for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '9997'))
				total_operaciones_exoneradas_dolar = abs(sum(line.amount_currency for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '9997'))

				total_operaciones_gratuitas = abs(sum(line.price_unit * line.quantity for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '9996'))
				total_operaciones_gratuitas_dolar = abs(sum(line.amount_currency * line.quantity for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '9996'))

				total_operaciones_inafectas = abs(sum(line.credit for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '9998'))
				total_operaciones_inafectas_dolar = abs(sum(line.amount_currency for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '9998'))

				total_operaciones_exportadas = abs(sum(line.credit for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '9995'))
				total_operaciones_exportadas_dolar = abs(sum(line.amount_currency for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '9995'))
			else:
				total_operaciones_gravadas = abs(sum(line.debit for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '1000'))
				total_operaciones_gravadas_dolar = abs(sum(line.amount_currency for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '1000'))

				total_operaciones_gravadas_descontar = abs(sum(line.credit for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '1000' and line.credit))
				total_operaciones_gravadas_dolar_descontar = abs(sum(line.amount_currency for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '1000' and line.credit))
				total_operaciones_gravadas = total_operaciones_gravadas - total_operaciones_gravadas_descontar
				total_operaciones_gravadas_dolar = total_operaciones_gravadas_dolar - total_operaciones_gravadas_dolar_descontar

				total_operaciones_exoneradas = abs(sum(line.debit for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '9997'))
				total_operaciones_exoneradas_dolar = abs(sum(line.amount_currency for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '9997'))

				total_operaciones_gratuitas = abs(sum(line.price_unit * line.quantity for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '9996'))
				total_operaciones_gratuitas_dolar = abs(sum(line.amount_currency * line.quantity for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '9996'))

				total_operaciones_inafectas = abs(sum(line.debit for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '9998'))
				total_operaciones_inafectas_dolar = abs(sum(line.amount_currency for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '9998'))

				total_operaciones_exportadas = abs(sum(line.debit for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '9995'))
				total_operaciones_exportadas_dolar = abs(sum(line.amount_currency for line in reg.invoice_line_ids if line.tax_ids and line.tax_ids[0].l10n_pe_edi_tax_code == '9995'))

			if reg.move_type in ['in_refund', 'out_refund']:
				total_operaciones_gravadas = total_operaciones_gravadas * -1
				total_operaciones_gravadas_dolar = total_operaciones_gravadas_dolar * -1
				total_operaciones_exoneradas = total_operaciones_exoneradas * -1
				total_operaciones_exoneradas_dolar = total_operaciones_exoneradas_dolar * -1
				total_operaciones_gratuitas = total_operaciones_gratuitas * -1
				total_operaciones_gratuitas_dolar = total_operaciones_gratuitas_dolar * -1
				total_operaciones_inafectas = total_operaciones_inafectas * -1
				total_operaciones_inafectas_dolar = total_operaciones_inafectas_dolar * -1
				total_operaciones_exportadas = total_operaciones_exportadas * -1
				total_operaciones_exportadas_dolar = total_operaciones_exportadas_dolar * -1

			reg.total_operaciones_gravadas = round(total_operaciones_gravadas, 2)
			reg.total_operaciones_gravadas_dolar = round(total_operaciones_gravadas_dolar, 2)
			reg.total_operaciones_exoneradas = round(total_operaciones_exoneradas, 2)
			reg.total_operaciones_exoneradas_dolar = round(total_operaciones_exoneradas_dolar, 2)
			reg.total_operaciones_gratuitas = round(total_operaciones_gratuitas, 2)
			reg.total_operaciones_gratuitas_dolar = round(total_operaciones_gratuitas_dolar, 2)
			reg.total_operaciones_inafectas = round(total_operaciones_inafectas, 2)
			reg.total_operaciones_inafectas_dolar = round(total_operaciones_inafectas_dolar, 2)
			reg.total_operaciones_exportadas = round(total_operaciones_exportadas, 2)
			reg.total_operaciones_exportadas_dolar = round(total_operaciones_exportadas_dolar, 2)


	def obtener_datos_entidad_emisora(self):
		invoice_id = self
		empresa = invoice_id.company_id
		province_id = empresa.partner_id.city_id
		province_id = province_id.name.strip() if province_id else ''
		if not empresa.partner_id.zip:
			raise UserError("Se debe establecer un ubigeo para la empresa")
		if not empresa.partner_id.street:
			raise UserError("Se debe establecer una dirección para la empresa")
		if not empresa.parent_id:
			datos = {
				'comercial_name': empresa.partner_id.commercial_name.strip() or '-',
				'legal_name': empresa.partner_id.legal_name.strip() or '-',
				'ubigeo': empresa.partner_id.zip,
				'pe_branch_code': '0000',
				'province_id': province_id,#empresa.partner_id.city_id.name.strip(),
				'state_id': empresa.partner_id.state_id.name,
				'district_id': empresa.partner_id.l10n_pe_district.name,
				'street_id': empresa.partner_id.street,
				'country_code': empresa.partner_id.country_id.code,
				'country_code': empresa.partner_id.country_id.code,
				'tipo_doc': empresa.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code,
				'nro_doc': empresa.partner_id.doc_number or empresa.partner_id.vat,
			}
		else:
			sucursal = invoice_id.company_id
			empresa = invoice_id.company_id.parent_id
			province_id = sucursal.parent_id.partner_id.city_id
			province_id = province_id.name.strip() if province_id else ''
			datos = {
				'comercial_name': sucursal.partner_id.commercial_name.strip() or '-',
				'legal_name': empresa.partner_id.legal_name.strip() or '-',
				'ubigeo': sucursal.partner_id.zip,
				'pe_branch_code': sucursal.company_registry,
				'province_id': province_id,#empresa.partner_id.city_id.name.strip(),
				'state_id': sucursal.partner_id.state_id.name,
				'district_id': sucursal.partner_id.l10n_pe_district.name,
				'street_id': sucursal.partner_id.street,
				'country_code': sucursal.partner_id.country_id.code,
				'tipo_doc': empresa.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code,
				'nro_doc': empresa.partner_id.doc_number or empresa.partner_id.vat,
			}
		return datos

	@api.onchange('invoice_payment_term_id', 'invoice_date_due', 'invoice_date')
	def _onchange_termino_pago(self):
		reg = self
		if reg.invoice_payment_term_id:
			reg.tipo_transaccion = reg.invoice_payment_term_id.tipo_transaccion or 'contado'
		elif reg.invoice_date_due and reg.invoice_date and reg.invoice_date_due > reg.invoice_date:
			reg.tipo_transaccion = 'credito'
		else:
			reg.tipo_transaccion = 'contado'


	def obtener_cuotas_pago(self):
		"""Cuotas del cronograma para el bloque FormaPago del XML (obs. 3319).

		Esta es la versión que EJECUTA la suite: `solse_pe_accountant`
		carga después de `solse_pe_cpe` y pisa a la del emisor, así que la
		lógica definitiva vive aquí (y el emisor mantiene una equivalente
		para instalaciones sin este módulo).

		Historia del bug que motivó la reescritura: la versión anterior
		restaba la detracción a la PRIMERA línea del cronograma y ADEMÁS
		saltaba la línea del split comparando su importe — con el split
		activo (1212 neto + 12123 detracción) el descuento se aplicaba dos
		veces, la suma de cuotas quedaba en neto − detracción y SUNAT
		observaba 3319 en toda factura con detracción al crédito.

		Reglas:
		  * la línea del split de detracción/retención NO es cuota: se
			excluye por cuenta configurada en la compañía o, si la
			configuración falta (pasa más de lo que debería), por importe
			exacto — solo cuando hay más de una línea, porque con una sola
			esa línea es el total;
		  * la resta legacy sobre la primera cuota corre ÚNICAMENTE cuando
			no se excluyó nada (facturas sin split);
		  * cuotas en cero o negativas se descartan;
		  * el último céntimo se ajusta contra el neto pendiente para que
			la suma cierre exacta.
		"""
		invoice = self
		company = invoice.company_id
		en_base = invoice.currency_id.id == company.currency_id.id
		monto_det = (invoice.monto_detraccion if en_base
					 else invoice.monto_detraccion_base)
		monto_ret = (invoice.monto_retencion if en_base
					 else invoice.monto_retencion_base)
		neto = (invoice.monto_neto_pagar if en_base
				else invoice.monto_neto_pagar_base)
		redondear = invoice.currency_id.round

		cuentas_excluidas = {
			cuenta.id for cuenta in (
				getattr(company, 'cuenta_detracciones', False),
				getattr(company, 'cuenta_detracciones_compra', False),
				getattr(company, 'cuenta_retenciones', False),
				getattr(company, 'cuenta_retenciones_venta', False),
			) if cuenta
		}

		lineas = invoice.line_ids.filtered(
			lambda l: l.account_id.account_type
			in ('asset_receivable', 'liability_payable'))
		varias = len(lineas) > 1

		cuotas = []
		excluidas = 0
		for rec_line in lineas:
			amount = redondear(rec_line.amount_currency)
			es_split = rec_line.account_id.id in cuentas_excluidas
			if not es_split and varias:
				# Configuración ausente: la línea del split se reconoce
				# por su importe exacto. Nunca con línea única, que ahí
				# el importe es el total.
				es_split = bool(
					(monto_det and redondear(monto_det) == amount)
					or (monto_ret and redondear(monto_ret) == amount))
			if es_split:
				excluidas += 1
				continue
			cuotas.append({
				'amount': amount,
				'currency_name': rec_line.move_id.currency_id.name,
				'date_maturity': rec_line.date_maturity,
			})

		if not excluidas and cuotas and (monto_det or monto_ret):
			cuotas[0]['amount'] = redondear(
				cuotas[0]['amount'] - monto_det - monto_ret)
		cuotas = [c for c in cuotas if c['amount'] > 0]

		if cuotas:
			desvio = redondear(
				neto - sum(c['amount'] for c in cuotas))
			if desvio and abs(desvio) <= 0.05:
				cuotas[-1]['amount'] = redondear(
					cuotas[-1]['amount'] + desvio)
		return cuotas

	def _get_related_ids(self):
		for move_id in self:
			related_ids = move_id.invoice_line_ids.mapped('pe_invoice_id').ids or []
			if move_id.debit_origin_id:
				related_ids.append(move_id.debit_origin_id.id)
			if move_id.reversed_entry_id:
				related_ids.append(move_id.reversed_entry_id.id)
			move_id.pe_related_ids = related_ids

	@api.onchange('l10n_latam_document_type_id')
	def _onchange_l10n_latam_document_type_id(self):
		self.pe_invoice_code = self.l10n_latam_document_type_id.code


	def _get_address_details(self, partner):
		self.ensure_one()
		address = ''
		if partner.l10n_pe_district:
			address = "%s" % (partner.l10n_pe_district.name)
		if partner.city:
			address += ", %s" % (partner.city)
		if partner.state_id.name:
			address += ", %s" % (partner.state_id.name)
		if partner.zip:
			address += ", %s" % (partner.zip)
		if partner.country_id.name:
			address += ", %s" % (partner.country_id.name)
		reload(sys)
		html_text = str(tools.plaintext2html(address, container_tag=True))
		data = html_text.split('p>')
		if data:
			return data[1][:-2]
		return False
		
	def _get_street(self, partner):
		self.ensure_one()
		address = ''
		if partner.street:
			address = "%s" % (partner.street)
		if partner.street2:
			address += ", %s" % (partner.street2)
		reload(sys)
		html_text = str(tools.plaintext2html(address, container_tag=True))
		data = html_text.split('p>')
		if data:
			return data[1][:-2]
		return False

	@api.model
	def _compute_pe_icbper_amount(self):
		for invoice_id in self:
			pe_icbper_amount = 0.0
			for line in invoice_id.invoice_line_ids:
				pe_icbper_amount += invoice_id.currency_id.round(line.pe_icbper_amount)

			invoice_id.pe_icbper_amount = pe_icbper_amount

	@api.model
	def get_pe_charge_amount(self):
		for invoice_id in self:
			pe_charge_total = 0.0
			for line in invoice_id.invoice_line_ids:
				pe_charge_total += line.pe_charge_amount

			invoice_id.pe_charge_total = pe_charge_total

	@api.model
	def _get_pe_condition_code(self):
		return self.env['pe.datas'].get_selection('PE.CPE.CATALOG19')

	@api.onchange('pe_license_plate')
	def onchange_pe_license_plate(self):
		for line in self.invoice_line_ids.filtered(lambda x: x.product_id and x.product_id.require_plate):
			line.pe_license_plate = self.pe_license_plate

	@api.onchange('invoice_date')
	def onchange_pe_license_plate(self):
		self.action_date_assign()

	@api.model
	def action_date_assign(self):
		for inv in self:
			today = fields.Date.context_today(self)
			if not inv.invoice_date:
				inv.pe_invoice_date = today
			else:
				local_date = fields.Date.from_string(today)
				dt = local_date == fields.Date.from_string(inv.invoice_date) and today or str(inv.invoice_date) + ' 23:55:00'
				inv.pe_invoice_date = dt

	@api.model
	def _get_pe_pe_sunat_transaction(self):
		return self.env['pe.datas'].get_selection('PE.CPE.CATALOG17')

	@api.model
	def _get_pe_additional_document(self):
		return self.env['pe.datas'].get_selection('PE.CPE.CATALOG12')

	@api.depends('pe_related_ids')
	def _compute_origin_doc(self):
		for rec in self:
			inv = rec.pe_related_ids
			rec.origin_doc_id = inv[0].id if inv else False
			if inv:
				# Factura de origen en Odoo: autollenar desde el registro.
				rec.origin_doc_number = inv[0].name
				rec.origin_doc_code = inv[0].pe_invoice_code
			else:
				# Sin factura vinculada: respetar el valor manual. Con
				# store=True + readonly=False, reasignar el propio valor
				# es la forma idiomática de decirle al ORM «no tocar»;
				# omitir la asignación lo dejaría en False.
				rec.origin_doc_number = rec.origin_doc_number
				rec.origin_doc_code = rec.origin_doc_code

	@api.model
	def _get_origin_doc_code(self):
		return self.env['pe.datas'].get_selection('PE.TABLA10')

	@api.model
	def _get_pe_credit_note_type(self):
		return self.env['pe.datas'].get_selection('PE.CPE.CATALOG9')

	@api.model
	def _get_pe_debit_note_type(self):
		return self.env['pe.datas'].get_selection('PE.CPE.CATALOG10')

	@api.depends('amount_total', 'currency_id', 'invoice_line_ids', 'invoice_line_ids.amount_discount')
	def _compute_discount(self):
		for reg in self:
			total_discount = 0.0
			ICPSudo = self.env['ir.config_parameter'].sudo()
			default_deposit_product_id = literal_eval(ICPSudo.get_param('sale.default_deposit_product_id', default='False'))
			discount = 0.0
			total_discount_tax = 0.0
			for line in reg.invoice_line_ids:
				if line.display_type == 'rounding':
					continue
				if line.price_total < 0.0:
					price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
					taxes = line.tax_ids.compute_all(price, reg.currency_id, line.quantity, line.product_id, reg.partner_id)
					if default_deposit_product_id:
						if default_deposit_product_id != line.product_id.id:
							if taxes:
								for tax in taxes.get('taxes', []):
									total_discount_tax += tax.get('amount', 0.0)

							total_discount += line.price_total
					if not default_deposit_product_id:
						total_discount += line.price_total
						if taxes:
							for tax in taxes.get('taxes', []):
								total_discount_tax += tax.get('amount', 0.0)

				discount += line.amount_discount

			reg.pe_total_discount = abs(total_discount)
			reg.pe_total_discount_tax = abs(total_discount_tax)
			reg.pe_amount_discount = discount

	@api.depends('pe_invoice_code')
	def _get_peruvian_doc_name(self):
		for invoice_id in self:
			if invoice_id.pe_invoice_code and invoice_id.is_cpe:
				doc = self.env['pe.datas'].search([('table_code', '=', 'PE.CPE.CATALOG1'), ('code', '=', invoice_id.pe_invoice_code)])
				pe_doc_name = doc.name and doc.name + ' Electronica' or ''
				invoice_id.pe_doc_name = pe_doc_name.title()
			elif invoice_id.l10n_latam_document_type_id:
				invoice_id.pe_doc_name = invoice_id.l10n_latam_document_type_id.report_name
			else:
				invoice_id.pe_doc_name = ""

	@api.depends('name', 'l10n_latam_document_type_id.is_cpe', 'l10n_latam_document_type_id.code', 'amount_tax', 'amount_total', 'invoice_date', 'partner_id.doc_number', 'partner_id.doc_type', 'company_id.partner_id.doc_number')
	def _compute_get_qr_code(self):
		for invoice in self:
			if not all((invoice.name != '/', invoice.l10n_latam_document_type_id.is_cpe, qr_mod)):
				invoice.sunat_qr_code = ''
			elif invoice.l10n_latam_document_number and len(invoice.l10n_latam_document_number.split('-')) > 1 and invoice.invoice_date:
				res = [
				 invoice.company_id.partner_id.doc_number or '-',
				 invoice.l10n_latam_document_type_id.code or '',
				 invoice.l10n_latam_document_number.split('-')[0] or '',
				 invoice.l10n_latam_document_number.split('-')[1] or '',
				 str(invoice.amount_tax), str(invoice.amount_total),
				 fields.Date.to_string(invoice.invoice_date), invoice.partner_id.doc_type or '-',
				 invoice.partner_id.doc_number or '-', '']

				qr_string = '|'.join(res)
				#20605310321|03|B001|00000001|1620.0|10620.0|2022-10-16|6|10712214789|
				qr = qrcode.QRCode(version=1, error_correction=(qrcode.constants.ERROR_CORRECT_Q))
				qr.add_data(qr_string)
				qr.make(fit=True)
				image = qr.make_image()
				tmpf = BytesIO()
				image.save(tmpf, 'png')
				codigo = encodestring(tmpf.getvalue())
				invoice.sunat_qr_code = codigo
			else:
				invoice.sunat_qr_code = ''

	@api.model
	def _get_pe_invoice_code(self):
		return self.env['pe.datas'].get_selection('PE.CPE.CATALOG1')

	@api.constrains('move_type', 'l10n_latam_document_type_id')
	def _check_invoice_type_document_type(self):
		#self._compute_l10n_latam_document_type()
		#self._onchange_partner_id()
		for rec in self.filtered('l10n_latam_document_type_id.internal_type'):
			internal_type = rec.l10n_latam_document_type_id.internal_type
			invoice_type = rec.move_type
			if internal_type in ['debit_note', 'invoice'] and invoice_type in ['out_refund', 'in_refund']:
				raise ValidationError(_('You can not use a %s document type with a refund invoice', internal_type))
			elif internal_type == 'credit_note' and invoice_type in ['out_invoice', 'in_invoice']:
				raise ValidationError(_('You can not use a %s document type with a invoice', internal_type))

	def validate_sunat_invoice(self):
		if self.pe_sunat_transaction51:
			if self.pe_sunat_transaction51[:2] == '02':
				if self.partner_id.country_id.code == 'PE':
					raise UserError('El cliente %s para exportación no es valido' % self.partner_id.display_name)
				if self.pe_invoice_code in ('01', ):
					for line in self.invoice_line_ids:
						if line.pe_affectation_code != '40':
							raise UserError('El tipo de afectacion del producto %s debe ser Exportacion' % line.name)

		if self.pe_invoice_code in ('01', ):
			for line in self.invoice_line_ids:
				if line.pe_affectation_code == '40' and line.move_id.pe_sunat_transaction51[:2] != '02':
					raise UserError('Para la linea con el producto %s debe ser Exportacion' % line.name)

		for linea in self.invoice_line_ids:
			# CC-PRODUCTIVO (rama casos-cpe, 2026-09-25, H-CC-20): el 17 es
			# «Gravado – IVAP», onerosa; exigirle descuento 100 % bloqueaba
			# toda venta con IVAP (medido FAC-36).
			if linea.pe_affectation_code in ['11', '12', '13', '14', '15', '16']:
				if not 'discount' in linea or int(linea.discount) != 100:
					raise UserError("El descuento no es valido, para este tipo de operaciones verifique que tiene activo la opción de descuentos")

		for line in self.invoice_line_ids.filtered(lambda ln: ln.display_type not in ['rounding']):
			if line.display_type not in ['product']:
				continue

			if line.product_id.type in ['combo']:
				continue

			#if line.display_type in ['product'] and (line.quantity == 0.0 or line.price_unit == 0.0):
			if line.display_type in ['product'] and (line.quantity == 0.0):
				es_icbper = True if len(line.tax_ids) == 1 and line.tax_ids[0].l10n_pe_edi_tax_code in ['7152'] else False
				nota_credito_especial = True if line.move_type == 'out_refund' and line.move_id.pe_credit_note_code == '13' else False
				if not es_icbper and not nota_credito_especial and line.product_id.type != 'combo':
					raise UserError('La cantidad o precio del producto %s debe ser mayor a 0.0' % line.name)
			if not line.tax_ids:
				if line.quantity > 0:
					raise UserError('Es Necesario definir por lo menos un impuesto para el pruducto %s' % line.name)
				if line.product_id.require_plate and not (line.pe_license_plate or self.pe_license_plate):
					raise UserError('Es Necesario registrar el numero de placa para el pruducto %s' % line.name)

		if self.move_type in ('in_invoice', 'in_refund'):
			# Salvaguarda por si se invoca desde otro punto: las validaciones
			# de este metodo son para comprobantes que EMITIMOS nosotros. La
			# factura de un proveedor no tiene por que cumplir nuestras
			# reglas de serie ni llevar nuestros datos de emisor.
			return True

		if not self.l10n_latam_document_number:
			raise UserError("No se pudo establecer el correlativo para la factura")

		# La serie de un comprobante propio es alfanumerica de cuatro
		# caracteres y empieza con F (facturas y sus notas) o B (boletas y las
		# suyas). Esto aplica a lo que emitimos nosotros; la serie del
		# proveedor puede empezar con cualquier letra —E001 del portal SUNAT,
		# por ejemplo— y no se valida aqui porque no la emitimos.
		if not re.match('^(B|F){1}[A-Z0-9]{3}\\-\\d+$', self.l10n_latam_document_number):
			raise UserError(
				'El número del comprobante «%s» no cumple el estándar de '
				'SUNAT.\n\n'
				'La serie debe tener cuatro caracteres y empezar con F para '
				'facturas y notas de factura, o con B para boletas y notas de '
				'boleta. Por ejemplo: F001-00000123 o B001-00000123.\n\n'
				'Se corrige en el tipo de documento (si usa prefijo '
				'personalizado) o en la secuencia del diario, en '
				'Configuración / Contabilidad / Diarios.'
				% (self.l10n_latam_document_number or self.name))
		if self.partner_id.parent_id:
			if self.partner_id.doc_number:
				raise UserError('Para generar este comprobante debe cambiar los datos  de contacto {} \nPor los datos de la Empresa principal {}'.format(self.partner_id.name, self.partner_id.parent_id.name))
		if self.pe_invoice_code in ('03', ) or self.reversed_entry_id.pe_invoice_code in ('03', ):
			doc_type = self.partner_id.doc_type or '-'
			doc_number = self.partner_id.doc_number or '-'
			#if doc_type == '6':
			#	if doc_number[:2] != '10':
			#		raise UserError('El dato ingresado no cumple con el estandar \nTipo: %s \nNumero de documento: %s\nDeberia emitir una Factura. Cambiar en Factura/Otra Informacion/Diario' % (
			#		 doc_type, doc_number))
			amount = self.company_id.sunat_amount or 0
			if self.amount_total >= amount:
				if doc_type in ['0', '-']:
					raise UserError('El dato ingresado no cumple con el estandar \nTipo: %s \nNumero de documento: %s\nSon obligatorios el Tipo de Doc. y Numero para montos iguales o mayores a %s' % (
					 doc_type, doc_number, str(amount)))
		if self.pe_invoice_code in ('01', ) or self.reversed_entry_id.pe_invoice_code in ('01', ):
			doc_type = self.partner_id.doc_type or self.partner_id.parent_id.doc_type or '-'
			doc_number = self.partner_id.doc_number or self.partner_id.parent_id.doc_number or '-'
			if not doc_number or doc_number == '-':
				doc_number = self.partner_id.vat or self.partner_id.parent_id.vat or '-'
			if doc_type not in ['6', '0'] or not doc_number:
				if not (self.pe_sunat_transaction51 and self.pe_sunat_transaction51[:2] == '02' and doc_type in ['7', '4']):
					raise UserError(' El numero de documento de identidad del receptor debe ser RUC \nTipo: %s \nNumero de documento: %s' % (
				 doc_type, doc_number))
			if doc_type == '6':
				partner_id = self.partner_id or self.partner_id.parent_id
				is_valid = partner_id.validate_ruc(doc_number)
				if not is_valid:
					raise UserError(' El ruc %s no es valido' % str(doc_number))
				if partner_id.state != 'ACTIVO' or partner_id.condition != 'HABIDO':
					partner_id.with_context(force_update=1)._doc_number_change()
					if partner_id.state != 'ACTIVO' or partner_id.condition != 'HABIDO':
						raise UserError(' El cliente no tiene condicion de ACTIVO/HABIDO %s %s' % (doc_type, doc_number))

			# La exigencia de identificar al receptor por encima del umbral es
			# de las BOLETAS. En una factura de exportacion el receptor es un
			# no domiciliado y su tipo de documento es justamente «0»
			# (DOC.TRIB.NO.DOM.SIN.RUC), que unas lineas mas arriba este mismo
			# metodo acepta como valido. Sin esta excepcion, toda exportacion
			# por encima de S/ 700 se bloqueaba: la validacion se contradecia
			# consigo misma.
			es_exportacion = (self.pe_sunat_transaction51 or '')[:2] == '02'
			amount = self.company_id.sunat_amount or 0
			if self.amount_total >= amount and not es_exportacion:
				if doc_type in ['0', '-'] or doc_number in ['0', '-']:
					raise UserError('El dato ingresado no cumple con el estandar \nTipo: %s \nNumero de documento: %s\nSon obligatorios el Tipo de Doc. y Numero' % (
					 doc_type, doc_number))
		date_invoice = fields.Datetime.from_string(self.pe_invoice_date or self.invoice_date)
		today = fields.Datetime.context_timestamp(self, datetime.now())
		"""days = today.replace(tzinfo=None) - date_invoice
		if days.days > 6:
			if self.pe_invoice_code in ('01', ) or self.reversed_entry_id.pe_invoice_code in ('01', ):
				raise UserError('La fecha de emision no puede ser menor a 6 dias de hoy ni mayor a la fecha de hoy.')
		if days.days < 0:
			raise UserError('La fecha de emision no puede ser menor a 6 dias de hoy ni mayor a la fecha de hoy.')"""
		company_id = self.company_id.partner_id

	
	def validar_impuestos(self):
		"""
		Valida la coherencia del IGV/IVAP del comprobante usando la tasa REAL de
		cada impuesto (18%, tasa reducida MYPE, IVAP 4%, etc.), no una tasa fija.

		Se trabaja sobre `taxes_data` de las base lines (Odoo 19), que ya traen:
		  - la base propia de cada impuesto (resuelve ISC con include_base_amount)
		  - el monto final, incluyendo ediciones manuales de las líneas de impuesto
		Así, las líneas exoneradas, inafectas, gratuitas y las negativas (gift card)
		quedan fuera solas, porque no llevan un impuesto 1000/1016.
		"""
		self.ensure_one()
		if not self.is_invoice(include_receipts=True):
			return True

		base_lines, _lineas_impuesto = self._get_rounded_base_and_tax_lines()

		base_gravada = 0.0
		igv_esperado = 0.0
		igv_calculado = 0.0
		for base_line in base_lines:
			for dato in base_line['tax_details']['taxes_data']:
				impuesto = dato['tax']
				if impuesto.l10n_pe_edi_tax_code not in CODIGOS_IGV_VALIDAR:
					continue
				if impuesto.amount_type != 'percent':
					continue
				base = dato['base_amount_currency']
				base_gravada += base
				igv_esperado += base * impuesto.amount / 100.0
				igv_calculado += dato['tax_amount_currency']

		if self.currency_id.is_zero(base_gravada):
			return True

		# Tolerancia por redondeos: max(1 unidad, 0.1% de la base gravada)
		tolerancia = max(1.0, abs(base_gravada) * 0.001)
		diferencia = abs(igv_calculado - igv_esperado)
		if diferencia > tolerancia:
			simbolo = self.currency_id.symbol or ''
			raise UserError(_(
				"El cálculo de impuestos no corresponde.\n"
				"Base gravada: %(simbolo)s %(base).2f\n"
				"IGV esperado (según tasa de cada impuesto): %(simbolo)s %(esperado).2f\n"
				"IGV calculado: %(simbolo)s %(calculado).2f\n"
				"Diferencia: %(simbolo)s %(diferencia).2f",
				simbolo=simbolo,
				base=base_gravada,
				esperado=igv_esperado,
				calculado=igv_calculado,
				diferencia=diferencia,
			))
		return True

		
	def _post(self, soft=True):
		# El parametro `soft` se propaga tal como llega. Antes se forzaba
		# `soft=True`, lo que descartaba el `soft=False` que envia
		# `action_post`: con posteo suave Odoo NO contabiliza los asientos con
		# fecha posterior a hoy, los deja en borrador sin avisar. En la
		# practica, una factura fechada para manana quedaba sin contabilizar y
		# nadie se enteraba hasta cerrar el mes.
		res = super(AccountMove, self)._post(soft=soft)
		for invoice_id in self:
			invoice_id.action_date_assign()
			invoice_id.validar_impuestos()
			# Solo se emite lo PROPIO. El tipo de documento distingue compra de
			# venta con `sub_type`, y para eso se duplica el codigo 01 en una
			# «Factura de compra»; pero si por configuracion una compra queda
			# con el tipo de venta, sin este filtro entraba en el flujo de
			# emision: se validaba como si fuera nuestra, se le creaba un
			# `solse.cpe` y se habria enviado a SUNAT un comprobante que no
			# nos corresponde emitir. El sintoma tipico es «el numero de la
			# factura ingresada no cumple con el estandar» sobre la serie del
			# proveedor.
			#
			# Se comprueba por partida doble: el tipo de movimiento y el
			# subtipo del documento. El primero no depende de que la
			# configuracion sea correcta; el segundo respeta la intencion de
			# quien configuro los tipos.
			es_venta = (
				invoice_id.move_type in ('out_invoice', 'out_refund')
				and invoice_id.l10n_latam_document_type_id.sub_type != 'purchase'
			)
			if (es_venta and invoice_id.is_cpe
					and invoice_id.l10n_latam_document_type_id.code
					in ('01', '03', '07', '08')):
				to_write = {}
				# Validaciones preventivas: avisan de lo que SUNAT rechazaria
				# antes de generar el XML, diciendo que campo corregir. Ver
				# `account_move_validacion.py`.
				invoice_id.validar_antes_de_emitir()
				invoice_id.validate_sunat_invoice()
				invoice_id._get_additionals()
				if not invoice_id.pe_cpe_id:
					cpe_id = self.env['solse.cpe'].create_from_invoice(invoice_id)
					invoice_id.pe_cpe_id = cpe_id.id
				else:
					cpe_id = invoice_id.pe_cpe_id
				if invoice_id.l10n_latam_document_type_id.code == '03' or invoice_id.origin_doc_code == '03':
					if not invoice_id.pe_condition_code:
						invoice_id.pe_condition_code = '1'
					else:
						invoice_id.pe_condition_code = '2'

				if self.env.context.get('is_pos_invoice') and not invoice_id.fue_offline:
					continue

				if 'pos_order_ids' in self.env['account.move']._fields:
					if self.pos_order_ids and not invoice_id.fue_offline:
						continue

				cpe_id.generate_cpe()
				if invoice_id.company_id.pe_is_sync:
					# validamos que cuando sea desde el POS no se envie por este metodo ya que en ese caso se envia por el propio modulo del POS
					if invoice_id.l10n_latam_document_type_id.is_synchronous:
						cpe_id.action_send()
				
				if (invoice_id.l10n_latam_document_type_id.code in ('07', '08') and invoice_id.origin_doc_code == '03' or invoice_id.l10n_latam_document_type_id.code == '03') and (not invoice_id.l10n_latam_document_type_id.is_synchronous):
					pe_summary_id = self.env['solse.cpe'].get_cpe_async('rc', invoice_id)
					invoice_id.pe_summary_id = pe_summary_id.id

				if invoice_id.company_id.enviar_email:
					invoice_id.enviarCorreoCPE()
		
		#_logging.info("generar al final")
		#res.pe_cpe_id.generate_cpe()
		return res

	def agregegar_a_resumen(self):
		invoice_id = self
		if (invoice_id.l10n_latam_document_type_id.code in ('07', '08') and invoice_id.origin_doc_code == '03' or invoice_id.l10n_latam_document_type_id.code == '03') and (not invoice_id.l10n_latam_document_type_id.is_synchronous):
			pe_summary_id = self.env['solse.cpe'].get_cpe_async('rc', invoice_id)
			invoice_id.pe_summary_id = pe_summary_id.id

	# usado para enviar el correo una vez confirmada la factura
	def enviarCorreoCPE(self):
		if self.partner_id.email:
			account_mail = self.action_invoice_sent()
			context = account_mail.get('context')
			if not context:
				pass
			else:
				template_id = account_mail['context'].get('default_template_id')
				if not template_id:
					pass
				else:
					attachment_ids = []
					if context.get('default_attachment_ids', False):
						for attach in context.get('default_attachment_ids'):
							attachment_ids += attach[2]
					mail_id = self.env['mail.template'].browse(template_id)
					mail_id.send_mail((self.id), force_send=True, email_values={'attachment_ids': attachment_ids})

	@api.model
	def _get_pe_error_code(self):
		return self.env['pe.datas'].get_selection('PE.CPE.ERROR')

	def tiene_codigo(self, linea, codigo):
		for impuesto in linea.tax_ids:
			if impuesto.l10n_pe_edi_tax_code == codigo:
				return True

		return False


	@api.depends('currency_id', 'partner_id', 'invoice_line_ids', 'invoice_line_ids.tax_ids', 'invoice_line_ids.quantity', 'invoice_line_ids.product_id', 'invoice_line_ids.discount')
	def _pe_compute_operations(self):
		for invoice_id in self:
			total_1001 = 0
			total_1002 = 0
			total_1003 = 0
			total_1004 = 0
			pe_export_amount = 0
			pe_tax_amount = 0.0
			round_curr = invoice_id.currency_id.round
			for line in invoice_id.invoice_line_ids:
				price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
				total_excluded = line.tax_ids.compute_all(price_unit, invoice_id.currency_id, line.quantity, line.product_id, invoice_id.partner_id)['total_excluded']
				if line.pe_affectation_code == '10':
					total_1001 += total_excluded
				elif line.pe_affectation_code == '20':
					total_1002 += total_excluded
				elif line.pe_affectation_code == '30':
					total_1003 += total_excluded
				elif line.pe_affectation_code == '40':
					pe_export_amount += total_excluded
				else:
					#price_unit = line.price_unit
					price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
					total_excluded = line.tax_ids.compute_all(price_unit, invoice_id.currency_id, line.quantity, line.product_id, invoice_id.partner_id)['total_excluded']
					total_1004 += total_excluded

			invoice_id.pe_taxable_amount = invoice_id.currency_id.round(total_1001)
			invoice_id.pe_exonerated_amount = invoice_id.currency_id.round(total_1002)
			invoice_id.pe_unaffected_amount = invoice_id.currency_id.round(total_1003)
			invoice_id.pe_free_amount = total_1004
			invoice_id.pe_export_amount = invoice_id.currency_id.round(pe_export_amount)
			pe_amount_tax = sum(round_curr(line.price_total) for line in invoice_id.line_ids.filtered(lambda tax: tax.tax_line_id.l10n_pe_edi_tax_code in ('1000', '1016', '2000', '9999')))
			sub_total = sum(round_curr(line.price_subtotal) for line in invoice_id.invoice_line_ids.filtered(lambda linea: invoice_id.tiene_codigo(linea, '1000')))
			price_total = sum(round_curr(line.price_total) for line in invoice_id.invoice_line_ids.filtered(lambda linea: invoice_id.tiene_codigo(linea, '1000')))
			igv = price_total - sub_total
			invoice_id.pe_amount_tax = igv - invoice_id.pe_charge_total

	@api.depends('currency_id')
	def _get_additionals(self):
		self.ensure_one()
		for total in self.pe_additional_total_ids:
			total.unlink()

		for property in self.pe_additional_property_ids:
			property.unlink()

		amount_total = self.pe_taxable_amount + self.pe_exonerated_amount + self.pe_unaffected_amount + self.pe_export_amount + self.amount_tax
		if amount_total > 0:
			if self.l10n_latam_document_type_id.code in ('01', '03'):
				amount_text = self.currency_id.amount_to_text(amount_total)
				self.env['account.move.additional.property'].create({'code':'1000', 'value':amount_text,  'invoice_id':self.id})
		total_1001 = {'code':'1001', 
		 'total_amount':self.pe_taxable_amount,  'invoice_id':self.id}
		total_1002 = {'code':'1002', 
		 'total_amount':self.pe_exonerated_amount,  'invoice_id':self.id}
		total_1003 = {'code':'1003',  'total_amount':self.pe_unaffected_amount + self.pe_export_amount, 
		 'invoice_id':self.id}
		total_1004 = {'code':'1004',  'total_amount':self.pe_free_amount, 
		 'invoice_id':self.id}
		self.env['account.move.additional.total'].create(total_1001)
		self.env['account.move.additional.total'].create(total_1002)
		self.env['account.move.additional.total'].create(total_1003)
		if self.pe_free_amount > 0:
			self.env['account.move.additional.total'].create(total_1004)
			self.env['account.move.additional.property'].create({'code':'1002', 'value':'TRANSFERENCIA GRATUITA',  'invoice_id':self.id})
		igv = self.invoice_line_ids.mapped('tax_ids').filtered(lambda tax: tax.l10n_pe_edi_tax_code == '1000')
		company_id = self.company_id.partner_id
		if not igv:
			line_ids = self.invoice_line_ids.filtered(lambda line: line.product_id.type in ('consu', 'product'))
			if self.invoice_line_ids.filtered(lambda line: line.product_id == False):
				if line_ids:
					if self.invoice_line_ids.mapped('tax_ids').filtered(lambda tax: tax.l10n_pe_edi_tax_code == '9997'):
						self.env['account.move.additional.property'].create({'code':'2001',  'value':'BIENES TRANSFERIDOS EN LA AMAZONÍA REGIÓN SELVA PARA SER CONSUMIDOS EN LA MISMA',  'invoice_id':self.id})
			line_ids = self.invoice_line_ids.filtered(lambda line: line.product_id.type in ('service', ))
			if line_ids:
				if self.invoice_line_ids.mapped('tax_ids').filtered(lambda tax: tax.l10n_pe_edi_tax_code == '9997'):
					self.env['account.move.additional.property'].create({'code':'2002',  'value':'SERVICIOS TRANSFERIDOS EN LA AMAZONÍA REGIÓN SELVA PARA SER CONSUMIDOS EN LA MISMA',  'invoice_id':self.id})
		total_discount = self.pe_total_discount - self.pe_total_discount_tax
		if total_discount > 0:
			total_2005 = {'code':'2005', 
			 'total_amount':total_discount, 
			 'invoice_id':self.id}
			self.env['account.move.additional.total'].create(total_2005)

	# button_cancel es llamado desde button_anull que esta en el modulo base solse_pe_edi
	def button_cancel(self):
		res = super().button_cancel()
		if res:
			for invoice_id in self:
				if 'pos_order_ids' in self.env['account.move']._fields:
					if invoice_id.pos_order_ids:
						raise UserError('Esta factura debe ser anulada desde el modulo "punto de venta" ')
				
				if invoice_id.is_cpe and invoice_id.pe_cpe_id and invoice_id.pe_cpe_id.state not in ('draft', 'cancel'):
					raise UserError('No puede cancelar este documento, esta enviado a sunat')

		return res

	def procesar_rechazados(self):
		if self.pe_cpe_id.estado_sunat in ['09', '07']:
			self.write({'annul': True, 'state': 'annul'})
			return True
		return False

	# anular factura
	def button_annul(self):
		state_temp = self.state
		res = super().button_annul()
		if not res:
			self.write({'state': state_temp})
			return False
		for invoice_id in self:
			if not invoice_id.is_cpe:
				continue
			if not invoice_id.pe_cpe_id:
				continue
			if invoice_id.pe_cpe_id.state in ('draft', 'cancel'):
				continue
			if invoice_id.procesar_rechazados():
				continue
			pe_summary_id = False
			invoice_id.pe_cpe_id.estado_sunat = '13'
			if invoice_id.l10n_latam_document_type_id.code == '03' or invoice_id.origin_doc_code == '03':
				invoice_id.pe_condition_code = '3'
				if invoice_id.pe_summary_id.state == 'done':
					pe_summary_id = self.env['solse.cpe'].get_cpe_async('rc', invoice_id, True)
					invoice_id.pe_summary_id = pe_summary_id.id
				elif not invoice_id.pe_summary_id:
					pe_summary_id = self.env['solse.cpe'].get_cpe_async('rc', invoice_id, True)
					invoice_id.pe_summary_id = pe_summary_id.id
			else:
				invoice_date = fields.Datetime.from_string(invoice_id.pe_invoice_date or invoice_id.invoice_date)
				today = fields.Datetime.context_timestamp(self, datetime.now())
				days = today.replace(tzinfo=None) - invoice_date
				if days.days > 7:
					raise UserError('No puede cancelar este documento, solo se puede hacer antes de las 72 horas contadas a partir del día siguiente de la fecha consignada en el CDR (constancia de recepción).\nPara cancelar este Documento emita una Nota de Credito')
				voided_id = self.env['solse.cpe'].get_cpe_async('ra', invoice_id)
				if not voided_id:
					raise UserError('No se pudo crear el resumen de anulación, vuelva a intentar.\nDe persistir el error comunicarse con el area de Sistemas.')
				
				invoice_id.pe_voided_id = voided_id.id
				if invoice_id.l10n_latam_document_type_id.is_synchronous_anull:
					voided_id.action_generate()
					voided_id.action_send()
					time.sleep(3)
					try:
						voided_id.action_done()
					except Exception as e:
						pass
				
			if pe_summary_id and invoice_id.l10n_latam_document_type_id.is_synchronous_anull:
				pe_summary_id.action_generate()
				pe_summary_id.action_send()
				time.sleep(3)
				try:
					pe_summary_id.action_done()
				except Exception as e:
					pass
		return res

	# pasar a borrador
	def button_draft(self):
		states = self.mapped('state')
		res = super().button_draft()
		if self.filtered(lambda inv: inv.pe_cpe_id and inv.pe_cpe_id.state in ('send', 'verify', 'done') and 'cancel' not in states):
			raise UserError('Este documento ha sido informado a la SUNAT no se puede cambiar a borrador')
		for move in self:
			self.env['solse.cpe'].search([('id', '=', move.pe_cpe_id.id)]).unlink()
		self.write({'pe_summary_id': False})
		return res

	@api.model
	def pe_credit_debit_code(self, invoice_ids, credit_code, debit_code):
		for invoice in self.browse(invoice_ids):
			if credit_code:
				invoice.pe_credit_note_code = credit_code
			else:
				if debit_code:
					invoice.pe_debit_note_code = debit_code

	def obtener_archivos_cpe(self):
		attachment_ids = []
		Attachment = self.env['ir.attachment']
		if self.l10n_latam_document_type_id.is_cpe and self.pe_cpe_id:
			if self.pe_cpe_id.datas_sign_fname:
				arc_n1 = Attachment.search([('res_id', '=', self.id), ('name', 'like', self.pe_cpe_id.datas_sign_fname + '%')], limit=1)
				if not arc_n1:
					attach = {}
					attach['name'] = self.pe_cpe_id.datas_sign_fname
					attach['type'] = 'binary'
					attach['datas'] = self.pe_cpe_id.datas_sign
					attach['res_model'] = 'mail.compose.message'
					attachment_id = self.env['ir.attachment'].create(attach)
					attachment_ids = []
					attachment_ids.append(attachment_id.id)
				else:
					attachment_ids.append(arc_n1.id)
			nombre = '%s.pdf' % self.pe_cpe_id.get_document_name()
			arc_n2 = Attachment.search([('res_id', '=', self.id), ('name', 'like', nombre + '%')], limit=1)
			if not arc_n2:
				attach = {}
				result_pdf, type = self.env['ir.actions.report']._get_report_from_name('account.report_invoice')._render_qweb_pdf('account.report_invoice', res_ids=self.ids)
				attach['name'] = '%s.pdf' % self.pe_cpe_id.get_document_name()
				attach['type'] = 'binary'
				attach['datas'] = encodestring(result_pdf)
				attach['res_model'] = 'mail.compose.message'
				attachment_id = self.env['ir.attachment'].create(attach)
				attachment_ids.append(attachment_id.id)
			else:
				attachment_ids.append(arc_n2.id)

			if self.pe_cpe_id.datas_response_fname:
				arc_n3 = Attachment.search([('res_id', '=', self.id), ('name', 'like', self.pe_cpe_id.datas_response_fname + '%')], limit=1)
				if not arc_n3:
					attach = {}
					attach['name'] = self.pe_cpe_id.datas_response_fname
					attach['type'] = 'binary'
					attach['datas'] = self.pe_cpe_id.datas_response
					attach['res_model'] = 'mail.compose.message'
					attachment_id = self.env['ir.attachment'].create(attach)
					attachment_ids.append(attachment_id.id)
				else:
					attachment_ids.append(arc_n3.id)

		return attachment_ids

	# retorna el json con los datos necesarios para la accion "enviar por correo"
	def action_invoice_sent(self):
		res = super().action_invoice_sent()
		self.ensure_one()
		if self.l10n_latam_document_type_id.is_cpe and self.pe_cpe_id:
			template = self.env.ref('solse_pe_cpe.email_template_edi_invoice_cpe2', False)
			
			attachment_ids = self.obtener_archivos_cpe()

			vals = {}
			vals['default_use_template'] = bool(template)
			vals['default_template_id'] = template and template.id or False
			vals['default_attachment_ids'] = [(6, 0, attachment_ids)]
			res['context'].update(vals)
		return res

	# metodo usado desde la busqueda de la web que usas los clientes para revisar las facturas que se les han emitido
	def get_public_cpe(self):
		self.ensure_one()
		res = {}
		if self.l10n_latam_document_type_id.is_cpe:
			if self.pe_cpe_id:
				#temporal = self.env['ir.actions.report']._get_report_from_name('account.report_invoice')
				#result_pdf, type = temporal._render_qweb_pdf('account.report_invoice', res_ids=self.ids)
				reporte = self.env['ir.actions.report']#._get_report_from_name('account.report_invoice')
				result_pdf, type = reporte._render_qweb_pdf('account.report_invoice', self.ids)
				res['datas_sign'] = str(encodestring(self.pe_cpe_id.datas_sign), 'utf-8')
				res['datas_invoice'] = str(encodestring(result_pdf), 'utf-8')
				res['name'] = self.pe_cpe_id.get_document_name()
			else:
				reporte = self.env['ir.actions.report']#._get_report_from_name('account.report_invoice')
				result_pdf, type = reporte._render_qweb_pdf('account.report_invoice', self.ids)
				res['datas_sign'] = ""
				res['datas_invoice'] = str(encodestring(result_pdf), 'utf-8')
				res['name'] = self.name

		return res


	# Tarea programada para "Envio Automatico Facturas/Boletas/Notas" por correo electronico
	def action_send_mass_mail(self):
		today = fields.Date.context_today(self)
		invoice_ids = self.search([('state', 'not in', ['draft', 'cancel', 'annul']), ('invoice_date', '=', today), ('is_cpe', '=', True), ('is_move_sent', '=', False)])
		for invoice_id in invoice_ids:
			if not invoice_id.partner_id.email:
				continue
			account_mail = invoice_id.action_invoice_sent()
			context = account_mail.get('context')
			if not context:
				continue
			template_id = account_mail['context'].get('default_template_id')
			if not template_id:
				continue
			attachment_ids = []
			if context.get('default_attachment_ids', False):
				for attach in context.get('default_attachment_ids'):
					attachment_ids += attach[2]

			mail_id = self.env['mail.template'].browse(template_id)
			mail_id.send_mail((invoice_id.id), force_send=True, email_values={'attachment_ids': attachment_ids})

	@api.onchange('partner_id', 'company_id')
	def _onchange_partner_id(self):
		self.ensure_one()
		#_logging.info(_onchange_partner_id)
		res = super(AccountMove, self)._onchange_partner_id()
		if not self.move_type or self.move_type not in TYPE2JOURNAL:
			return res

		journal_type = TYPE2JOURNAL[self.move_type]
		tipo_documento = self.env['l10n_latam.document.type']
		if not all((self.partner_id, self.env.context.get('force_pe_journal'))):
			return res

		if self.move_type in ['out_refund', 'in_refund']:
			return res

		partner_id = self.partner_id.parent_id or self.partner_id
		doc_type = partner_id.doc_type
		if not doc_type:
			return res

		tipo_doc_id = False
		if doc_type in '6':
			if not self.env.context.get('is_pos_invoice'):
				if self.l10n_latam_document_type_id.code != '01':
					tipo_doc_id = tipo_documento.search([('company_id', 'in', [False, self.company_id.id]), ('code', '=', '01'), ('sub_type', '=', journal_type)], limit=1)
					if tipo_doc_id:
						self.l10n_latam_document_type_id = tipo_doc_id.id
						
		if doc_type in ('6', ):
			dominio = [('id', 'in', self.l10n_latam_available_document_type_ids.ids)]
			dominio.extend([('company_id', 'in', [False, self.company_id.id]), ('code', '=', '01'), ('sub_type', '=', journal_type)])
			tipo_doc_id = tipo_documento.search(dominio, limit=1)
			if tipo_doc_id:
				self.l10n_latam_document_type_id = tipo_doc_id.id
		else:
			if self.l10n_latam_document_type_id.code != '03':
				dominio = [('id', 'in', self.l10n_latam_available_document_type_ids.ids)]
				dominio.extend([('company_id', 'in', [False, self.company_id.id]), ('code', '=', '03'), ('sub_type', '=', journal_type)])
				tipo_doc_id = tipo_documento.search(dominio, limit=1)
				if tipo_doc_id:
					self.l10n_latam_document_type_id = tipo_doc_id.id

		if not tipo_doc_id:
			dominio = [('id', 'in', self.l10n_latam_available_document_type_ids.ids)]
			dominio.extend([('company_id', 'in', [False, self.company_id.id]), ('code', '=', '00'), ('sub_type', '=', journal_type)])
			tipo_doc_id = tipo_documento.search(dominio, limit=1)
			if tipo_doc_id:
				self.l10n_latam_document_type_id = tipo_doc_id.id

		if not tipo_doc_id:
			dominio = [('id', 'in', self.l10n_latam_available_document_type_ids.ids)]
			dominio.extend([('company_id', 'in', [False, self.company_id.id]), ('sub_type', '=', journal_type)])
			tipo_doc_id = tipo_documento.search(dominio, limit=1)
			if tipo_doc_id:
				self.l10n_latam_document_type_id = tipo_doc_id.id

		if not tipo_doc_id:
			return res

			



