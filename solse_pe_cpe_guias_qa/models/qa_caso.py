# -*- coding: utf-8 -*-
"""Laboratorio QA de guías electrónicas (09 y 31).

Flujo por caso: Sembrar → Verificar XML → (opcional) Enviar a beta → Limpiar.
La verificación genera el XML por el mismo camino que el usuario
(validate_eguide*/create_from_stock/_prepare_eguide) sin firmar ni enviar,
y lo contrasta con las verificaciones de `casos_definidos.py`.
"""

import logging
import time
import traceback
from datetime import date

from lxml import etree

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .casos_definidos import (
	CASOS, NS, DNI_CONDUCTOR_1, DNI_CONDUCTOR_2, DNI_TERCERO, RUC_CONDUCTOR_2,
)

_logger = logging.getLogger(__name__)

PREFIJO_QA = 'QA-GRE'


class CasoQaGuias(models.Model):
	_name = 'solse.cpe.guias.qa.caso'
	_description = 'Caso QA de guía electrónica'
	_order = 'codigo'

	codigo = fields.Char(required=True, index=True)
	name = fields.Char('Nombre', required=True)
	tipo_guia = fields.Selection([('09', 'Remitente (09)'), ('31', 'Transportista (31)')],
								 string='Tipo de guía', required=True)
	descripcion = fields.Text()
	resultado_esperado = fields.Selection([
		('aceptada', 'Validación local pasa y XML correcto'),
		('rechazo_local', 'La validación local debe frenar'),
	], required=True, default='aceptada')
	error_esperado = fields.Char(help='Fragmento que debe contener el UserError esperado.')
	picking_id = fields.Many2one('stock.picking', string='Transferencia', readonly=True, copy=False)
	guia_numero = fields.Char('Número de guía', compute='_compute_guia', readonly=True)
	guia_estado = fields.Char('Estado en SUNAT', compute='_compute_guia', readonly=True)
	estado = fields.Selection([
		('pendiente', 'Pendiente'),
		('sembrado', 'Sembrado'),
		('ok', 'Verificado OK'),
		('error', 'Con errores'),
		('enviado', 'Enviado a beta'),
	], default='pendiente', readonly=True, copy=False)
	resultado = fields.Text(readonly=True, copy=False)
	xml_generado = fields.Text(readonly=True, copy=False)
	company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)

	_codigo_unico = models.Constraint('unique(codigo, company_id)', 'El código del caso ya existe.')

	@api.depends('picking_id', 'picking_id.pe_guide_number', 'picking_id.pe_guide_id.state',
				 'picking_id.pe_guide_transport_id.state')
	def _compute_guia(self):
		for caso in self:
			picking = caso.picking_id
			caso.guia_numero = picking.pe_guide_number if picking else ''
			guia = caso._guia()
			caso.guia_estado = guia and '%s / %s' % (guia.state, guia.response or '') or ''

	# ------------------------------------------------------------------
	# Definiciones
	# ------------------------------------------------------------------
	@api.model
	def cargar_casos_definidos(self, sobrescribir=False):
		"""Crea los casos que falten. Con sobrescribir=True reescribe la
		definición (nombre, descripción, esperado) sin tocar la siembra."""
		for compania in self.env['res.company'].sudo().search([]):
			for definicion in CASOS:
				existente = self.sudo().search([
					('codigo', '=', definicion['codigo']), ('company_id', '=', compania.id)], limit=1)
				valores = {
					'codigo': definicion['codigo'],
					'name': definicion['nombre'],
					'tipo_guia': definicion['tipo_guia'],
					'descripcion': definicion.get('descripcion'),
					'resultado_esperado': definicion['resultado_esperado'],
					'error_esperado': definicion.get('error_esperado'),
					'company_id': compania.id,
				}
				if existente:
					if sobrescribir:
						existente.write(valores)
					continue
				self.sudo().create(valores)
		return True

	def action_actualizar_casos_precargados(self):
		self.cargar_casos_definidos(sobrescribir=True)
		return True

	def _definicion(self):
		self.ensure_one()
		for definicion in CASOS:
			if definicion['codigo'] == self.codigo:
				return definicion
		raise UserError(_('El caso %s no existe en casos_definidos.py.') % self.codigo)

	def _guia(self):
		self.ensure_one()
		picking = self.picking_id
		if not picking:
			return self.env['solse.cpe.eguide']
		if self.tipo_guia == '31':
			return picking.pe_guide_transport_id
		return picking.pe_guide_id

	# ------------------------------------------------------------------
	# Sembrado
	# ------------------------------------------------------------------
	def _tipo_identificacion(self, codigo_sunat):
		tipo = self.env['l10n_latam.identification.type'].search(
			[('l10n_pe_vat_code', '=', codigo_sunat)], limit=1)
		if not tipo:
			raise UserError(_('No existe el tipo de identificación SUNAT %s (l10n_pe).') % codigo_sunat)
		return tipo

	def _distrito(self, ubigeo='150101'):
		campo = self.env['res.partner']._fields['l10n_pe_district']
		Distrito = self.env[campo.comodel_name]
		return Distrito.search([('code', '=', ubigeo)], limit=1) or Distrito.search([], limit=1)

	def _direccion_pe(self):
		"""País, departamento, provincia y distrito coherentes con el ubigeo
		QA. solse_pe_edi exige los cuatro en todo contacto peruano
		principal (res_partner_validacion.py)."""
		distrito = self._distrito()
		valores = {'l10n_pe_district': distrito.id}
		peru = self.env.ref('base.pe', raise_if_not_found=False)
		if peru:
			valores['country_id'] = peru.id
		ciudad = getattr(distrito, 'city_id', False)
		if ciudad:
			valores['city_id'] = ciudad.id
			if ciudad.state_id:
				valores['state_id'] = ciudad.state_id.id
		return valores

	def _partner(self, nombre, documento, tipo='6', extra=None):
		"""Busca o crea un contacto QA por número de documento."""
		Partner = self.env['res.partner'].with_company(self.company_id)
		partner = Partner.search([('vat', '=', documento), ('parent_id', '=', False)], limit=1)
		valores = {
			'name': nombre,
			'company_type': 'company' if tipo == '6' else 'person',
			'vat': documento,
			'l10n_latam_identification_type_id': self._tipo_identificacion(tipo).id,
			'commercial_name': nombre,
			'street': 'AV. LABORATORIO QA 123',
			'ref': PREFIJO_QA,
		}
		valores.update(self._direccion_pe())
		valores.update(extra or {})
		if partner:
			partner.write({k: v for k, v in valores.items() if k not in ('vat', 'l10n_latam_identification_type_id')})
			return partner
		return Partner.create(valores)

	def _conductor(self, clave):
		datos = {
			'conductor_1': ('JOSE QA LOPEZ RAMOS', DNI_CONDUCTOR_1, '1', 'Q45678912'),
			'conductor_2': ('ANA QA TORRES DIAZ', DNI_CONDUCTOR_2, '1', 'Q87654321'),
			# RUC persona natural: el generador debe convertirlo a DNI (ERR-2571).
			'conductor_2_ruc': ('ANA QA TORRES DIAZ', RUC_CONDUCTOR_2, '6', 'Q87654321'),
		}[clave]
		return self._partner(datos[0], datos[1], datos[2], {'pe_driver_license': datos[3]})

	def _vehiculo(self, placa):
		Vehiculo = self.env['fleet.vehicle'].with_company(self.company_id)
		vehiculo = Vehiculo.search([('license_plate', '=', placa)], limit=1)
		if vehiculo:
			return vehiculo
		marca = self.env['fleet.vehicle.model.brand'].search([('name', '=', 'QA')], limit=1) \
			or self.env['fleet.vehicle.model.brand'].create({'name': 'QA'})
		modelo = self.env['fleet.vehicle.model'].search([('brand_id', '=', marca.id)], limit=1) \
			or self.env['fleet.vehicle.model'].create({'name': 'CAMION QA', 'brand_id': marca.id})
		return Vehiculo.create({'model_id': modelo.id, 'license_plate': placa})

	def _producto(self):
		Producto = self.env['product.product']
		producto = Producto.search([('default_code', '=', PREFIJO_QA)], limit=1)
		if producto:
			return producto
		return Producto.create({
			'name': 'Producto laboratorio guías', 'default_code': PREFIJO_QA,
			'type': 'consu', 'is_storable': False, 'weight': 10.0, 'list_price': 100.0,
		})

	def _asegurar_direccion(self, partner, etiqueta):
		"""El emisor y el almacén necesitan calle y ubigeo; se completan y
		se deja constancia en el resultado para que no sorprenda."""
		faltantes = {}
		if not partner.street:
			faltantes['street'] = 'AV. LABORATORIO QA 1'
		if not partner.l10n_pe_district:
			faltantes.update(self._direccion_pe())
		if faltantes:
			partner.write(faltantes)
			return '- Se completó dirección/ubigeo de %s (%s).\n' % (etiqueta, partner.name)
		return ''

	def _almacen(self, ubigeo=None):
		Almacen = self.env['stock.warehouse'].with_company(self.company_id)
		if not ubigeo:
			almacen = Almacen.search([('company_id', '=', self.company_id.id)], limit=1)
			if not almacen:
				raise UserError(_('La compañía no tiene almacén.'))
			return almacen
		codigo = 'QA%s' % ubigeo[-3:]
		almacen = Almacen.search([('code', '=', codigo), ('company_id', '=', self.company_id.id)], limit=1)
		if almacen:
			return almacen
		distrito = self._distrito(ubigeo)
		direccion = self._direccion_pe()
		direccion['l10n_pe_district'] = distrito.id
		ciudad = getattr(distrito, 'city_id', False)
		if ciudad:
			direccion['city_id'] = ciudad.id
			if ciudad.state_id:
				direccion['state_id'] = ciudad.state_id.id
		partner = self.env['res.partner'].with_context(solse_skip_validacion_pe=True).create(dict(
			direccion, name='ALMACEN %s %s' % (PREFIJO_QA, ubigeo), type='other',
			street='TERMINAL PORTUARIO QA', company_id=self.company_id.id))
		return Almacen.create({
			'name': 'Almacén %s %s' % (PREFIJO_QA, ubigeo), 'code': codigo,
			'company_id': self.company_id.id, 'partner_id': partner.id,
		})

	def _crear_picking(self, destinatario, almacen_ubigeo=None):
		almacen = self._almacen(almacen_ubigeo)
		tipo = almacen.out_type_id
		producto = self._producto()
		picking = self.env['stock.picking'].with_company(self.company_id).create({
			'partner_id': destinatario.id,
			'picking_type_id': tipo.id,
			'location_id': tipo.default_location_src_id.id,
			'location_dest_id': destinatario.property_stock_customer.id,
			'origin': '%s %s' % (PREFIJO_QA, self.codigo),
			# stock.move en v19 no tiene `name` y la unidad se calcula del
			# producto: solo producto, cantidad y ubicaciones.
			'move_ids': [(0, 0, {
				'product_id': producto.id,
				'product_uom_qty': 5,
				'location_id': tipo.default_location_src_id.id,
				'location_dest_id': destinatario.property_stock_customer.id,
			})],
		})
		picking.action_confirm()
		picking.action_assign()
		for movimiento in picking.move_ids:
			movimiento.quantity = movimiento.product_uom_qty
			movimiento.picked = True
		# Mismo camino que el usuario: button_validate completa peso y bultos.
		picking.with_context(skip_backorder=True, skip_sms=True, skip_immediate=True).button_validate()
		return picking, almacen

	def action_sembrar(self):
		for caso in self:
			if caso.picking_id:
				raise UserError(_('El caso %s ya está sembrado. Límpielo primero.') % caso.codigo)
			try:
				with self.env.cr.savepoint():
					caso._sembrar()
			except Exception as error:
				mensaje = str(error)
				if caso.resultado_esperado == 'rechazo_local' and (caso.error_esperado or '') in mensaje:
					# El rechazo llegó al registrar los datos (constraint), no
					# en validate_eguide*: cuenta igual como el resultado esperado.
					caso.write({'estado': 'ok', 'resultado': 'OK: rechazo local esperado (al registrar el dato).\n%s' % mensaje})
					continue
				caso.write({'estado': 'error', 'resultado': 'ERROR AL SEMBRAR:\n%s\n%s' % (error, traceback.format_exc())})
		return True

	def _sembrar(self):
		self.ensure_one()
		definicion = self._definicion()
		datos = dict(definicion['datos'])
		notas = ''
		emisor = self.company_id.partner_id
		if not emisor.doc_number or emisor.doc_type != '6':
			raise UserError(_('La compañía %s no tiene RUC configurado.') % self.company_id.name)
		notas += self._asegurar_direccion(emisor, 'la compañía')

		if self.tipo_guia == '31':
			remitente = self._partner('REMITENTE QA SAC', datos.pop('remitente'))
			destinatario = self._partner('DESTINATARIO QA SAC', datos.pop('destinatario'))
			picking, almacen = self._crear_picking(destinatario)
			notas += self._asegurar_direccion(almacen.partner_id, 'el almacén')
			valores = {
				'pe_is_eguide': True, 'pe_guide_mode': 'carrier',
				'pe_grt_remitente_id': remitente.id, 'pe_grt_destinatario_id': destinatario.id,
				'pe_grt_fecha_inicio_traslado': date.today(),
			}
			if datos.pop('subcontratador', None):
				valores['pe_grt_subcontratador_id'] = self._partner(
					'SUBCONTRATADOR QA SAC', definicion['datos']['subcontratador']).id
			if datos.pop('pagador_tercero', None):
				valores['pe_grt_pagador_tercero_id'] = self._partner(
					'TERCERO QA PAGADOR', definicion['datos']['pagador_tercero'], '1').id
		else:
			destinatario = self._partner('CLIENTE QA SAC', '20601234565')
			picking, almacen = self._crear_picking(destinatario, datos.pop('almacen_ubigeo', None))
			notas += self._asegurar_direccion(almacen.partner_id, 'el almacén')
			valores = {'pe_is_eguide': True, 'pe_guide_mode': 'sender'}
			codigo_puerto = datos.pop('puerto', None)
			if codigo_puerto:
				puerto = self.env['solse.pe.puerto'].search([('codigo', '=', codigo_puerto)], limit=1)
				if not puerto:
					raise UserError(_('No existe el puerto %s en el catálogo 63/64.') % codigo_puerto)
				valores['pe_puerto_id'] = puerto.id
			if datos.pop('transportista', None):
				valores['pe_carrier_id'] = self._partner(
					'TRANSPORTES QA PUBLICO SAC', definicion['datos']['transportista'],
					'6', {'pe_mtc_number': 'MTC0099'}).id
			if datos.get('pe_delivery_date') == 'hoy':
				datos['pe_delivery_date'] = date.today()

		vehiculos = datos.pop('vehiculos', [])
		contenedores = datos.pop('contenedores', [])
		documentos = datos.pop('documentos', [])
		valores.update(datos)
		valores['pe_fleet_ids'] = [(5, 0, 0)] + [(0, 0, {
			'fleet_id': self._vehiculo(v[0]).id, 'name': v[0],
			'driver_id': self._conductor(v[1]).id, 'is_main': v[2],
			'pe_tuce': v[3] if len(v) > 3 else False,
		}) for v in vehiculos]
		valores['pe_contenedor_ids'] = [(5, 0, 0)] + [(0, 0, {
			'numero_contenedor': c[0], 'numero_precinto': c[1]}) for c in contenedores]
		valores['pe_documento_relacionado_ids'] = [(5, 0, 0)] + [(0, 0, {
			'codigo_documento': d[0], 'numero_documento': d[1],
			'emisor_id': self._partner('EMISOR DOC QA', d[2]).id}) for d in documentos]
		if contenedores:
			valores['pe_unit_quantity'] = 0
		picking.write(valores)
		self.write({
			'picking_id': picking.id, 'estado': 'sembrado', 'xml_generado': False,
			'resultado': 'Sembrado: %s\n%s' % (picking.name, notas),
		})

	# ------------------------------------------------------------------
	# Verificación offline del XML
	# ------------------------------------------------------------------
	def action_verificar(self):
		for caso in self:
			if not caso.picking_id:
				raise UserError(_('Siembre primero el caso %s.') % caso.codigo)
			caso._verificar()
		return True

	def _numerar(self, picking):
		if picking.pe_guide_number != '/':
			return
		if self.tipo_guia == '31':
			picking.pe_guide_number = picking._obtener_numero_guia_transporte()
		else:
			secuencia = picking.picking_type_id.warehouse_id.eguide_sequence_id
			picking.pe_guide_number = secuencia.next_by_id() if secuencia else \
				self.env['ir.sequence'].with_company(picking.company_id).next_by_code('pe.eguide.sync')

	def _generar_xml(self, picking):
		"""Genera el XML sin firmar ni enviar, por el camino real."""
		# action_generate_eguide* fija la fecha de emisión antes de generar;
		# aquí no pasamos por ahí, así que se fija igual.
		if not picking.pe_date_issue:
			picking.pe_date_issue = fields.Date.context_today(picking)
		if self.tipo_guia == '31':
			picking.validate_eguide_transport()
			self._numerar(picking)
			guia = picking.pe_guide_transport_id or \
				self.env['solse.cpe.eguide.transport'].create_from_stock(picking)
			picking.pe_guide_transport_id = guia.id
		else:
			picking.validate_eguide()
			self._numerar(picking)
			guia = picking.pe_guide_id or self.env['solse.cpe.eguide'].create_from_stock(picking)
			picking.pe_guide_id = guia.id
		if guia.state == 'draft':
			guia.xml_document = False
			guia._prepare_eguide()
		return guia.xml_document

	def _verificar(self):
		self.ensure_one()
		definicion = self._definicion()
		picking = self.picking_id
		lineas = []
		try:
			with self.env.cr.savepoint():
				xml = self._generar_xml(picking)
		except UserError as error:
			mensaje = str(error)
			if self.resultado_esperado == 'rechazo_local':
				if (self.error_esperado or '') in mensaje:
					self.write({'estado': 'ok', 'resultado': 'OK: rechazo local esperado.\n%s' % mensaje})
				else:
					self.write({'estado': 'error', 'resultado': 'RECHAZO LOCAL CON OTRO MENSAJE.\nEsperado: %s\nObtenido: %s' % (self.error_esperado, mensaje)})
			else:
				self.write({'estado': 'error', 'resultado': 'LA VALIDACIÓN LOCAL FRENÓ (no esperado):\n%s' % mensaje})
			return
		except Exception as error:
			self.write({'estado': 'error', 'resultado': 'EXCEPCIÓN:\n%s\n%s' % (error, traceback.format_exc())})
			return

		if self.resultado_esperado == 'rechazo_local':
			self.write({'estado': 'error', 'xml_generado': xml,
						'resultado': 'SE ESPERABA RECHAZO LOCAL (%s) y el XML se generó.' % self.error_esperado})
			return

		raiz = etree.fromstring(xml.encode('utf-8') if isinstance(xml, str) else xml)
		errores = 0
		for descripcion, xpath, esperado in definicion['verificaciones']:
			if esperado == 'RUC_COMPANIA':
				esperado = self.company_id.partner_id.doc_number
			ok, detalle = self._evaluar(raiz, xpath, esperado)
			errores += 0 if ok else 1
			lineas.append('%s %s: %s' % ('✔' if ok else '✘', descripcion, detalle))
		self.write({
			'estado': 'ok' if not errores else 'error',
			'xml_generado': xml,
			'resultado': '%d verificaciones, %d con error.\n%s' % (
				len(definicion['verificaciones']), errores, '\n'.join(lineas)),
		})

	@staticmethod
	def _evaluar(raiz, xpath, esperado):
		if xpath.startswith('ORDEN:'):
			ruta = xpath[len('ORDEN:'):]
			nodos = [raiz] if ruta == '/*' else raiz.xpath('//' + ruta, namespaces=NS)
			if not nodos:
				return False, 'nodo %s no encontrado' % ruta
			obtenido = [etree.QName(hijo).localname for hijo in nodos[0]]
			return obtenido == esperado, '%s' % obtenido
		resultado = raiz.xpath(xpath, namespaces=NS)
		valores = [r if isinstance(r, str) else etree.tostring(r, encoding='unicode')[:60] for r in resultado]
		if esperado is None:
			return bool(resultado), 'existe' if resultado else 'NO existe'
		if isinstance(esperado, list):
			return valores == esperado, '%s (esperado %s)' % (valores, esperado)
		return bool(valores) and valores[0] == esperado, '%s (esperado %s)' % (valores[:1], esperado)

	# ------------------------------------------------------------------
	# Envío al beta configurado en la compañía
	# ------------------------------------------------------------------
	def action_enviar_beta(self):
		for caso in self:
			if not caso.picking_id or caso.resultado_esperado != 'aceptada':
				raise UserError(_('El caso %s no está sembrado o no es enviable.') % caso.codigo)
			if self.company_id.pe_is_sync is False:
				raise UserError(_('Active el envío síncrono (pe_is_sync) en la compañía para enviar desde el laboratorio.'))
			picking = caso.picking_id
			try:
				if caso.tipo_guia == '31':
					picking.action_generate_eguide_transport()
				else:
					picking.action_generate_eguide()
				guia = caso._guia()
				caso.write({
					'estado': 'enviado',
					'xml_generado': guia.xml_document,
					'resultado': (caso.resultado or '') + '\n\nENVÍO: estado %s, respuesta: %s, error: %s, ticket: %s' % (
						guia.state, guia.response, guia.error_code, guia.ticket),
				})
			except Exception as error:
				caso.write({'estado': 'error', 'resultado': (caso.resultado or '') + '\n\nERROR AL ENVIAR:\n%s\n%s' % (error, traceback.format_exc())})
		return True

	def action_consultar_ticket(self):
		for caso in self:
			guia = caso._guia()
			if not guia:
				continue
			try:
				guia.action_done()
			except Exception as error:
				_logger.info('QA guías: consulta de ticket %s', error)
			caso.resultado = (caso.resultado or '') + '\nCONSULTA: estado %s, respuesta: %s, error: %s' % (
				guia.state, guia.response, guia.error_code)
		return True

	# ------------------------------------------------------------------
	# Limpieza
	# ------------------------------------------------------------------
	def action_limpiar(self):
		for caso in self:
			picking = caso.picking_id.sudo()
			if picking:
				for guia in (picking.pe_guide_id, picking.pe_guide_transport_id,
							 picking.pe_voided_id, picking.pe_voided_transport_id):
					if guia and guia.state in ('draft', 'generate', 'cancel'):
						guia.unlink()
				picking.write({'pe_guide_id': False, 'pe_guide_transport_id': False})
				# Los movimientos hechos no se pueden borrar: es un laboratorio,
				# se fuerzan a borrador para poder eliminar la transferencia.
				picking.move_line_ids.write({'state': 'draft'})
				picking.move_ids.write({'state': 'draft'})
				picking.write({'state': 'draft'})
				picking.unlink()
			caso.write({'picking_id': False, 'estado': 'pendiente', 'resultado': False, 'xml_generado': False})
		return True
