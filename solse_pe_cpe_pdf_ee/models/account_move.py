# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
import base64
import sys
import logging

_logging = logging.getLogger(__name__)

def encodestring(datos):
	respuesta = datos
	if not respuesta:
		return respuesta
	if sys.version_info >= (3, 9):
		respuesta = base64.b64encode(datos)
	else:
		respuesta = base64.encodestring(datos)

	return respuesta

class AccountJournal(models.Model):
	_inherit = 'account.journal'

	formato_defecto = fields.Selection([("formato_n1", "Formato n1"), ("formato_n2", "Formato n2"), ("formato_n3", "Formato n3"),
		("formato_n4", "Formato n4"), ("formato_n5", "Formato n5"), ("formato_n6", "Formato n6")], default="formato_n1", string="Formato")

class AccountMove(models.Model):
	_inherit = 'account.move'

	secuencia = fields.Char("Secuencia") 

	def obtner_cuentas_bancarias(self):
		texto = []
		cuentas = self.company_id.partner_id.bank_ids
		for cuenta in cuentas:
			texto_item = "%s %s" % (cuenta.bank_id.name, cuenta.acc_number)
			texto.append(texto_item)
			texto_item2 = "%s CCI %s" % (cuenta.bank_id.name, cuenta.cci)
			texto.append(texto_item2)

		return "\n".join(texto)

	def obtener_cantidad_bultos(self):
		if 'pe_stock_ids' not in self:
			return 0
		if self.pe_stock_ids:
			return self.pe_stock_ids[0].pe_unit_quantity
		else:
			return 0

	def obtener_peso_bruto(self):
		if 'pe_stock_ids' not in self:
			return 0.00
		if self.pe_stock_ids:
			return self.pe_stock_ids[0].pe_gross_weight
		else:
			return 0.00

	def obtener_cantidad_total(self):
		cant = 0
		for linea in self.invoice_line_ids:
			cant += linea.quantity
		return cant

	def obtener_punto_origen(self):
		if 'pe_stock_ids' not in self:
			return ""
		direccion = ""
		guia = self.pe_stock_ids[0] if self.pe_stock_ids else False
		if guia:
			punto_partida = guia.company_id.partner_id 
			if guia.picking_type_id.code == 'internal' and guia.almacen_origen:
				punto_partida = guia.almacen_origen.partner_id

			if guia.picking_type_id.code == 'outgoing' and guia.almacen_origen:
				punto_partida = guia.almacen_origen.partner_id

			if guia.pe_transfer_code == '02':
				punto_partida = guia.partner_id

			direccion = "%s, %s" % (punto_partida.street, guia._get_address_details(punto_partida))
		return direccion

	def obtener_punto_destino(self):
		if 'pe_stock_ids' not in self:
			return ""
		direccion = ""

		direccion = ""
		guia = self.pe_stock_ids[0] if self.pe_stock_ids else False
		if guia:
			punto_llegada = guia.partner_id 
			if guia.picking_type_id.code == 'internal' and guia.almacen_destino:
				punto_llegada = guia.almacen_destino.partner_id


			if guia.pe_transfer_code == '02':
				punto_llegada = guia.company_id.partner_id

			direccion = "%s, %s" % (punto_llegada.street, guia._get_address_details(punto_llegada))

		return direccion

	def obtener_motivo_transferencia(self):
		if 'pe_stock_ids' not in self:
			return ""

		direccion = ""
		guia = self.pe_stock_ids[0] if self.pe_stock_ids else False
		if guia:
			#return guia.pe_transfer_code
			nombre = dict(guia.fields_get(allfields=['pe_transfer_code'])['pe_transfer_code']['selection'])[guia.pe_transfer_code]
			return nombre

		return ""

	def obtener_pedido_venta(self):
		dato = []
		sale_ids = self.invoice_line_ids.mapped('sale_line_ids').mapped('order_id')
		for sale in sale_ids:
			dato.append(sale.name)
		return ",".join(dato)

	def obtener_transportista(self):
		if 'pe_stock_ids' not in self:
			return ""
		nombre = ""
		guia = self.pe_stock_ids[0] if self.pe_stock_ids else False
		if not guia:
			return nombre
		if guia and guia.pe_transport_mode == '01':
			nombre = guia.pe_carrier_id.name
		elif guia and guia.pe_transport_mode == '02':
			if guia.pe_fleet_ids:
				nombre = guia.pe_fleet_ids[0].driver_id.name

		return nombre

	def obtener_ruc_transportista(self):
		if 'pe_stock_ids' not in self:
			return ""
		datos = ""
		guia = self.pe_stock_ids[0] if self.pe_stock_ids else False
		if not guia:
			return datos
		if guia and guia.pe_transport_mode == '01':
			datos = guia.pe_carrier_id.doc_number
		elif guia and guia.pe_transport_mode == '02':
			if guia.pe_fleet_ids:
				datos = guia.pe_fleet_ids[0].driver_id.doc_number

		return datos

	def obtener_lote(self, linea, ids_array):
		if 'pe_stock_ids' not in self:
			return ["", []]
		lote = ""
		guia = self.pe_stock_ids[0] if self.pe_stock_ids else False
		if not guia:
			return [lote, ids_array]
		linea_prod = guia.mapped('move_line_ids_without_package').filtered(lambda r: r.product_id.id == linea.product_id.id and r.qty_done == linea.quantity and r.id not in ids_array)
		if not linea_prod:
			linea_prod = guia.mapped('move_line_ids_without_package').filtered(lambda r: r.product_id.id == linea.product_id.id and r.id not in ids_array)

		if linea_prod:
			linea_prod = linea_prod[0]
			lote = linea_prod.lot_id.name
			ids_array.append(linea_prod.id)
			
		return [lote, ids_array]

	def obtener_vencimiento(self, linea, ids_array):
		if 'pe_stock_ids' not in self:
			return ""
		vencimiento = ""		
		guia = self.pe_stock_ids[0] if self.pe_stock_ids else False
		if not guia:
			return vencimiento 
		linea_prod = guia.mapped('move_line_ids_without_package').filtered(lambda r: r.product_id.id == linea.product_id.id and r.qty_done == linea.quantity and r.id not in ids_array)
		if not linea_prod:
			linea_prod = guia.mapped('move_line_ids_without_package').filtered(lambda r: r.product_id.id == linea.product_id.id and r.id not in ids_array)

		if linea_prod:
			linea_prod = linea_prod[0]
			vencimiento = str(linea_prod.lot_id.expiration_date)
			if vencimiento:
				vencimiento = vencimiento.split(" ")[0].replace("-", "")
		return vencimiento

	def obtener_guia(self):
		dato = ""
		if 'guide_number' in self:
			dato = self.guide_number
		if not dato and 'pe_stock_name':
			dato = self.pe_stock_name
		return dato

	def obtener_igv(self, linea):
		igv = 0.00
		igv = linea.price_total - linea.price_subtotal
		igv = round(igv, 2)
		return igv

	def obtener_isc(self, linea):
		return 0.00

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
			if not arc_n2 or self.journal_id.formato_defecto and self.journal_id.formato_defecto != "formato_n1":
				attach = {}

				if self.journal_id.formato_defecto == "formato_n2":
					result_pdf, type = self.env['ir.actions.report']._get_report_from_name('solse_pe_cpe_pdf_ee.report_invoice_with_payments')._render_qweb_pdf('solse_pe_cpe_pdf_ee.report_invoice_with_payments', res_ids=self.ids)
				elif self.journal_id.formato_defecto == "formato_n3":
					result_pdf, type = self.env['ir.actions.report']._get_report_from_name('solse_pe_cpe_pdf_ee.report_invoice_with_payments_m3')._render_qweb_pdf('solse_pe_cpe_pdf_ee.report_invoice_with_payments_m3', res_ids=self.ids)
				elif self.journal_id.formato_defecto == "formato_n4":
					result_pdf, type = self.env['ir.actions.report']._get_report_from_name('solse_pe_cpe_pdf_ee.report_invoice_with_payments_m4')._render_qweb_pdf('solse_pe_cpe_pdf_ee.report_invoice_with_payments_m4', res_ids=self.ids)
				elif self.journal_id.formato_defecto == "formato_n5":
					result_pdf, type = self.env['ir.actions.report']._get_report_from_name('solse_pe_cpe_pdf_ee.report_invoice_with_payments_m5')._render_qweb_pdf('solse_pe_cpe_pdf_ee.report_invoice_with_payments_m5', res_ids=self.ids)
				elif self.journal_id.formato_defecto == "formato_n6":
					result_pdf, type = self.env['ir.actions.report']._get_report_from_name('solse_pe_cpe_pdf_ee.report_invoice_with_payments_m6')._render_qweb_pdf('solse_pe_cpe_pdf_ee.report_invoice_with_payments_m6', res_ids=self.ids)
				else:
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

	# ===== Helpers para representación impresa (Formato 5 y otros) =====

	def _pe_obtener_doc_origen_pdf(self):
		"""
		Devuelve el comprobante de origen (account.move) que esta NC/ND modifica,
		con fallback robusto. Para usar en los templates PDF.

		Orden de búsqueda:
		1) origin_doc_id (custom de solse_pe_cpe, auto-llenado o manual)
		2) reversed_entry_id / debit_origin_id (nativo Odoo)
		3) invoice_origin / ref (texto referencia)
		"""
		self.ensure_one()
		AccountMove = self.env['account.move']

		# 1) Camino preferente: campo custom solse_pe_cpe
		if 'origin_doc_id' in self._fields and self.origin_doc_id:
			return self.origin_doc_id

		# 2) Camino nativo Odoo
		if self.pe_invoice_code == '07' and self.reversed_entry_id:
			return self.reversed_entry_id
		if self.pe_invoice_code == '08' and self.debit_origin_id:
			return self.debit_origin_id

		if self.pe_invoice_code not in ('07', '08'):
			return AccountMove

		referencia = (self.invoice_origin or '').strip() or (self.ref or '').strip()
		if referencia and '-' in referencia:
			token = referencia.split()[0]
			if '-' in token and len(token.split('-')) == 2:
				candidato = AccountMove.search([
					('l10n_latam_document_number', '=', token),
					('partner_id', '=', self.partner_id.id),
					('company_id', '=', self.company_id.id),
					('move_type', 'in', ('out_invoice',)),
					('state', 'in', ('posted', 'annul', 'cancel')),
				], limit=1)
				if candidato:
					return candidato

		return AccountMove

	def _pe_obtener_label_doc_origen_pdf(self):
		"""
		Retorna string formateado del documento que modifica esta NC/ND,
		listo para imprimir en el PDF. Cubre 3 escenarios:

		a) Doc origen en sistema (origin_doc_id, reversed_entry_id, etc.):
		   "Factura F001-00000123 del 15/03/2026"

		b) NC directa con origin_doc_code y origin_doc_number manuales (CP origen
		   fuera del sistema): "Factura F003-00000146" (sin fecha)

		c) Sin datos: string vacío -> el template oculta el bloque.
		"""
		self.ensure_one()
		if self.pe_invoice_code not in ('07', '08'):
			return ''

		# a) Documento en sistema
		origen = self._pe_obtener_doc_origen_pdf()
		if origen:
			tipo_label = origen.l10n_latam_document_type_id.name or ''
			numero = origen.l10n_latam_document_number or ''
			fecha = ''
			if origen.invoice_date:
				fecha = ' del %s' % origen.invoice_date.strftime('%d/%m/%Y')
			return ('%s %s%s' % (tipo_label, numero, fecha)).strip()

		# b) NC directa con campos manuales (origin_doc_code + origin_doc_number)
		if 'origin_doc_code' in self._fields and (self.origin_doc_code or self.origin_doc_number):
			# Label del tipo desde la selection (Tabla 10 SUNAT)
			tipo_label = ''
			if self.origin_doc_code:
				sel = dict(self.fields_get(allfields=['origin_doc_code'])['origin_doc_code']['selection'])
				tipo_label = sel.get(self.origin_doc_code, self.origin_doc_code)
			numero = self.origin_doc_number or ''
			return ('%s %s' % (tipo_label, numero)).strip()

		# c) Sin datos
		return ''

	def _pe_obtener_motivo_nota_label(self):
		"""
		Retorna la descripción legible del motivo de NC o ND
		(Catálogo SUNAT N°09 para NC, N°10 para ND).
		"""
		self.ensure_one()
		if self.pe_invoice_code == '07' and self.pe_credit_note_code:
			selection = dict(self.fields_get(allfields=['pe_credit_note_code'])['pe_credit_note_code']['selection'])
			return selection.get(self.pe_credit_note_code, '')
		if self.pe_invoice_code == '08' and self.pe_debit_note_code:
			selection = dict(self.fields_get(allfields=['pe_debit_note_code'])['pe_debit_note_code']['selection'])
			return selection.get(self.pe_debit_note_code, '')
		return ''

	def _pe_obtener_anticipos_aplicados(self):
		"""
		Wrapper de _obtener_comprobantes_anticipos para uso en templates.
		Retorna lista de dicts con datos formateados para imprimir, o lista vacía.
		"""
		self.ensure_one()
		try:
			# Reutilizamos la lógica de cálculo del XML para no duplicar reglas
			from odoo.addons.solse_pe_cpe.models.cpe_xml import CPE
			cpe = CPE()
			lista, montos = cpe._obtener_comprobantes_anticipos(self)
		except Exception as e:
			_logging.warning("Error obteniendo anticipos aplicados para PDF: %s", e)
			return []

		resultado = []
		for anticipo in lista:
			datos_anticipo = montos.get(anticipo.id, {}) if isinstance(montos, dict) else {}
			resultado.append({
				'tipo_operacion': 'Factura por Anticipo',
				'comprobante': anticipo.l10n_latam_document_number or anticipo.name or '',
				'fecha_pago': anticipo.invoice_date.strftime('%d/%m/%Y') if anticipo.invoice_date else '',
				'monto': datos_anticipo.get('amount_total', 0.0),
			})
		return resultado

	def _pe_obtener_cuentas_bancarias_pdf(self):
		"""
		Retorna lista estructurada de cuentas bancarias de la compañía para
		mostrar en el PDF. Cada item: {bank, moneda, cc, cci}.
		"""
		self.ensure_one()
		resultado = []
		for cuenta in self.company_id.partner_id.bank_ids:
			resultado.append({
				'bank': cuenta.bank_id.name if cuenta.bank_id else '',
				'moneda': cuenta.currency_id.name if cuenta.currency_id else '',
				'cc': cuenta.acc_number or '',
				'cci': getattr(cuenta, 'cci', '') or '',
			})
		return resultado


class AccountMoveLine(models.Model):
	_inherit = 'account.move.line'

	def _obtener_glosa_pdf(self):
		"""
		Retorna la descripción de la línea para impresión, removiendo el
		default_code del producto si ya está prefijado en line.name (Odoo
		lo agrega automáticamente como '[CODE] Descripción').
		Evita la duplicación cuando default_code se muestra en su propia columna.
		"""
		self.ensure_one()
		desc = self.name or ''
		code = self.product_id.default_code if self.product_id else None
		if code:
			prefijo = '[%s]' % code
			if desc.startswith(prefijo):
				desc = desc[len(prefijo):].strip()
		return desc