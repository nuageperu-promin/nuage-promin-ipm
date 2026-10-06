# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .sire_report import get_last_day, fill_name_data, number_to_ascii_chr
from io import TextIOWrapper
import base64
import zipfile
import csv
from io import BytesIO
import requests
import json
import datetime
import logging

_logger = logging.getLogger(__name__)

# Dominio activo verificado: api-sire.sunat.gob.pe (CON guión) para todos los endpoints
# El manual menciona apisire.sunat.gob.pe pero ese host no resuelve en producción
_BASE_SIRE = "https://api-sire.sunat.gob.pe"
_BASE_SIRE_RCE = _BASE_SIRE  # alias para compatibilidad
_BASE_SIRE_MSV = _BASE_SIRE  # alias para compatibilidad
_BASE_SEG      = "https://api-seguridad.sunat.gob.pe"

# 5.34 Descargar propuesta
_URL_PROPUESTA      = _BASE_SIRE + "/v1/contribuyente/migeigv/libros/rce/propuesta/web/propuesta/{per}/exportacioncomprobantepropuesta"
# 5.31 Consultar ticket  /  5.32 Descargar archivo
_URL_TICKETS        = _BASE_SIRE + "/v1/contribuyente/migeigv/libros/rvierce/gestionprocesosmasivos/web/masivo/consultaestadotickets"
_URL_ARCHIVO        = _BASE_SIRE + "/v1/contribuyente/migeigv/libros/rvierce/gestionprocesosmasivos/web/masivo/archivoreporte"
# 5.2 Aceptar propuesta
_URL_ACEPTAR        = _BASE_SIRE + "/v1/contribuyente/migeigv/libros/rce/propuesta/web/registroslibros/{per}/aceptarpropuesta"
# 5.3 Reemplazar propuesta — TUS upload
_TUS_URL_REEMPLAZO  = _BASE_SIRE + "/v1/contribuyente/migeigv/libros/rvierce/receptorpropuesta/web/propuesta/upload"
# 5.18 / 5.24 Ajustes posteriores — TUS upload
_TUS_URL_AJUSTE     = _BASE_SIRE + "/v1/contribuyente/migeigv/libros/rvierce/receptorajustesposteriores/web/ajustesposteriores/upload"
# 5.19 Enviar ajuste periodo actual / 5.25 Enviar ajuste periodos anteriores
_URL_ENVIAR_AJUSTE      = _BASE_SIRE + "/v1/contribuyente/migeigv/libros/rvierce/comprobantesajuspost/{per}/1/registrarlibro"
_URL_ENVIAR_AJUSTE_PREV = _BASE_SIRE + "/v1/contribuyente/migeigv/libros/rvierce/ajustesposteriores/3/{per}/registrarlibro"

_TUS_CHUNK = 2 * 1024 * 1024

# Codigos de proceso para servicios masivos SIRE
COD_PROCESO_REEMPLAZO        = "3"   # 5.4 Reemplazar propuesta
COD_PROCESO_AJUSTE_POSTERIOR = "87"  # 5.18/5.19 Ajustes posteriores periodo actual
COD_PROCESO_AJUSTE_ANTERIOR  = "88"  # 5.24/5.25 Ajustes posteriores periodos anteriores


class SireReport08(models.Model):
	_name = "sire.report.08"
	_description = "SIRE 08 - Estructura del Registro de Compras"
	_inherit = "sire.report.templ"

	year = fields.Integer(required=True)
	month = fields.Selection(selection_add=[], required=True)

	bill_ids = fields.Many2many(comodel_name="account.move", string="Compras", readonly=True)

	sire_txt_01 = fields.Text(string="Contenido del TXT 08.4")
	sire_txt_01_binary = fields.Binary(string="TXT 08.4")
	sire_txt_01_filename = fields.Char(string="Nombre del TXT 08.4")
	sire_xls_01_binary = fields.Binary(string="Excel 08.4")
	sire_xls_01_filename = fields.Char(string="Nombre del Excel 08.4")
	datas_zip = fields.Binary("Zip 08.4", readonly=True)

	sire_txt_02 = fields.Text(string="Contenido del TXT 8.5")
	sire_txt_02_binary = fields.Binary(string="TXT 8.5", readonly=True)
	sire_txt_02_filename = fields.Char(string="Nombre del TXT 8.5")
	sire_xls_02_binary = fields.Binary(string="Excel 8.5", readonly=True)
	sire_xls_02_filename = fields.Char(string="Nombre del Excel 8.5")
	datas_zip_02 = fields.Binary("Zip 8.5", readonly=True)
	datas_zip_fname_02 = fields.Char("Nombre de archivo zip", readonly=True)

	documento_compra_ids = fields.Many2many(
		"l10n_latam.document.type",
		"sire_08_report_l10n_latam_id", "report_08_id", "doc_08_id",
		string="Documentos a incluir",
		domain="[('sub_type', 'in', ['purchase'])]",
	)

	# Sobreescribir tipo_informacion del padre para garantizar valores correctos
	tipo_informacion = fields.Selection(
		selection_add=[
			("aceptar", "Aceptar propuesta"),
			("reemplazar", "Reemplazar propuesta"),
			("posterior", "Ajuste posterior"),
			("poseriorperiodo", "Ajuste período anterior"),
		],
		string="Tipo Información",
	)

	ticket_sire = fields.Char("Ticket Sire")
	tipo_ticket = fields.Selection(
		[("propuesta", "Propuesta"), ("confirmar", "Confirmar"), ("reemplazar", "Reemplazar")],
		default="propuesta", string="Tipo ticket",
	)
	estado_ticket_sire = fields.Selection(
		[("borrador", "Borrador"), ("recibido", "Recibido"), ("enviado", "Enviado"), ("confirmado", "Confirmado")],
		default="borrador", string="Estado Ticket",
	)

	csv_temporal = fields.Binary("Archivo csv recibido")
	estado_propuesta = fields.Selection(
		[("borrador", "Borrador"), ("solicitado", "Solicitado"), ("recibido", "Recibido"),
         ("confirmado", "Confirmado"), ("reemplazado", "Reemplazado")],
		default="borrador", string="Estado Propuesta",
	)
	archivo_propuesta = fields.Binary("Propuesta")
	nombre_archivo_propuesta = fields.Char("Nom. Propuesta")
	nombre_contenido_propuesta = fields.Char("Nom. Contenido Propuesta")
	archivo_confirmacion = fields.Binary("Respuesta confirmacion")
	nombre_archivo_confirmacion = fields.Char("Nom. confirmacion")
	archivo_reemplazo = fields.Binary("Respuesta reemplazo")
	nombre_archivo_reemplazo = fields.Char("Nom. reemplazo")
	compras_registradas = fields.One2many("solse.pe.compras.recibidas", "periodo_id")

	# Proveedor base para comprobantes sin RUC/DNI (ej. tipo S3, doc_identidad vacío o "0")
	proveedor_base_id = fields.Many2one(
		"res.partner",
		string="Proveedor base (sin documento)",
		help=(
			"Contacto a usar cuando el comprobante no tiene número de documento de identidad "
			"(nro_doc_identidad vacío o 0). Típicamente para documentos tipo S3 u otros "
			"sin proveedor identificado. Si no se configura, esos comprobantes fallarán."
		),
	)

	# Ajuste posterior periodo actual (5.18/5.19/5.20)
	ajuste_zip_binario = fields.Binary("ZIP Ajuste posterior")
	ajuste_zip_nombre = fields.Char("Nombre ZIP Ajuste")
	ajuste_tus_upload_url = fields.Char("TUS Upload URL ajuste")
	ajuste_tus_offset = fields.Integer("TUS Offset ajuste", default=0)
	ajuste_ticket = fields.Char("Ticket ajuste")
	ajuste_num_posterior = fields.Char("Nro. Ajuste posterior")
	ajuste_estado = fields.Selection(
		[("borrador", "Borrador"), ("subiendo", "Subiendo ZIP"),
         ("subido", "ZIP subido"), ("enviado", "Enviado")],
		default="borrador", string="Estado ajuste",
	)
	ajuste_notas = fields.Text("Notas ajuste")

	# Ajuste periodos anteriores al SIRE (5.24/5.25/5.26)
	ajuste_prev_zip_binario = fields.Binary("ZIP Ajuste per. anteriores")
	ajuste_prev_zip_nombre = fields.Char("Nombre ZIP Ajuste per. ant.")
	ajuste_prev_tus_upload_url = fields.Char("TUS Upload URL ajuste prev.")
	ajuste_prev_tus_offset = fields.Integer("TUS Offset ajuste prev.", default=0)
	ajuste_prev_ticket = fields.Char("Ticket ajuste per. anteriores")
	ajuste_prev_num_posterior = fields.Char("Nro. Ajuste per. anteriores")
	ajuste_prev_anio = fields.Char("Anio periodo a corregir")
	ajuste_prev_mes = fields.Char("Mes periodo a corregir")
	ajuste_prev_estado = fields.Selection(
		[("borrador", "Borrador"), ("subiendo", "Subiendo ZIP"),
         ("subido", "ZIP subido"), ("enviado", "Enviado")],
		default="borrador", string="Estado ajuste per. ant.",
	)
	ajuste_prev_notas = fields.Text("Notas ajuste per. ant.")

	# ── Auth ──────────────────────────────────────────────────────────

	def validar_conexion(self):
		"""Diagnóstico completo de la conexión SUNAT — muestra cada paso."""
		self.ensure_one()
		msgs = []

		# 1. Buscar configuración
		config = self.env["solse.sunat.api"].search(
			[("tipo", "=", "api"), ("company_id", "=", self.company_id.id)], limit=1
		)
		if not config:
			# Intentar sin filtro de tipo para ver qué hay
			todos = self.env["solse.sunat.api"].search([("company_id", "=", self.company_id.id)])
			if todos:
				tipos = ", ".join(set(todos.mapped("tipo")))
				raise UserError(
					"No se encontró configuración con tipo='api' para esta empresa.\n"
					"Registros encontrados con tipos: %s\n"
					"Verifique que el campo 'Tipo' sea 'api'." % tipos
				)
			raise UserError(
				"No existe ninguna configuración de API SUNAT para la empresa '%s'.\n"
				"Vaya a Configuración > API SUNAT y cree un registro." % self.company_id.name
			)

		msgs.append("✓ Configuración encontrada: %s" % config.name)
		msgs.append("  Client ID: %s" % (config.client_id or '(vacío)'))
		msgs.append("  Usuario SOL: %s%s" % (self.company_id.vat, config.user or '(vacío)'))

		# 2. Intentar token
		try:
			token = self.conectar()
			msgs.append("✓ Token obtenido correctamente")
			msgs.append("  Token (primeros 40 chars): %s..." % token[:40])
		except UserError as e:
			msgs.append("✗ Error obteniendo token: %s" % str(e))
			raise UserError("\n".join(msgs))
		except Exception as e:
			msgs.append("✗ Excepción inesperada: %s" % str(e))
			raise UserError("\n".join(msgs))

		# 3. Consultar períodos habilitados y su estado
		try:
			url = "%s/v1/contribuyente/migeigv/libros/rvierce/padron/web/omisos/080000/periodos" % _BASE_SIRE_MSV
			resp = requests.get(url, headers=self._hdr(token), timeout=15)
			msgs.append("✓ Ping SIRE: HTTP %d" % resp.status_code)
			if resp.status_code == 200:
				try:
					datos_per = resp.json()
					msgs.append("\nEstado de períodos en SUNAT:")
					for ejercicio in (datos_per if isinstance(datos_per, list) else []):
						anio = ejercicio.get("numEjercicio", "")
						for p in ejercicio.get("lisPeriodos", []):
							per_str = p.get("perTributario", "")
							estado = p.get("desEstado", p.get("codEstado", ""))
							msgs.append("  %s — %s" % (per_str, estado))
				except Exception:
					msgs.append("  (no se pudo parsear lista de períodos)")
			else:
				msgs.append("  Respuesta: %s" % resp.text[:200])
		except requests.exceptions.ConnectTimeout:
			msgs.append("✗ Timeout conectando a SUNAT (¿proxy/firewall?)")
		except requests.exceptions.ConnectionError as e:
			msgs.append("✗ Error de conexión: %s" % str(e)[:200])
		except Exception as e:
			msgs.append("✗ Error: %s" % str(e)[:200])

		raise UserError("\n".join(msgs))

	def conectar(self):
		config = self.env["solse.sunat.api"].search(
			[("tipo", "=", "api"), ("company_id", "=", self.company_id.id)], limit=1
		)
		if not config:
			raise UserError("No se encontro configuracion de API SUNAT para esta empresa.")
		endpoint = "%s/v1/clientessol/%s/oauth2/token/" % (_BASE_SEG, config.client_id)
		datos = {
			"grant_type": "password",
			"scope": "https://api-sire.sunat.gob.pe",
			"client_id": config.client_id,
			"client_secret": config.client_secret,
			"username": "%s%s" % (self.company_id.vat, config.user),
			"password": config.password,
		}
		resp = requests.post(endpoint, data=datos, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
		if resp.status_code == 200:
			return resp.json()["access_token"]
		raise UserError("No se pudo obtener token SUNAT: %s" % resp.text[:300])

	def _hdr(self, token):
		return {"Content-Type": "application/json", "Accept": "application/json", "Authorization": "Bearer %s" % token}

	def _error(self, resp):
		try:
			d = resp.json()
			if "errors" in d:
				return "\n".join("%s: %s" % (e.get("cod",""), e.get("msg","")) for e in d["errors"])
			return d.get("msg", resp.text[:300])
		except Exception:
			return resp.text[:300]

	# ── Propuesta ─────────────────────────────────────────────────────

	def descargar_propuesta(self):
		if self.ticket_sire and self.estado_ticket_sire == "recibido":
			raise UserError("Ya tiene una peticion pendiente. Consulte el ticket primero.")
		per = self.date.strftime("%Y%m")
		fec_ini = self.date.strftime("%Y-%m-01")
		fec_fin = str(get_last_day(self.date))
		url = _URL_PROPUESTA.format(per=per) + "?codTipoArchivo=1&codOrigenEnvio=1&fecEmisionIni=%s&fecEmisionFin=%s" % (fec_ini, fec_fin)
		_logger.info("SIRE descargar_propuesta URL: %s", url)
		token = self.conectar()
		try:
			resp = requests.get(url, headers=self._hdr(token), timeout=60)
		except requests.exceptions.Timeout:
			raise UserError("Timeout conectando a SUNAT (>60s). Verifique la conexion a internet.")
		except requests.exceptions.ConnectionError as e:
			raise UserError("Error de conexion a SUNAT: %s" % str(e)[:300])

		_logger.info("SIRE descargar_propuesta HTTP %d: %s", resp.status_code, resp.text[:500])

		if resp.status_code == 200:
			try:
				datos = resp.json()
			except Exception:
				raise UserError(
					"SUNAT retorno HTTP 200 pero la respuesta no es JSON.\n"
					"Contenido: %s" % resp.text[:300]
				)
			if "numTicket" not in datos:
				raise UserError(
					"Respuesta inesperada de SUNAT (sin numTicket).\n"
					"Respuesta: %s" % str(datos)[:300]
				)
			self.write({
				"tipo_ticket": "propuesta",
				"ticket_sire": datos["numTicket"],
				"estado_ticket_sire": "recibido",
				"estado_propuesta": "solicitado",
			})
		elif resp.status_code == 500 and "<html>" in resp.text:
			# SUNAT devuelve HTML 500 cuando el período ya fue declarado
			# o cuando no hay propuesta disponible para ese período
			raise UserError(
				"SUNAT retorno error 500 para el período %s.\n\n"
				"Causas posibles:\n"
				"- El período ya fue declarado/confirmado en SUNAT\n"
				"- No existe propuesta disponible para este período\n"
				"- El RUC no está habilitado para SIRE Compras\n\n"
				"Verifique en el portal web de SUNAT (SIRE) si el período %s "
				"ya tiene estado 'Confirmado' o 'Reemplazado'." % (per, per)
			)
		else:
			raise UserError(
				"Error solicitando propuesta (HTTP %d):\n%s" % (resp.status_code, self._error(resp))
			)

	def consultar_ticket(self, token=False):
		if not self.ticket_sire:
			raise UserError("No hay ticket que consultar.")
		if not token:
			token = self.conectar()
		per = self.date.strftime("%Y%m")
		url = "%s?perIni=%s&perFin=%s&page=1&perPage=30&numTicket=%s" % (_URL_TICKETS, per, per, self.ticket_sire)
		resp = requests.get(url, headers=self._hdr(token), timeout=30)
		if resp.status_code != 200:
			raise UserError("Error consultando ticket:\n" + self._error(resp))
		datos = resp.json()
		if "registros" not in datos or not datos["registros"]:
			raise UserError("Respuesta inesperada de SUNAT (sin registros).")
		registro = datos["registros"][0]
		cod = registro.get("codEstadoProceso", "")
		if cod != "06":
			raise UserError("El proceso aun no termino. Estado: %s" % registro.get("desEstadoProceso", ""))
		self._descargar_archivo_ticket(registro, token)

	def _descargar_archivo_ticket(self, registro, token):
		archivos = registro.get("archivoReporte", [])
		if not archivos:
			raise UserError("El ticket no tiene archivos para descargar.")
		info = archivos[0]
		nom = info.get("nomArchivoReporte", "")
		nom_csv = info.get("nomArchivoContenido", "")
		url = "%s?nomArchivoReporte=%s&codTipoArchivoReporte=00&perTributario=%s&codProceso=%s&numTicket=%s" % (
			_URL_ARCHIVO, nom, registro.get("perTributario",""), registro.get("codProceso",""), registro.get("numTicket",""))
		resp = requests.get(url, headers=self._hdr(token), timeout=60)
		if resp.status_code != 200:
			raise UserError("Error descargando archivo:\n" + self._error(resp))
		tipo = self.tipo_ticket
		vals = {"estado_ticket_sire": "confirmado"}
		if tipo == "propuesta":
			vals.update({"nombre_archivo_propuesta": nom, "nombre_contenido_propuesta": nom_csv,
                         "archivo_propuesta": base64.b64encode(resp.content), "estado_propuesta": "recibido"})
		elif tipo == "confirmar":
			vals.update({"nombre_archivo_confirmacion": nom, "archivo_confirmacion": base64.b64encode(resp.content)})
		elif tipo == "reemplazar":
			vals.update({"nombre_archivo_reemplazo": nom, "archivo_reemplazo": base64.b64encode(resp.content)})
		self.write(vals)

	def leer_zip_propuesta(self):
		zf = zipfile.ZipFile(BytesIO(base64.b64decode(self.archivo_propuesta)))
		try:
			with zf.open(self.nombre_contenido_propuesta) as lect:
				reader = csv.reader(TextIOWrapper(lect, "utf-8"), delimiter=",", quotechar="|")
				self.compras_registradas.unlink()
				for i, row in enumerate(reader):
					if i == 0:
						continue
					self.env["solse.pe.compras.recibidas"].agregar_linea(self, row)
		except Exception as e:
			raise UserError("Error procesando ZIP de propuesta: %s" % str(e))

	def procesar_propuesta(self):
		self.leer_zip_propuesta()
		self.recalcular_tipo_respuesta()

	def recalcular_tipo_respuesta(self):
		cant_s = len(self.bill_ids)
		cant_r = len(self.compras_registradas)
		monto_s = sum(self.bill_ids.mapped("amount_total"))
		monto_r = sum(self.compras_registradas.mapped("total_cp"))
		self.tipo_informacion = "reemplazar" if (cant_s != cant_r or round(monto_s, 2) != round(monto_r, 2)) else "aceptar"

	def confirmar_propuesta(self):
		"""Acepta la propuesta SUNAT vía POST al endpoint aceptapropuesta.

        Este flujo NO usa el archivo TXT/ZIP (solo es un POST simple). El
        tipo_informacion queda tal cual — el usuario lo maneja como estado
        visible de la intencion sobre la propuesta.
        """
		self.ensure_one()
		if self.ticket_sire and self.estado_ticket_sire == "recibido":
			raise UserError("Ya tiene una peticion pendiente. Consulte el ticket primero.")

		per = self.date.strftime("%Y%m")
		token = self.conectar()
		resp = requests.post(_URL_ACEPTAR.format(per=per), json={}, headers=self._hdr(token), timeout=30)
		if resp.status_code == 200:
			datos = resp.json()
			self.write({"tipo_ticket": "confirmar", "ticket_sire": datos.get("numTicket", resp.text),
						"estado_ticket_sire": "recibido", "estado_propuesta": "confirmado"})
		else:
			raise UserError("Error aceptando propuesta:\n" + self._error(resp))

	# ── TUS utilidades ────────────────────────────────────────────────

	def _tus_metadata(self, nom_archivo, per_tributario, cod_proceso):
		def b64(s): return base64.b64encode(s.encode()).decode()
		return ",".join([
			"filename %s" % b64(nom_archivo),
			"filetype %s" % b64("application/zip"),
			"numRuc %s" % b64(self.company_id.vat),
			"perTributario %s" % b64(per_tributario),
			"codOrigenEnvio %s" % b64("2"),
			"codProceso %s" % b64(cod_proceso),
			"codTipoCorrelativo %s" % b64("01"),
			"nomArchivoImportacion %s" % b64(nom_archivo),
			"codLibro %s" % b64("080000"),
		])

	def _tus_crear(self, token, datos, nom, per, cod_proc, tus_url):
		headers = {
			"Authorization": "Bearer %s" % token,
			"Tus-Resumable": "1.0.0",
			"Upload-Length": str(len(datos)),
			"Upload-Metadata": self._tus_metadata(nom, per, cod_proc),
			"Content-Type": "application/offset+octet-stream",
		}
		resp = requests.post(tus_url, headers=headers, timeout=30)
		if resp.status_code not in (200, 201):
			raise UserError("Error creando upload TUS:\n" + self._error(resp))
		loc = resp.headers.get("Location", "")
		if not loc:
			raise UserError("SUNAT no retorno Location en respuesta TUS.")
		return loc

	def _tus_chunks(self, token, upload_url, datos, offset_ini, campo_url, campo_offset):
		offset = offset_ini
		total = len(datos)
		while offset < total:
			chunk = datos[offset: offset + _TUS_CHUNK]
			headers = {
				"Authorization": "Bearer %s" % token,
				"Tus-Resumable": "1.0.0",
				"Upload-Offset": str(offset),
				"Content-Type": "application/offset+octet-stream",
			}
			resp = requests.patch(upload_url, data=chunk, headers=headers, timeout=120)
			if resp.status_code not in (200, 204):
				raise UserError("Error chunk TUS (offset %d):\n%s" % (offset, self._error(resp)))
			offset = int(resp.headers.get("Upload-Offset", offset + len(chunk)))
			self.write({campo_url: upload_url, campo_offset: offset})
			self.env.cr.commit()
		if offset != total:
			raise UserError("Upload TUS incompleto: %d != %d." % (offset, total))

	def _tus_cargar(self, campo_zip, campo_nom, campo_url, campo_offset,
					campo_estado, campo_notas, per, cod_proc, tus_url):
		zip_b64 = getattr(self, campo_zip)
		nom = getattr(self, campo_nom)
		if not zip_b64 or not nom:
			raise UserError("Debe adjuntar el ZIP antes de subirlo.")
		datos = base64.b64decode(zip_b64)
		token = self.conectar()
		upload_url = getattr(self, campo_url)
		offset = getattr(self, campo_offset) or 0
		self.write({campo_estado: "subiendo"})
		self.env.cr.commit()
		if not upload_url:
			upload_url = self._tus_crear(token, datos, nom, per, cod_proc, tus_url)
			self.write({campo_url: upload_url, campo_offset: 0})
			offset = 0
		self._tus_chunks(token, upload_url, datos, offset, campo_url, campo_offset)
		# Consultar ticket automáticamente tras subida exitosa
		ticket_auto = self._consultar_ticket_ajuste(token, per)
		vals = {campo_estado: "subido"}
		if ticket_auto:
			vals[campo_notas] = "ZIP subido. Ticket asignado: %s" % ticket_auto
		else:
			vals[campo_notas] = "ZIP subido correctamente. Obtenga el ticket en el portal SUNAT."
		self.write(vals)
		return ticket_auto

	def _consultar_ticket_ajuste(self, token, per):
		"""Consulta el ticket más reciente de ajuste para el período dado."""
		try:
			url = "%s?perIni=%s&perFin=%s&page=1&perPage=5" % (_URL_TICKETS, per, per)
			resp = requests.get(url, headers=self._hdr(token), timeout=15)
			if resp.status_code != 200:
				return False
			datos = resp.json()
			registros = datos.get("registros", [])
			# Buscar el ticket más reciente de tipo ajuste (codProceso 59 o 87)
			for reg in registros:
				cod = str(reg.get("codProceso", ""))
				if cod in ("59", "87", "88"):
					return reg.get("numTicket", False)
			# Si no hay específico de ajuste, retornar el más reciente
			if registros:
				return registros[0].get("numTicket", False)
		except Exception:
			pass
		return False

	# ── Reemplazar propuesta TUS (5.4) ───────────────────────────────

	def reemplazar_propuesta(self):
		"""Reemplaza la propuesta SUNAT subiendo el archivo TXT/ZIP via TUS.

        Como en v1.4.2 el nombre del archivo lleva report_03='02' tanto para
        'aceptar' como para 'reemplazar' (aceptar no usa TXT/ZIP), ya no se
        fuerza el cambio de tipo_informacion aqui. El campo tipo_informacion
        refleja la intencion del usuario y debe ser visible sin ser modificado
        automaticamente.

        Aborta si el tipo_informacion es de ajuste posterior ('posterior' o
        'poseriorperiodo'), porque en ese caso el archivo lleva '03' o '04' en
        el nombre y no es compatible con el flujo de reemplazo.

        Flujo:
        1. Valida que tipo_informacion no sea de ajuste posterior.
        2. Genera el ZIP si no existe.
        3. Valida que el nombre lleve '02' en posiciones 28-29.
        4. Sube el ZIP via TUS (POST + PATCH chunked).
        5. Extrae el numTicket de la respuesta TUS.
        """
		self.ensure_one()

		# 1. Validar que el tipo_informacion sea compatible con reemplazo
		if self.tipo_informacion in ('posterior', 'poseriorperiodo'):
			tipo_label = dict(self._fields['tipo_informacion'].selection).get(
				self.tipo_informacion) or self.tipo_informacion
			raise UserError(
				"El tipo de informacion actual es '%s', que corresponde a un "
				"ajuste posterior (nombre del archivo con codigo '03' o '04'). "
				"Este flujo es solo para 'Aceptar' o 'Reemplazar propuesta'.\n\n"
				"Use el flujo de ajustes posteriores dedicado o cambie el tipo "
				"de informacion." % tipo_label
			)

		# 2. Generar ZIP si todavia no existe
		if not self.datas_zip:
			self.generate_report()
			if not self.datas_zip:
				raise UserError(
					"No se pudo generar el archivo ZIP.\n"
					"Verifique que existen facturas registradas en el periodo."
				)

		if self.ticket_sire and self.estado_ticket_sire == "recibido":
			raise UserError("Ya tiene una peticion pendiente. Consulte el ticket primero.")

		# 3. Validar que el nombre del archivo lleva '02' en las posiciones 28-29
		nombre_actual = self.sire_txt_01_filename or ''
		if nombre_actual and nombre_actual[27:29] != '02':
			raise UserError(
				"El nombre del archivo generado no contiene el codigo '02' de "
				"reemplazo en las posiciones 28-29. Nombre actual: %s\n"
				"Use 'Generar Estructuras' para regenerarlo." % nombre_actual
			)

		per = self.date.strftime("%Y%m")
		nom = self.datas_zip_fname or ("LE%s%s00080000021112.zip" % (self.company_id.vat, per))
		datos = base64.b64decode(self.datas_zip)
		token = self.conectar()

		# 4. Crear recurso TUS y obtener numTicket del POST (si viene)
		upload_url = self._tus_crear(token, datos, nom, per, COD_PROCESO_REEMPLAZO, _TUS_URL_REEMPLAZO)

		# 5. Subir chunks
		offset = 0
		total = len(datos)
		num_ticket = ''
		ultima_respuesta = None
		while offset < total:
			chunk = datos[offset: offset + _TUS_CHUNK]
			headers = {"Authorization": "Bearer %s" % token, "Tus-Resumable": "1.0.0",
                       "Upload-Offset": str(offset), "Content-Type": "application/offset+octet-stream"}
			resp = requests.patch(upload_url, data=chunk, headers=headers, timeout=120)
			if resp.status_code not in (200, 204):
				raise UserError("Error subiendo ZIP reemplazo:\n" + self._error(resp))
			offset = int(resp.headers.get("Upload-Offset", offset + len(chunk)))
			ultima_respuesta = resp

		# 6. Extraer numTicket de la ultima respuesta PATCH o de los headers TUS
		if ultima_respuesta is not None:
			num_ticket = ultima_respuesta.headers.get('numTicket', '')
			if not num_ticket:
				try:
					body = ultima_respuesta.json()
					num_ticket = body.get('numTicket', '')
				except Exception:
					pass

		# 7. Si no llego ticket en TUS, intentar obtenerlo del listado reciente
		if not num_ticket:
			num_ticket = self._consultar_ticket_ajuste(token, per) or ''

		vals = {
			"tipo_ticket": "reemplazar",
			"ticket_sire": num_ticket,
			"estado_ticket_sire": "recibido",
			"estado_propuesta": "reemplazado",
		}
		self.write(vals)

		mensaje_ok = (
			"Propuesta reemplazada. Ticket: %s" % num_ticket
			if num_ticket else
			"Propuesta enviada pero no se recibio numero de ticket. "
			"Consulte el portal SUNAT para verificar el estado."
		)
		return {
			'type': 'ir.actions.client',
			'tag': 'display_notification',
			'params': {
				'title': "Reemplazo de propuesta",
				'message': mensaje_ok,
				'sticky': True,
				'next': {'type': 'ir.actions.client', 'tag': 'reload'},
			},
		}

	# ── Ajuste posterior periodo actual (5.18/5.19) ──────────────────

	def cargar_ajuste_zip(self):
		per = self.date.strftime("%Y%m")
		# Auto-nombre: usar el ZIP del período si no se ingresó nombre
		if not self.ajuste_zip_nombre and self.datas_zip_fname:
			self.ajuste_zip_nombre = self.datas_zip_fname
		# Auto-zip: usar datas_zip si no se adjuntó uno específico
		if not self.ajuste_zip_binario and self.datas_zip:
			self.ajuste_zip_binario = self.datas_zip
		ticket = self._tus_cargar("ajuste_zip_binario", "ajuste_zip_nombre",
                         "ajuste_tus_upload_url", "ajuste_tus_offset",
                         "ajuste_estado", "ajuste_notas", per, "6", _TUS_URL_AJUSTE)
		if ticket:
			self.write({"ajuste_ticket": ticket})

	def enviar_ajuste(self):
		if self.ajuste_estado != "subido":
			raise UserError("Primero suba el ZIP del ajuste.")
		# Si el ticket no se auto-llenó, consultarlo ahora
		if not self.ajuste_ticket:
			token = self.conectar()
			per = self.date.strftime("%Y%m")
			ticket = self._consultar_ticket_ajuste(token, per)
			if ticket:
				self.write({"ajuste_ticket": ticket})
			else:
				raise UserError("No se pudo obtener el ticket automáticamente.\nIngrese el ticket del ajuste manualmente.")
		if not self.ajuste_num_posterior:
			# Usar el ticket como num_posterior provisional si SUNAT no lo retornó
			self.ajuste_num_posterior = "1"
		per = self.date.strftime("%Y%m")
		url = _URL_ENVIAR_AJUSTE.format(per=per)
		params = "?num_ajuste=%s&cod_libro=080000&num_ticket=%s" % (self.ajuste_num_posterior, self.ajuste_ticket)
		token = self.conectar()
		resp = requests.post(url + params, json={}, headers=self._hdr(token), timeout=30)
		if resp.status_code == 200:
			d = resp.json()
			num_ticket = d.get("numTicket", "")
			self.write({
				"ajuste_estado": "enviado",
				"ajuste_ticket": num_ticket or self.ajuste_ticket,
				"ajuste_num_posterior": d.get("numAjustePost", d.get("numPosterior", self.ajuste_num_posterior or "")),
				"ajuste_notas": "Enviado correctamente. Ticket: %s" % num_ticket,
			})
		else:
			raise UserError("Error enviando ajuste:\n" + self._error(resp))

	def reiniciar_ajuste_tus(self):
		self.write({"ajuste_tus_upload_url": False, "ajuste_tus_offset": 0,
					"ajuste_estado": "borrador", "ajuste_notas": False})

	# ── Ajuste periodos anteriores al SIRE (5.24/5.25) ──────────────

	def cargar_ajuste_prev_zip(self):
		if not self.ajuste_prev_anio or not self.ajuste_prev_mes:
			raise UserError("Ingrese el anio y mes del periodo a corregir.")
		per = "%s%s" % (self.ajuste_prev_anio, str(self.ajuste_prev_mes).zfill(2))
		ticket = self._tus_cargar("ajuste_prev_zip_binario", "ajuste_prev_zip_nombre",
                         "ajuste_prev_tus_upload_url", "ajuste_prev_tus_offset",
                         "ajuste_prev_estado", "ajuste_prev_notas", per, "7", _TUS_URL_AJUSTE)
		if ticket:
			self.write({"ajuste_prev_ticket": ticket})

	def enviar_ajuste_prev(self):
		if self.ajuste_prev_estado != "subido":
			raise UserError("Primero suba el ZIP del ajuste.")
		if not self.ajuste_prev_anio or not self.ajuste_prev_mes:
			raise UserError("Ingrese el anio y mes del periodo a corregir.")
		# Si el ticket no se auto-llenó, consultarlo ahora
		if not self.ajuste_prev_ticket:
			token = self.conectar()
			per = "%s%s" % (self.ajuste_prev_anio, str(self.ajuste_prev_mes).zfill(2))
			ticket = self._consultar_ticket_ajuste(token, per)
			if ticket:
				self.write({"ajuste_prev_ticket": ticket})
			else:
				raise UserError("No se pudo obtener el ticket automáticamente.\nIngrese el ticket del ajuste manualmente.")
		if not self.ajuste_prev_num_posterior:
			self.ajuste_prev_num_posterior = "1"
		per = "%s%s" % (self.ajuste_prev_anio, str(self.ajuste_prev_mes).zfill(2))
		url = _URL_ENVIAR_AJUSTE_PREV.format(per=per)
		params = "?num_ajuste=%s&cod_libro=080000&num_ticket=%s" % (self.ajuste_prev_num_posterior, self.ajuste_prev_ticket)
		token = self.conectar()
		resp = requests.post(url + params, json={}, headers=self._hdr(token), timeout=30)
		if resp.status_code == 200:
			d = resp.json()
			num_ticket = d.get("numTicket", "")
			self.write({
				"ajuste_prev_estado": "enviado",
				"ajuste_prev_ticket": num_ticket or self.ajuste_prev_ticket,
				"ajuste_prev_num_posterior": d.get("numAjustePost", d.get("numPosterior", self.ajuste_prev_num_posterior or "")),
				"ajuste_prev_notas": "Enviado correctamente. Ticket: %s" % num_ticket,
			})
		else:
			raise UserError("Error enviando ajuste per. anteriores:\n" + self._error(resp))

	def reiniciar_ajuste_prev_tus(self):
		self.write({"ajuste_prev_tus_upload_url": False, "ajuste_prev_tus_offset": 0,
					"ajuste_prev_estado": "borrador", "ajuste_prev_notas": False})

	# ── Facturas propuesta ────────────────────────────────────────────

	def enlazar_facturas(self):
		registros = self.compras_registradas
		# Procesar todos: los ya enlazados revalidan diferencia, los sin enlazar buscan
		registros.enlazar_con_factura()
		# Resumen
		total     = len(registros)
		ok        = len(registros.filtered(lambda r: r.estado_enlace == "ok"))
		diferencia= len(registros.filtered(lambda r: r.estado_enlace == "diferencia"))
		solo_sunat= len(registros.filtered(lambda r: r.estado_enlace == "solo_sunat"))
		lineas = [
			"Resultado del enlace:",
			"",
			"  OK Coinciden:         %d" % ok,
			"  !! Con diferencia:    %d" % diferencia,
			"  XX Solo en SUNAT:     %d" % solo_sunat,
			"------------------------------",
			"  Total propuesta:      %d" % total,
			"",
			("Revise los marcados con !! o XX antes de declarar." if (diferencia or solo_sunat) else "Todo en orden!"),
		]
		msg = "\n".join(lineas)
		return {
			"type": "ir.actions.client",
			"tag": "display_notification",
			"params": {
				"title": "Enlace completado",
				"message": msg,
				"type": "warning" if (diferencia or solo_sunat) else "success",
				"sticky": True,
			},
		}

	def abrir_lista_propuesta(self):
		"""Abre los comprobantes SUNAT del período en vista lista con filtros."""
		return {
			"name": "Propuesta SUNAT - %s/%s" % (self.month, self.year),
			"type": "ir.actions.act_window",
			"view_mode": "list",
			"res_model": "solse.pe.compras.recibidas",
			"domain": [("periodo_id", "=", self.id)],
			"views": [(self.env.ref("solse_pe_sire_compra.view_compras_recibidas_list").id, "list")],
			"search_view_id": self.env.ref("solse_pe_sire_compra.view_compras_recibidas_search").id,
			"context": {"create": False, "delete": False},
		}

	def abrir_facturas_no_declaradas(self):
		"""Facturas de Odoo del período que NO aparecen en la propuesta SUNAT."""
		per_ini = self.date.replace(day=1)
		import calendar
		ultimo_dia = calendar.monthrange(self.date.year, self.date.month)[1]
		per_fin = self.date.replace(day=ultimo_dia)
		ruc_sunat = set(self.compras_registradas.mapped("nro_doc_identidad"))
		serie_corr_sunat = set(
			(r.serie, r.nro_correlativo) for r in self.compras_registradas
		)
		facturas = self.env["account.move"].search([
			("company_id", "=", self.company_id.id),
			("move_type", "in", ["in_invoice", "in_refund"]),
			("state", "=", "posted"),
			("invoice_date", ">=", per_ini),
			("invoice_date", "<=", per_fin),
		])
		# Filtrar las que no están en la propuesta por serie+correlativo
		no_declaradas = facturas.filtered(
			lambda f: (
				getattr(f, "serie_compra", False) and
				getattr(f, "correlativo_compra", False) and
				(f.serie_compra, f.correlativo_compra) not in serie_corr_sunat
			)
		)
		if not no_declaradas:
			raise UserError(
				"Todas las facturas del periodo estan presentes en la propuesta SUNAT. No se encontraron facturas no declaradas."
			)
		return {
			"name": "Facturas NO en propuesta SUNAT - %s/%s" % (self.month, self.year),
			"type": "ir.actions.act_window",
			"view_mode": "list,form",
			"res_model": "account.move",
			"domain": [("id", "in", no_declaradas.ids)],
			"context": {"create": False},
		}

	def crear_facturas(self):
		for linea in self.compras_registradas.filtered(lambda r: not r.factura_enlazada):
			try:
				linea.crear_factura()
			except Exception as e:
				_logger.warning("SIRE crear_factura %s-%s: %s", linea.serie, linea.nro_correlativo, e)

	def abrir_facturas(self):
		facturas = self.compras_registradas.mapped("factura_enlazada")
		if not facturas:
			raise UserError("No hay facturas enlazadas en la propuesta de este periodo.")
		return {
			"name": "Facturas propuesta SUNAT",
			"type": "ir.actions.act_window",
			"view_mode": "list,form",
			"res_model": "account.move",
			"domain": [("id", "in", facturas.ids)],
			"context": {"default_move_type": "in_invoice", "create": False},
			"target": "current",
		}

	# ── onchange / helpers ────────────────────────────────────────────

	@api.onchange("company_id")
	def _onchange_company(self):
		dominio = [("company_id", "=", self.company_id.id), ("sub_type", "=", "purchase"), ("inc_sire_compras", "=", True)]
		self.documento_compra_ids = [(6, 0, self.env["l10n_latam.document.type"].search(dominio).ids)]

	def get_default_filename(self, sire_id="080400", tiene_datos=False):
		name = super().get_default_filename()
		name_dict = {"month": str(self.month).rjust(2, "0"), "sire_id": sire_id}
		mapa = {
			# 'aceptar' y 'reemplazar' comparten el mismo nombre de archivo con
			# report_03='02', porque 'aceptar' NO envia el TXT/ZIP a SUNAT (es
			# solo un POST directo al endpoint aceptapropuesta). Cuando el
			# usuario descarga el archivo manualmente para subirlo al portal
			# SUNAT en el dialogo "Reemplazo de la Propuesta del RCE", el
			# nombre debe llevar '02' o SUNAT lo rechaza con "Error en Posicion
			# 28, Codigo RCE Remplazar Propuesta 02".
			"aceptar":        {"report_03": "02", "operacion": "1", "contenido": "1", "moneda": "1", "sire": "2"},
			"reemplazar":     {"report_03": "02", "operacion": "1", "contenido": "1", "moneda": "1", "sire": "2"},
			"posterior":      {"report_03": "03", "operacion": "1", "contenido": "1", "moneda": "1", "sire": "201"},
			"poseriorperiodo":{"report_03": "04", "operacion": "1", "contenido": "1", "moneda": "1", "sire": "201"},
		}
		name_dict.update(mapa.get(self.tipo_informacion, {}))
		if not tiene_datos:
			name_dict["contenido"] = "0"
		fill_name_data(name_dict)
		return name % name_dict

	def generar_zip(self):
		if not self.sire_txt_01_binary:
			return
		buf = BytesIO()
		zf = zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, False)
		zf.writestr(self.sire_txt_01_filename, base64.b64decode(self.sire_txt_01_binary))
		for z in zf.filelist:
			z.create_system = 0
		zf.close()
		self.datas_zip = base64.b64encode(buf.getvalue())
		self.datas_zip_fname = "%s.zip" % self.sire_txt_01_filename[:-4]

	def update_report(self):
		res = super().update_report()
		start = datetime.date(self.year, int(self.month), 1)
		end = get_last_day(start)
		doc_ids = self.documento_compra_ids.ids
		dominio = [
			("company_id", "=", self.company_id.id),
			("company_id.partner_id.country_id", "=", self.env.ref("base.pe").id),
			("move_type", "in", ["in_invoice", "in_refund"]),
			("state", "=", "posted"),
			("date", ">=", str(start)),
			("date", "<=", str(end)),
		]
		if doc_ids:
			dominio.append(("l10n_latam_document_type_id", "in", doc_ids))
		self.bill_ids = self.env["account.move"].search(dominio, order="date asc, ref asc")
		return res

	def generate_report(self):
		res = super().generate_report()
		lines_01 = []
		peru = self.env.ref("base.pe")
		contador = 1
		fecha_inicio = datetime.date(self.year, int(self.month), 1)
		for move in self.bill_ids.sudo():
			m = move.sire_8_1_fields(contador, fecha_inicio)
			contador += 1
			if m:
				try:
					if move.partner_id.country_id == peru:
						lines_01.append("|".join(m))
				except Exception:
					raise UserError("Error procesando factura %s: datos no validos para SUNAT." % move.ref)

		name_01 = self.get_default_filename(sire_id="080400", tiene_datos=bool(lines_01))
		lines_01.append("")
		txt_01 = "\r\n".join(lines_01)
		dict_w = {}

		if txt_01:
			hdrs = [
				"RUC", "Apellidos y nombres o razon social del generador",
				"Periodo", "CAR - SUNAT (No llenar)", "Fecha de emision",
				"Fecha de Vencimiento o Fecha de Pago",
				"Tipo de Comprobante de Pago o Documento",
				"Serie del comprobante de pago o documento",
				"Anio de emision de la DUA o DSI",
				"Numero del comprobante de pago o numero inicial",
				"Numero final", "Tipo de Documento de Identidad del proveedor",
				"Numero de RUC del proveedor o numero de documento de Identidad",
				"Apellidos y nombres o razon social del proveedor",
				"Base imponible adquisiciones gravadas DG", "Monto IGV/IPM DG",
				"Base imponible adquisiciones gravadas DGNG", "Monto IGV/IPM DGNG",
				"Base imponible adquisiciones gravadas DNG", "Monto IGV/IPM DNG",
				"Valor de las adquisiciones no gravadas",
				"Monto del Impuesto Selectivo al Consumo",
				"Impuesto al Consumo de las Bolsas de Plastico",
				"Otros conceptos, tributos y cargos",
				"Importe total de las adquisiciones",
				"Codigo de la Moneda", "Tipo de cambio",
				"Fecha emision comprobante que se modifica",
				"Tipo comprobante que se modifica",
				"Serie comprobante que se modifica",
				"Codigo dependencia Aduanera (DUA/DSI)",
				"Numero comprobante que se modifica",
				"Tipo de Bien/Servicio", "ID Proyecto Operadores",
				"PorcPart", "IBM", "CAR orig", "",
			]
			xlsx_b64 = self._generate_xlsx_base64_bytes(txt_01, name_01[4:], headers=hdrs)
			dict_w.update({
				"sire_txt_01": txt_01,
				"sire_txt_01_binary": base64.b64encode(txt_01.encode()),
				"sire_txt_01_filename": name_01 + ".txt",
				"sire_xls_01_binary": xlsx_b64.encode(),
				"sire_xls_01_filename": name_01 + ".xlsx",
			})
		else:
			dict_w.update({"sire_txt_01": False, "sire_txt_01_binary": False,
                           "sire_txt_01_filename": False, "sire_xls_01_binary": False,
                           "sire_xls_01_filename": False})

		dict_w["date_generated"] = str(fields.Datetime.now())
		res = self.write(dict_w)
		self.generar_zip()
		return res
