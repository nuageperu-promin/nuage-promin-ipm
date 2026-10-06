# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .sire_report import get_last_day, fill_name_data, number_to_ascii_chr
from io import TextIOWrapper
import base64
import zipfile
import csv
from base64 import b64decode, b64encode, encodebytes
import datetime
from io import StringIO, BytesIO
import requests
import json
import pandas
import logging
_logging = logging.getLogger(__name__)

# Códigos de proceso para la API SUNAT SIRE Ventas
COD_PROCESO_REEMPLAZO = '3'
COD_PROCESO_IMPORTAR_CP = '1'
COD_PROCESO_IMPORTAR_CP_PRELIMINAR = '4'
COD_PROCESO_AJUSTE_POSTERIOR = '87'
COD_PROCESO_AJUSTE_ANTERIOR = '88'
COD_LIBRO_RVIE = '140000'
COD_ORIGEN_ENVIO_WEB = '2'
COD_TIPO_CORRELATIVO_MASIVO = '01'


class TicketsSire(models.Model):
	_name = 'solse.sire.ticket'
	_description = 'Tickets SIRE Ventas'

	name = fields.Char("Ticket")
	reporte_venta_id = fields.Many2one("sire.report.14", string="Reporte")
	tipo_modelo = fields.Selection([("ventas", "Ventas"), ("compras", "Compras")], default="ventas")
	tipo_cosulta = fields.Selection([
		("solicitar_propuesta", "Solicitar Propuesta"),
		("confirmar_propuesta", "Confirmar Propuesta"),
		("reemplazar_propuesta", "Reemplazar Propuesta"),
		("solicitar_preliminar", "Solicitar Preliminar"),
		("generar_envio", "Generar Envío"),
	], default="solicitar_propuesta")
	datos_crudo = fields.Text("Respuesta en crudo")

	def descargar_propuesta(self):
		token = self.reporte_venta_id.conectar()
		datos_enviar = json.loads(self.datos_crudo)
		self.reporte_venta_id.descargar_archivo(token, 'propuesta', datos_enviar)


class SireReport14(models.Model):
	_name = 'sire.report.14'
	_description = 'SIRE 14 - Registro de Ventas e Ingresos'
	_inherit = 'sire.report.templ'

	year = fields.Integer(required=True)
	month = fields.Selection(selection_add=[], required=True)

	invoice_ids = fields.Many2many(comodel_name='account.move', string='Ventas', readonly=True)

	sire_txt_01 = fields.Text(string='Contenido del TXT 14.4')
	sire_txt_01_binary = fields.Binary(string='TXT 14.4')
	sire_txt_01_filename = fields.Char(string='Nombre del TXT 14.4')
	sire_xls_01_binary = fields.Binary(string='Excel 14.4')
	sire_xls_01_filename = fields.Char(string='Nombre del Excel 14.4')
	datas_zip = fields.Binary("Zip 14.4", readonly=True)

	documento_compra_ids = fields.Many2many(
		'l10n_latam.document.type',
		'sire_14_report_l10n_latam_id',
		'report_14_id', 'doc_14_id',
		string='Documentos a incluir',
		domain="[('sub_type', 'in', ['sale'])]",
	)

	# Ticket activo / propuesta
	ticket_sire = fields.Char("Ticket Sire")
	tipo_ticket = fields.Selection([
		("propuesta", "Propuesta"),
		("confirmar", "Confirmar"),
		("reemplazar", "Reemplazar"),
		("preliminar", "Preliminar"),
	], default="propuesta", string="Tipo ticket")
	estado_ticket_sire = fields.Selection([
		("borrador", "Borrador"),
		("recibido", "Recibido"),
		("enviado", "Enviado"),
		("confirmado", "Confirmado"),
	], default="borrador", string="Estado Ticket")

	csv_temporal = fields.Binary("Archivo csv recibido")
	estado_propuesta = fields.Selection([
		("borrador", "Borrador"),
		("solicitado", "Solicitado"),
		("recibido", "Recibido"),
		("confirmado", "Confirmado"),
		("reemplazado", "Reemplazado"),
	], default="borrador", string="Estado Propuesta")
	archivo_propuesta = fields.Binary("Propuesta")
	nombre_archivo_propuesta = fields.Char("Nom. Propuesta")
	nombre_contenido_propuesta = fields.Char("Nom. Contenido Propuesta")
	archivo_confirmacion = fields.Binary("Respuesta confirmación")
	nombre_archivo_confirmacion = fields.Char("Nom. confirmación")
	archivo_reemplazo = fields.Binary("Respuesta reemplazo")
	nombre_archivo_reemplazo = fields.Char("Nom. reemplazo")
	archivo_preliminar = fields.Binary("Respuesta preliminar")
	nombre_archivo_preliminar = fields.Char("Nom. preliminar")
	nombre_contenido_preliminar = fields.Char("Nom. Contenido Preliminar")

	ventas_registradas = fields.One2many("solse.pe.ventas.recibidas", "periodo_id")
	ventas_preliminar = fields.One2many("solse.pe.ventas.preliminar", "periodo_id")
	ticket_ids = fields.One2many("solse.sire.ticket", "reporte_venta_id", string="Tickets")

	ticket_solicitar_propuesta = fields.Integer("Cant. tickets solicitar propuesta", compute="_compute_datos_ticket")
	ticket_confirmar_propuesta = fields.Integer("Cant. tickets confirmar propuesta", compute="_compute_datos_ticket")
	ticket_reemplazar_propuesta = fields.Integer("Cant. tickets reemplazar propuesta", compute="_compute_datos_ticket")
	esta_vacio = fields.Boolean("La propuesta está vacía")

	# ── Facturas Odoo no reportadas en SUNAT ─────────────────────────────────
	facturas_sin_sunat = fields.Many2many(
		'account.move',
		'sire_14_facturas_sin_sunat_rel',
		'reporte_id', 'move_id',
		string="Facturas no en SUNAT",
		readonly=True,
	)
	cant_facturas_sin_sunat = fields.Integer(
		string="Sin SUNAT",
		compute="_compute_cant_sin_sunat",
	)

	@api.depends('facturas_sin_sunat')
	def _compute_cant_sin_sunat(self):
		for reg in self:
			reg.cant_facturas_sin_sunat = len(reg.facturas_sin_sunat)

	# ─── Ajuste posterior (servicio 5.6, codProceso=87) ─────────────────────────
	zip_ajuste_posterior = fields.Binary("ZIP Ajuste posterior")
	nombre_zip_ajuste_posterior = fields.Char("Nombre ZIP Ajuste")
	estado_ajuste_posterior = fields.Selection([
		("borrador", "Borrador"),
		("enviado", "Enviado"),
		("procesado", "Procesado"),
	], default="borrador", string="Estado ajuste")
	ticket_ajuste_posterior = fields.Char("Ticket ajuste")
	nro_ajuste_posterior = fields.Char("Nro. Ajuste posterior")
	notas_ajuste_posterior = fields.Text("Notas ajuste")

	# ─── Ajuste periodos anteriores (servicio 5.7, codProceso=88) ───────────────
	anio_periodo_anterior = fields.Integer("Año periodo a corregir")
	mes_periodo_anterior = fields.Selection([
		('1','Enero'), ('2','Febrero'), ('3','Marzo'), ('4','Abril'),
		('5','Mayo'), ('6','Junio'), ('7','Julio'), ('8','Agosto'),
		('9','Setiembre'), ('10','Octubre'), ('11','Noviembre'), ('12','Diciembre'),
	], string="Mes periodo a corregir")
	zip_ajuste_anterior = fields.Binary("ZIP Ajuste per. anteriores")
	nombre_zip_ajuste_anterior = fields.Char("Nombre ZIP Ajuste ant.")
	estado_ajuste_anterior = fields.Selection([
		("borrador", "Borrador"),
		("enviado", "Enviado"),
		("procesado", "Procesado"),
	], default="borrador", string="Estado ajuste ant.")
	ticket_ajuste_anterior = fields.Char("Ticket ajuste ant.")
	nro_ajuste_anterior = fields.Char("Nro. Ajuste ant.")
	notas_ajuste_anterior = fields.Text("Notas ajuste ant.")

	# ─────────────────────────────────────────────────────────────────────────────

	@api.depends('ticket_ids')
	def _compute_datos_ticket(self):
		for reg in self:
			reg.ticket_solicitar_propuesta = len(reg.ticket_ids.filtered(lambda r: r.tipo_cosulta == 'solicitar_propuesta'))
			reg.ticket_confirmar_propuesta = len(reg.ticket_ids.filtered(lambda r: r.tipo_cosulta == 'confirmar_propuesta'))
			reg.ticket_reemplazar_propuesta = len(reg.ticket_ids.filtered(lambda r: r.tipo_cosulta == 'reemplazar_propuesta'))

	# ─── Helpers de ticket ───────────────────────────────────────────────────────

	def obtener_nro_ticket(self, tipo):
		reg_ticket = self.env['solse.sire.ticket'].search([
			('reporte_venta_id', '=', self.id),
			('tipo_cosulta', '=', tipo),
		])
		if not reg_ticket:
			raise UserError("No se encontró un ticket para la operación '%s'" % tipo)
		if len(reg_ticket) > 1:
			raise UserError("Se encontró más de un ticket para la operación '%s', solo debe tener uno activo." % tipo)
		return reg_ticket

	def guardar_nro_ticket(self, tipo, nro_ticket):
		reg_ticket = self.env['solse.sire.ticket'].search([
			('reporte_venta_id', '=', self.id),
			('tipo_cosulta', '=', tipo),
		])
		vals = {'name': str(nro_ticket), 'tipo_cosulta': tipo}
		if not reg_ticket:
			vals['reporte_venta_id'] = self.id
			self.env['solse.sire.ticket'].create(vals)
		else:
			reg_ticket.write({'name': str(nro_ticket)})

	# ─── Notificaciones ──────────────────────────────────────────────────────────

	def show_notification_ok(self, mensaje, titulo="Operación exitosa", recargar=False):
		params = {
			'title': titulo,
			'message': mensaje or '¡Operación completada con éxito!',
			'sticky': False,
		}
		if recargar:
			params['next'] = {'type': 'ir.actions.client', 'tag': 'reload'}
		return {
			'type': 'ir.actions.client',
			'tag': 'display_notification',
			'params': params,
		}

	def show_notification_warning(self, mensaje, titulo="Advertencia", recargar=False):
		params = {
			'title': titulo,
			'message': mensaje or 'Ha ocurrido un problema.',
			'type': 'warning',
			'sticky': True,
		}
		if recargar:
			params['next'] = {'type': 'ir.actions.client', 'tag': 'reload'}
		return {
			'type': 'ir.actions.client',
			'tag': 'display_notification',
			'params': params,
		}

	# ─── Procesamiento de propuestas ─────────────────────────────────────────────

	def concatenate_elements(self, arr):
		"""Reensambla elementos que fueron divididos por el delimitador dentro de campos entrecomillados."""
		result = []
		current_item = ""
		for item in reversed(arr):
			if item.startswith(" "):
				current_item = item.strip() + " " + current_item
			else:
				if current_item:
					result.append(item.strip() + " " + current_item.strip())
					current_item = ""
					continue
				result.append(item)
		if current_item:
			result.append(current_item.strip())
		return list(reversed(result))

	def procesar_archivo_zip(self, modelo, lista, archivo, nombre):
		"""
		Procesa el archivo ZIP de propuesta/preliminar de SUNAT.
		FIX CRÍTICO: El archivo TXT de SUNAT usa '|' como separador de campos,
		no ',' con '|' como quotechar como estaba implementado antes.
		"""
		if not archivo or not nombre:
			raise UserError("No hay archivo o nombre de contenido definido para procesar.")

		zf = zipfile.ZipFile(BytesIO(base64.b64decode(archivo)))
		filas_procesadas = 0
		filas_error = 0

		try:
			with zf.open(nombre) as lectura:
				# El archivo de propuesta de SUNAT usa pipe '|' como separador de campos.
				# Bug original: quotechar='|' trataba todo entre pipes como entrecomillado
				# y descartaba filas. Fix: delimiter='|', quotechar='"' estandar.
				# NUNCA usar el mismo caracter como delimiter y quotechar.
				spamreader = csv.reader(
					TextIOWrapper(lectura, 'utf-8', errors='replace'),
					delimiter='|',
					quotechar='"',
				)

				# Borrar registros previos del periodo
				for reg in lista:
					reg.unlink()

				for contador, row in enumerate(spamreader):
					if contador == 0:
						# Primera fila = encabezado, saltar
						continue
					if not row:
						continue

					try:
						self.env[modelo].agregar_linea(self, row)
						filas_procesadas += 1
					except Exception as e:
						filas_error += 1
						_logging.warning("Error al procesar fila %s: %s | row=%s", contador + 1, e, row[:5])

		except KeyError:
			raise UserError("El archivo '%s' no se encontró dentro del ZIP." % nombre)
		except Exception as e:
			raise UserError("Error al procesar el archivo ZIP: %s" % str(e))

		_logging.info("SIRE Ventas: procesadas %s filas, %s con error", filas_procesadas, filas_error)
		if filas_error:
			return self.show_notification_warning(
				"Se procesaron %s registros correctamente y %s con error. Revise los logs para más detalle." % (filas_procesadas, filas_error), recargar=True
			)
		return self.show_notification_ok("Se procesaron %s registros correctamente." % filas_procesadas, recargar=True)

	def procesar_propuesta(self):
		return self.procesar_archivo_zip(
			'solse.pe.ventas.recibidas',
			self.ventas_registradas,
			self.archivo_propuesta,
			self.nombre_contenido_propuesta,
		)

	def procesar_preliminar(self):
		return self.procesar_archivo_zip(
			'solse.pe.ventas.preliminar',
			self.ventas_preliminar,
			self.archivo_preliminar,
			self.nombre_contenido_preliminar,
		)

	def recalcular_tipo_respuesta(self):
		cant_fact_sistema = len(self.invoice_ids)
		cant_fact_sire = len(self.ventas_registradas)
		monto_fact_sistema = sum(self.invoice_ids.mapped('amount_total'))
		monto_fact_sire = sum(self.ventas_registradas.mapped('total_cp'))
		respuesta = "aceptar"
		if cant_fact_sistema != cant_fact_sire or abs(monto_fact_sistema - monto_fact_sire) > 0.01:
			respuesta = "reemplazar"
		self.tipo_informacion = respuesta

	# ─── Enlace de facturas ──────────────────────────────────────────────────────

	def enlazar_facturas(self):
		"""
		Enlaza masivamente las ventas SUNAT con facturas Odoo, calcula diferencias
		y marca el estado_comparacion de cada linea.
		"""
		todas_las_lineas = self.ventas_registradas
		if not todas_las_lineas:
			return self.show_notification_warning("No hay registros de propuesta SUNAT para procesar.")

		# ── Paso 1: Construir indice de facturas Odoo por (serie, correlativo) ──
		series = list({l.serie_del_cdp for l in todas_las_lineas if l.serie_del_cdp})
		facturas_odoo = self.env['account.move'].search([
			('company_id', '=', self.company_id.id),
			('move_type', 'in', ['out_invoice', 'out_refund']),
			('serie_venta', 'in', series),
		])
		indice_facturas = {}
		for f in facturas_odoo:
			clave = (f.serie_venta, (f.correlativo_venta or '').lstrip('0') or '0')
			indice_facturas[clave] = f

		# ── Paso 2: Enlazar y calcular diferencias ───────────────────────────────
		enlazadas = 0
		diferencias = 0
		sin_odoo = 0
		TOLERANCIA = 0.02

		for linea in todas_las_lineas:
			if not linea.serie_del_cdp or not linea.nro_cp_o_doc_nro_inicial:
				linea.write({'estado_comparacion': 'sin_odoo', 'observacion': 'Sin serie o correlativo en propuesta SUNAT.'})
				sin_odoo += 1
				continue

			# Enlazar si aun no tiene factura
			if not linea.factura_enlazada:
				correlativo_norm = (linea.nro_cp_o_doc_nro_inicial or '').lstrip('0') or '0'
				clave = (linea.serie_del_cdp, correlativo_norm)
				if clave in indice_facturas:
					linea.factura_enlazada = indice_facturas[clave]
					enlazadas += 1

			# Calcular diferencia con la factura enlazada
			if linea.factura_enlazada:
				total_sunat = linea.total_cp or 0.0
				total_odoo = linea.factura_enlazada.amount_total or 0.0
				dif = abs(total_sunat - total_odoo)
				if dif <= TOLERANCIA:
					linea.write({
						'estado_comparacion': 'ok',
						'observacion': False,
					})
				else:
					linea.write({
						'estado_comparacion': 'diferencia',
						'observacion': 'Total SUNAT: %.2f | Total Odoo: %.2f | Diferencia: %.2f' % (
							total_sunat, total_odoo, total_sunat - total_odoo
						),
					})
					diferencias += 1
			else:
				linea.write({
					'estado_comparacion': 'sin_odoo',
					'observacion': 'No se encontró en Odoo: %s-%s' % (
						linea.serie_del_cdp, linea.nro_cp_o_doc_nro_inicial
					),
				})
				sin_odoo += 1

		# ── Paso 3: Detectar facturas Odoo que NO están en propuesta SUNAT ───────
		self._calcular_facturas_sin_sunat()

		mensaje = "Enlazadas: %s | OK: %s | Con diferencia: %s | Sin enlace: %s" % (
			enlazadas,
			len(todas_las_lineas) - diferencias - sin_odoo,
			diferencias,
			sin_odoo,
		)
		if diferencias or sin_odoo:
			return self.show_notification_warning(mensaje, recargar=True)
		return self.show_notification_ok(mensaje, recargar=True)

	def _calcular_facturas_sin_sunat(self):
		"""
		Detecta facturas de Odoo que existen en el período pero NO están
		en la propuesta SUNAT. Las almacena en facturas_sin_sunat.
		"""
		# Serie+correlativo de todos los registros SUNAT del período
		claves_sunat = set()
		for linea in self.ventas_registradas:
			if linea.serie_del_cdp and linea.nro_cp_o_doc_nro_inicial:
				correlativo_norm = (linea.nro_cp_o_doc_nro_inicial or '').lstrip('0') or '0'
				claves_sunat.add((linea.serie_del_cdp, correlativo_norm))

		# Facturas Odoo del período que no aparecen en SUNAT
		facturas_no_sunat = self.env['account.move']
		for factura in self.invoice_ids:
			if not factura.serie_venta or not factura.correlativo_venta:
				continue
			clave = (factura.serie_venta, (factura.correlativo_venta or '').lstrip('0') or '0')
			if clave not in claves_sunat:
				facturas_no_sunat |= factura

		self.facturas_sin_sunat = [(6, 0, facturas_no_sunat.ids)]

	def abrir_propuesta_lista(self):
		"""Abre la propuesta SUNAT en modo lista con filtros."""
		return {
			'name': "Propuesta SUNAT - %s" % self.display_name,
			'type': 'ir.actions.act_window',
			'view_mode': 'list,form',
			'res_model': 'solse.pe.ventas.recibidas',
			'domain': [('periodo_id', '=', self.id)],
			'context': {
				'default_periodo_id': self.id,
				'search_default_group_by_estado': 1,
			},
			'target': 'current',
		}

	def abrir_facturas_sin_sunat(self):
		"""Abre las facturas Odoo que no aparecen en la propuesta SUNAT."""
		if not self.facturas_sin_sunat:
			return self.show_notification_ok("Todas las facturas del período están en la propuesta SUNAT.")
		return {
			'name': "Facturas en Odoo no reportadas en SUNAT",
			'type': 'ir.actions.act_window',
			'view_mode': 'list,form',
			'res_model': 'account.move',
			'domain': [('id', 'in', self.facturas_sin_sunat.ids)],
			'context': {'create': False},
			'target': 'current',
		}

	def crear_facturas(self):
		for linea in self.ventas_registradas:
			if linea.factura_enlazada:
				continue
			linea.crear_factura()

	def abrir_facturas(self):
		facturas = self.ventas_registradas.mapped('factura_enlazada')
		return {
			'name': "Facturas",
			'type': 'ir.actions.act_window',
			'view_mode': 'list,form',
			'res_model': "account.move",
			'domain': [('id', 'in', facturas.ids)],
			'context': {'create': False, 'delete': False, 'edit': True},
			'target': 'current',
		}

	# ─── Conexión SUNAT ──────────────────────────────────────────────────────────

	def conectar(self):
		"""Obtiene el access_token OAuth de la API SUNAT."""
		url_base = 'https://api-seguridad.sunat.gob.pe'
		configuracion = self.env['solse.sunat.api'].search([
			('tipo', '=', 'api'),
			('company_id', '=', self.company_id.id),
		], limit=1)
		if not configuracion:
			raise UserError("No se encontró configuración de API SUNAT para la empresa seleccionada.")

		endpoint = "%s/v1/clientessol/%s/oauth2/token/" % (url_base, configuracion.client_id)
		datos_json = {
			'grant_type': 'password',
			'scope': 'https://api-sire.sunat.gob.pe',
			'client_id': configuracion.client_id,
			'client_secret': configuracion.client_secret,
			'username': "%s%s" % (self.company_id.vat, configuracion.user),
			'password': configuracion.password,
		}
		resp = requests.post(endpoint, data=datos_json, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
		if resp.status_code == 200:
			return resp.json().get('access_token')
		raise UserError("No se pudo obtener el token SUNAT. Verifique las credenciales. (%s)" % resp.status_code)

	def validar_conexion(self):
		"""Verifica que las credenciales y la conexión a la API SUNAT funcionen."""
		try:
			token = self.conectar()
			if token:
				return self.show_notification_ok("Conexión con API SUNAT validada correctamente.")
		except Exception as e:
			raise UserError("Error al validar la conexión: %s" % str(e))

	# ─── Consultar ticket ────────────────────────────────────────────────────────

	def consultar_ticket(self, token=False, numTicket=False):
		if not token:
			token = self.conectar()
		per_ini = self.date.strftime('%Y%m')
		per_fin = self.date.strftime('%Y%m')

		params = {
			'perIni': per_ini,
			'perFin': per_fin,
			'page': '1',
			'perPage': '30',
			# FIX: parámetros obligatorios que faltaban
			'codLibro': COD_LIBRO_RVIE,
			'codOrigenEnvio': COD_ORIGEN_ENVIO_WEB,
		}
		if numTicket:
			params['numTicket'] = numTicket

		url = "https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/gestionprocesosmasivos/web/masivo/consultaestadotickets"
		headers = {
			"Content-Type": "application/json",
			"Accept": "application/json",
			"Authorization": "Bearer %s" % token,
		}
		resp = requests.get(url, params=params, headers=headers, timeout=30)
		if resp.status_code == 200:
			return resp.json()
		raise UserError("No se pudo consultar el estado del ticket. (%s) %s" % (resp.status_code, resp.text))

	def consultar_estado_propuesta(self):
		token = self.conectar()
		ticket = self.obtener_nro_ticket('confirmar_propuesta')
		datos = self.consultar_ticket(token=token, numTicket=ticket.name)
		_logging.info("Estado ticket aceptación: %s", datos)
		if 'registros' in datos and datos['registros']:
			estado = datos['registros'][0].get('desEstadoProceso', '')
			if estado == 'Terminado':
				self.estado_propuesta = 'confirmado'
				return self.show_notification_ok("La propuesta ha sido confirmada correctamente.", recargar=True)
			return self.show_notification_warning("Estado actual del ticket: %s" % estado)

	# ─── Descargar archivo ───────────────────────────────────────────────────────

	def descargar_archivo(self, token, tipo_ticket, datos_ticket):
		"""
		Descarga el archivo ZIP del ticket generado.
		FIX: se agrega codLibro obligatorio al endpoint.
		"""
		if 'registros' not in datos_ticket or not datos_ticket['registros']:
			raise UserError("Respuesta de ticket inválida o vacía.")

		registro = datos_ticket['registros'][0]
		if registro.get('codEstadoProceso') != '06':
			raise UserError("La operación aún no ha terminado. Estado actual: %s" % registro.get('desEstadoProceso', ''))

		archivos_reporte = registro.get('archivoReporte')
		if not archivos_reporte:
			raise UserError("No hay archivos para descargar en este ticket.")

		nom_archivo = archivos_reporte[0]['nomArchivoReporte']
		cod_tipo = archivos_reporte[0].get('codTipoArchivoReporte') or ''
		_logging.info("SIRE descargar_archivo: nom=%s cod_tipo=%s registro=%s", nom_archivo, cod_tipo, registro)

		if tipo_ticket == "propuesta":
			self.nombre_archivo_propuesta = nom_archivo
			self.nombre_contenido_propuesta = archivos_reporte[0].get('nomArchivoContenido', '')
		elif tipo_ticket == "confirmar":
			self.nombre_archivo_confirmacion = nom_archivo
		elif tipo_ticket == "reemplazar":
			self.nombre_archivo_reemplazo = nom_archivo
		elif tipo_ticket == "preliminar":
			self.nombre_archivo_preliminar = nom_archivo
			self.nombre_contenido_preliminar = archivos_reporte[0].get('nomArchivoContenido', '')

		params = {
			'nomArchivoReporte': nom_archivo,
			'codLibro': COD_LIBRO_RVIE,
			'perTributario': registro.get('perTributario', ''),
			'codProceso': registro.get('codProceso', ''),
			'numTicket': registro.get('numTicket', ''),
		}
		# SUNAT rechaza codTipoArchivoReporte vacío — omitir si no viene en la respuesta del ticket
		if cod_tipo:
			params['codTipoArchivoReporte'] = cod_tipo
		url = "https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/gestionprocesosmasivos/web/masivo/archivoreporte"
		headers = {
			"Content-Type": "application/json",
			"Accept": "application/json",
			"Authorization": "Bearer %s" % token,
		}
		resp = requests.get(url, params=params, headers=headers, timeout=60)
		if resp.status_code == 200:
			contenido = base64.b64encode(resp.content)
			if tipo_ticket == "propuesta":
				self.archivo_propuesta = contenido
				self.estado_propuesta = 'recibido'
			elif tipo_ticket == "confirmar":
				self.archivo_confirmacion = contenido
			elif tipo_ticket == "reemplazar":
				self.archivo_reemplazo = contenido
			elif tipo_ticket == "preliminar":
				self.archivo_preliminar = contenido
			self.estado_ticket_sire = "confirmado"
		else:
			raise UserError("Error al descargar el archivo: %s" % resp.text)

	# ─── Solicitar / Descargar propuesta ─────────────────────────────────────────

	def solicitar_propuesta(self):
		per_tributario = self.date.strftime('%Y%m')
		params = {
			# FIX: codTipoArchivo=0 para txt (pipe-delimited), antes era "1" (xls)
			'codTipoArchivo': '0',
			'codOrigenEnvio': COD_ORIGEN_ENVIO_WEB,
		}
		url = "https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvie/propuesta/web/propuesta/%s/exportapropuesta" % per_tributario
		token = self.conectar()
		headers = {
			"Content-Type": "application/json",
			"Accept": "application/json",
			"Authorization": "Bearer %s" % token,
		}
		resp = requests.get(url, params=params, headers=headers, timeout=30)
		if resp.status_code == 200:
			datos = resp.json()
			if 'numTicket' in datos:
				self.guardar_nro_ticket('solicitar_propuesta', datos['numTicket'])
				self.estado_propuesta = 'solicitado'
				return self.show_notification_ok("Propuesta solicitada. Ticket: %s" % datos['numTicket'], recargar=True)
			if 'nombreArchivo' in datos:
				self.esta_vacio = True
				return self.show_notification_warning("No se encontraron comprobantes para el periodo seleccionado.")
		else:
			datos = resp.json()
			if 'errors' in datos:
				raise UserError("\n".join(e["msg"] for e in datos["errors"]))
			raise UserError("Error al solicitar propuesta: %s" % resp.text)

	def descargar_propuesta(self):
		ticket = self.obtener_nro_ticket('solicitar_propuesta')
		token = self.conectar()
		datos_ticket = self.consultar_ticket(token=token, numTicket=ticket.name)
		ticket.write({'datos_crudo': json.dumps(datos_ticket)})
		self.descargar_archivo(token, 'propuesta', datos_ticket)
		return self.show_notification_ok('Propuesta descargada correctamente.', recargar=True)

	def descargar_preliminar(self):
		ticket = self.obtener_nro_ticket('solicitar_preliminar')
		token = self.conectar()
		datos_ticket = self.consultar_ticket(token=token, numTicket=ticket.name)
		ticket.write({'datos_crudo': json.dumps(datos_ticket)})
		self.descargar_archivo(token, 'preliminar', datos_ticket)
		return self.show_notification_ok('Preliminar descargado correctamente.', recargar=True)

	# ─── Aceptar propuesta ───────────────────────────────────────────────────────

	def confirmar_propuesta(self):
		"""
		Acepta la propuesta SUNAT vía POST al endpoint aceptapropuesta.
		Este flujo NO usa el archivo TXT/ZIP (solo es un POST simple).
		El tipo_informacion queda tal cual — el usuario lo maneja como
		estado visible de la intencion sobre la propuesta.
		"""
		self.ensure_one()

		per_tributario = self.date.strftime('%Y%m')
		url = "https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvie/propuesta/web/propuesta/%s/aceptapropuesta" % per_tributario
		token = self.conectar()
		headers = {
			"Content-Type": "application/json",
			"Accept": "application/json",
			"Authorization": "Bearer %s" % token,
		}
		resp = requests.post(url, json={}, headers=headers, timeout=30)
		if resp.status_code == 200:
			datos = resp.json()
			if 'numTicket' in datos:
				self.guardar_nro_ticket('confirmar_propuesta', datos['numTicket'])
				self.estado_propuesta = 'confirmado'
			return self.show_notification_ok("Propuesta aceptada correctamente.", recargar=True)
		datos = resp.json()
		if 'errors' in datos:
			raise UserError("\n".join(e["msg"] for e in datos["errors"]))
		raise UserError("Error al aceptar propuesta: %s" % resp.text)

	# ─── TUS: subida de archivos ─────────────────────────────────────────────────

	def _subir_archivo_tus(self, token, url_subida, contenido_zip, nombre_archivo_zip, nombre_txt_importacion, per_tributario, cod_proceso):
		"""
		Implementación del protocolo TUS.IO para subir archivos a SUNAT.
		Paso 1: POST con metadata → obtiene Location y numTicket
		Paso 2: PATCH con contenido del archivo → 204 No Content
		"""
		ruc = self.company_id.vat
		tam_archivo = len(contenido_zip)

		# Construir metadata con valores en base64
		def b64(valor):
			return base64.b64encode(str(valor).encode()).decode()

		metadata_items = [
			('filename', b64(nombre_archivo_zip)),
			('filetype', b64('application/zip')),
			('numRuc', b64(ruc)),
			('perTributario', b64(per_tributario)),
			('codOrigenEnvio', b64(COD_ORIGEN_ENVIO_WEB)),
			('codProceso', b64(cod_proceso)),
			('codTipoCorrelativo', b64(COD_TIPO_CORRELATIVO_MASIVO)),
			('nomArchivoImportacion', b64(nombre_txt_importacion)),
			('codLibro', b64(COD_LIBRO_RVIE)),
		]
		metadata_str = ','.join('%s %s' % (k, v) for k, v in metadata_items)

		# ── Paso 1: Crear el recurso TUS ────────────────────────────────────────
		headers_create = {
			"Authorization": "Bearer %s" % token,
			"Tus-Resumable": "1.0.0",
			"Upload-Length": str(tam_archivo),
			"Upload-Metadata": metadata_str,
			"Content-Length": "0",
			"Content-Type": "application/x-www-form-urlencoded",
		}
		resp_create = requests.post(url_subida, headers=headers_create, timeout=30)
		if resp_create.status_code not in (200, 201):
			raise UserError("Error TUS al crear la carga (HTTP %s): %s" % (resp_create.status_code, resp_create.text))

		# Obtener URL de destino para el PATCH
		upload_location = resp_create.headers.get('Location', '')
		if not upload_location:
			raise UserError("SUNAT no devolvió una URL de destino para la carga TUS.")
		if not upload_location.startswith('http'):
			upload_location = 'https://api-sire.sunat.gob.pe' + upload_location

		# Extraer el numTicket de la respuesta POST
		num_ticket = ''
		try:
			datos_create = resp_create.json()
			num_ticket = datos_create.get('numTicket', '')
		except Exception:
			pass

		# ── Paso 2: Subir el contenido (PATCH) ──────────────────────────────────
		headers_patch = {
			"Authorization": "Bearer %s" % token,
			"Tus-Resumable": "1.0.0",
			"Upload-Offset": "0",
			"Content-Length": str(tam_archivo),
			"Content-Type": "application/offset+octet-stream",
		}
		resp_patch = requests.patch(upload_location, data=contenido_zip, headers=headers_patch, timeout=120)
		if resp_patch.status_code not in (200, 204):
			raise UserError("Error TUS al subir el archivo (HTTP %s): %s" % (resp_patch.status_code, resp_patch.text))

		# Si el ticket no vino en el POST, intentar del PATCH
		if not num_ticket:
			try:
				datos_patch = resp_patch.json()
				num_ticket = datos_patch.get('numTicket', '')
			except Exception:
				num_ticket = resp_patch.headers.get('numTicket', '')

		return num_ticket

	# ─── Reemplazar propuesta ────────────────────────────────────────────────────

	def reemplazar_propuesta(self):
		"""
		Reemplaza la propuesta SUNAT subiendo el archivo TXT/ZIP vía TUS.

		Como en v0.5 el nombre del archivo lleva report_03='02' tanto para
		'aceptar' como para 'reemplazar' (aceptar no usa TXT/ZIP), ya no se
		fuerza el cambio de tipo_informacion aquí. El campo tipo_informacion
		refleja la intención del usuario y debe ser visible sin ser
		modificado automáticamente.

		Aborta si el tipo_informacion es de ajuste posterior ('posterior' o
		'poseriorperiodo'), porque en ese caso el archivo lleva '03' o '04'
		en el nombre y no es compatible con el flujo de reemplazo.
		"""
		self.ensure_one()

		# 1. Validar que el tipo_informacion sea compatible con reemplazo
		if self.tipo_informacion in ('posterior', 'poseriorperiodo'):
			tipo_label = dict(self._fields['tipo_informacion'].selection).get(
				self.tipo_informacion) or self.tipo_informacion
			raise UserError(
				"El tipo de información actual es '%s', que corresponde a un "
				"ajuste posterior (nombre del archivo con código '03' o '04'). "
				"Este flujo es solo para 'Aceptar' o 'Reemplazar propuesta'.\n\n"
				"Use el flujo de ajustes posteriores dedicado o cambie el tipo "
				"de información." % tipo_label
			)

		# 2. Si no hay archivo generado aún, intentar regenerarlo
		if not self.datas_zip:
			self.update_report()
			self.generate_report()

		if not self.datas_zip:
			raise UserError(
				"No hay archivo TXT/ZIP generado para reemplazar la propuesta. "
				"Verifique que existan facturas para el período y use el botón "
				"'Generar Estructuras'."
			)

		# 3. Validación adicional: el nombre del archivo debe llevar '02' en
		#    las posiciones 28-29 (1-indexed) que corresponden a report_03.
		#    SUNAT rechaza con "Error en Posicion 28, Codigo RVIE Remplazar
		#    Propuesta 02" si encuentra otro código.
		nombre_actual = self.sire_txt_01_filename or ''
		# Estructura del nombre (1-indexed): LE(1-2) + RUC(3-13) + AÑO(14-17) +
		# MES(18-19) + DIA(20-21) + SIRE_ID(22-27) + REPORT_03(28-29) + ...
		# En 0-indexed Python: report_03 está en nombre[27:29].
		if nombre_actual and nombre_actual[27:29] != '02':
			raise UserError(
				"El nombre del archivo generado no contiene el código '02' de reemplazo "
				"en las posiciones 28-29. Nombre actual: %s\n"
				"Use 'Generar Estructuras' para regenerarlo." % nombre_actual
			)

		per_tributario = self.date.strftime('%Y%m')
		url_subida = "https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/receptorpropuesta/web/propuesta/upload"

		token = self.conectar()
		if not token:
			raise UserError("No se pudo obtener un token de autenticación.")

		# Nombre del archivo TXT (sin extensión .zip)
		nombre_txt = self.sire_txt_01_filename or (self.get_default_filename() + '.txt')
		nombre_zip = self.datas_zip_fname or (nombre_txt[:-4] + '.zip')

		contenido_zip = base64.b64decode(self.datas_zip)

		num_ticket = self._subir_archivo_tus(
			token=token,
			url_subida=url_subida,
			contenido_zip=contenido_zip,
			nombre_archivo_zip=nombre_zip,
			nombre_txt_importacion=nombre_zip,  # SUNAT acepta el nombre del ZIP aquí
			per_tributario=per_tributario,
			cod_proceso=COD_PROCESO_REEMPLAZO,
		)

		if num_ticket:
			self.guardar_nro_ticket('reemplazar_propuesta', num_ticket)
			self.estado_propuesta = 'reemplazado'
			return self.show_notification_ok("Propuesta reemplazada. Ticket: %s" % num_ticket, recargar=True)
		return self.show_notification_warning(
			"La propuesta fue enviada pero no se recibió número de ticket.",
			recargar=True,
		)

	# ─── Preliminar ──────────────────────────────────────────────────────────────

	def solicitar_preliminar(self):
		per_tributario = self.date.strftime('%Y%m')
		params = {
			'codTipoArchivo': '1',
			'codOrigenEnvio': COD_ORIGEN_ENVIO_WEB,
			'codLibro': COD_LIBRO_RVIE,
		}
		url = "https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/gestionlibro/web/registroslibros/%s/reportepreliminar" % per_tributario
		token = self.conectar()
		headers = {
			"Content-Type": "application/json",
			"Accept": "application/json",
			"Authorization": "Bearer %s" % token,
		}
		resp = requests.get(url, params=params, headers=headers, timeout=30)
		if resp.status_code == 200:
			datos = resp.json()
			self.guardar_nro_ticket('solicitar_preliminar', datos.get('numTicket', ''))
			return self.show_notification_ok("Preliminar solicitado. Ticket: %s" % datos.get('numTicket', ''))
		datos = resp.json()
		if 'errors' in datos:
			raise UserError("\n".join(e["msg"] for e in datos["errors"]))
		raise UserError("Error al solicitar el preliminar: %s" % resp.text)

	def enviar_preliminar(self):
		per_tributario = self.date.strftime('%Y%m')
		token = self.conectar()
		url = "https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/gestionlibro/web/registroslibros/%s/registrapreliminar" % per_tributario
		headers = {
			"Content-Type": "application/json",
			"Accept": "application/json",
			"Authorization": "Bearer %s" % token,
		}
		resp = requests.post(url, json={}, headers=headers, timeout=30)
		if resp.status_code == 200:
			return self.show_notification_ok("Preliminar registrado correctamente en SUNAT.")
		raise UserError("Error al registrar el preliminar: %s" % resp.text)

	# ─── Ajustes posteriores ─────────────────────────────────────────────────────

	def enviar_ajuste_posterior(self):
		"""
		Servicio 5.6: Importar ajustes posteriores (codProceso=87).
		Sube el ZIP de ajuste via TUS al endpoint de ajustes posteriores.
		"""
		if not self.zip_ajuste_posterior:
			raise UserError("Cargue el archivo ZIP de ajuste posterior antes de enviarlo.")

		per_tributario = self.date.strftime('%Y%m')
		url_subida = "https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/receptorajustesposteriores/web/ajustesposteriores/upload"
		token = self.conectar()

		nombre_zip = self.nombre_zip_ajuste_posterior or ('AP_%s_%s.zip' % (self.company_id.vat, per_tributario))
		contenido_zip = base64.b64decode(self.zip_ajuste_posterior)

		num_ticket = self._subir_archivo_tus(
			token=token,
			url_subida=url_subida,
			contenido_zip=contenido_zip,
			nombre_archivo_zip=nombre_zip,
			nombre_txt_importacion=nombre_zip,
			per_tributario=per_tributario,
			cod_proceso=COD_PROCESO_AJUSTE_POSTERIOR,
		)

		if num_ticket:
			self.ticket_ajuste_posterior = num_ticket
			self.estado_ajuste_posterior = 'enviado'
			return self.show_notification_ok("Ajuste posterior enviado. Ticket: %s" % num_ticket, recargar=True)
		return self.show_notification_warning("Ajuste enviado pero no se recibió número de ticket.", recargar=True)

	def enviar_ajuste_posterior_periodo_anterior(self):
		"""
		Servicio 5.7: Importar ajustes posteriores de periodos anteriores (codProceso=88).
		El período de referencia se obtiene de los campos anio_periodo_anterior / mes_periodo_anterior.
		"""
		if not self.zip_ajuste_anterior:
			raise UserError("Cargue el archivo ZIP de ajuste de periodo anterior antes de enviarlo.")
		if not self.anio_periodo_anterior or not self.mes_periodo_anterior:
			raise UserError("Indique el año y mes del periodo a corregir.")

		per_tributario = "%s%s" % (self.anio_periodo_anterior, str(self.mes_periodo_anterior).zfill(2))
		url_subida = "https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/receptorajustesposteriores/web/ajustesposteriores/upload"
		token = self.conectar()

		nombre_zip = self.nombre_zip_ajuste_anterior or ('APA_%s_%s.zip' % (self.company_id.vat, per_tributario))
		contenido_zip = base64.b64decode(self.zip_ajuste_anterior)

		num_ticket = self._subir_archivo_tus(
			token=token,
			url_subida=url_subida,
			contenido_zip=contenido_zip,
			nombre_archivo_zip=nombre_zip,
			nombre_txt_importacion=nombre_zip,
			per_tributario=per_tributario,
			cod_proceso=COD_PROCESO_AJUSTE_ANTERIOR,
		)

		if num_ticket:
			self.ticket_ajuste_anterior = num_ticket
			self.estado_ajuste_anterior = 'enviado'
			return self.show_notification_ok("Ajuste de periodo anterior enviado. Ticket: %s" % num_ticket, recargar=True)
		return self.show_notification_warning("Ajuste enviado pero no se recibió número de ticket.", recargar=True)

	# ─── Onchange / Defaults ─────────────────────────────────────────────────────

	@api.onchange('company_id')
	def _onchange_company(self):
		dominio = [
			('company_id', '=', self.company_id.id),
			('sub_type', '=', 'sale'),
			('inc_sire_ventas', '=', True),
		]
		documentos = self.env['l10n_latam.document.type'].search(dominio)
		self.documento_compra_ids = [(6, 0, documentos.ids)]

	# ─── Nombre de archivo ───────────────────────────────────────────────────────

	def get_default_filename(self, sire_id='140100', tiene_datos=False):
		name = super().get_default_filename()
		name_dict = {
			'month': str(self.month).rjust(2, '0'),
			'sire_id': sire_id,
		}
		# 'aceptar' y 'reemplazar' comparten report_03='02' en el nombre del
		# archivo, porque 'aceptar' NO envia el TXT/ZIP a SUNAT (es solo un
		# POST directo). Cuando el usuario descarga el archivo manualmente para
		# subirlo al portal SUNAT en el dialogo "Reemplazo de la Propuesta del
		# RVIE", el nombre debe llevar '02' o SUNAT lo rechaza con "Error en
		# Posicion 28, Codigo RVIE Remplazar Propuesta 02".
		if self.tipo_informacion in ("aceptar", "reemplazar"):
			name_dict.update({'report_03': '02', 'operacion': '1', 'contenido': '1', 'moneda': '1', 'sire': '2'})
		elif self.tipo_informacion == "posterior":
			name_dict.update({'report_03': '03', 'operacion': '1', 'contenido': '1', 'moneda': '1', 'sire': '201'})
		elif self.tipo_informacion == "poseriorperiodo":
			name_dict.update({'report_03': '04', 'operacion': '1', 'contenido': '1', 'moneda': '1', 'sire': '201'})

		if not tiene_datos:
			name_dict.update({'contenido': '0'})
		fill_name_data(name_dict)
		return name % name_dict

	# ─── Generar ZIP ─────────────────────────────────────────────────────────────

	def generar_zip(self):
		if not self.sire_txt_01_binary:
			return
		in_memory_data = BytesIO()
		in_memory_zip = zipfile.ZipFile(in_memory_data, 'w', zipfile.ZIP_DEFLATED, False)
		filecontent = base64.b64decode(self.sire_txt_01_binary)
		in_memory_zip.writestr(self.sire_txt_01_filename, filecontent)
		for zfile in in_memory_zip.filelist:
			zfile.create_system = 0
		in_memory_zip.close()
		self.datas_zip = base64.b64encode(in_memory_data.getvalue())
		self.datas_zip_fname = "%s.zip" % self.sire_txt_01_filename[:-4]

	# ─── Actualizar datos (facturas del período) ──────────────────────────────────

	def update_report(self):
		res = super().update_report()
		inicio = datetime.date(self.year, int(self.month), 1)
		fin = get_last_day(inicio)

		doc_type_ids = [reg.id for reg in self.documento_compra_ids]
		pais_pe = self.env.ref('base.pe').id
		dominio = [
			('company_id', '=', self.company_id.id),
			('company_id.partner_id.country_id', '=', pais_pe),
			('move_type', 'in', ['out_invoice', 'out_refund']),
			('state', 'in', ['posted', 'annul', 'cancel']),
			('invoice_date', '>=', str(inicio)),
			('invoice_date', '<=', str(fin)),
		]
		if doc_type_ids:
			dominio.append(('l10n_latam_document_type_id', 'in', doc_type_ids))

		facturas = self.env[self.invoice_ids._name].search(dominio, order='invoice_date asc, name asc')
		self.invoice_ids = facturas
		return res

	# ─── Generar TXT para SIRE ───────────────────────────────────────────────────

	def generate_report(self):
		res = super().generate_report()
		lineas = []
		facturas = self.invoice_ids.sudo()

		for move in facturas:
			# L4.3 (tras L4.1): quedan FUERA del RVIE los rechazados (09)
			# y las excepciones (15/17) — no existen para SUNAT. El
			# OBSERVADO (07) es un comprobante ACEPTADO con reparos y SÍ SE
			# DECLARA: excluirlo descuadraba el RVIE contra lo que SUNAT ya
			# tiene. (El comentario anterior decía «anulados/rechazados» y
			# el código excluía observados: ni describía ni acertaba.)
			if move.is_cpe and move.estado_sunat in ['09', '15', '17']:
				continue
			# RVIE-01: un CANCELADO sin serie-número nunca llegó a SUNAT
			# — no existe como comprobante y no se declara. Los anulados
			# CON número sí van: con sus datos y los importes en 0
			# (obtener_montos_libro_ventas ya los anula por estado).
			if move.state == 'cancel' \
					and not (move.l10n_latam_document_number or '').strip():
				continue
			try:
				linea = self._generar_linea_move(move)
			except Exception as e:
				raise UserError("Error procesando factura %s: %s" % (move.name, e))
			if linea:
				lineas.append('|'.join(linea))

		codigo = "140400"
		nombre_base = self.get_default_filename(sire_id=codigo, tiene_datos=bool(lineas))
		lineas.append('')
		txt_contenido = '\r\n'.join(lineas)

		if txt_contenido:
			xlsx_b64 = self._generate_xlsx_base64_bytes(txt_contenido, nombre_base[4:], headers=self._get_headers_reporte())
			self.write({
				'sire_txt_01': txt_contenido,
				'sire_txt_01_binary': base64.b64encode(txt_contenido.encode()),
				'sire_txt_01_filename': nombre_base + '.txt',
				'sire_xls_01_binary': xlsx_b64.encode(),
				'sire_xls_01_filename': nombre_base + '.xlsx',
				'date_generated': str(fields.Datetime.now()),
			})
		else:
			self.write({
				'sire_txt_01': False,
				'sire_txt_01_binary': False,
				'sire_txt_01_filename': False,
				'sire_xls_01_binary': False,
				'sire_xls_01_filename': False,
				'date_generated': str(fields.Datetime.now()),
			})
		self.generar_zip()
		return res

	def _partir_numero_origen(self, numero, move=None):
		"""Separa SERIE-CORRELATIVO del documento modificado.

		Sustituye a `numero.split('-') if '-' in numero else ['', '']`, que
		tenia dos problemas silenciosos:

		  * SIN GUION se perdia el numero ENTERO. `'00001234'` devolvia
			`['', '']` y la fila salia a SUNAT con serie y correlativo en
			blanco, sin ningun aviso. Ahora el numero se conserva como
			correlativo, que es lo que dice el dato.

		  * CON DOS GUIONES —`'F001-123-45'`— se quedaba con `'123'` y
			descartaba el resto. Se parte solo por el primero.

		Ademas avisa cuando el documento modificado no tiene numero: es un
		campo obligatorio de la nota de credito y de la de debito, y es
		mejor verlo en el log que descubrirlo en el archivo rechazado.
		"""
		numero = (numero or '').strip()
		if not numero:
			_logging.warning(
				'SIRE ventas: la nota %s no tiene número del documento que '
				'modifica. SUNAT exige ese dato; la fila saldrá incompleta.',
				(move.name if move else '') or '?')
			return ['', '']
		if '-' in numero:
			partes = numero.split('-', 1)
			return [partes[0].strip(), partes[1].strip()]
		return ['', numero]

	def _limpiar_correlativo(self, correlativo):
		"""Quita los ceros a la izquierda del correlativo para envío a SUNAT.
		SUNAT espera el correlativo sin padding (ej. '63' en lugar de '00000063').
		Si el correlativo es vacío, devuelve ''. Si es solo ceros, devuelve '0'."""
		if not correlativo:
			return ''
		return correlativo.lstrip('0') or '0'

	def _generar_linea_move(self, move):
		"""Genera la lista de campos para una factura según el formato RVIE."""
		# RVIE-03: sanear ANTES de partir. Series capturadas como
		# «B B012» (espacios de por medio) salían con el espacio dentro,
		# y un número sin guion perdía el correlativo entero (caía al
		# else ['', ''] y la fila iba vacía).
		sunat_number = ' '.join((move.l10n_latam_document_number or '').split())
		if '-' in sunat_number:
			partes_num = [p.replace(' ', '') for p in sunat_number.split('-', 1)]
		elif ' ' in sunat_number:
			# «B012 63» o «B B012»: el último token es el correlativo si
			# hay dos, y todo junto es la serie+número si no se puede
			# distinguir — mejor serie vacía que un campo con espacios.
			trozos = sunat_number.split(' ')
			partes_num = [''.join(trozos[:-1]), trozos[-1]] \
				if len(trozos) > 1 else ['', sunat_number]
		else:
			partes_num = ['', sunat_number]
		sunat_code = move.pe_invoice_code or ''
		invoice_date = move.invoice_date
		date_due = move.invoice_date_due

		m = []
		# Campos 1-4: RUC, Razón Social generador, Período, CAR SUNAT
		m.append(self.company_id.vat)
		m.append(self.company_id.display_name or '')
		# Período debe ser el periodo tributario del reporte (basado en la
		# fecha contable, no en la fecha de emision de cada factura). Una
		# factura emitida en marzo pero anotada contablemente en abril debe
		# declararse con periodo 202604, no 202603. self.date es la fecha
		# del reporte (1er dia del mes del periodo).
		m.append(self.date.strftime('%Y%m'))
		m.append('')  # CAR SUNAT vacío para reemplazo (nota 1 del XLSX)

		# Campo 5: Fecha emisión
		m.append(invoice_date.strftime('%d/%m/%Y'))
		# Campo 6: Fecha vencimiento
		m.append(date_due.strftime('%d/%m/%Y') if date_due else '')

		# Campos 7-10: Tipo CDP, Serie, Nro, Nro Final
		# FIX: el correlativo debe ir SIN ceros adelante. SUNAT lo rechaza
		# si llega como '00000063' en lugar de '63'.
		m.append(sunat_code)
		m.append(partes_num[0])
		m.append(self._limpiar_correlativo(partes_num[1]))
		m.append('')  # Nro Final Rango

		# Campos 11-13: Tipo Doc, Nro Doc, Razón Social cliente
		# RVIE-04: el código de identidad se sanea y, si falta, se
		# INFIERE del propio número — un RUC de 11 dígitos es un '6' y un
		# DNI de 8 es un '1' aunque el partner no tenga configurado el
		# tipo. Antes el campo salía vacío y SUNAT observaba la fila.
		nro_doc = (move.partner_id.vat or '').strip().replace(' ', '')
		cod_doc = (move.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code or '').strip()
		if not cod_doc and nro_doc.isdigit():
			if len(nro_doc) == 11:
				cod_doc = '6'
			elif len(nro_doc) == 8:
				cod_doc = '1'
		nombre_cliente = move.partner_id.name or ''
		m.extend([cod_doc, nro_doc, nombre_cliente])

		# Campos 14-26: Montos tributarios
		montos = move.obtener_montos_libro_ventas()
		for nro in range(13, 26):
			m.append(format(montos.get('nro_%s' % nro, 0), '.2f'))

		# Campos 27-28: Moneda, Tipo de cambio
		# FIX: SUNAT valida (inconsistencia 404 "Campo debe estar vacio")
		# que el Tipo de cambio vaya VACIO cuando la moneda del comprobante
		# es PEN. Solo se registra cuando la moneda es extranjera.
		moneda = move.currency_id.name or 'PEN'
		if moneda == 'PEN':
			valor_tipo_cambio = ''
		else:
			# TC-00 (L4b.1): la búsqueda EXACTA por fecha devolvía 1.000 en
			# fines de semana/feriados sin tasa cargada — importes en soles
			# falsos. _get_conversion_rate usa la última tasa <= fecha,
			# la misma semántica que la contabilidad nativa.
			pen = self.env.ref('base.PEN')
			tipo_cambio = self.env['res.currency']._get_conversion_rate(
				move.currency_id, pen, move.company_id, invoice_date)
			valor_tipo_cambio = format(tipo_cambio, '.3f')
		m.extend([moneda, valor_tipo_cambio])

		# Campos 29-32: Referencias para notas de crédito/débito
		m.extend(self._rvie_doc_modificado(move, sunat_code))

		# Campos 33-34: ID Proyecto, Campo libre
		m.extend(['', ''])

		return m

	def _rvie_doc_modificado(self, move, sunat_code):
		"""Campos 29-32 del Reemplazo RVIE: fecha, tipo, serie y número
		del comprobante que la nota modifica.

		RVIE-03b. Prioridad: el enlace real de Odoo (reversed_entry_id /
		debit_origin_id) y, en su defecto, los campos manuales rvie_*.
		Sin ninguno de los dos, columnas vacías y un warning que nombra
		el comprobante — SUNAT observará la nota, pero el libro entero no
		muere por ella.

		El correlativo va SIN ceros a la izquierda, igual que el del
		propio comprobante.
		"""
		if sunat_code not in ['07', '08']:
			return ['', '', '', '']
		origen = move.reversed_entry_id if sunat_code == '07' \
			else move.debit_origin_id
		if origen and origen.invoice_date:
			partes = self._partir_numero_origen(
				origen.l10n_latam_document_number or '', move)
			return [
				origen.invoice_date.strftime('%d/%m/%Y'),
				origen.pe_invoice_code or '',
				partes[0],
				self._limpiar_correlativo(partes[1]),
			]
		# Sin enlace: el tipo, la serie y el número salen de los campos
		# manuales que solse_pe_cpe ya expone —`origin_doc_code` y
		# `origin_doc_number`, los mismos que hay que rellenar para que
		# SUNAT acepte la nota— y solo la fecha es propia del RVIE.
		# `_partir_numero_origen` sabe partir «F001-00000357» igual que
		# para el enlace.
		if move.rvie_origen_fecha and getattr(move, 'origin_doc_number', False):
			partes = self._partir_numero_origen(move.origin_doc_number, move)
			return [
				move.rvie_origen_fecha.strftime('%d/%m/%Y'),
				(move.origin_doc_code or '01').strip(),
				partes[0],
				self._limpiar_correlativo(partes[1]),
			]
		_logging.warning(
			'RVIE: la nota %s no tiene documento modificado — ni enlace en '
			'Odoo, ni la fecha RVIE con el documento de origen del CPE. '
			'Los campos 29-32 van vacíos, '
			'SUNAT la observará, y además se declara como del mismo periodo '
			'porque no hay fecha con la que compararla.',
			move.name or move.id)
		return ['', '', '', '']

	def _get_headers_reporte(self):
		return [
			'RUC',
			'Apellidos y nombres, denominación o razón social del generador',
			'Periodo',
			'CAR - SUNAT',
			'Fecha de emisión del CP',
			'Fecha de Vencimiento o Fecha de Pago',
			'Tipo de Comprobante de Pago o Documento',
			'Serie del comprobante de pago o documento',
			'Número del comprobante de pago o documento',
			'Número final (Rango)',
			'Tipo de Documento de Identidad del cliente',
			'Número de Documento de Identidad del cliente',
			'Apellidos y nombres, denominación o razón social del cliente',
			'Valor facturado de la exportación',
			'Base imponible de la operación gravada',
			'Descuento de la Base Imponible',
			'IGV y/o IPM',
			'Descuento del IGV y/o IPM',
			'Importe total de la operación exonerada',
			'Importe total de la operación inafecta',
			'Impuesto Selectivo al Consumo',
			'Base imponible - IVAP',
			'IVAP',
			'ICBPER',
			'Otros conceptos, tributos y cargos',
			'Importe total del comprobante de pago',
			'Código de la Moneda',
			'Tipo de cambio',
			'Fecha de emisión del documento original que se modifica',
			'Tipo del comprobante de pago que se modifica',
			'Serie del CP que se modifica',
			'Número del CP que se modifica',
			'Identificación del Contrato o del proyecto',
			'Campo Libre',
		]
