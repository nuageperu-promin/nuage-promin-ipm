# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import unicodedata
from datetime import datetime, timedelta
import requests
import logging
import json
_logging = logging.getLogger(__name__)

class VentasPreliminar(models.Model) :
	_name = 'solse.pe.ventas.preliminar'
	_description = 'Ventas Recibidas'

	periodo_id = fields.Many2one("sire.report.14")
	fecha_de_emision = fields.Date(string="﻿Fecha de emisión")
	fecha_vctopago = fields.Date(string="Fecha Vcto/Pago")
	tipo_cpdoc = fields.Char(string="Tipo CP/Doc.")
	serie_del_cdp = fields.Char(string="Serie del CDP")
	nro_cp_o_doc_nro_inicial = fields.Char(string="Nro CP o Doc. Nro Inicial (Rango)")
	nro_final = fields.Char(string="Nro Final (Rango)")
	tipo_doc_identidad = fields.Char(string="Tipo Doc Identidad")
	nro_doc_identidad = fields.Char(string="Nro Doc Identidad")
	name = fields.Char(string="Apellidos Nombres/ Razón Social")
	valor_facturado_exportacion = fields.Float(string="Valor Facturado Exportación")
	bi_gravada = fields.Float(string="BI Gravada")
	dscto_bi = fields.Float(string="Dscto BI")
	igv__ipm = fields.Float(string="IGV / IPM")
	dscto_igv__ipm = fields.Float(string="Dscto IGV / IPM")
	mto_exonerado = fields.Float(string="Mto Exonerado")
	mto_inafecto = fields.Float(string="Mto Inafecto")
	isc = fields.Float(string="ISC")
	bi_grav_ivap = fields.Float(string="BI Grav IVAP")
	ivap = fields.Float(string="IVAP")
	icbper = fields.Float(string="ICBPER")
	otros_tributos = fields.Float(string="Otros Tributos")
	total_cp = fields.Float(string="Total CP")
	moneda = fields.Char(string="Moneda")
	tipo_cambio = fields.Float(string="Tipo Cambio")
	fecha_emision_doc_modificado = fields.Date(string="Fecha Emisión Doc Modificado")
	tipo_cp_modificado = fields.Char(string="Tipo CP Modificado")
	serie_cp_modificado = fields.Char(string="Serie CP Modificado")
	nro_cp_modificado = fields.Char(string="Nro CP Modificado")
	id_proyecto_operadores_atribucion = fields.Char(string="ID Proyecto Operadores Atribución")
	tipo_de_nota = fields.Char(string="Tipo de Nota")
	est_comp = fields.Char(string="Est. Comp")
	valor_fob_embarcado = fields.Float(string="Valor FOB Embarcado")
	valor_op_gratuitas = fields.Float(string="Valor OP Gratuitas")
	tipo_operacion = fields.Float(string="Tipo Operación")
	dam__cp = fields.Char(string="DAM / CP")
	clu = fields.Char(string="CLU")
	car_sunat = fields.Char(string="CAR SUNAT")

	factura_enlazada = fields.Many2one("account.move", string="Factura")

	def agregar_linea(self, periodo, datos_array):
		datos_json = {}
		campos = ["fecha_de_emision", "fecha_vctopago", "tipo_cpdoc", "serie_del_cdp", "nro_cp_o_doc_nro_inicial", "nro_final", "tipo_doc_identidad", "nro_doc_identidad", "name", "valor_facturado_exportacion", "bi_gravada", "dscto_bi", "igv__ipm", "dscto_igv__ipm", "mto_exonerado", "mto_inafecto", "isc", "bi_grav_ivap", "ivap", "icbper", "otros_tributos", "total_cp", "moneda", "tipo_cambio", "fecha_emision_doc_modificado", "tipo_cp_modificado", "serie_cp_modificado", "nro_cp_modificado", "id_proyecto_operadores_atribucion", "tipo_de_nota", "est_comp", "valor_fob_embarcado", "valor_op_gratuitas", "tipo_operacion", "dam__cp", "clu", "car_sunat"]
		contador = 0
		for valor in datos_array:
			nombre_campo = campos[contador]
			contador += 1
			if nombre_campo in ['fecha_de_emision', 'fecha_vctopago', 'fecha_emision_doc_modificado']:
				if not valor:
					continue
				fe_array = valor.split("/")
				if len(fe_array) != 3:
					continue
				valor = "%s-%s-%s" % (fe_array[2], fe_array[1], fe_array[0])
			datos_json[nombre_campo] = valor
			
			if contador > 41:
				break

		datos_json['periodo_id'] = periodo.id

		self.create(datos_json)


