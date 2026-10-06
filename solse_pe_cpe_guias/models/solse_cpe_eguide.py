# -*- coding: utf-8 -*-

from odoo import models, fields, api
from .eguide import get_document, get_sign_document, send_sunat_eguide, get_response, get_ticket_status, get_status_cdr
from base64 import b64decode, b64encode
from lxml import etree
from datetime import datetime
from odoo.exceptions import UserError
import logging
_logging = logging.getLogger(__name__)


class CPESunatEguide(models.Model):
	_name = 'solse.cpe.eguide'
	_inherit = ['mail.thread']
	_description = 'Guia Electronica'

	name = fields.Char("Numero", readonly=True, default="/")
	state = fields.Selection([
		('draft', 'Borrador'),
		('generate', 'Generado'),
		('send', 'Enviado'),
		('verify', 'Esperando'),
		('done', 'Hecho'),
		('cancel', 'Cancelado'),
	], string='Status', index=True, readonly=False, default='draft',
		tracking=True, copy=False)
	type = fields.Selection([
		('sync', 'Envio online'),
		('low', 'Comunicación de baja'),
	], string="Tipo", default='sync')
	date = fields.Date("Fecha", default=fields.Date.context_today)
	# 19.0.4.20: `states=` no existe desde v17 (el kwarg se ignoraba) y
	# `_company_default_get` desapareció en v13; el default solo se evaluaba
	# cuando se creaba sin company_id, por eso no estallaba. La condición
	# de solo lectura por estado vive en la vista.
	company_id = fields.Many2one('res.company', string='Company', change_default=True,
								 required=True, default=lambda self: self.env.company)
	xml_document = fields.Text("Documento XML")
	datas = fields.Binary("Datos XML", readonly=True)
	datas_fname = fields.Char("Nombre de archivo XML", readonly=True)
	datas_sign = fields.Binary("XML firmado", readonly=True)
	datas_sign_fname = fields.Char("Nombre de archivo firmado XML", readonly=True)
	datas_zip = fields.Binary("Datos Zip XML", readonly=True)
	datas_zip_fname = fields.Char("Nombre de archivo zip XML", readonly=True)
	datas_response = fields.Binary("Datos de respuesta XML", readonly=True)
	datas_response_fname = fields.Char("Nombre de archivo de respuesta XML", readonly=True)
	response = fields.Char("Respuesta", readonly=True)
	response_code = fields.Char("Código de respuesta", readonly=True)
	note = fields.Text("Nota", readonly=True)
	error_code = fields.Selection(
		"_get_error_code", string="Código de error", readonly=True)
	digest = fields.Char("Codigo", readonly=True)
	signature = fields.Text("Firma", readonly=True)
	ticket = fields.Char("Ticket")
	date_end = fields.Datetime("Fecha final")
	send_date = fields.Datetime("Fecha de envio")
	url_doc = fields.Char("Url Documento")
	voided_ids = fields.One2many("stock.picking", "pe_voided_id", string="Guía cancelada")
	picking_ids = fields.One2many("stock.picking", "pe_guide_id", string="Guía")

	_order = 'name, date'

	@api.model
	def _get_error_code(self):
		return self.env['pe.datas'].get_selection("PE.CPE.ERROR")

	def action_draft(self):
		self.state = 'draft'

	def action_generate(self):
		if not self.xml_document and self.type == "sync":
			self._prepare_eguide()
			self._sign_eguide()
		# else:
		#    self._sign_eguide()
		self.state = 'generate'

	def action_send(self):
		state = self.send_eguide()
		self.state = state

	def action_verify(self):
		self.state = 'verify'

	def action_done(self):
		if self.ticket:
			status = self.get_sunat_ticket_status()
			if status:
				self.state = status
		else:
			self.state = 'done'

	def action_cancel(self):
		self.state = 'cancel'

	@api.model
	def create_from_stock(self, picking_id):
		vals = {}
		vals['picking_ids'] = [(4, picking_id.id)]
		vals['type'] = 'sync'
		vals['company_id'] = picking_id.company_id.id
		res = self.create(vals)
		return res

	@api.model
	def get_eguide_async(self, type, picking_id):
		res = None
		eguide_id = self.search([('state', '=', 'draft'), ('type', '=', type), ('date', '=', picking_id.pe_date_issue),
								 ('name', '=', "/"), ('company_id', '=', picking_id.company_id.id)], limit=1, order="date DESC")
		if eguide_id:
			res = eguide_id
		else:
			vals = {}
			vals['type'] = type
			vals['company_id'] = picking_id.company_id.id
			vals['date'] = picking_id.pe_date_issue
			res = self.create(vals)
		return res

	def obtener_empresa(self):
		empresa = self.company_id
		if empresa.parent_id:
			empresa = empresa.parent_id

		empresa = self.env['res.company'].sudo().search([('id', '=', empresa.id)])
		return empresa

	def obtener_servidor(self):
		"""Servidor CPE usado por este tipo de guía.

		Punto de extensión: los módulos que emiten otro tipo de guía (la
		Transportista 31 en solse_pe_cpe_guias_transp) redefinen este método
		para apuntar a su propio servidor sin duplicar la mecánica de firma,
		envío y lectura del CDR.
		"""
		self.ensure_one()
		return self.obtener_empresa().pe_cpe_eguide_server_id

	def get_document_name(self):
		self.ensure_one()
		empresa = self.obtener_empresa()
		ruc = empresa.partner_id.doc_number
		if self.type == "sync":
			doc_code = "-%s" % "09"
			number = self.picking_ids[0].pe_guide_number
		else:
			doc_code = "-%s" % "09"
			number = self.name
		return "%s%s-%s" % (ruc, doc_code, number)

	def prepare_sunat_auth(self):
		self.ensure_one()
		empresa = self.obtener_empresa()
		servidor = self.obtener_servidor()
		res = {}
		res['ruc'] = empresa.partner_id.doc_number
		res['username'] = servidor.user
		res['password'] = servidor.password
		res['client_id'] = servidor.client_id
		res['client_secret'] = servidor.client_secret
		res['url'] = servidor.url
		return res

	def _prepare_eguide(self):
		if not self.xml_document and self.type != "low":
			file_name = self.get_document_name()
			xml_document = get_document(self)
			self.xml_document = xml_document
			self.datas = b64encode(xml_document)
			self.datas_fname = file_name+".xml"

	def _sign_eguide(self):
		empresa = self.obtener_empresa()
		file_name = self.get_document_name()
		if not self.xml_document:
			self._prepare_eguide()
		elif self.xml_document.encode('utf-8') != b64decode(self.datas):
			self.datas = b64encode(self.xml_document.encode('utf-8'))
		# M-11: la clave privada se lee con sudo y NO con los permisos del
		# usuario. Hasta 19.0.1.19 la ACL de cpe.certificate daba lectura a
		# todo usuario interno —fila sin grupo y perm_read a 1— precisamente
		# porque cualquiera que emitiera una factura tenía que poder leerla.
		# Con el sudo aquí, la ACL puede restringirse al grupo manager: el
		# que firma es el proceso, no la persona.
		certificado = empresa.pe_certificate_id.sudo()
		key = certificado.key
		crt = certificado.crt
		self.datas_sign = b64encode(
			get_sign_document(self.xml_document, key, crt))
		
		self.datas_sign_fname = file_name+".xml"
		self.get_sign_details()

	# Enviar guía electronica
	def send_eguide(self):
		self.ensure_one()
		file_name = self.get_document_name()
		record = self.with_context(tz=self.env.user.tz)
		#self.send_date = fields.Datetime.to_string(fields.Datetime.context_timestamp(record, datetime.now()))
		self.send_date = fields.Datetime.to_string(datetime.now())
		if self.name == "/" and self.type != "low":
			self.name = self.picking_ids[0].pe_guide_number
		else:
			if self.name == "/":
				# L-8: correlativo de la compañía del documento.
				self.name = self.env['ir.sequence'].with_company(self.company_id).next_by_code('pe.eguide.cancel')
			file_name = self.get_document_name()
			#xml_document = get_document(self)
			#self.xml_document = xml_document
			xml_document = self.xml_document
			#self.datas = b64encode(xml_document)
			#self.datas_fname = file_name+".xml"
			#self._sign_eguide()
		if self.xml_document.encode('utf-8') != b64decode(self.datas):
			self._sign_eguide()

		client = self.prepare_sunat_auth()
		document = {}
		document['document_name'] = file_name
		document['type'] = self.type
		document['xml'] = b64decode(self.datas_sign)
		self.datas_zip, response_status, response, response_data = send_sunat_eguide(client, document)
		self.datas_zip_fname = file_name+".zip"
		if response_status:
			self.ticket = response_data
			state = "verify"
		else:
			state = "send"
		return state


	def send_eguide_anterior(self):
		self.ensure_one()
		file_name = self.get_document_name()
		record = self.with_context(tz=self.env.user.tz)
		#self.send_date = fields.Datetime.to_string(fields.Datetime.context_timestamp(record, datetime.now()))
		self.send_date = fields.Datetime.to_string(datetime.now())
		if self.name == "/" and self.type != "low":
			self.name = self.picking_ids[0].pe_guide_number
		else:
			if self.name == "/":
				# L-8: correlativo de la compañía del documento.
				self.name = self.env['ir.sequence'].with_company(
					self.company_id).next_by_code('pe.eguide.cancel')
			file_name = self.get_document_name()
			xml_document = get_document(self)
			self.xml_document = xml_document
			self.datas = b64encode(xml_document)
			self.datas_fname = file_name+".xml"
			self._sign_eguide()
		if self.xml_document.encode('utf-8') != b64decode(self.datas):
			self._sign_eguide()

		client = self.prepare_sunat_auth()
		document = {}
		document['document_name'] = file_name
		document['type'] = self.type
		document['xml'] = b64decode(self.datas_sign)
		self.datas_zip, response_status, response, response_data = send_sunat_eguide(
			client, document)
		self.datas_zip_fname = file_name+".zip"
		res = None
		if response_status:
			res = "verify"
			if self.type == "sync":
				self.datas_response = response_data
				new_state = self.get_response_details()
				self.datas_response_fname = 'R-%s.zip' % file_name
				res = new_state or res
			else:
				self.ticket = response_data
		else:
			res = "send"
			if 'faultcode' not in response:
				raise UserError('No se pudo obtener una respuesta')
			self.response = response.get("faultcode")
			self.note = response.get("faultstring")
			if not response.get("faultcode"):
				code = len(response.get("faultcode").split(".")) >= 2 and "%04d" % int(
					response.get("faultcode").split(".")[-1].encode('utf-8')) or False
				self.response_code = code
			#self.error_code= code
		return res

	def get_sign_details(self):
		self.ensure_one()
		vals = {}
		tag = etree.QName('http://www.w3.org/2000/09/xmldsig#', 'DigestValue')
		xml_sign = b64decode(self.datas_sign)
		digest = etree.fromstring(xml_sign).find('.//'+tag.text)
		if digest != -1:
			self.digest = digest.text
		tag = etree.QName(
			'http://www.w3.org/2000/09/xmldsig#', 'SignatureValue')
		sign = etree.fromstring(xml_sign).find('.//'+tag.text)
		if sign != -1:
			self.signature = sign.text

	def get_response_details(self):
		self.ensure_one()
		vals = {}
		state = None
		return state

	def generate_eguide(self):
		self._prepare_eguide()
		self._sign_eguide()
		self.state = "generate"

	def get_sunat_ticket_status(self):
		self.ensure_one()
		empresa = self.obtener_empresa()
		client = self.prepare_sunat_auth()
		response_status, response, response_file = get_ticket_status(self.ticket, client)
		state = None
		if response_status in ['99', '0', '00']:
			file_name = self.get_document_name()
			nombre_completo =  'R-%s.%s' % (file_name, self.obtener_servidor().extension_xml)
			xml_response = get_response({'file': response_file, 'name': nombre_completo})
			if not xml_response and response_file:
				self.datas_response = response_file
				return
			sunat_response = etree.fromstring(xml_response)
			cbc = 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
			tag = etree.QName(cbc, 'ResponseDate')
			date = sunat_response.find('.//'+tag.text)
			tag = etree.QName(cbc, 'ResponseTime')
			time = sunat_response.find('.//'+tag.text)
			if time != -1 and date != -1:
				record = self.with_context(tz=self.env.user.tz)
				self.date_end = fields.Datetime.to_string(datetime.now())
			tag = etree.QName(cbc, 'ResponseCode')
			code = sunat_response.find('.//'+tag.text)
			res_code = ""
			if code != -1:
				res_code = "%04d" % int(code.text)
				self.response_code = res_code
				if res_code == "0000":
					self.error_code = False
					state = "done"
			tag = etree.QName(cbc, 'Description')
			description = sunat_response.find('.//'+tag.text)
			res_desc = ""
			if description != -1:
				res_desc = description.text

			tag = etree.QName(cbc, 'DocumentDescription')
			url_doc = sunat_response.find('.//'+tag.text)
			if url_doc != -1:
				try:
					self.url_doc = url_doc.text
				except:
					_logging.info("esto retorno en la url de guia")
					_logging.info(url_doc)
					self.url_doc = url_doc

			self.datas_response = response_file
			self.datas_response_fname = 'R-%s.zip' % file_name
			#state = "done"
			if response_status == '99':
				self.response = response["error"]["desError"]
				self.note = response["error"]["desError"]
				try:
					self.error_code = response["error"]["numError"]

				except:
					self.response = response["error"]["desError"]
			else:
				self.response = "%s - %s" % (res_code, res_desc)
				self.error_code = False
				self.note = ""

		return state
		

	def action_document_status(self):
		pass