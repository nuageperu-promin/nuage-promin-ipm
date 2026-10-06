# -*- coding: utf-8 -*-
#
#
# IMPORTANTE: todos los métodos que existen en solse_pe_cpe_guias se
# extienden llamando a super(). En la v17 este módulo redefinía
# `action_cancel_eguide` y `_compute_editar_xml` sin super(), lo que
# rompía la Guía de Remisión Remitente apenas se instalaba. Esa es la
# causa raíz de que no se pudieran emitir ambas guías.

import re
import time
from io import BytesIO

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.solse_pe_cpe_guias.models.stock import qr_mod, encodestring
try:
	import qrcode
except ImportError:
	qrcode = None

from .res_company import MODALIDAD_GUIA

import logging

_logging = logging.getLogger(__name__)


# Entidades que emiten autorizaciones especiales de circulación (campo 11 de
# la hoja Guía-Transportista2_0; atributo schemeID del cbc:CompanyID).
ENTIDADES_AUTORIZADORAS = [
	('01', '01 - SUCAMEC'),
	('02', '02 - DIGEMID'),
	('03', '03 - DIGESA'),
	('04', '04 - SENASA'),
	('05', '05 - SERFOR'),
	('06', '06 - MTC'),
	('07', '07 - PRODUCE'),
	('08', '08 - Ministerio del Ambiente'),
	('09', '09 - SANIPES'),
	('10', '10 - Municipalidad Metropolitana de Lima'),
	('11', '11 - MINSA'),
	('12', '12 - Gobierno Regional'),
]

# ERR-3441 para la GRT (hoja Guía-Transportista2_0, reglas del 20/06/2026).
# El constraint del módulo base solo conoce los tipos de la GRR; la 31
# admite documentos que allí no tienen patrón (31, 50 con régimen 10/40,
# 65-69, 82).
PATRONES_DOCUMENTO_GRT = {
	'09': r'^[T][A-Z0-9]{3}-\d{1,8}$|^EG07-\d{1,8}$|^EG02-\d{1,8}$|^\d{1,4}-\d{1,8}$',
	'31': r'^[V][A-Z0-9]{3}-\d{1,8}$|^EG03-\d{1,8}$|^EG04-\d{1,8}$',
	'50': r'^\d{3}-\d{4}-(10|40)-[1-9]\d{0,5}$',
	'65': r'^\S{1,100}$',
	'66': r'^\S{1,100}$',
	'67': r'^\S{1,100}$',
	'68': r'^\S{1,100}$',
	'69': r'^\S{1,100}$',
	'82': r'^\S{1,100}$',
}


# Catálogo de pagador del flete (campo 58 de la hoja Guía-Transportista2_0).
PAGADOR_FLETE = [
	('remitente', 'Remitente'),
	('subcontratador', 'Subcontratador'),
	('tercero', 'Tercero'),
]

# Tipo de evento (campo 59). Uso exclusivo de los casos excepcionales.
TIPO_EVENTO_GRT = [
	('1', '1 - Transbordo no programado'),
	('2', '2 - Imposibilidad de arribo al punto de llegada'),
	('3', '3 - Imposibilidad de entrega al destinatario'),
]

UNIDAD_PESO_GRT = [
	('KGM', 'Kilogramos'),
	('TNE', 'Toneladas'),
]

# Documentos de identidad aceptados por SUNAT para el pagador del flete
# cuando es un tercero (campo 62): DNI y RUC.
DOCS_PAGADOR_TERCERO = ('1', '6')


class Picking(models.Model):
	_inherit = "stock.picking"

	# ------------------------------------------------------------------
	# Modalidad: por Tipo de Operación, editable por transferencia
	# ------------------------------------------------------------------
	pe_guide_mode = fields.Selection(
		selection=MODALIDAD_GUIA,
		string='Modalidad de guía',
		compute='_compute_pe_guide_mode',
		store=True,
		readonly=False,
		copy=True,
		help="Toma el valor del Tipo de Operación y puede ajustarse en cada "
			 "transferencia. Determina si se emite la Guía de Remisión "
			 "Remitente (09) o la Transportista (31).",
	)

	@api.depends('picking_type_id', 'company_id')
	def _compute_pe_guide_mode(self):
		for registro in self:
			modalidad = registro.picking_type_id.pe_guide_mode \
				or registro.company_id.pe_guide_mode \
				or 'sender'
			registro.pe_guide_mode = modalidad

	# ------------------------------------------------------------------
	# Enlaces al documento electrónico de la GRT
	# ------------------------------------------------------------------
	pe_guide_transport_id = fields.Many2one(
		comodel_name="solse.cpe.eguide.transport",
		string="Guía electrónica transportista",
		copy=False,
	)
	pe_voided_transport_id = fields.Many2one(
		comodel_name="solse.cpe.eguide.transport",
		string="Guía transportista cancelada",
		copy=False,
	)
	pe_response_transp = fields.Char(
		"Respuesta (GRT)", related="pe_guide_transport_id.response"
	)
	pe_note_transp = fields.Text(
		"Nota SUNAT (GRT)", related="pe_guide_transport_id.note"
	)
	pe_error_code_transp = fields.Selection(
		string="Código de error (GRT)",
		related="pe_guide_transport_id.error_code",
		readonly=True,
	)
	pe_guide_transport_state = fields.Selection(
		string='Estado de la GRT', related="pe_guide_transport_id.state"
	)
	pe_digest_transp = fields.Char(
		"Digest (GRT)", related="pe_guide_transport_id.digest"
	)
	pe_signature_transp = fields.Text(
		"Firma (GRT)", related="pe_guide_transport_id.signature"
	)

	# ------------------------------------------------------------------
	# Partes del traslado (campos 16 a 19)
	# ------------------------------------------------------------------
	pe_grt_remitente_id = fields.Many2one(
		comodel_name='res.partner',
		string='Remitente',
		copy=False,
		help="Titular de los bienes que contrata el servicio de transporte. "
			 "Se emite en cac:Delivery/cac:Despatch/cac:DespatchParty.",
	)
	pe_grt_destinatario_id = fields.Many2one(
		comodel_name='res.partner',
		string='Destinatario',
		copy=False,
		help="Quien recibe los bienes. Se emite en cac:DeliveryCustomerParty.",
	)
	pe_grt_punto_partida_id = fields.Many2one(
		comodel_name='res.partner',
		string='Punto de partida',
		copy=False,
		help="Dirección de recojo. Si se deja vacío se usa la del remitente.",
	)
	pe_grt_punto_llegada_id = fields.Many2one(
		comodel_name='res.partner',
		string='Punto de llegada',
		copy=False,
		help="Dirección de entrega. Si se deja vacío se usa la del destinatario.",
	)

	# ------------------------------------------------------------------
	# Datos del traslado (campos 10, 11, 49 a 52)
	# ------------------------------------------------------------------
	pe_grt_fecha_inicio_traslado = fields.Date(
		string='Fecha de inicio del traslado',
		copy=False,
		help="No puede ser anterior a la fecha de emisión de la guía.",
	)
	pe_grt_peso_unidad = fields.Selection(
		selection=UNIDAD_PESO_GRT,
		string='Unidad del peso bruto',
		default='KGM',
		copy=False,
	)
	pe_grt_registro_mtc = fields.Char(
		string='Número de Registro MTC',
		copy=False,
		help="Registro del transportista ante el MTC. Se emite en "
			 "cac:ShipmentStage/cac:CarrierParty/cac:PartyLegalEntity/cbc:CompanyID.",
	)
	pe_grt_autorizacion_numero = fields.Char(
		string='Número de autorización especial',
		copy=False,
		help="Autorización especial de circulación (MATPEL, carga en Lima, "
			 "productos pesqueros, etc.). SUNAT rechaza si se consigna más "
			 "de una autorización.",
	)
	pe_grt_autorizacion_entidad = fields.Selection(
		selection=ENTIDADES_AUTORIZADORAS,
		string='Entidad autorizadora',
		copy=False,
		help="Entidad que emite la autorización especial. Su código se "
			 "emite como atributo schemeID de cbc:CompanyID.",
	)
	pe_grt_anotacion = fields.Char(
		string='Anotación sobre los bienes',
		copy=False,
		help="Descripción libre de la carga. Solo se emite (en una línea con "
			 "ID 0) cuando un documento relacionado ampara los bienes: GRE "
			 "física (09 con serie numérica), tipo 82, o 01/04 físicos y "
			 "03/12/48 con traslado total. En otro caso la guía detalla los "
			 "productos de la transferencia (regla 3458).",
	)
	pe_grt_tipo_evento = fields.Selection(
		selection=TIPO_EVENTO_GRT,
		string='Tipo de evento',
		copy=False,
		help="Solo para transbordo no programado o imposibilidad de arribo "
			 "o entrega.",
	)

	# ------------------------------------------------------------------
	# Indicadores SUNAT de la GRT (campos 53 a 58)
	# ------------------------------------------------------------------
	pe_grt_traslado_total = fields.Boolean(
		string='Traslado total de bienes', copy=False
	)
	pe_grt_retorno_envase_vacio = fields.Boolean(
		string='Retorno de vehículo con envases o embalajes vacíos', copy=False
	)
	pe_grt_retorno_vehiculo_vacio = fields.Boolean(
		string='Retorno de vehículo vacío', copy=False
	)
	pe_grt_transbordo_programado = fields.Boolean(
		string='Transbordo programado', copy=False
	)
	pe_grt_subcontratado = fields.Boolean(
		string='Transporte subcontratado', copy=False
	)
	pe_grt_subcontratador_id = fields.Many2one(
		comodel_name='res.partner',
		string='Empresa subcontratadora',
		copy=False,
		help="Transportista que subcontrata el servicio. Su RUC no puede "
			 "ser el mismo del emisor de la guía.",
	)
	pe_grt_pagador_flete = fields.Selection(
		selection=PAGADOR_FLETE,
		string='Pagador del flete',
		copy=False,
		help="Indicador obligatorio en la GRT.",
	)
	pe_grt_pagador_tercero_id = fields.Many2one(
		comodel_name='res.partner',
		string='Tercero que paga el flete',
		copy=False,
		help="Solo se completa cuando el pagador del flete es un tercero.",
	)

	# ------------------------------------------------------------------
	# Overrides no destructivos
	# ------------------------------------------------------------------
	def action_generate_eguide(self):
		"""Solo procesa las transferencias en modalidad remitente."""
		remitentes = self.filtered(lambda p: p.pe_guide_mode != 'carrier')
		if not remitentes:
			return True
		return super(Picking, remitentes).action_generate_eguide()

	def action_cancel_eguide(self):
		"""Da de baja la guía que corresponda a cada modalidad."""
		super(Picking, self).action_cancel_eguide()
		for picking_id in self:
			if picking_id.pe_guide_mode != 'carrier':
				continue
			guia = picking_id.pe_guide_transport_id
			if guia and guia.state not in ["draft", "generate", "cancel"]:
				voided_id = self.env['solse.cpe.eguide.transport'].get_eguide_async(
					'low', picking_id
				)
				picking_id.pe_voided_transport_id = voided_id.id

	# ------------------------------------------------------------------
	# Validaciones cliente-side de la GRT
	# ------------------------------------------------------------------
	def _validar_partes_grt(self):
		"""Remitente y destinatario son obligatorios (campos 16 a 19)."""
		self.ensure_one()
		for partner, etiqueta in (
			(self.pe_grt_remitente_id, _("remitente")),
			(self.pe_grt_destinatario_id, _("destinatario")),
		):
			if not partner:
				raise UserError(
					_("Debe indicar el %s de la guía de transportista.") % etiqueta
				)
			if not partner.doc_type or not partner.doc_number:
				raise UserError(_(
					"El %s %s no tiene tipo o número de documento de identidad."
				) % (etiqueta, partner.name or ''))

		emisor = self.company_id.partner_id
		if self.pe_grt_remitente_id.doc_number == emisor.doc_number:
			raise UserError(_(
				"El remitente no puede ser la misma empresa que emite la "
				"guía de transportista."
			))

	def _validar_direcciones_grt(self):
		"""Ubigeo y dirección de partida y llegada (campos 29, 30, 32, 33)."""
		self.ensure_one()
		partida = self.pe_grt_punto_partida_id or self.pe_grt_remitente_id
		llegada = self.pe_grt_punto_llegada_id or self.pe_grt_destinatario_id
		for partner, etiqueta in (
			(partida, _("punto de partida")),
			(llegada, _("punto de llegada")),
		):
			if not partner.l10n_pe_district:
				raise UserError(_(
					"Falta el distrito (ubigeo) del %s: %s"
				) % (etiqueta, partner.name or ''))
			if not partner.street:
				raise UserError(_(
					"Falta la dirección del %s: %s"
				) % (etiqueta, partner.name or ''))

	def _validar_vehiculos_grt(self):
		"""La placa es obligatoria en la GRT (campo 35). El resto (formato
		de placa, licencia y TUCE, un solo principal, máximo dos secundarios)
		lo valida el módulo base con pe_transport_mode = '02'."""
		self.ensure_one()
		if not self.pe_fleet_ids:
			raise UserError(_(
				"La guía de transportista exige al menos un vehículo con placa."
			))
		if len(self.pe_fleet_ids) > 3:
			raise UserError(_(
				"SUNAT admite un vehículo principal y hasta dos secundarios. "
				"Actualmente hay %s registrados."
			) % len(self.pe_fleet_ids))
		self._validar_vehiculos_conductores()

	def _validar_conductores_grt(self):
		"""Conductor principal con licencia (campo 44) y documento de
		identidad admitido (ERR-2571, helper del base)."""
		self.ensure_one()
		principal = self.pe_fleet_ids.filtered('is_main')[:1] \
			or self.pe_fleet_ids[:1]
		if not principal.driver_id:
			raise UserError(_(
				"El vehículo principal no tiene conductor asignado."
			))
		self._validar_documentos_conductores()

	def _validar_documentos_grt(self):
		"""ERR-3441 con los patrones propios de la 31.

		Los tipos que la GRT no admite como relacionados en la hoja
		Guía-Transportista2_0 (p.ej. 52, 91, 92) se rechazan aquí para
		evitar el viaje a SUNAT. ERR-3620 / ERR-3622 (GRE única o de baja
		como documento relacionado) son validaciones REST del lado de
		SUNAT y no pueden comprobarse localmente.
		"""
		self.ensure_one()
		admitidos = set(PATRONES_DOCUMENTO_GRT) | {'01', '03', '04', '12', '48', '80', '93', '94', '95'}
		for documento in self.pe_documento_relacionado_ids:
			codigo = documento.codigo_documento
			if codigo not in admitidos:
				raise UserError(_(
					"El tipo de documento relacionado %s no está previsto para "
					"la guía de transportista (hoja Guía-Transportista2_0)."
				) % codigo)
			patron = PATRONES_DOCUMENTO_GRT.get(codigo)
			numero = (documento.numero_documento or '').strip()
			if patron and not re.match(patron, numero):
				raise UserError(_(
					"El número '%s' del documento relacionado tipo %s no cumple "
					"el formato de la guía de transportista (ERR-3441)."
				) % (numero, codigo))

	def _validar_indicadores_grt(self):
		"""Coherencia de los indicadores y sus datos asociados."""
		self.ensure_one()
		if not self.pe_grt_pagador_flete:
			raise UserError(_(
				"El indicador de pagador del flete es obligatorio en la guía "
				"de transportista."
			))

		if self.pe_grt_subcontratado:
			if not self.pe_grt_subcontratador_id:
				raise UserError(_(
					"Marcó transporte subcontratado: debe indicar la empresa "
					"subcontratadora."
				))
			subcontratador = self.pe_grt_subcontratador_id
			if subcontratador.doc_type != '6' or not subcontratador.doc_number:
				raise UserError(_(
					"La empresa subcontratadora %s debe tener RUC registrado."
				) % (subcontratador.name or ''))
			if subcontratador.doc_number == self.company_id.partner_id.doc_number:
				raise UserError(_(
					"El RUC de la empresa subcontratadora no puede ser el "
					"mismo del transportista emisor."
				))

		if self.pe_grt_pagador_flete == 'tercero':
			tercero = self.pe_grt_pagador_tercero_id
			if not tercero:
				raise UserError(_(
					"Indicó que el flete lo paga un tercero: debe registrar "
					"a ese tercero."
				))
			if tercero.doc_type not in DOCS_PAGADOR_TERCERO or not tercero.doc_number:
				raise UserError(_(
					"El tercero que paga el flete debe identificarse con DNI "
					"o RUC."
				))

		if self.pe_grt_registro_mtc and self.pe_grt_autorizacion_numero:
			raise UserError(_(
				"Solo puede consignar un número de autorización: Registro MTC "
				"o autorización especial, no ambos."
			))

	def _validar_bienes_grt(self):
		"""Regla 3435: con documentos 01/03/04/12/48/50/52 sin traslado
		total, o sin ningún documento que ampare (01/03/04/12/48/50/52/09/
		82), la GRT debe detallar al menos un bien con cantidad mayor a
		cero. Con GRE física (09 serie numérica) o 82 se emite la línea 0."""
		self.ensure_one()
		from .eguide_transport import EGuideTransport
		generador = EGuideTransport()
		if generador._admite_linea_anotacion(self):
			return
		con_cantidad = self.move_ids.filtered(
			lambda m: (m.quantity or m.product_uom_qty) > 0)
		if not con_cantidad and generador._exige_detalle_bienes(self):
			raise UserError(_(
				"La guía de transportista debe detallar los bienes (al menos "
				"un producto con cantidad mayor a cero) porque ningún "
				"documento relacionado los ampara (regla 3435). La anotación "
				"sola (línea 0) solo se admite con GRE-Remitente física (09 "
				"con serie numérica), documento 82, o 01/04 físicos y "
				"03/12/48 con el indicador de traslado total."
			))

	def validate_eguide_transport(self):
		"""Validaciones previas al envío de la GRT.

		NOTA: no se reutiliza `_validar_documentos_relacionados()` del
		módulo base porque sus reglas dependen del motivo de traslado
		(`pe_transfer_code`), que es un concepto de la GRR: la 31 no lleva
		motivo y admite documentos (50, 52, 65-69) que esas reglas
		bloquearían. Las validaciones de emisor y formato de los
		documentos relacionados siguen activas: son @api.constrains del
		modelo `pe.stock.documento.relacionado` y se disparan solas
		(ERR-3380, ERR-3382, ERR-3614, ERR-3441).
		"""
		self.ensure_one()

		# En la GRT el emisor es el propio transportista, es decir siempre
		# hay vehículos y conductores propios en el documento. Se normaliza
		# `pe_transport_mode` a '02' para que las validaciones y el helper
		# ERR-2571 del módulo base se apliquen. El tag no forma parte del
		# XML de la 31, así que el valor no llega a SUNAT.
		if self.pe_transport_mode != '02':
			self.pe_transport_mode = '02'

		self._validar_partes_grt()
		self._validar_direcciones_grt()
		self._validar_vehiculos_grt()
		self._validar_conductores_grt()
		self._validar_indicadores_grt()
		self._validar_documentos_grt()
		self._validar_bienes_grt()

		if not self.pe_gross_weight:
			raise UserError(_(
				"El peso bruto total de la carga es obligatorio."
			))

		fecha_inicio = self.pe_grt_fecha_inicio_traslado
		if fecha_inicio and self.pe_date_issue and fecha_inicio < self.pe_date_issue:
			raise UserError(_(
				"La fecha de inicio del traslado no puede ser anterior a la "
				"fecha de emisión de la guía."
			))

	# ------------------------------------------------------------------
	# Emisión de la GRT
	# ------------------------------------------------------------------
	def _obtener_numero_guia_transporte(self):
		"""Numeración de la GRT: serie V###- (campo 3)."""
		self.ensure_one()
		secuencia = self.picking_type_id.warehouse_id.eguide_transport_sequence_id
		if secuencia:
			return secuencia.next_by_id()
		# Correlativo de la compañía del picking, no de la activa del usuario.
		numero = self.env['ir.sequence'].with_company(
			self.company_id).next_by_code('pe.eguide.transport.sync')
		if not numero:
			raise UserError(_(
				"No se encontró una secuencia de guía de transportista para "
				"la empresa %s."
			) % self.company_id.name)
		return numero

	def action_generate_eguide_transport(self):
		for stock in self:
			if not stock.pe_is_eguide or stock.pe_guide_mode != 'carrier':
				continue
			stock.validate_eguide_transport()
			stock.pe_date_issue = fields.Date.context_today(stock)

			if stock.pe_guide_number == '/':
				stock.pe_guide_number = stock._obtener_numero_guia_transporte()

			if not re.match(r'^(V){1}[A-Z0-9]{3}\-\d+$', stock.pe_guide_number):
				raise UserError(_(
					"El número de la guía de transportista no cumple con el "
					"estándar SUNAT (V###-NNNNNNNN).\n"
					"Verificar la secuencia del almacén, por ejemplo V001- o "
					"VG01-.\n"
					"Para cambiarla ir a Inventario/Configuración/Almacenes."
				))

			if not stock.pe_guide_transport_id:
				guia = self.env['solse.cpe.eguide.transport'].create_from_stock(stock)
				stock.pe_guide_transport_id = guia.id
			else:
				guia = stock.pe_guide_transport_id

			guia.generate_eguide()
			if stock.company_id.pe_is_sync:
				guia.action_send()
				time.sleep(3)
				try:
					guia.action_done()
				except Exception as error:
					_logging.info(
						"Error al consultar el ticket de la guía de "
						"transportista %s", stock.pe_guide_number
					)
					_logging.info(error)
			stock.pe_number = stock.pe_guide_number

	def regenerar_y_reenviar_xml_transp(self):
		"""Regenera y reenvía el XML de la GRT."""
		self.ensure_one()
		guia = self.pe_guide_transport_id
		if not guia:
			raise UserError(_("Esta transferencia no tiene guía de "
							  "transportista generada."))
		guia.action_cancel()
		guia.action_draft()
		guia.xml_document = ""
		guia.action_generate()
		guia.action_send()
		time.sleep(3)
		try:
			guia.action_done()
		except Exception as error:
			_logging.info("Error al reenviar la guía de transportista")
			_logging.info(error)




class PeStockDocumentoRelacionadoGrt(models.Model):
	_inherit = 'pe.stock.documento.relacionado'

	@api.constrains('codigo_documento', 'numero_documento')
	def _validar_formato_numero(self):
		"""En modalidad transportista rigen los patrones de la hoja
		Guía-Transportista2_0 (p.ej. 09 admite serie numérica, cosa que la
		GRR no); el resto sigue con el constraint del base."""
		remitentes = self.filtered(lambda d: d.picking_id.pe_guide_mode != 'carrier')
		super(PeStockDocumentoRelacionadoGrt, remitentes)._validar_formato_numero()
		for documento in self - remitentes:
			patron = PATRONES_DOCUMENTO_GRT.get(documento.codigo_documento)
			numero = (documento.numero_documento or '').strip()
			if patron and numero and not re.match(patron, numero):
				raise UserError(_(
					"El número '%s' del documento relacionado tipo %s no cumple "
					"el formato de la guía de transportista (ERR-3441)."
				) % (numero, documento.codigo_documento))


class PickingQrGrt(models.Model):
	_inherit = "stock.picking"

	# ------------------------------------------------------------------
	# QR de la representación impresa: tipo 31 y URL de la GRT
	# ------------------------------------------------------------------
	@api.depends('pe_guide_mode', 'pe_guide_transport_id', 'pe_guide_transport_id.url_doc',
				 'pe_grt_destinatario_id.doc_number', 'pe_grt_destinatario_id.doc_type')
	def _compute_get_qr_code(self):
		remitentes = self.filtered(lambda p: p.pe_guide_mode != 'carrier')
		super(PickingQrGrt, remitentes)._compute_get_qr_code()
		for guia in self - remitentes:
			fecha_guia = guia.date_done or guia.scheduled_date
			numero = guia.pe_guide_number or '/'
			if not all((guia.name != '/', guia.pe_is_eguide, qr_mod)) \
					or len(numero.split('-')) < 2 or not fecha_guia:
				guia.sunat_qr_code = ''
				continue
			destinatario = guia.pe_grt_destinatario_id
			res = [
				guia.company_id.partner_id.doc_number or '-',
				'31',
				numero.split('-')[0],
				numero.split('-')[1],
				'0',
				fields.Date.to_string(fecha_guia),
				destinatario.doc_type or '-',
				destinatario.doc_number or '-',
				guia.pe_guide_transport_id.url_doc or '-',
				'',
			]
			qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_Q)
			qr.add_data('|'.join(res))
			qr.make(fit=True)
			imagen = BytesIO()
			qr.make_image().save(imagen, 'png')
			guia.sunat_qr_code = encodestring(imagen.getvalue())
