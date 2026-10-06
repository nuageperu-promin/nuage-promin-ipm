# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import unicodedata
import logging
_logging = logging.getLogger(__name__)

class VentasRecibidas(models.Model):
	_name = 'solse.pe.ventas.recibidas'
	_description = 'Ventas Recibidas (Propuesta SUNAT)'

	ruc = fields.Char(string="RUC")
	name = fields.Char(string="Razón Social")
	periodo = fields.Char(string="Periodo")
	periodo_id = fields.Many2one("sire.report.14")
	car_sunat = fields.Char(string="CAR SUNAT")
	fecha_de_emision = fields.Date(string="Fecha de Emisión")
	fecha_vctopago = fields.Date(string="Fecha Vcto/Pago")
	# FIX: Integer → Char para preservar ceros a la izquierda y códigos alfanuméricos
	tipo_cpdoc = fields.Char(string="Tipo CP/Doc.")
	serie_del_cdp = fields.Char(string="Serie del CDP")
	# FIX: Integer → Char para preservar formato y permitir rangos
	nro_cp_o_doc_nro_inicial = fields.Char(string="Nro CP o Doc. Nro Inicial")
	nro_final = fields.Char(string="Nro Final (Rango)")
	tipo_doc_identidad = fields.Char(string="Tipo Doc Identidad")
	nro_doc_identidad = fields.Char(string="Nro Doc Identidad")
	apellidos_nombres_razon_social = fields.Char(string="Apellidos Nombres / Razón Social")
	valor_facturado_exportacion = fields.Float(string="Valor Facturado Exportación", digits=(14, 2))
	bi_gravada = fields.Float(string="BI Gravada", digits=(14, 2))
	dscto_bi = fields.Float(string="Dscto BI", digits=(14, 2))
	igv__ipm = fields.Float(string="IGV / IPM", digits=(14, 2))
	dscto_igv__ipm = fields.Float(string="Dscto IGV / IPM", digits=(14, 2))
	mto_exonerado = fields.Float(string="Mto Exonerado", digits=(14, 2))
	mto_inafecto = fields.Float(string="Mto Inafecto", digits=(14, 2))
	isc = fields.Float(string="ISC", digits=(14, 2))
	bi_grav_ivap = fields.Float(string="BI Grav IVAP", digits=(14, 2))
	ivap = fields.Float(string="IVAP", digits=(14, 2))
	icbper = fields.Float(string="ICBPER", digits=(14, 2))
	otros_tributos = fields.Float(string="Otros Tributos", digits=(14, 2))
	total_cp = fields.Float(string="Total CP", digits=(14, 2))
	moneda = fields.Char(string="Moneda")
	tipo_cambio = fields.Float(string="Tipo Cambio", digits=(4, 3))
	fecha_emision_doc_modificado = fields.Date(string="Fecha Emisión Doc Modificado")
	tipo_cp_modificado = fields.Char(string="Tipo CP Modificado")
	serie_cp_modificado = fields.Char(string="Serie CP Modificado")
	nro_cp_modificado = fields.Char(string="Nro CP Modificado")
	id_proyecto_operadores_atribucion = fields.Char(string="ID Proyecto / Operadores Atribución")
	tipo_de_nota = fields.Char(string="Tipo de Nota")
	# FIX: Integer → Char
	est_comp = fields.Char(string="Est. Comp")
	# FIX: Integer → Float
	valor_fob_embarcado = fields.Float(string="Valor FOB Embarcado", digits=(14, 2))
	valor_op_gratuitas = fields.Float(string="Valor Op Gratuitas", digits=(14, 2))
	# FIX: Integer → Char
	tipo_operacion = fields.Char(string="Tipo Operación")
	dam__cp = fields.Char(string="DAM / CP")
	clu = fields.Char(string="CLU")

	factura_enlazada = fields.Many2one("account.move", string="Factura")

	# ── Comparación SUNAT vs Odoo ────────────────────────────────────────────
	estado_comparacion = fields.Selection([
		('ok', 'OK'),
		('diferencia', 'Diferencia'),
		('sin_odoo', 'Sin enlace'),
	], string="Estado", default='sin_odoo', index=True)
	observacion = fields.Text(string="Observación")

	def ver_factura(self):
		return {
			'name': "Factura",
			'type': 'ir.actions.act_window',
			'view_mode': 'form',
			'views': [(False, 'form')],
			'res_model': "account.move",
			'res_id': self.factura_enlazada.id,
			'context': {'create': False, 'delete': False},
			'target': 'current',
		}

	def agregar_linea(self, periodo, datos_array):
		datos_json = {}
		campos = [
			"ruc", "name", "periodo", "car_sunat",
			"fecha_de_emision", "fecha_vctopago",
			"tipo_cpdoc", "serie_del_cdp",
			"nro_cp_o_doc_nro_inicial", "nro_final",
			"tipo_doc_identidad", "nro_doc_identidad",
			"apellidos_nombres_razon_social",
			"valor_facturado_exportacion", "bi_gravada", "dscto_bi",
			"igv__ipm", "dscto_igv__ipm",
			"mto_exonerado", "mto_inafecto", "isc",
			"bi_grav_ivap", "ivap", "icbper", "otros_tributos",
			"total_cp", "moneda", "tipo_cambio",
			"fecha_emision_doc_modificado",
			"tipo_cp_modificado", "serie_cp_modificado", "nro_cp_modificado",
			"id_proyecto_operadores_atribucion",
			"tipo_de_nota", "est_comp",
			"valor_fob_embarcado", "valor_op_gratuitas",
			"tipo_operacion", "dam__cp", "clu",
		]
		for contador, valor in enumerate(datos_array):
			if contador >= len(campos):
				break
			nombre_campo = campos[contador]
			valor = str(valor).strip() if valor is not None else ''

			if nombre_campo in ['fecha_de_emision', 'fecha_vctopago', 'fecha_emision_doc_modificado']:
				if not valor:
					continue
				partes = valor.split("/")
				if len(partes) != 3:
					continue
				valor = "%s-%s-%s" % (partes[2], partes[1], partes[0])

			# Conversión segura de campos float
			if nombre_campo in ['valor_facturado_exportacion', 'bi_gravada', 'dscto_bi',
				'igv__ipm', 'dscto_igv__ipm', 'mto_exonerado', 'mto_inafecto', 'isc',
				'bi_grav_ivap', 'ivap', 'icbper', 'otros_tributos', 'total_cp',
				'tipo_cambio', 'valor_fob_embarcado', 'valor_op_gratuitas']:
				try:
					valor = float(valor) if valor else 0.0
				except (ValueError, TypeError):
					valor = 0.0

			if valor != '':
				datos_json[nombre_campo] = valor

		datos_json['periodo_id'] = periodo.id
		self.create(datos_json)

	def enlazar_con_factura(self):
		"""
		Busca la factura en Odoo que corresponde a este registro de la propuesta SUNAT.
		Usa los campos stored serie_venta y correlativo_venta de account.move
		(computados desde l10n_latam_document_number que no es searchable).
		El correlativo de SUNAT puede venir sin padding (ej: '78') mientras Odoo
		lo guarda con padding (ej: '00000078'), se normaliza con lstrip('0').
		"""
		if not self.serie_del_cdp or not self.nro_cp_o_doc_nro_inicial:
			return
		# Normalizar correlativo: quitar ceros a la izquierda para comparar
		correlativo_norm = self.nro_cp_o_doc_nro_inicial.lstrip('0') or '0'
		factura = self.env['account.move'].search([
			('company_id', '=', self.periodo_id.company_id.id),
			('move_type', 'in', ['out_invoice', 'out_refund']),
			('serie_venta', '=', self.serie_del_cdp),
			('correlativo_venta', '=', correlativo_norm),
		], limit=1)
		if not factura:
			# Segundo intento: con el correlativo tal cual (por si Odoo no tiene padding)
			factura = self.env['account.move'].search([
				('company_id', '=', self.periodo_id.company_id.id),
				('move_type', 'in', ['out_invoice', 'out_refund']),
				('serie_venta', '=', self.serie_del_cdp),
				('correlativo_venta', '=', self.nro_cp_o_doc_nro_inicial),
			], limit=1)
		if factura:
			self.factura_enlazada = factura

	def obtener_entidad(self, tipo_documento, nro_ruc):
		datos_entidad = self.env['res.partner'].consulta_datos_completo(tipo_documento, nro_ruc)
		if datos_entidad['error']:
			raise UserError(datos_entidad['message'])
		elif 'registro' in datos_entidad and datos_entidad['registro']:
			return datos_entidad['registro']
		elif 'data' in datos_entidad and datos_entidad['data']:
			return self.crear_entidad(datos_entidad['data'], nro_ruc)
		raise UserError("No se pudo establecer el proveedor")

	def crear_factura(self):
		if self.factura_enlazada:
			return
		contacto = self.obtener_entidad(self.tipo_doc_identidad, self.nro_doc_identidad)
		# La suite mantiene DOS res.currency por divisa, una por cada tipo de
		# cambio que publica SUNAT: solse_pe_rate_api añade `rate_type`
		# (compra/venta) con constraint unique(name, rate_type). Sin filtrar,
		# este search elegía entre las dos por orden de id y la factura nacía
		# con un tipo de cambio arbitrario. Las ventas se valorizan al de
		# compra, que es el que usa el resto de la suite.
		Moneda = self.env['res.currency']
		dominio = [("name", "=", self.moneda)]
		if 'rate_type' in Moneda._fields:
			dominio.append(("rate_type", "=", "compra"))
		moneda_id = Moneda.search(dominio, limit=1) \
			or Moneda.search([("name", "=", self.moneda)], limit=1)
		datos_factura = {
			'move_type': 'out_invoice',
			'invoice_date': self.fecha_de_emision,
			'currency_id': moneda_id.id,
			'partner_id': contacto.id,
			'l10n_latam_document_number': "%s-%s" % (self.serie_del_cdp, self.nro_cp_o_doc_nro_inicial),
			'company_id': self.periodo_id.company_id.id,
		}
		datos_factura['invoice_line_ids'] = self.obtener_lineas_a_facturar()
		factura = self.env['account.move'].create(datos_factura)
		if factura:
			self.factura_enlazada = factura

	def obtener_lineas_a_facturar(self):
		if self.bi_gravada and self.igv__ipm and not self.bi_grav_ivap:
			impuesto = self.env['account.tax'].search([
				('company_id', '=', self.periodo_id.company_id.id),
				('type_tax_use', '=', 'sale'),
				('l10n_pe_edi_tax_code', '=', '1000'),
				('price_include', '=', True),
			], limit=1)
		else:
			impuesto = self.env['account.tax'].search([
				('company_id', '=', self.periodo_id.company_id.id),
				('type_tax_use', '=', 'sale'),
				('l10n_pe_edi_tax_code', '=', '9998'),
			], limit=1)
		tax_ids = [(6, 0, [impuesto.id])] if impuesto else False
		return [(0, 0, {
			'name': 'Línea general de pedido',
			'display_type': 'product',
			'tax_ids': tax_ids,
			'quantity': 1,
			'price_unit': self.total_cp,
		})]

	def crear_entidad(self, datos_json, nro_ruc):
		datos = datos_json.get("data", datos_json)
		json_entidad = {
			"commercial_name": datos.get("razonSocial", ""),
			"legal_name": datos.get("razonSocial", ""),
			"name": datos.get("razonSocial", ""),
			"street": datos.get("direccion", ""),
			"company_type": "company",
			"is_validate": True,
			"doc_number": nro_ruc,
			"vat": nro_ruc,
		}
		for campo in ['estado', 'condicion', 'buen_contribuyente', 'a_partir_del', 'resolucion']:
			if datos.get(campo):
				json_entidad[campo] = datos.get(campo)

		ditrict_obj = self.env['l10n_pe.res.city.district']
		district = False
		if datos.get('ubigeo'):
			district = ditrict_obj.search([('code', '=', datos.get('ubigeo'))], limit=1)
		elif datos.get('distrito') and datos.get('provincia'):
			distrito = unicodedata.normalize('NFKD', datos.get('distrito')).encode('ASCII', 'ignore').strip().upper().decode()
			district = ditrict_obj.search([('name_simple', '=ilike', distrito), ('city_id', '!=', False)])
			if len(district) > 1:
				district = ditrict_obj.search([
					('name_simple', '=ilike', distrito),
					('city_id.name_simple', '=ilike', datos.get('provincia')),
				])
		if district and len(district) == 1:
			json_entidad.update({
				"l10n_pe_district": district.id,
				"city_id": district.city_id.id,
				"state_id": district.city_id.state_id.id,
				"zip": district.code,
				"country_id": district.city_id.state_id.country_id.id,
			})
		return self.env["res.partner"].create(json_entidad)
