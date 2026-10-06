# -*- coding: utf-8 -*-

from odoo import api, fields, tools, models, _
"""from pdf417gen.encoding import to_bytes, encode_high, encode_rows
from pdf417gen.util import chunks
from pdf417gen.compaction import compact_bytes
from pdf417gen import render_image"""
import tempfile
import time
#from base64 import encodestring
import base64
from odoo.exceptions import UserError
from .eguide import convertir_fecha_a_peru
import re
from io import StringIO, BytesIO
from importlib import reload
import sys
try:
	import qrcode
	qr_mod = True
except:
	qr_mod = False

import logging
_logging = logging.getLogger(__name__)

# Parámetros del sistema (ir.config_parameter). Se editan desde
# Ajustes > Técnico > Parámetros del sistema, sin actualizar el módulo.
PARAM_TUCE_OBLIGATORIA = 'solse_pe_cpe_guias.tuce_obligatoria'

# Valores que se interpretan como verdadero en los parámetros del sistema.
VALORES_VERDADEROS = ('1', 'true', 'verdadero', 'si', 'sí', 'x', 'on')

def encodestring(datos):
	respuesta = datos
	if not datos:
		return False
	if sys.version_info >= (3, 9):
		respuesta = base64.b64encode(datos)
	else:
		respuesta = base64.encodestring(datos)

	return respuesta

"""
class StockMove(models.Model):
	_inherit = 'stock.move'

	def _should_bypass_reservation(self, forced_location=False):
		self.ensure_one()
		if self.picking_id and self.picking_id.forzar_reserva:
			return True
		location = forced_location or self.location_id
		return location.should_bypass_reservation() or self.product_id.type != 'product'
"""

class ProductProduct(models.Model):
	_inherit = 'product.product'

	def obtener_nombre_impresion(self):
		nombre = self.name
		if self.combination_indices and not self.product_template_variant_value_ids:
			producto = self.product_tmpl_id
			valores_atributos = producto.attribute_line_ids.mapped("value_ids").mapped("name")
			nombre = "%s (%s)" % (nombre, "-".join(valores_atributos))
		return nombre

class Picking(models.Model):
	_inherit = "stock.picking"

	pe_voided_id = fields.Many2one("solse.cpe.eguide", "Guía cancelada", copy=False)
	pe_guide_id = fields.Many2one("solse.cpe.eguide", "Guía electrónica", copy=False)
	pe_guide_number = fields.Char("Número de guía", default="/", copy=False)

	# Refactor SUNAT 01/06/2026: documentos relacionados ahora son One2many
	# (antes solo se permitía uno; SUNAT siempre admitió varios).
	pe_documento_relacionado_ids = fields.One2many(
		comodel_name='pe.stock.documento.relacionado',
		inverse_name='picking_id',
		string='Documentos relacionados',
		copy=False,
	)

	# SUNAT 01/06/2026 - Contenedores y precintos (F4)
	# Mapea a cac:Shipment/cac:TransportHandlingUnit/cac:TransportEquipment.
	pe_contenedor_ids = fields.One2many(
		comodel_name='pe.stock.contenedor',
		inverse_name='picking_id',
		string='Contenedores',
		copy=False,
		help="Contenedores que transportan los bienes. Mutuamente excluyente "
			 "con 'Cantidad de bultos' según ERR-3621."
	)

	# SUNAT 01/06/2026 - Indicadores especiales (F3)
	# Mapean a cac:Shipment/cbc:SpecialInstructions con valores fijos.
	pe_puerto_id = fields.Many2one(
		'solse.pe.puerto', string='Puerto/Aeropuerto de embarque',
		help='Catálogos 63/64 de SUNAT. Obligatorio en exportación '
			 '(motivo 09, error 3369) y en importación cuando no se '
			 'consigna el RUC del depósito temporal (motivo 08, error '
			 '3365). El ubigeo del punto de llegada debe corresponder '
			 'al del puerto (error 3364).')

	pe_traslado_total_dam = fields.Boolean(
		string="Traslado total de bienes amparados por DAM o DS",
		copy=False,
		help="Indica que se trasladan todos los bienes amparados por la "
			 "Declaración Aduanera (DAM) o Declaración Simplificada (DS). "
			 "Aplica solo para motivos 08 o 19 con documentos tipo 50 o 52 "
			 "(ERR-3485, ERR-3631, ERR-3632)."
	)
	pe_traslado_contenedor_mc = fields.Boolean(
		string="Traslado en contenedor de Manifiesto de Carga",
		copy=False,
		help="Indica que los bienes se trasladan en el mismo contenedor del "
			 "Manifiesto de Carga (MC). Aplica para motivos 08 o 09 con "
			 "documento tipo 91 (ERR-3419)."
	)
	pe_transbordo_programado = fields.Boolean(
		string="Transbordo programado",
		copy=False,
		help="Indica que el traslado es un transbordo programado. "
			 "Solo aplica para modalidad de traslado 01-Público. "
			 "Mutuamente excluyente con 'Registro de vehículos y conductores' "
			 "según ERR-3615."
	)
	pe_registro_vehiculos_conductores = fields.Boolean(
		string="Registro de vehículos y conductores del transportista",
		copy=False,
		help="El remitente registra en ESTA guía los vehículos y conductores "
			 "del transportista (último párrafo del numeral 3.1 del artículo "
			 "3 de la RS 255-2015/SUNAT). Al activarlo se vuelven "
			 "OBLIGATORIOS la placa, el conductor principal con su documento "
			 "de identidad y su licencia de conducir (ERR-2566, ERR-3357, "
			 "ERR-2568, ERR-2572), y el transportista queda exceptuado de "
			 "emitir su GRE - Transportista.\n"
			 "Solo aplica para modalidad 01-Público. Mutuamente excluyente "
			 "con 'Transbordo programado' (ERR-3615) y con 'Traslado en "
			 "vehículos categoría M1 o L' (ERR-3451)."
	)
	pe_vehiculos_m1_l = fields.Boolean(
		string="Traslado en vehículos categoría M1 o L",
		copy=False,
		help="Indica que el traslado se realiza en vehículos categoría M1 "
			 "(automóviles) o L (motocicletas y similares)."
	)
	pe_retorno_vehiculo_vacio = fields.Boolean(
		string="Retorno con vehículo vacío",
		copy=False,
		help="Indica que el traslado corresponde al retorno del vehículo "
			 "vacío después de un servicio de transporte."
	)
	pe_retorno_envase_vacio = fields.Boolean(
		string="Retorno con envases vacíos",
		copy=False,
		help="Indica que el traslado corresponde al retorno del vehículo "
			 "con envases vacíos (botellas, cilindros, contenedores "
			 "retornables, etc.)."
	)

	# Computed: sub-régimen especial motivo 19 + doc 92
	# Cuando se activa, el XML suprime: NetWeight, Information, GrossWeight,
	# TotalTransportHandlingUnitQuantity, contenedores y reemplaza las
	# DespatchLines reales por una línea dummy (ERR-3623 a ERR-3630).
	pe_es_subregimen_19_92 = fields.Boolean(
		compute='_compute_pe_es_subregimen_19_92',
		string='Sub-régimen 19+92',
		store=False,
		help="Verdadero cuando aplica el sub-régimen de Traslado de "
			 "mercancía extranjera con Cita/Orden Terminal Portuario."
	)

	# Campos legacy - DEPRECATED desde 19.0.2.0.0
	# Se mantienen para no romper reportes y automatizaciones existentes.
	# Los datos viejos se migran al One2many vía migrations/19.0.2.0.0/post-migrate.py
	pe_is_realeted = fields.Boolean("Esta relacionada (legacy)", copy=False)
	pe_related_number = fields.Char("Número relacionado (legacy)", copy=False)
	pe_related_code = fields.Selection(selection="_get_pe_related_code", string="Código relacionado (legacy)", copy=False)

	@api.depends('pe_transfer_code', 'pe_documento_relacionado_ids.codigo_documento')
	def _compute_pe_es_subregimen_19_92(self):
		"""Sub-régimen SUNAT 01/06/2026 - motivo 19 + doc relacionado 92.
		Cuando se activa, el XML se genera con tags suprimidos y una
		DespatchLine dummy en vez de las líneas reales (ERR-3623 a ERR-3630).
		"""
		for picking in self:
			tipos_docs = picking.pe_documento_relacionado_ids.mapped('codigo_documento')
			picking.pe_es_subregimen_19_92 = (
				picking.pe_transfer_code == '19' and '92' in tipos_docs
			)
	supplier_id = fields.Many2one(comodel_name="res.partner", string="Proveedor", copy=False)
	pe_transfer_code = fields.Selection(selection="_get_pe_transfer_code", string="Código de transferencia", default="01", copy=False)
	motivo_transferencia = fields.Text("Motivo trasnferencia")
	pe_gross_weight = fields.Float("Peso bruto", digits='Product Unit of Measure', copy=False)
	pe_unit_quantity = fields.Integer("Cantidad Bultos", copy=False)
	pe_transport_mode = fields.Selection(selection="_get_pe_transport_mode", string="Modo de transporte", copy=False)
	pe_carrier_id = fields.Many2one(comodel_name="res.partner", string="Transportista", copy=False)
	pe_is_eguide = fields.Boolean("Es Guía Electrónica", copy=False)
	pe_is_programmed = fields.Boolean("Transferencia programada", copy=False)
	pe_date_issue = fields.Date('Fecha de emisión', copy=False)
	# Nuevo SUNAT 01/06/2026 - Fecha de entrega de bienes al transportista.
	# Mapea a: cac:Shipment/cac:ShipmentStage/cac:LoadingTransportEvent/cbc:OccurrenceDate
	# Obligatorio para modalidad de traslado 01-Público (ERR-3617).
	# Debe ser >= pe_date_issue (ERR-3618).
	pe_delivery_date = fields.Date(
		'Fecha de entrega al transportista',
		copy=False,
		help="Fecha en que se entregan los bienes al transportista. "
			 "Obligatorio cuando la modalidad de traslado es Público (01). "
			 "Debe ser igual o posterior a la fecha de emisión."
	)
	pe_fleet_ids = fields.One2many(comodel_name="pe.stock.fleet", inverse_name="picking_id", string="Flota Privada", copy=False)
	placa = fields.Char("Placa", compute="_compute_placa")

	pe_digest = fields.Char("Digest", related="pe_guide_id.digest")
	sunat_qr_code = fields.Binary('QR Code (cpe)', compute='_compute_get_qr_code')
	pe_signature = fields.Text("Firma", related="pe_guide_id.signature")
	pe_response = fields.Char("Respuesta", related="pe_guide_id.response")
	pe_note = fields.Text("Sunat nota", related="pe_guide_id.note")
	pe_error_code = fields.Selection(string="Codigo de error", related="pe_guide_id.error_code", readonly=True)
	sunat_pdf417_code = fields.Binary("Pdf 417 Code", compute="_get_pdf417_code")
	pe_guide_state = fields.Selection(string='Estado de Guía', related="pe_guide_id.state")

	pe_invoice_ids = fields.Many2many(comodel_name="account.move", string="Pickings", compute ="_compute_pe_invoice_ids", readonly=True)
	pe_invoice_name = fields.Char("Número interno", compute ="_compute_pe_invoice_ids")
	pe_type_operation = fields.Selection("_get_pe_type_operation", "Tipo de operación", help="Tipo de operación efectuada", copy=False)
	pe_number = fields.Char("Numero de Guia")

	almacen_origen = fields.Many2one('stock.warehouse', 'Almacén Origen', compute="_compute_almacen", store=True)
	almacen_destino = fields.Many2one('stock.warehouse', 'Almacén Destino', compute="_compute_almacen", store=True)
	ocultar_en_pdf = fields.Boolean("Ocultar en pdf")
	forzar_reserva = fields.Boolean("Forzar reserva", default=True)

	location_id = fields.Many2one(check_company=False)
	location_dest_id = fields.Many2one(check_company=False)

	@api.depends('location_id', 'location_dest_id', 'picking_type_id')
	def _compute_almacen(self):
		for reg in self:
			almacen_origen = False
			almacen_destino = False
			if reg.location_id:
				almacen_origen = self.env['stock.warehouse'].search([('lot_stock_id', '=', reg.location_id.id)], limit=1)


			if reg.location_dest_id:
				almacen_destino = self.env['stock.warehouse'].search([('lot_stock_id', '=', reg.location_dest_id.id)], limit=1)

			"""if reg.location_id and reg.location_dest_id and reg.location_id.id == reg.picking_type_id.default_location_dest_id:
				alm_temp = almacen_origen
				almacen_origen = almacen_destino
				almacen_destino = alm_temp"""

			reg.almacen_origen = almacen_origen.id if almacen_origen else False
			reg.almacen_destino = almacen_destino.id if almacen_destino else False

	@api.depends('pe_fleet_ids', 'pe_fleet_ids.fleet_id', 'pe_fleet_ids.fleet_id.license_plate')
	def _compute_placa(self):
		for reg in self:
			placa = ""
			if reg.pe_fleet_ids:
				registro = reg.pe_fleet_ids[0]
				if registro.fleet_id:
					placa = registro.fleet_id.license_plate
			reg.placa = placa
	
	@api.model
	def _get_pe_type_operation(self):
		return self.env['pe.datas'].get_selection("PE.TABLA12")    
	
	@api.model
	def _compute_pe_invoice_ids(self):
		pe_invoice_ids = False
		pe_invoice_name=[]
		for stock_id in self:
			stock_id.sale_id
			pe_invoice_ids = stock_id.sale_id.order_line.invoice_lines.move_id.filtered(lambda r: r.move_type in ('out_invoice', 'out_refund') and r.state in ['posted'])
			if pe_invoice_ids:
				pe_invoice_name = pe_invoice_ids.mapped('l10n_latam_document_number')
			stock_id.pe_invoice_ids=pe_invoice_ids and pe_invoice_ids.ids or []
			stock_id.pe_invoice_name = ", ".join(pe_invoice_name) or False

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
			address += "( %s)" % (partner.zip)
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
	def action_cancel_eguide(self):
		for picking_id in self:
			if picking_id.pe_guide_id and picking_id.pe_guide_id.state not in ["draft", "generate", "cancel"]:
				voided_id = self.env['solse.cpe.eguide'].get_eguide_async('low', picking_id)
				picking_id.pe_voided_id = voided_id.id

	@api.model
	def _get_pdf417_code(self):
		for picking_id in self:
			picking_id.sunat_pdf417_code = False
			

	@api.depends('name', 'pe_is_eguide', 'date_done', 'scheduled_date', 'partner_id.doc_number', 'partner_id.doc_type', 'company_id.partner_id.doc_number', 'pe_guide_id', 'pe_guide_id.url_doc')
	def _compute_get_qr_code(self):
		for guia in self:
			fecha_guia = guia.date_done or guia.scheduled_date
			if not all((guia.name != '/', guia.pe_is_eguide, qr_mod)):
				guia.sunat_qr_code = ''
			elif len(guia.pe_guide_number.split('-')) > 1 and fecha_guia:
				url_guia = '-'
				if guia.pe_guide_id.url_doc:
					url_guia = guia.pe_guide_id.url_doc

				res = [
				 guia.company_id.partner_id.doc_number or '-',
				 '09',
				 guia.pe_guide_number.split('-')[0] or '',
				 guia.pe_guide_number.split('-')[1] or '',
				 str('0'),
				 fields.Date.to_string(fecha_guia), guia.partner_id.doc_type or '-',
				 guia.partner_id.doc_number or '-', url_guia, '']

				qr_string = '|'.join(res)
				qr = qrcode.QRCode(version=1, error_correction=(qrcode.constants.ERROR_CORRECT_Q))
				qr.add_data(qr_string)
				qr.make(fit=True)
				image = qr.make_image()
				tmpf = BytesIO()
				image.save(tmpf, 'png')
				guia.sunat_qr_code = encodestring(tmpf.getvalue())
			else:
				guia.sunat_qr_code = ''

	@api.model
	def _get_pe_error_code(self):
		return self.env['pe.datas'].get_selection("PE.CPE.ERROR")

	def button_validate(self):
		res = super(Picking, self).button_validate()
		peso_total = sum([(line.product_id.weight * line.quantity)  for line in self.move_ids])
		self.pe_gross_weight = self.weight or peso_total #sum([line.product_id.weight for line in self.move_ids_without_package])
		self._completar_bultos_desde_movimientos()
		return res

	@api.model
	def do_new_transfer(self):
		res = super(Picking, self).do_new_transfer()
		peso_total = sum([(line.product_id.weight * line.quantity)  for line in self.move_ids])
		self.pe_gross_weight = self.weight or peso_total #sum([line.product_id.weight for line in self.move_ids_without_package])
		self._completar_bultos_desde_movimientos()
		return res

	@api.model
	def _get_pe_transport_mode(self):
		return self.env['pe.datas'].get_selection("PE.CPE.CATALOG18")

	@api.model
	def _get_pe_related_code(self):
		return self.env['pe.datas'].get_selection("PE.CPE.CATALOG21")

	@api.model
	def _get_pe_transfer_code(self):
		return self.env['pe.datas'].get_selection("PE.CPE.CATALOG20")

	@api.model
	def _completar_bultos_desde_movimientos(self):
		"""Rellena 'Cantidad Bultos' con las unidades movidas al validar.

		Solo cuando no hay contenedores: contenedor y bultos son mutuamente
		excluyentes (ERR-3621) y hasta 19.0.4.18 este relleno dejaba
		inemitible toda guía en contenedor, porque el usuario tenía que
		acordarse de limpiar el campo a mano.
		"""
		for picking in self:
			if picking.pe_contenedor_ids:
				picking.pe_unit_quantity = 0
				continue
			picking.pe_unit_quantity = sum(
				line.quantity or line.product_qty for line in picking.move_ids)

	@api.onchange('pe_contenedor_ids')
	def _onchange_pe_contenedor_ids(self):
		# Al registrar el primer contenedor los bultos pasan a cero y el
		# campo queda de solo lectura en la vista (ERR-3621).
		if self.pe_contenedor_ids and self.pe_unit_quantity:
			self.pe_unit_quantity = 0

	def _validar_puerto_embarque(self):
		"""Validación preventiva del bloque de puerto (R.S. 123-2022).

		SUNAT rechaza la GRE de exportación sin puerto (3369) y observa el
		ubigeo inconsistente (3364). Detectarlo aquí evita el rechazo del
		beta y da un mensaje accionable.
		"""
		for picking in self:
			motivo = picking.pe_transfer_code
			if motivo == '09' and not picking.pe_puerto_id:
				raise UserError(_(
					"La guía de exportación (motivo 09) exige el puerto o "
					"aeropuerto de embarque del Catálogo 63/64 — SUNAT la "
					"rechaza con el error 3369. Asigne el campo "
					"«Puerto/Aeropuerto de embarque»."))
			# 3365 (confirmado en beta, 19.0.4.22): en importación (08) el
			# punto de PARTIDA es el puerto/aeropuerto; sin él SUNAT exige el
			# establecimiento anexo de partida, que este módulo aún no emite.
			if motivo == '08' and not picking.pe_puerto_id:
				raise UserError(_(
					"La guía de importación (motivo 08) exige el puerto o "
					"aeropuerto de desembarque del Catálogo 63/64 — SUNAT la "
					"rechaza con el error 3365. Asigne el campo "
					"«Puerto/Aeropuerto de embarque»."))
			# 3364: en 09 el ubigeo de LLEGADA debe ser el del puerto; en 08
			# el de PARTIDA (la mercancía sale del puerto).
			if not picking.pe_puerto_id or not picking.pe_puerto_id.ubigeo:
				continue
			if motivo == '09':
				punto, etiqueta = picking.partner_id, _('llegada')
			elif motivo == '08':
				punto = (picking.almacen_origen.partner_id
						 or picking.picking_type_id.warehouse_id.partner_id)
				etiqueta = _('partida')
			else:
				continue
			ubigeo = punto.l10n_pe_district.code if punto and punto.l10n_pe_district else ''
			if ubigeo and ubigeo != picking.pe_puerto_id.ubigeo:
				_logging.warning(
					'GRE %s: el ubigeo del punto de %s (%s) no coincide con el '
					'del puerto %s (%s) — SUNAT rechaza con 3364.',
					picking.name, etiqueta, ubigeo,
					picking.pe_puerto_id.codigo, picking.pe_puerto_id.ubigeo)

	def validate_eguide(self):
		self._validar_puerto_embarque()
		if not self.partner_id and self.pe_transfer_code != '18':
			raise UserError(_("Customer is required"))

		if self.pe_transfer_code != '18':
			if self.picking_type_id.code != 'internal':
				if self.partner_id.id == self.company_id.partner_id.id:
					raise UserError("Destinatario no debe ser igual al remitente")
			if not self.partner_id.parent_id.doc_type and not self.partner_id.doc_type:
				raise UserError(_("Customer type document is required"))
			if not self.partner_id.parent_id.doc_number and not self.partner_id.doc_number:
				raise UserError(_("Customer number document is required"))
			if not self.partner_id.street:
				raise UserError(_("Customer street is required for %s") %
								(self.partner_id.name or ""))
			if not self.partner_id.l10n_pe_district:
				raise UserError(_("Customer district is required for %s") %
								(self.partner_id.name or ""))

		if not self.pe_carrier_id.doc_type and self.pe_transport_mode == "01":
			raise UserError(_("Carrier type document is required for %s") % (
				self.pe_carrier_id.name or ""))
		if not self.pe_carrier_id.doc_number and self.pe_transport_mode == "01":
			raise UserError(_("Carrier number document is required for %s") % (
				self.pe_carrier_id.name or ""))

		# SUNAT 01/06/2026 - Fecha de entrega de bienes al transportista
		# ERR-3617: obligatorio para modalidad 01
		# ERR-3618: debe ser >= fecha de emisión
		if self.pe_transport_mode == '01':
			if not self.pe_delivery_date:
				raise UserError(_(
					"La 'Fecha de entrega de bienes al transportista' es "
					"obligatoria para modalidad de traslado Público (01)."
				))
			fecha_emision = self.pe_date_issue or fields.Date.context_today(self)
			if self.pe_delivery_date < fecha_emision:
				raise UserError(_(
					"La 'Fecha de entrega de bienes al transportista' (%s) "
					"debe ser igual o posterior a la fecha de emisión (%s)."
				) % (self.pe_delivery_date, fecha_emision))
		if not self.picking_type_id.warehouse_id.partner_id or not self.picking_type_id.warehouse_id.partner_id.street:
			raise UserError(_("It is necessary to enter the warehouse address for %s") % (
				self.picking_type_id.warehouse_id.partner_id.name or ""))
		if self.picking_type_id.warehouse_id.partner_id and not self.picking_type_id.warehouse_id.partner_id.l10n_pe_district:
			raise UserError(_("It is necessary to enter the warehouse district for %s") % (
				self.picking_type_id.warehouse_id.partner_id.name or ""))
		if self._emite_vehiculos_conductores() and len(self.pe_fleet_ids) > 0:
			for line in self.pe_fleet_ids:
				if not line.driver_id.doc_type:
					raise UserError(_("Carrier type document is required for %s") % (
						line.driver_id.name or ""))
				if not line.driver_id.doc_number:
					raise UserError(_("Carrier number document is required for %s") % (
						line.driver_id.name or ""))

		if not self.pe_gross_weight:
			raise UserError("Peso bruto es obligatorio para guias electronicas")

		# El relleno por defecto de bultos solo aplica cuando no hay
		# contenedores registrados. Antes corría siempre y, como va ANTES de
		# _validar_indicadores_y_contenedores(), toda guía en contenedor caía
		# en el ERR-3621 con los bultos visiblemente en cero (fix 19.0.4.19).
		if not self.pe_unit_quantity and not self.pe_contenedor_ids:
			self.pe_unit_quantity = 1

		if self._emite_vehiculos_conductores() and len(self.pe_fleet_ids) == 0:
			raise UserError(_("It is necessary to add a vehicle and driver"))

		# Validaciones de documentos relacionados (SUNAT 01/06/2026)
		# Cubre ERR-3445, ERR-3493, ERR-3612, ERR-3613.
		self._validar_documentos_relacionados()

		# Validaciones de indicadores y contenedores (SUNAT 01/06/2026)
		# Cubre ERR-3451, ERR-3615, ERR-3485, ERR-3419, ERR-3420, ERR-3421,
		# ERR-3422, ERR-3621, ERR-3631, ERR-3632.
		# Va ANTES de _validar_vehiculos_conductores porque una combinación
		# de indicadores inválida es la causa raíz: si M1/L y registro de
		# vehículos están activos a la vez, el mensaje útil es el ERR-3451 y
		# no el de "no debe consignar vehículo" que se derivaría de él.
		self._validar_indicadores_y_contenedores()

		# Validaciones de vehículos y conductores (SUNAT 20/06/2026)
		# Cubre ERR-2566, ERR-3354, ERR-3357, ERR-3358, ERR-3362, ERR-3452,
		# ERR-3453, ERR-3454, ERR-3455, ERR-3616, OBS-4389, OBS-4399.
		self._validar_vehiculos_conductores()

		# Validación de documento de identidad de conductores (ERR-2571).
		self._validar_documentos_conductores()

	def _obs_es_bloqueante(self, clave, defecto=False):
		"""Indica si una regla SUNAT de tipo OBSERVACIÓN debe frenar el envío.

		Las reglas OBSERV no impiden que SUNAT acepte la guía: el CDR vuelve
		'aceptado con observaciones'. Convertirlas en bloqueo es una decisión
		de cada cliente, así que se resuelve con ir.config_parameter y no con
		un campo, para que pueda cambiarse desde
		Ajustes > Técnico > Parámetros del sistema sin actualizar el módulo
		por consola.

		Se devuelve `defecto` cuando el parámetro no existe o está vacío.
		"""
		valor = self.env['ir.config_parameter'].sudo().get_param(clave)
		if valor in (False, None) or not str(valor).strip():
			return defecto
		return str(valor).strip().lower() in VALORES_VERDADEROS

	def _emite_vehiculos_conductores(self):
		"""Indica si la guía debe llevar placa y conductor en el XML.

		Reglas de validación SUNAT (publicadas al 20/06/2026), hoja
		Guía-Remitente2_0, campos 46 al 55:

		  - Modalidad 02-Privado sin M1/L .......... obligatorio
		  - Modalidad 01-Público + 'Registro de vehículos y conductores
			del transportista' sin M1/L ............ obligatorio
		  - Modalidad 01-Público sin ese indicador . PROHIBIDO
			(ERR-3354 vehículo principal, ERR-3455 conductor principal,
			 ERR-3453 vehículos secundarios, ERR-3456 conductores
			 secundarios)
		  - Indicador M1/L verdadero ............... PROHIBIDO
		"""
		self.ensure_one()
		if self.pe_vehiculos_m1_l:
			return False
		if self.pe_transport_mode == '02':
			return True
		return self.pe_transport_mode == '01' \
			and self.pe_registro_vehiculos_conductores

	def _validar_vehiculos_conductores(self):
		"""Coherencia de vehículos y conductores frente a las reglas SUNAT."""
		self.ensure_one()
		emite = self._emite_vehiculos_conductores()

		# Caso prohibido: hay vehículos/conductores cargados pero SUNAT no
		# los admite para esta combinación de modalidad e indicadores.
		if not emite and self.pe_fleet_ids:
			if self.pe_vehiculos_m1_l:
				raise UserError(_(
					"En traslados con 'Vehículos categoría M1 o L' no se debe "
					"consignar vehículo ni conductor (ERR-3453, ERR-3455). "
					"Retire las líneas de vehículos."
				))
			raise UserError(_(
				"Para modalidad de traslado Público (01) sin el 'Indicador de "
				"registro de vehículos y conductores del transportista' NO se "
				"debe consignar placa ni conductor (ERR-3354, ERR-3455). "
				"Active el indicador o retire las líneas de vehículos."
			))

		if not emite:
			return

		# Vehículo principal: exactamente uno (ERR-2566, ERR-3358).
		principales = self.pe_fleet_ids.filtered('is_main')
		if len(principales) > 1:
			raise UserError(_(
				"Solo puede marcar un vehículo como 'Principal'. SUNAT admite "
				"un único conductor principal (ERR-3358)."
			))
		if not principales:
			principales = self.pe_fleet_ids[:1]

		secundarios = self.pe_fleet_ids - principales
		if len(secundarios) > 2:
			raise UserError(_(
				"Solo corresponde consignar hasta dos vehículos secundarios "
				"(OBS-4389). Actualmente hay %s."
			) % len(secundarios))

		# ERR-3362: no se repite la información de conductores secundarios.
		licencias = [
			(linea.driver_id.pe_driver_license or '').strip().upper()
			for linea in secundarios
			if (linea.driver_id.pe_driver_license or '').strip()
		]
		if len(licencias) != len(set(licencias)):
			raise UserError(_(
				"No debe repetirse la información de conductores secundarios: "
				"hay licencias de conducir duplicadas (ERR-3362)."
			))

		for linea in self.pe_fleet_ids:
			es_principal = linea in principales

			# ERR-2566 / ERR-2567: placa obligatoria y con formato.
			placa = (linea.name or '').strip().upper()
			if not placa:
				raise UserError(_(
					"Debe consignar el número de placa del vehículo "
					"(ERR-2566)."
				))
			if not re.match(r'^[A-Z0-9]{6,8}$', placa) or not placa.strip('0'):
				raise UserError(_(
					"La placa '%s' no cumple el formato SUNAT (ERR-2567): de 6 "
					"a 8 caracteres, solo letras mayúsculas y números, sin "
					"espacios ni guiones."
				) % placa)

			# ERR-2572 / ERR-2573: licencia de conducir del conductor.
			licencia = (linea.driver_id.pe_driver_license or '').strip().upper()
			if es_principal and not licencia:
				raise UserError(_(
					"El conductor principal '%s' no tiene número de licencia "
					"de conducir (ERR-2572). Regístrelo en la ficha del "
					"contacto."
				) % (linea.driver_id.name or ''))
			if licencia and (
				not re.match(r'^[A-Z0-9]{9,10}$', licencia)
				or not licencia.strip('0')
			):
				raise UserError(_(
					"La licencia de conducir '%s' del conductor '%s' no cumple "
					"el formato SUNAT (ERR-2573): de 9 a 10 caracteres, solo "
					"letras mayúsculas y números."
				) % (licencia, linea.driver_id.name or ''))

			# ERR-3452 / ERR-3454: la TUCE solo se admite en modalidad 01 con
			# el indicador activo. En modalidad 02 es opcional desde el
			# 01/06/2026, así que aquí solo validamos formato (ERR-3355).
			tuce = (linea.pe_tuce or '').strip().upper()
			if tuce and (
				not re.match(r'^[A-Z0-9]{10,15}$', tuce)
				or not tuce.strip('0')
			):
				raise UserError(_(
					"La TUCE / Certificado de habilitación '%s' del vehículo "
					"'%s' no cumple el formato SUNAT (ERR-3355): de 10 a 15 "
					"caracteres, solo letras mayúsculas y números."
				) % (tuce, placa))

		# OBS-4399: en modalidad 01 con el indicador, SUNAT espera la TUCE del
		# vehículo principal, pero es una OBSERVACIÓN, no un rechazo: sin ella
		# la guía se acepta igual. Por eso el bloqueo es opcional y viene
		# desactivado; se activa con el parámetro del sistema
		# 'solse_pe_cpe_guias.tuce_obligatoria'.
		if self.pe_transport_mode == '01' and not principales.pe_tuce:
			if self._obs_es_bloqueante(PARAM_TUCE_OBLIGATORIA):
				raise UserError(_(
					"Con el 'Indicador de registro de vehículos y conductores "
					"del transportista' debe consignar la TUCE / Certificado "
					"de habilitación del vehículo principal (OBS-4399). "
					"Regístrela en la ficha del vehículo o en la línea de la "
					"guía.\n\n"
					"Si prefiere emitir sin la TUCE y asumir la observación "
					"de SUNAT, ponga en 0 el parámetro del sistema "
					"'%s' (Ajustes > Técnico > Parámetros del sistema)."
				) % PARAM_TUCE_OBLIGATORIA)
			_logging.warning(
				"Guía %s (%s): se emite sin TUCE del vehículo principal. "
				"SUNAT devolverá la OBS-4399.",
				self.pe_guide_number or self.name, self.id
			)

		# ERR-3616: la fecha de inicio de traslado debe ser mayor o igual a la
		# fecha de entrega de bienes al transportista.
		if self.pe_transport_mode == '01' and self.pe_delivery_date:
			fecha_peru = convertir_fecha_a_peru(
				self.scheduled_date or self.date_done
			)
			fecha_inicio = fecha_peru and fecha_peru.date() or False
			if fecha_inicio and fecha_inicio < self.pe_delivery_date:
				raise UserError(_(
					"La 'Fecha de inicio de traslado' (%s) debe ser igual o "
					"posterior a la 'Fecha de entrega de bienes al "
					"transportista' (%s) (ERR-3616)."
				) % (fecha_inicio, self.pe_delivery_date))

	def _validar_documentos_conductores(self):
		"""SUNAT ERR-2571: el conductor (persona natural) NO puede tener RUC.
		El catálogo 06 acepta para conductor: 1=DNI, 4=Carnet extranjería,
		7=Pasaporte, A=Cédula diplomática. NUNCA 6=RUC.

		Para RUC peruano de persona natural (inicia con '10'), el sistema
		extrae automáticamente el DNI subyacente al generar el XML, así que
		ese caso se permite con un mensaje informativo opcional.
		Para RUC empresarial ('20...') se bloquea.
		"""
		self.ensure_one()
		# Aplica siempre que la guía lleve conductores: modalidad 02 o
		# modalidad 01 con 'Registro de vehículos y conductores'.
		if not self._emite_vehiculos_conductores():
			return

		tipos_validos = {'1', '4', '7', 'A'}
		for line in self.pe_fleet_ids:
			driver = line.driver_id
			if not driver:
				continue
			doc_type = driver.doc_type
			doc_number = (driver.doc_number or '').strip()

			# RUC empresarial: nunca puede ser conductor.
			if doc_type == '6' and doc_number.startswith('20'):
				raise UserError(_(
					"El conductor '%s' tiene RUC empresarial (%s). Un "
					"conductor debe ser persona natural identificada con "
					"DNI (1), Carnet de extranjería (4), Pasaporte (7) o "
					"Cédula diplomática (A). Corrija el tipo de documento "
					"del contacto."
				) % (driver.name, doc_number))

			# Tipos no aceptados por SUNAT para conductor (distintos de 6).
			if doc_type and doc_type != '6' and doc_type not in tipos_validos:
				raise UserError(_(
					"El conductor '%s' tiene tipo de documento '%s' que no "
					"es válido para SUNAT. Acepta solo DNI (1), Carnet de "
					"extranjería (4), Pasaporte (7) o Cédula diplomática (A)."
				) % (driver.name, doc_type))

	def _validar_documentos_relacionados(self):
		"""Reglas SUNAT actualizadas al 01/06/2026 sobre documentos relacionados
		a la guía de remisión.

		Implementa validaciones cliente-side de:
		  - ERR-3445: tipos de documento permitidos según motivo de traslado
		  - ERR-3493: motivo 19 requiere al menos un doc tipo 50, 52, 91 o 92
		  - ERR-3612: motivo 19 solo permite un documento tipo 92
		  - ERR-3613: doc 92 no coexiste con docs 50, 52 o 91
		"""
		self.ensure_one()
		documentos = self.pe_documento_relacionado_ids
		motivo = self.pe_transfer_code

		# ERR-3493: motivo 19 (mercancía extranjera) requiere al menos un doc
		# tipo 50, 52, 91 o 92.
		if motivo == '19':
			tipos_validos_19 = {'50', '52', '91', '92'}
			if not documentos or not any(
				d.codigo_documento in tipos_validos_19 for d in documentos
			):
				raise UserError(_(
					"Para motivo de traslado 19 (Traslado de mercancía "
					"extranjera) debe registrar al menos un documento "
					"relacionado de tipo: DAM (50), DS (52), Manifiesto de "
					"Carga (91) o Cita/Orden Terminal Portuario (92)."
				))

		if not documentos:
			return

		tipos = documentos.mapped('codigo_documento')

		# ERR-3445: tipos permitidos por motivo
		if motivo in ('08', '09'):
			permitidos = {'09', '49', '50', '52', '80'}
			invalidos = set(tipos) - permitidos
			if invalidos:
				raise UserError(_(
					"Para motivo %s los tipos de documento relacionado %s no "
					"son permitidos. Permitidos: %s."
				) % (motivo, ', '.join(sorted(invalidos)), ', '.join(sorted(permitidos))))

		if motivo == '13' and '52' in tipos:
			# Cambio 01/06/2026 - motivo 13 ya NO permite tipo 52 (DS)
			raise UserError(_(
				"Para motivo 13 el tipo de documento relacionado 52 (DS) "
				"no es permitido."
			))

		if motivo == '19':
			permitidos = {'50', '52', '91', '92'}
			invalidos = set(tipos) - permitidos
			if invalidos:
				raise UserError(_(
					"Para motivo 19 los tipos %s no son permitidos. "
					"Permitidos: 50, 52, 91, 92."
				) % ', '.join(sorted(invalidos)))

		# Restricciones cruzadas (no permitir docs aduaneros con motivos
		# que no sean 08/09/13/19).
		if motivo not in ('08', '09', '13', '19'):
			conflictivos = set(tipos) & {'50', '52'}
			if conflictivos:
				raise UserError(_(
					"El tipo de documento %s solo es permitido para motivos "
					"08, 09, 13 (solo 50) o 19."
				) % ', '.join(sorted(conflictivos)))

		if motivo != '19':
			conflictivos = set(tipos) & {'91', '92'}
			if conflictivos:
				raise UserError(_(
					"Los tipos 91 y 92 solo son permitidos para motivo de "
					"traslado 19."
				))

		# ERR-3612: solo un documento tipo 92 para motivo 19
		if motivo == '19':
			cantidad_92 = tipos.count('92')
			if cantidad_92 > 1:
				raise UserError(_(
					"Solo se permite una Cita/Orden Entrega Mercancías del "
					"Terminal Portuario (tipo 92) para el motivo de "
					"traslado 19."
				))

			# ERR-3613: si hay 92 no puede haber 50, 52 o 91
			if cantidad_92 == 1:
				incompatibles = set(tipos) & {'50', '52', '91'}
				if incompatibles:
					raise UserError(_(
						"Si existe un documento relacionado tipo 92 no puede "
						"coexistir con documentos tipo 50, 52 o 91. "
						"Encontrados: %s."
					) % ', '.join(sorted(incompatibles)))

	def _validar_indicadores_y_contenedores(self):
		"""Reglas SUNAT 01/06/2026 para indicadores especiales y contenedores.

		Implementa:
		  - ERR-3451: indicador de registro de vehículos y conductores y
			traslado en vehículos M1/L no pueden coexistir.
		  - ERR-3615: indicador transbordo programado y registro vehículos
			no pueden coexistir (modalidad 01).
		  - ERR-3485: traslado total DAM/DS solo aplica para docs 50 o 52
			(NO para 92, que ya tiene su propio sub-régimen).
		  - ERR-3621: contenedor y bultos son mutuamente excluyentes.
		  - ERR-3420 / ERR-3421: máximo dos contenedores, sin repetidos.
		  - ERR-3419 (motivo 09) y ERR-3631 / ERR-3632 (motivos 08/19): con
			doc 50/52 y sin contenedor, los bultos son obligatorios. Ninguna
			prohíbe el contenedor (Excel 20/06/2026).
		  - ERR-3422: con contenedor y sin indicador de manifiesto de carga,
			el precinto es obligatorio (motivo 09, o 08/09/19 con traslado
			total).
		"""
		self.ensure_one()
		motivo = self.pe_transfer_code
		tipos_docs = self.pe_documento_relacionado_ids.mapped('codigo_documento')
		tiene_contenedor = bool(self.pe_contenedor_ids)
		tiene_bultos = bool(self.pe_unit_quantity and self.pe_unit_quantity > 0)

		# ERR-3451: el indicador de registro de vehículos y conductores no
		# puede coexistir con el de traslado en vehículos M1 o L. Sin esta
		# comprobación se emitían ambos SpecialInstructions y, además, el
		# helper _emite_vehiculos_conductores() suprimía placa y conductor
		# en silencio.
		if self.pe_registro_vehiculos_conductores and self.pe_vehiculos_m1_l:
			raise UserError(_(
				"No puede activar simultáneamente 'Registro de vehículos y "
				"conductores del transportista' y 'Traslado en vehículos "
				"categoría M1 o L' (ERR-3451)."
			))

		# ERR-3615: exclusión transbordo programado vs registro vehículos
		if self.pe_transport_mode == '01':
			if self.pe_transbordo_programado and self.pe_registro_vehiculos_conductores:
				raise UserError(_(
					"No puede activar simultáneamente 'Transbordo programado' "
					"y 'Registro de vehículos y conductores' para modalidad "
					"de traslado Público (01)."
				))

		# Indicadores que solo aplican a modalidad 01
		if self.pe_transport_mode != '01':
			if self.pe_transbordo_programado:
				raise UserError(_(
					"'Transbordo programado' solo aplica para modalidad "
					"de traslado Público (01)."
				))
			if self.pe_registro_vehiculos_conductores:
				raise UserError(_(
					"'Registro de vehículos y conductores' solo aplica para "
					"modalidad de traslado Público (01)."
				))

		# ERR-3485: traslado total DAM/DS solo para docs 50 o 52
		if self.pe_traslado_total_dam:
			docs_validos = {'50', '52'} & set(tipos_docs)
			if not docs_validos:
				raise UserError(_(
					"'Traslado total de bienes amparados por DAM o DS' "
					"requiere al menos un documento relacionado tipo "
					"50 (DAM) o 52 (DS)."
				))
			# Regla 39 de la estructura GRE: el indicador de traslado
			# total de la DAM/DS aplica a 08 Importación, 09 Exportación
			# y 19 Mercancía extranjera. La versión anterior excluía la
			# exportación por error y bloqueaba las guías del motivo 09.
			if motivo not in ('08', '09', '19'):
				raise UserError(_(
					"'Traslado total de bienes amparados por DAM o DS' "
					"solo aplica para motivos de traslado 08, 09 o 19."
				))

		# Sub-régimen 19+92: NO debe consignar contenedor ni bultos
		# (ERR-3625 a ERR-3628). Las validaciones de tags suprimidos son
		# server-side; aquí solo validamos coherencia de los datos del usuario.
		if self.pe_es_subregimen_19_92:
			if tiene_contenedor:
				raise UserError(_(
					"En el sub-régimen Motivo 19 + Documento 92 no se debe "
					"registrar contenedor. Elimine los contenedores antes "
					"de generar la guía."
				))
			# La cantidad de bultos no se enviará en el XML; el usuario
			# puede dejarla pero se ignora.
			return

		# ERR-3621: contenedor y bultos mutuamente excluyentes
		if tiene_contenedor and tiene_bultos:
			raise UserError(_(
				"No se permite registrar simultáneamente contenedores y "
				"cantidad de bultos (ERR-3621). La guía tiene %d contenedor(es) "
				"y %d bulto(s). Si la carga va en contenedor, deje la cantidad "
				"de bultos en cero; tenga en cuenta que Odoo la completa con las "
				"unidades movidas al validar la transferencia.",
				len(self.pe_contenedor_ids), self.pe_unit_quantity))

		# ERR-3420 / ERR-3421: máximo dos contenedores y sin repetidos.
		if tiene_contenedor:
			numeros = [(c.numero_contenedor or '').strip().upper()
					   for c in self.pe_contenedor_ids]
			if len(numeros) > 2:
				raise UserError(_(
					"SUNAT admite como máximo dos contenedores por guía "
					"(ERR-3420); la guía tiene %d.", len(numeros)))
			if len(set(numeros)) != len(numeros):
				raise UserError(_(
					"El número de contenedor no debe repetirse (ERR-3421)."))

		# ERR-3419 / ERR-3631 / ERR-3632: contenedor XOR bultos.
		# Contrastado con el Excel del 20/06/2026: ninguna de las tres reglas
		# prohíbe el contenedor; las tres exigen bultos únicamente cuando NO
		# hay contenedor. La versión anterior bloqueaba "traslado total +
		# contenedor", combinación que el propio ERR-3422 contempla como
		# válida. Alcance: 3419 → motivo 09; 3631/3632 → motivos 08 y 19.
		tiene_doc_aduanero = bool({'50', '52'} & set(tipos_docs))
		if motivo in ('08', '09', '19') and tiene_doc_aduanero:
			if not tiene_contenedor and not tiene_bultos:
				regla = 'ERR-3419' if motivo == '09' else (
					'ERR-3631' if self.pe_traslado_total_dam else 'ERR-3632')
				raise UserError(_(
					"Para el motivo %s con DAM/DS (documento 50 o 52) debe "
					"registrar al menos un contenedor o la cantidad de bultos "
					"o pallets (%s).", motivo, regla))

		# ERR-3422: con contenedor, el precinto es obligatorio. El Excel lo
		# condiciona a que NO esté activo el indicador de traslado en
		# contenedor del manifiesto de carga, y lo exige en dos casos:
		#   - motivo 09 sin indicador de traslado total (filas 218/227)
		#   - motivos 08/09/19 con indicador de traslado total (219/228)
		if tiene_contenedor and not self.pe_traslado_contenedor_mc:
			exige_precinto = self.pe_traslado_total_dam and motivo in ('08', '09', '19')
			exige_precinto = exige_precinto or motivo == '09'
			if exige_precinto:
				sin_precinto = self.pe_contenedor_ids.filtered(
					lambda c: not (c.numero_precinto or '').strip())
				if sin_precinto:
					raise UserError(_(
						"Todo contenedor debe llevar número de precinto "
						"(ERR-3422). Sin precinto: %s.",
						', '.join(sin_precinto.mapped('numero_contenedor'))))

	def action_generate_eguide(self):
		for stock in self:
			if stock.pe_is_eguide:
				self.validate_eguide()
				self.pe_date_issue = fields.Date.context_today(self)
				if stock.pe_guide_number == '/':
					if stock.picking_type_id.warehouse_id.eguide_sequence_id:
						stock.pe_guide_number = stock.picking_type_id.warehouse_id.eguide_sequence_id.next_by_id()
					else:
						# L-8 (corrida 2 de MULTIEMPRESA): sin with_company el correlativo
						# sale de la compañía ACTIVA del usuario, no de la del picking
						# — dos razones sociales mezclarían numeración entre RUCs.
						stock.pe_guide_number = self.env['ir.sequence'].with_company(stock.company_id).next_by_code('pe.eguide.sync')
						if not stock.pe_guide_number:
							raise UserError("No se pudo encontrar una secuencia de guías por defecto para la empresa %s" % self.company_id.name)

				if not re.match(r'^(T){1}[A-Z0-9]{3}\-\d+$', stock.pe_guide_number):
					raise UserError("El numero de la guia ingresada no cumple con el estandar.\n"
									"Verificar la secuencia del Diario por jemplo T001- o TG01-. \n"
									"Para cambiar ir a Configuracion/Gestion de Almacenes/Almacenes")
				if not self.pe_guide_id:
					pe_guide_id = self.env['solse.cpe.eguide'].create_from_stock(
						stock)
					stock.pe_guide_id = pe_guide_id.id
				else:
					pe_guide_id = stock.pe_guide_id
				if stock.company_id.pe_is_sync:
					pe_guide_id.generate_eguide()
					pe_guide_id.action_send()
					time.sleep(3)
					try:
						pe_guide_id.action_done()
					except Exception as e:
						_logging.info("error al consultar los datos del ticket para guias de remision")
						_logging.info(e)
						pass
				else:
					pe_guide_id.generate_eguide()
				self.pe_number = stock.pe_guide_number


class PeStockFleet(models.Model):
	_name = "pe.stock.fleet"
	_description = 'Stock Fleet'

	name = fields.Char("Placa", required=True)
	fleet_id = fields.Many2one(comodel_name="fleet.vehicle", string="Vehículo")
	picking_id = fields.Many2one(comodel_name="stock.picking", string="Guía")
	driver_id = fields.Many2one(comodel_name="res.partner", string="Conductor", required=True)
	is_main = fields.Boolean("Principal")
	pe_tuce = fields.Char(
		string="TUCE / Cert. habilitación",
		help="Tarjeta Única de Circulación Electrónica o Certificado de "
			 "Habilitación Vehicular. Se toma del vehículo al seleccionarlo "
			 "y puede editarse por guía. SUNAT lo espera (OBS-4399) cuando "
			 "la modalidad es 01-Público con 'Registro de vehículos y "
			 "conductores del transportista'; su ausencia se observa pero no "
			 "impide la aceptación. Para exigirlo antes del envío, ponga en 1 "
			 "el parámetro del sistema "
			 "'solse_pe_cpe_guias.tuce_obligatoria'."
	)

	@api.onchange("fleet_id")
	def onchange_fleet_id(self):
		if self.fleet_id:
			self.name = self.fleet_id.license_plate
			self.driver_id = self.fleet_id.driver_id.id
			# La TUCE se registra en fleet.vehicle y se arrastra a la guía.
			self.pe_tuce = self.fleet_id.pe_tuce or False


class Warehouse(models.Model):
	_inherit = "stock.warehouse"

	eguide_sequence_id = fields.Many2one('ir.sequence', string='Secuencia de guía electrónica', )
	mostrar_loteserie_porlineas = fields.Boolean("Mostrar Serie/Lote detallatado")

