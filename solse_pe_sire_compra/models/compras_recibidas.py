# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ComprasRecibidas(models.Model):
	_name = "solse.pe.compras.recibidas"
	_description = "Compras Recibidas SIRE"

	ruc = fields.Char("RUC")
	name = fields.Char("Razon Social")
	periodo = fields.Char("Periodo")
	periodo_id = fields.Many2one("sire.report.08", ondelete="cascade")
	car_sunat = fields.Char("Car Sunat")
	fecha_emision = fields.Date("Fecha de emision")
	fecha_vencimiento = fields.Date("Fecha de vencimiento")
	tipo_doc = fields.Char("Tipo Doc")
	serie = fields.Char("Serie")
	anio = fields.Char("Anio")
	nro_correlativo = fields.Char("Nro. Correlativo")
	nro_final = fields.Char("Nro final")
	tipo_doc_identidad = fields.Char("Tipo Doc Identidad")
	nro_doc_identidad = fields.Char("Nro Doc. Identidad")
	apellidos_nombre_rz = fields.Char("Proveedor")
	bi_gravado_dg = fields.Float("BI Gravado DG", digits=(16, 2))
	igv_dg = fields.Float("IGV / IPM DG", digits=(16, 2))
	bi_gravado_dgng = fields.Float("BI Gravado DGNG", digits=(16, 2))
	igv_dgng = fields.Float("IGV / IPM DGNG", digits=(16, 2))
	bi_gravado_dgn = fields.Float("BI Gravado DNG", digits=(16, 2))
	igv_dgn = fields.Float("IGV / IPM DNG", digits=(16, 2))
	valor_ng = fields.Float("Valor Adq. NG", digits=(16, 2))
	isc = fields.Float("ISC", digits=(16, 2))
	icbper = fields.Float("ICBPER", digits=(16, 2))
	otros_cargos = fields.Float("Otros Trib/Cargos", digits=(16, 2))
	total_cp = fields.Float("Total CP", digits=(16, 2))
	moneda = fields.Char("Moneda")
	tipo_cambio = fields.Float("Tipo de Cambio", digits=(16, 3), default=1)
	fecha_doc_modificado = fields.Date("Fecha Emision Doc Modificado")
	tipo_cp_modificado = fields.Char("Tipo CP Modificado")
	serie_cp_modificado = fields.Char("Serie CP Modificado")
	cod_dam_dsi = fields.Char("COD. DAM O DSI")
	nro_cp_modificado = fields.Char("Nro CP Modificado")
	bss_sss = fields.Char("Clasif de Bss y Sss")
	proyecto_operadores = fields.Char("ID Proyecto Operadores")
	porc_part = fields.Char("PorcPart")
	ibm = fields.Char("IBM")
	car_orig = fields.Char("CAR Orig/Ind E o I")
	detraccion = fields.Char("Detraccion")
	tipo_nota = fields.Char("Tipo de Nota")
	est_comp = fields.Char("Est. Comp.")
	incal = fields.Char("Incal")
	clu1 = fields.Char("CLU1")
	factura_enlazada = fields.Many2one("account.move", string="Factura")
	estado_enlace = fields.Selection([
		("ok",         "✔ Coincide"),
		("diferencia", "⚠ Diferencia"),
		("solo_sunat", "✘ Solo en SUNAT"),
	], string="Estado", default="solo_sunat", copy=False)
	observacion = fields.Char("Observación", copy=False)

	# ── Navegacion ───────────────────────────────────────────────────

	def ver_factura(self):
		self.ensure_one()
		if not self.factura_enlazada:
			raise UserError("No hay factura enlazada a este comprobante.")
		return {
			"name": "Factura",
			"type": "ir.actions.act_window",
			"view_mode": "form",
			"views": [(False, "form")],
			"res_model": "account.move",
			"res_id": self.factura_enlazada.id,
			"context": {"create": False, "delete": False},
			"target": "current",
		}

	def ver_detalle(self):
		"""Abre formulario completo del registro de compra SIRE en ventana modal."""
		self.ensure_one()
		return {
			"name": "Detalle: %s-%s" % (self.serie or "", self.nro_correlativo or ""),
			"type": "ir.actions.act_window",
			"view_mode": "form",
			"res_model": "solse.pe.compras.recibidas",
			"res_id": self.id,
			"views": [(False, "form")],
			"target": "new",
		}

	# ── Carga desde CSV ──────────────────────────────────────────────

	def agregar_linea(self, periodo, datos_array):
		_CAMPOS = [
			"ruc", "name", "periodo", "car_sunat", "fecha_emision",
			"fecha_vencimiento", "tipo_doc", "serie", "anio", "nro_correlativo",
			"nro_final", "tipo_doc_identidad", "nro_doc_identidad",
			"apellidos_nombre_rz", "bi_gravado_dg", "igv_dg", "bi_gravado_dgng",
			"igv_dgng", "bi_gravado_dgn", "igv_dgn", "valor_ng", "isc", "icbper",
			"otros_cargos", "total_cp", "moneda", "tipo_cambio",
			"fecha_doc_modificado", "tipo_cp_modificado", "serie_cp_modificado",
			"cod_dam_dsi", "nro_cp_modificado", "bss_sss", "proyecto_operadores",
			"porc_part", "ibm", "car_orig", "detraccion", "tipo_nota",
			"est_comp", "incal", "clu1",
		]
		_FECHAS = {"fecha_emision", "fecha_vencimiento", "fecha_doc_modificado"}
		_FLOATS = {
			"bi_gravado_dg", "igv_dg", "bi_gravado_dgng", "igv_dgng",
			"bi_gravado_dgn", "igv_dgn", "valor_ng", "isc", "icbper",
			"otros_cargos", "total_cp", "tipo_cambio",
		}
		datos_json = {"periodo_id": periodo.id}
		for idx, campo in enumerate(_CAMPOS):
			if idx >= len(datos_array):
				break
			valor = datos_array[idx].strip() if datos_array[idx] else ""
			if campo in _FECHAS:
				if not valor:
					continue
				partes = valor.split("/")
				if len(partes) == 3:
					datos_json[campo] = "%s-%s-%s" % (partes[2], partes[1], partes[0])
			elif campo in _FLOATS:
				try:
					datos_json[campo] = float(valor.replace(",", ".")) if valor else 0.0
				except (ValueError, AttributeError):
					datos_json[campo] = 0.0
			else:
				datos_json[campo] = valor
		self.create(datos_json)

	# ── Enlazar factura existente ────────────────────────────────────

	def enlazar_con_factura(self):
		"""Enlaza la linea de propuesta SUNAT con una factura de Odoo.

        El correlativo de SUNAT viene SIN ceros adelante (ej. '63') mientras
        que en Odoo puede estar guardado con padding (ej. '00000063') segun
        como lo haya escrito el usuario en la referencia del proveedor.
        Se normaliza con lstrip('0') en ambos lados para poder enlazar.
        """
		for rec in self:
			if rec.factura_enlazada:
				rec._validar_diferencia()
				continue
			# Normalizar correlativo SUNAT: sin ceros adelante
			correlativo_norm = (rec.nro_correlativo or '').lstrip('0') or '0'
			# Buscar facturas de la serie y comparar correlativo normalizado
			candidatas = self.env["account.move"].search([
				("company_id", "=", rec.periodo_id.company_id.id),
				("move_type", "in", ["in_invoice", "in_refund"]),
				("state", "=", "posted"),
				("serie_compra", "=", rec.serie),
			])
			factura = self.env["account.move"]
			for f in candidatas:
				if (f.correlativo_compra or '').lstrip('0') == correlativo_norm.lstrip('0'):
					factura = f
					break
			if factura:
				rec.factura_enlazada = factura
				rec._validar_diferencia()
			else:
				rec.write({"estado_enlace": "solo_sunat", "observacion": False})

	def _validar_diferencia(self):
		"""Compara total_cp de SUNAT con amount_total de Odoo y marca estado."""
		self.ensure_one()
		if not self.factura_enlazada:
			return
		total_sunat = round(self.total_cp, 2)
		total_odoo  = round(self.factura_enlazada.amount_total, 2)
		if total_sunat == total_odoo:
			self.write({"estado_enlace": "ok", "observacion": False})
		else:
			diff = total_odoo - total_sunat
			self.write({
				"estado_enlace": "diferencia",
				"observacion": "SUNAT: %.2f | Odoo: %.2f | Dif: %+.2f" % (
					total_sunat, total_odoo, diff),
			})

	# ── Obtener/crear proveedor ──────────────────────────────────────

	def obtener_entidad(self, tipo_documento, nro_doc):
		"""
        Usa consulta_datos_completo de solse_pe_cpe si esta disponible.
        Si no, busca por vat o crea con datos del CSV como fallback.
        """
		if hasattr(self.env["res.partner"], "consulta_datos_completo"):
			try:
				resultado = self.env["res.partner"].consulta_datos_completo(tipo_documento, nro_doc)
				if resultado.get("error"):
					raise UserError(resultado.get("message", "Error al consultar proveedor."))
				if resultado.get("registro"):
					return resultado["registro"]
				if resultado.get("data"):
					return self.crear_entidad(resultado["data"], nro_doc)
			except UserError:
				raise
			except Exception as e:
				_logger.warning("SIRE: consulta_datos_completo fallo (%s), usando fallback", e)

		# Fallback: buscar por vat o crear desde CSV
		proveedor = self.env["res.partner"].search([("vat", "=", nro_doc)], limit=1)
		if proveedor:
			return proveedor
		return self._crear_proveedor_desde_csv(nro_doc)

	def _crear_proveedor_desde_csv(self, nro_doc):
		"""
        Crea partner minimo con datos del CSV.
        - tipo_doc_identidad en (0, 00, vacio) o nro_doc invalido:
          crea contacto solo con nombre, sin VAT ni tipo documento.
        - RUC (11 digitos): company con tipo RUC.
        - Otros: person con tipo segun codigo SUNAT.
        """
		razon_social = (self.apellidos_nombre_rz or "").strip() or nro_doc
		cod_tipo = (self.tipo_doc_identidad or "").strip()
		sin_id = (not nro_doc or nro_doc in ("0", "00", "-")
                  or not cod_tipo or cod_tipo in ("0",))

		pais = self.env["res.country"].search([("code", "=", "PE")], limit=1)

		if sin_id:
			# Contacto solo con nombre — nro o tipo invalido para crear VAT
			vals = {
				"name": razon_social or "Proveedor sin identificar",
				"supplier_rank": 1,
				"customer_rank": 0,
			}
			if pais:
				vals["country_id"] = pais.id
			proveedor = self.env["res.partner"].create(vals)
			_logger.info("SIRE: proveedor creado sin documento: %s", razon_social)
			return proveedor

		es_ruc = len(nro_doc) == 11
		vals = {
			"name": razon_social,
			"vat": nro_doc,
			"company_type": "company" if es_ruc else "person",
			"supplier_rank": 1,
			"customer_rank": 0,
		}
		if es_ruc:
			tipo_id = (
				self.env["l10n_latam.identification.type"].search(
					[("l10n_pe_vat_code", "=", "6")], limit=1
				) or self.env["l10n_latam.identification.type"].search(
					[("name", "ilike", "RUC")], limit=1
				)
			)
		else:
			tipo_id = self.env["l10n_latam.identification.type"].search(
				[("l10n_pe_vat_code", "=", cod_tipo)], limit=1
			)
		if tipo_id:
			vals["l10n_latam_identification_type_id"] = tipo_id.id
		if pais:
			vals["country_id"] = pais.id
		proveedor = self.env["res.partner"].create(vals)
		_logger.info("SIRE: proveedor creado desde CSV: %s (%s)", razon_social, nro_doc)
		return proveedor

	def crear_entidad(self, datos_json, nro_ruc):
		"""
        Crea partner con datos de la API solse_pe_cpe.
        Campos de solse_pe_cpe verificados con hasattr para no romper sin el modulo.
        """
		datos = datos_json.get("data", datos_json)
		vals = {
			"name": datos.get("razonSocial", nro_ruc),
			"vat": nro_ruc,
			"company_type": "company",
			"supplier_rank": 1,
		}
		if datos.get("direccion"):
			vals["street"] = datos["direccion"]
		# Campos exclusivos de solse_pe_cpe — solo si existen en el modelo
		ResPartner = self.env["res.partner"]
		for api_key, odoo_key in [("estado", "state"), ("condicion", "condition")]:
			if datos.get(api_key) and odoo_key in ResPartner._fields:
				vals[odoo_key] = datos[api_key]
		if "is_validate" in ResPartner._fields:
			vals["is_validate"] = True
		for api_key, odoo_key in [
			("buen_contribuyente", "buen_contribuyente"),
			("a_partir_del", "a_partir_del"),
			("resolucion", "resolucion"),
		]:
			if datos.get(api_key) and odoo_key in ResPartner._fields:
				vals[odoo_key] = datos[api_key]
		# Ubigeo via l10n_pe (si el modelo existe)
		if "l10n_pe.res.city.district" in self.env:
			ditrict_obj = self.env["l10n_pe.res.city.district"]
			district = False
			if datos.get("ubigeo"):
				district = ditrict_obj.search([("code", "=", datos["ubigeo"])], limit=1)
			if district:
				vals.update({
					"l10n_pe_district": district.id,
					"city_id": district.city_id.id,
					"state_id": district.city_id.state_id.id,
					"zip": district.code,
					"country_id": district.city_id.state_id.country_id.id,
				})
		tipo_id = self.env["l10n_latam.identification.type"].search(
			[("l10n_pe_vat_code", "=", "6")], limit=1
		)
		if tipo_id:
			vals["l10n_latam_identification_type_id"] = tipo_id.id
		if "doc_number" in ResPartner._fields:
			vals["doc_number"] = nro_ruc
		return self.env["res.partner"].create(vals)

	# ── Lineas de factura con desglose de montos ─────────────────────

	def _impuesto(self, tax_code, price_include=None):
		"""Busca impuesto de compra por codigo SUNAT. Filtra price_include si se indica."""
		dominio = [
			("company_id", "=", self.periodo_id.company_id.id),
			("type_tax_use", "=", "purchase"),
			("l10n_pe_edi_tax_code", "=", tax_code),
			("active", "=", True),
		]
		if price_include is not None:
			dominio.append(("price_include", "=", price_include))
		return self.env["account.tax"].search(dominio, limit=1)

	def obtener_lineas_a_facturar(self):
		"""
        Genera invoice_line_ids con precision milimetrica respecto a los montos SUNAT.

        PROBLEMA de redondeo:
          SUNAT almacena bi e igv redondeados por separado.
          Si usamos price_unit=bi con IGV excluido, Odoo calcula total=round(bi*1.18,2)
          que puede diferir en 0.01 de (bi + igv) por distintos criterios de redondeo.

        SOLUCION:
          Para lineas gravadas usamos price_unit = bi + igv (total exacto de SUNAT)
          con un impuesto IGV price_include=True. Odoo guarda ese total sin recalcular,
          garantizando que amount_total == total_cp de SUNAT.
          Si no existe IGV price_include=True, creamos dos sub-lineas sin tax (base + igv)
          para que la suma sea exacta — el total cuadra aunque no haya impuesto registrado.
        """
		lineas = []

		# Buscar IGV en modo "incluido en precio" (price_include=True)
		igv_inc = self._impuesto("1000", price_include=True)
		# IGV normal (price_include=False) — para fallback y calculo de cuentas
		igv_exc = self._impuesto("1000", price_include=False) or self._impuesto("1000")
		exo = self._impuesto("9997") or self._impuesto("9998")
		isc_imp = self._impuesto("2000")
		icbper_imp = self._impuesto("7152")

		def _linea(desc, monto, imp):
			vals = {
				"name": desc,
				"display_type": "product",
				"quantity": 1,
				"price_unit": round(monto, 2),
			}
			if imp:
				vals["tax_ids"] = [(6, 0, [imp.id])]
			return (0, 0, vals)

		def _linea_gravada(desc, bi, igv_sunat, sufijo=""):
			"""
            Crea linea gravada con total exacto de SUNAT.
            Usa price_include=True si esta disponible, sino divide en bi + igv sin tax.
            """
			total_exacto = round(bi + igv_sunat, 2)
			if igv_inc:
				# total = bi + igv exactos de SUNAT → Odoo no recalcula
				return [_linea(f"Base gravada {sufijo}", total_exacto, igv_inc)]
			else:
				# Fallback: dos lineas sin impuesto para que la suma sea exacta
				# El IGV no queda en cuenta de impuesto — es el mejor esfuerzo sin price_include
				_logger.warning(
					"SIRE: No se encontro IGV price_include=True. "
					"La precision de centavos puede verse afectada para %s-%s.",
					self.serie, self.nro_correlativo,
				)
				return [_linea(f"Base gravada {sufijo}", bi, igv_exc)]

		# Lineas gravadas — con precision exacta bi+igv
		if self.bi_gravado_dg:
			lineas.extend(_linea_gravada("DG", self.bi_gravado_dg, self.igv_dg, "DG"))
		if self.bi_gravado_dgng:
			lineas.extend(_linea_gravada("DGNG", self.bi_gravado_dgng, self.igv_dgng, "DGNG"))
		if self.bi_gravado_dgn:
			lineas.extend(_linea_gravada("DGN", self.bi_gravado_dgn, self.igv_dgn, "DGN"))

		# Lineas no gravadas — montos exactos de SUNAT, sin recalculo de impuesto
		if self.valor_ng:
			lineas.append(_linea("Adquisicion no gravada", self.valor_ng, exo))
		if self.isc:
			lineas.append(_linea("ISC", self.isc, isc_imp))
		if self.icbper:
			lineas.append(_linea("ICBPER", self.icbper, icbper_imp))
		if self.otros_cargos:
			lineas.append(_linea("Otros tributos/cargos", self.otros_cargos, False))

		# Fallback: una linea con el total exacto si no hay desgloses
		if not lineas:
			lineas.append(_linea("Compra segun propuesta SUNAT", self.total_cp, igv_inc or igv_exc or exo))

		return lineas

	# ── Crear factura ────────────────────────────────────────────────

	# ── helpers: proveedor y tipo de documento ───────────────────────────────

	def _sin_documento(self):
		"""True cuando el comprobante no tiene numero de documento de identidad valido."""
		nro = (self.nro_doc_identidad or "").strip()
		return not nro or nro in ("0", "00", "-")

	def _obtener_proveedor(self):
		"""
        Resuelve el res.partner a usar como proveedor:
        - Con nro_doc_identidad valido: consulta SUNAT / busca en BD (flujo normal).
        - Sin documento (vacio, "0", etc.): usa proveedor_base_id del periodo.
          Si no esta configurado, lanza UserError con instrucciones.
        """
		if self._sin_documento():
			proveedor_base = self.periodo_id.proveedor_base_id
			if not proveedor_base:
				raise UserError(
					"El comprobante %s-%s no tiene numero de documento de identidad. "
					"Para crear su factura configure el campo 'Proveedor base (sin documento)' "
					"en el encabezado del Registro de Compras SIRE. "
					"Este contacto se usara para todos los comprobantes sin proveedor identificado "
					"(tipicamente tipo S3 u otros documentos sin RUC/DNI)."
					% (self.serie or "", self.nro_correlativo or "")
				)
			_logger.info(
				"SIRE: comprobante %s-%s sin documento, usando proveedor base: %s",
				self.serie, self.nro_correlativo, proveedor_base.name,
			)
			return proveedor_base

		return self.obtener_entidad(
			self.tipo_doc_identidad or "6",
			(self.nro_doc_identidad or "").strip(),
		)

	def _obtener_tipo_documento(self):
		"""
        Busca el l10n_latam.document.type por el codigo tipo_doc del comprobante.
        - Si lo encuentra: retorna el registro.
        - Si tipo_doc esta vacio: retorna False (sin asignar tipo).
        - Si el codigo no existe en BD: lanza UserError con instrucciones
          para que el usuario pueda crear/activar el tipo de documento.
        """
		codigo = (self.tipo_doc or "").strip()
		if not codigo:
			return False

		# Buscar primero con sub_type purchase, luego sin filtro
		tipo_doc = self.env["l10n_latam.document.type"].search(
			[("code", "=", codigo), ("sub_type", "=", "purchase")], limit=1
		)
		if not tipo_doc:
			tipo_doc = self.env["l10n_latam.document.type"].search(
				[("code", "=", codigo)], limit=1
			)

		if not tipo_doc:
			raise UserError(
				"Tipo de documento no encontrado: codigo '%s'. "
				"Comprobante: %s-%s. "
				"Para solucionarlo vaya a: "
				"  Facturacion - Configuracion - Tipos de Documento Latam. "
				"Cree o active un tipo de documento con codigo '%s' "
				"y sub_tipo 'Compra (purchase)'. "
				"Una vez configurado vuelva a intentar crear la factura."
				% (codigo, self.serie or "", self.nro_correlativo or "", codigo)
			)
		return tipo_doc

	def crear_factura(self):
		self.ensure_one()
		if self.factura_enlazada:
			return

		# 1. Proveedor: por documento o por proveedor_base_id del periodo
		contacto = self._obtener_proveedor()

		# 2. Tipo de documento latam por codigo tipo_doc
		tipo_documento = self._obtener_tipo_documento()

		moneda = self.env["res.currency"].search(
			[("name", "=", (self.moneda or "PEN").strip())], limit=1
		)
		move_type = "in_refund" if (self.tipo_doc or "") == "07" else "in_invoice"

		vals = {
			"move_type": move_type,
			"invoice_date": self.fecha_emision,
			"company_id": self.periodo_id.company_id.id,
			"partner_id": contacto.id,
			"ref": "%s-%s" % (self.serie or "", self.nro_correlativo or ""),
			"invoice_line_ids": self.obtener_lineas_a_facturar(),
		}
		if moneda:
			vals["currency_id"] = moneda.id
		if tipo_documento:
			vals["l10n_latam_document_type_id"] = tipo_documento.id
		# Campos SIRE para enlace posterior
		vals["serie_compra"] = self.serie or ""
		vals["correlativo_compra"] = self.nro_correlativo or ""

		factura = self.env["account.move"].create(vals)
		self.factura_enlazada = factura
		_logger.info(
			"SIRE: factura creada id=%s ref=%s-%s tipo_doc=%s proveedor=%s",
			factura.id, self.serie, self.nro_correlativo,
			tipo_documento.code if tipo_documento else "N/A",
			contacto.name,
		)

	def action_crear_facturas_masivo(self):
		"""Accion masiva — crea facturas para registros seleccionados sin factura."""
		sin_factura = self.filtered(lambda r: not r.factura_enlazada)
		if not sin_factura:
			raise UserError("Todos los comprobantes seleccionados ya tienen factura enlazada.")
		creadas, errores = 0, []
		for rec in sin_factura:
			try:
				rec.crear_factura()
				creadas += 1
			except Exception as e:
				errores.append("%s-%s: %s" % (rec.serie, rec.nro_correlativo, str(e)))
		msg = "%d factura(s) creada(s) en borrador." % creadas
		if errores:
			msg += "\n\nErrores:\n" + "\n".join(errores)
		return {
			"type": "ir.actions.client",
			"tag": "display_notification",
			"params": {
				"title": "Creacion de facturas SIRE",
				"message": msg,
				"type": "warning" if errores else "success",
				"sticky": bool(errores),
			},
		}
