# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round
from base64 import b64decode, b64encode, encodebytes
import datetime
import logging
_logging = logging.getLogger(__name__)

class AccountMove(models.Model) :
	_inherit = 'account.move'

	serie_compra = fields.Char("Serie Compra", compute="_compute_serie_compra", store=True)
	correlativo_compra = fields.Char("Correlativo compra", compute="_compute_serie_compra", store=True)

	def obtener_montos_libro_compras(self):
		"""Distribuye los montos de las líneas de la factura en las columnas
		15-25 del SIRE Registro de Compras Electrónico (Anexo 11):

			15-16  Base imponible / IGV — destinadas a op. gravadas
			17-18  Base imponible / IGV — destinadas a op. gravadas y no gravadas (mixta)
			19-20  Base imponible / IGV — destinadas a op. no gravadas (sin crédito fiscal)
			21     Valor de adquisiciones no gravadas (exoneradas/inafectas)
			22     ISC
			23     ICBPER
			24     Otros tributos
			25     Importe total

		La distribución se gobierna por:
		- impuesto_afect_ids de la afectación (un mapeo por cada account.tax)
		- nro_col_importe_afectacion como fallback cuando la línea no tiene
		  impuestos vinculados a la afectación (caso exonerada/inafecta).

		Las líneas con afectación que tenga aplica_rce=False (uso interno o
		no domiciliadas) se excluyen del libro 8.4.
		"""
		move = self
		json = {f"nro_{n}": 0.0 for n in range(15, 26)}

		estado_comprobante = '1'
		if move.state in ["annul", "cancel"]:
			estado_comprobante = '2'

		# Solo líneas que aplican al RCE 8.4 (excluye 'excluir' y 'no_domiciliado')
		lineas_aplicables = move.invoice_line_ids.filtered(
			lambda l: l.tipo_afectacion_compra and l.tipo_afectacion_compra.aplica_rce
		)

		for line in lineas_aplicables:
			tipo_afectacion = line.tipo_afectacion_compra
			monto_distribuido = False

			# 1) Distribución por impuestos vinculados a la afectación.
			#    Una afectación gravada típicamente define DOS líneas en
			#    impuesto_afect_ids para el mismo IGV: una con toma=base→col 15,
			#    otra con toma=impuesto→col 16. El bucle suma a ambas.
			#    RCE-01: si el impuesto exacto no está mapeado, hereda el
			#    mapeo de su MISMO tipo funcional — el IGV 10,5 % de la
			#    Ley 31556 usa las columnas del IGV 18 sin configurar nada.
			#    RCE-06: los impuestos de percepción NUNCA se distribuyen a
			#    columnas (C15-C24): la percepción no forma parte del RCE
			#    8.4 — su crédito viaja por su propio circuito.
			for impuesto in line.tax_ids:
				if self._es_impuesto_percepcion(impuesto):
					continue
				for imp_afect in self._mapeos_para_impuesto(
						tipo_afectacion, impuesto):
					if not imp_afect.nro_col_importe_impuesto:
						continue
					if imp_afect.toma_para_calculo == "total":
						valor = line.price_total
					elif imp_afect.toma_para_calculo == "impuesto":
						valor = line.price_total - line.price_subtotal
					else:  # 'base' (o cualquier otro)
						valor = line.price_subtotal
					clave = "nro_%s" % imp_afect.nro_col_importe_impuesto
					if clave in json:
						json[clave] += valor
						monto_distribuido = True

			# 2) Fallback: línea sin impuestos vinculados a la afectación.
			#    Caso típico: exonerada/inafecta sin account.tax definido en
			#    la línea, o cuando la configuración usa nro_col_importe_afectacion
			#    a nivel afectación.
			if not monto_distribuido and tipo_afectacion.nro_col_importe_afectacion:
				if tipo_afectacion.toma_para_calculo == "total":
					valor = line.price_total
				elif tipo_afectacion.toma_para_calculo == "impuesto":
					valor = line.price_total - line.price_subtotal
				else:
					valor = line.price_subtotal
				clave = "nro_%s" % tipo_afectacion.nro_col_importe_afectacion
				if clave in json:
					json[clave] += valor

		# Importe total siempre desde el move (no se distribuye por línea)
		json["nro_25"] = abs(move.amount_total_signed)

		# Notas de crédito: invertir signo
		if move.pe_invoice_code in ['07']:
			for k in list(json.keys()):
				json[k] = json[k] * -1.0

		# Comprobante anulado/cancelado: ceros
		if estado_comprobante == '2':
			for k in list(json.keys()):
				json[k] = 0.0

		return json

	def _clave_impuesto_sire(self, impuesto):
		"""Tipo funcional del impuesto para el RCE.

		El código EDI de SUNAT ('1000' IGV, '2000' ISC, '7152' ICBPER…)
		agrupa las tasas de un mismo tributo: el IGV al 18 % y el 10,5 %
		de la Ley 31556 comparten '1000' y por tanto columnas (15/16,
		17/18 o 19/20 según la afectación).
		"""
		return impuesto.l10n_pe_edi_tax_code or ''

	def _es_impuesto_percepcion(self, impuesto):
		"""RCE-06: la percepción no se anota en el 8.4.

		Se detecta por el código EDI ('2001') o por el grupo/nombre del
		impuesto. Nota de alcance: si una MISMA línea mezcla IGV y
		percepción, el componente «impuesto» del mapeo declara el
		agregado de la línea — la percepción debe registrarse por su
		circuito propio (módulo de percepciones), no como impuesto
		adicional de la línea gravada.
		"""
		codigo = (impuesto.l10n_pe_edi_tax_code or '').strip()
		nombre = '%s %s' % (impuesto.tax_group_id.name or '',
							impuesto.name or '')
		return codigo == '2001' or 'PERCEP' in nombre.upper()

	def _mapeos_para_impuesto(self, tipo_afectacion, impuesto):
		"""Mapeos de la afectación aplicables a un impuesto de la línea.

		Exactos primero; sin exacto, los del mismo tipo funcional
		(RCE-01). Deduplicados por columna+toma para no sumar dos veces
		cuando la afectación mapea varias tasas del mismo tributo.
		"""
		exactos = tipo_afectacion.impuesto_afect_ids.filtered(
			lambda m: m.impuesto_id.id == impuesto.id)
		if exactos:
			return exactos
		clave = self._clave_impuesto_sire(impuesto)
		if not clave:
			return exactos
		funcionales = tipo_afectacion.impuesto_afect_ids.filtered(
			lambda m: self._clave_impuesto_sire(m.impuesto_id) == clave)
		vistos = set()
		resultado = funcionales.browse()
		for mapeo in funcionales:
			firma = (mapeo.nro_col_importe_impuesto, mapeo.toma_para_calculo)
			if firma in vistos:
				continue
			vistos.add(firma)
			resultado |= mapeo
		return resultado

	@api.depends('l10n_latam_document_number', 'ref')
	def _compute_serie_compra(self):
		"""Serie y correlativo del comprobante del proveedor.

		Se delega en el helper de `solse_pe_ple_pro`, que es la única
		implementación del parseo. Antes esto hacía `ref.split("-")` y exigía
		exactamente dos partes: un `ref` escrito como
		«F001-00012450 (rectificada)» dejaba serie y correlativo VACÍOS sin
		avisar, y el SIRE se enviaba incompleto. El helper además usa
		`l10n_latam_document_number`, que es donde vive el número desde que la
		captura en compras es manual.
		"""
		for reg in self:
			# El helper vive en `solse_pe_ple_pro`, que ya se declara en el
			# manifiesto. La comprobacion queda como red de seguridad:
			# esto es un campo CALCULADO, y una excepcion aqui no da un
			# aviso —impide CONFIRMAR la factura—. Que falte un modulo no
			# puede dejar al usuario sin poder registrar una compra.
			if not hasattr(reg, '_split_serie_numero'):
				_logging.warning(
					'SIRE compras: falta `solse_pe_ple_pro`, de donde sale '
					'`_split_serie_numero`. La serie y el correlativo de la '
					'factura %s quedan vacíos.', reg.name or reg.id)
				reg.serie_compra = ''
				reg.correlativo_compra = ''
				continue
			serie, numero = reg._split_serie_numero(reg.get_sunat_number())
			reg.serie_compra = serie
			reg.correlativo_compra = numero

	def convertir_nc(self, monto):
		return monto * -1.00

	def _limpiar_correlativo_sire(self, correlativo):
		"""Quita los ceros a la izquierda del correlativo para envío a SUNAT.
		SUNAT espera el correlativo sin padding (ej. '63' en lugar de '00000063').
		Si el correlativo es vacío, devuelve ''. Si es solo ceros, devuelve '0'."""
		if not correlativo:
			return ''
		return correlativo.lstrip('0') or '0'

	def sire_8_1_fields(self, contador, fecha_inicio):
		m_01 = []
		move = self
		try :
			# Fuente única: el helper de ple_pro (l10n_latam_document_number
			# con respaldo en ref para bases sin migrar).
			numero_completo = move.get_sunat_number()
			# `_split_serie_numero` parte solo en el PRIMER guion: un
			# correlativo que contenga otro no rompe la serie.
			sunat_number = list(move._split_serie_numero(numero_completo))
			sunat_code = move.pe_invoice_code or '00'
			# RCE-04: en los formularios físicos (tipo 46) SUNAT exige la
			# serie numérica a 5 posiciones con ceros a la izquierda.
			# Solo se rellena lo que ya es numérico: una serie vacía o
			# alfanumérica se deja tal cual (inventarla sería peor).
			if sunat_code == '46' and (sunat_number[0] or '').isdigit():
				sunat_number[0] = sunat_number[0].zfill(5)
			sunat_partner_code = move.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code
			sunat_partner_vat = move.partner_id.vat
			#sunat_partner_name = move.partner_id.legal_name or move.partner_id.name
			sunat_partner_name = move.partner_id.name
			move_id = move.l10n_latam_document_number
			invoice_date = move.invoice_date
			date_due = move.invoice_date_due
			amount_untaxed = move.amount_untaxed
			amount_tax = move.amount_tax
			amount_total = move.amount_total
			#1-4
			# FIX: Periodo (campo 3) debe ser el periodo tributario del reporte
			# (basado en la fecha contable, no en la fecha de emision de la
			# factura). Una factura emitida en marzo pero anotada en abril
			# debe declararse con periodo 202604, no 202603.
			# fecha_inicio es datetime.date(self.year, self.month, 1) del SIRE.
			m_01.extend([
				self.company_id.vat,
				self.company_id.display_name,
				fecha_inicio.strftime('%Y%m'),
				''
			])
			
			contador = contador + 1
			#5
			m_01.append(invoice_date.strftime('%d/%m/%Y'))
			#6
			if date_due :
				m_01.append(date_due.strftime('%d/%m/%Y'))
			else :
				m_01.append('')
			#7-11
			# FIX: el correlativo (sunat_number[1]) debe ir SIN ceros adelante.
			# move.ref viene tal cual lo escribio el usuario en "Referencia del
			# proveedor". Si lo escribio como "F001-00000063", SUNAT lo rechaza:
			# debe ser "63".
			m_01.extend([
				sunat_code,
				sunat_number[0],
				'',
				self._limpiar_correlativo_sire(sunat_number[1]),
				'',
			])
			#12-14
			if sunat_partner_code and sunat_partner_vat and sunat_partner_name :
				m_01.extend([
					sunat_partner_code,
					sunat_partner_vat,
					sunat_partner_name,
				])
			else :
				m_01.extend(['', '', ''])

			# TC-00 (L4b.1): la búsqueda EXACTA por fecha devolvía 1.000 en
			# fines de semana/feriados sin tasa cargada — importes en soles
			# falsos. _get_conversion_rate usa la última tasa <= fecha,
			# la misma semántica que la contabilidad nativa.
			pen = self.env.ref('base.PEN')
			tipo_cambio = self.env['res.currency']._get_conversion_rate(
				move.currency_id, pen, move.company_id, invoice_date)

			#15-16
			#15 Base imponible de las adquisiciones gravadas que dan derecho a crédito fiscal y/o saldo a favor por exportación, 
			#destinadas exclusivamente a operaciones gravadas y/o de exportación 
			#16 Monto del Impuesto General a las Ventas y/o Impuesto de Promoción Municipal
			#total_sin_impuestos = abs(move.amount_untaxed_signed)
			valores_json_compra = move.obtener_montos_libro_compras()
			valor_campo_15 = format(valores_json_compra['nro_15'], '.2f')
			#total_impuestos = abs(move.amount_tax_signed)
			valor_campo_16 = format(valores_json_compra['nro_16'], '.2f')
			if sunat_code in ['07']:
				valor_campo_15 = (valor_campo_15)
				valor_campo_16 = (valor_campo_16)
			m_01.extend([valor_campo_15, valor_campo_16])
			#17-24
			#17 Base imponible de las adquisiciones gravadas que dan derecho a crédito fiscal y/o saldo a favor por exportación, 
			#destinadas a operaciones gravadas y/o de exportación y a operaciones no gravadas
			#-18 Monto del Impuesto General a las Ventas y/o Impuesto de Promoción Municipal
			#19 Base imponible de las adquisiciones gravadas que no dan derecho a crédito fiscal y/o saldo a favor por exportación, 
			#por no estar destinadas a operaciones gravadas y/o de exportación.
			#-20 Monto del Impuesto General a las Ventas y/o Impuesto de Promoción Municipal
			#21 Valor de las adquisiciones no gravadas
			#22 Monto del Impuesto Selectivo al Consumo en los casos en que el sujeto pueda utilizarlo como deducción.
			#23 Impuesto al Consumo de las Bolsas de Plástico.
			#24 Otros conceptos, tributos y cargos que no formen parte de la base imponible.
			#adquision_no_grabada = move.obtener_total_base_inafecto()

			valor_campo_17 = format(valores_json_compra['nro_17'], '.2f')
			valor_campo_18 = format(valores_json_compra['nro_18'], '.2f')
			valor_campo_19 = format(valores_json_compra['nro_19'], '.2f')
			valor_campo_20 = format(valores_json_compra['nro_20'], '.2f')
			valor_campo_21 = format(valores_json_compra['nro_21'], '.2f')
			valor_campo_22 = format(valores_json_compra['nro_22'], '.2f')
			valor_campo_23 = format(valores_json_compra['nro_23'], '.2f')
			valor_campo_24 = format(valores_json_compra['nro_24'], '.2f')
			if sunat_code in ['07']:
				valor_campo_17 = (valor_campo_17)
				valor_campo_18 = (valor_campo_18)
				valor_campo_19 = (valor_campo_19)
				valor_campo_20 = (valor_campo_20)
				valor_campo_21 = (valor_campo_21)
				valor_campo_22 = (valor_campo_22)
				valor_campo_23 = (valor_campo_23)
				valor_campo_24 = (valor_campo_24)


			m_01.extend([valor_campo_17, valor_campo_18, valor_campo_19, valor_campo_20, valor_campo_21, valor_campo_22, valor_campo_23, valor_campo_24]) #ICBP
			#25
			monto_total = abs(move.amount_total_signed)
			if sunat_code in ['07']:
				monto_total = (monto_total * -1.00)
			m_01.extend([format(monto_total, '.2f')])
			#26-27 Codigo de moneda y tipo de cambio
			# FIX: SUNAT valida (inconsistencia 404 "Campo debe estar vacio")
			# que el campo 27 (Tipo de cambio) vaya VACIO cuando la moneda
			# del comprobante es PEN. Solo se registra el tipo de cambio
			# cuando la moneda es extranjera (se usa para convertir a soles).
			moneda = move.currency_id.name or 'PEN'
			if moneda == 'PEN':
				valor_tipo_cambio = ''
			else:
				valor_tipo_cambio = format(tipo_cambio, '.3f')
			m_01.extend([moneda, valor_tipo_cambio])
			#28-32
			# RCE-05: el doc modificado sale del enlace de Odoo cuando
			# existe, y de los campos MANUALES cuando la factura original
			# no está en el sistema (histórico del sistema anterior, por
			# ejemplo). Antes, una NC/ND sin `reversed_entry_id`/
			# `debit_origin_id` reventaba en `origin.invoice_date.strftime`
			# y el UserError genérico no decía qué faltaba.
			if sunat_code in ['07', '08']:
				m_01.extend(move._sire_doc_modificado(sunat_code))
			else :
				m_01.extend(['', '', '', '', ''])

			tipo_bien_servicio = move.invoice_line_ids.filtered(lambda linea: linea.product_id.product_tmpl_id.tipo_bien_servicio)
			if tipo_bien_servicio:
				tipo_bien_servicio = tipo_bien_servicio[0].product_id.product_tmpl_id.tipo_bien_servicio
			else:
				tipo_bien_servicio = ''

			# 33
			m_01.extend([tipo_bien_servicio])

			m_01.extend(['', '', '', ''])
			
			#m_01.extend(['', '', '', '', '', '', '', '', '', '', codigo, ''])
		except Exception as e:
			_logging.info(":::::::::::::::::::::::::::::::::::::::::::::::::::::")
			_logging.info(e)
			raise UserError('Ocurrio un inconveniente: %s' % str(e))
			m_01 = []

		return m_01

	# ------------------------------------------------ RCE-05 · doc modificado
	sire_fecha_doc_modificado = fields.Date(
		string='SIRE · Fecha doc. modificado',
		help='Solo para NC/ND de compra cuya factura original NO está '
			 'registrada en Odoo: fecha de emisión del comprobante que la '
			 'nota modifica (columna 28 del RCE 8.4). Si la nota está '
			 'enlazada a su factura en Odoo, este campo se ignora.')
	sire_tipo_doc_modificado = fields.Char(
		string='SIRE · Tipo doc. modificado', size=2,
		help='Tipo del comprobante modificado según la tabla 10 de SUNAT '
			 '(01 factura, 03 boleta…). Columna 29 del RCE 8.4.')
	sire_serie_doc_modificado = fields.Char(
		string='SIRE · Serie doc. modificado', size=20,
		help='Serie del comprobante modificado (columna 30).')
	sire_numero_doc_modificado = fields.Char(
		string='SIRE · Número doc. modificado', size=20,
		help='Correlativo del comprobante modificado, sin ceros a la '
			 'izquierda (columna 32).')

	def _sire_doc_modificado(self, sunat_code):
		"""Columnas 28-32 del 8.4: fecha, tipo, serie, DAM/DSI y número.

		Prioridad: el enlace real de Odoo (reversed_entry_id /
		debit_origin_id) y, en su defecto, los campos manuales sire_*.
		Sin ninguno de los dos, columnas vacías con un warning que nombra
		el comprobante — SUNAT observará la nota, pero el libro entero ya
		no muere por ella.
		"""
		self.ensure_one()
		origin = self.reversed_entry_id if sunat_code == '07' \
			else self.debit_origin_id
		if origin and origin.invoice_date:
			numero = origin.get_sunat_number() or ''
			serie, correlativo = self._split_serie_numero(numero)
			return [origin.invoice_date.strftime('%d/%m/%Y'),
					origin.pe_invoice_code or '',
					serie, '',
					self._limpiar_correlativo_sire(correlativo)]
		if self.sire_fecha_doc_modificado and self.sire_numero_doc_modificado:
			return [self.sire_fecha_doc_modificado.strftime('%d/%m/%Y'),
					(self.sire_tipo_doc_modificado or '01').strip(),
					(self.sire_serie_doc_modificado or '').strip(), '',
					self._limpiar_correlativo_sire(
						(self.sire_numero_doc_modificado or '').strip())]
		_logging.warning(
			'SIRE 8.4: la nota %s no tiene documento modificado — ni '
			'enlace en Odoo ni los campos manuales SIRE. Las columnas '
			'28-32 van vacías y SUNAT la observará.', self.name or self.id)
		return ['', '', '', '', '']


class AccountMoveLine(models.Model):
	_inherit = 'account.move.line'

	glosa = fields.Char("Glosa", related="move_id.glosa", store=True)
