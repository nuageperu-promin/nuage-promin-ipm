# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from .ple_report import get_last_day
from .ple_report import fill_name_data
from .ple_report import number_to_ascii_chr

import base64
import datetime
from io import StringIO, BytesIO
import pandas
import logging
_logging = logging.getLogger(__name__)

class PLEReport05(models.Model) :
	_name = 'ple.report.05'
	_description = 'PLE 05 - Estructura del Libro Diario'
	_inherit = 'ple.report.templ'
	
	year = fields.Integer(required=True)
	month = fields.Selection(selection_add=[], required=True)
	eximido_presentar_caja_bancos = fields.Boolean(
		"Eximido de presentar Libro Caja y Bancos",
		default=lambda self: self.env.company.ple_eximido_caja_bancos,
	)
	
	line_ids = fields.Many2many(comodel_name='account.move.line', string='Movimientos', readonly=True)
	
	ple_txt_01 = fields.Text(string='Contenido del TXT 5.1')
	ple_txt_01_binary = fields.Binary(string='TXT 5.1', readonly=True)
	ple_txt_01_filename = fields.Char(string='Nombre del TXT 5.1')
	ple_xls_01_binary = fields.Binary(string='Excel 5.1', readonly=True)
	ple_xls_01_filename = fields.Char(string='Nombre del Excel 5.1')
	ple_txt_02 = fields.Text(string='Contenido del TXT 5.2')
	ple_txt_02_binary = fields.Binary(string='TXT 5.2', readonly=True)
	ple_txt_02_filename = fields.Char(string='Nombre del TXT 5.2')
	ple_xls_02_binary = fields.Binary(string='Excel 5.2', readonly=True)
	ple_xls_02_filename = fields.Char(string='Nombre del Excel 5.2')
	ple_txt_03 = fields.Text(string='Contenido del TXT 5.3')
	ple_txt_03_binary = fields.Binary(string='TXT 5.3', readonly=True)
	ple_txt_03_filename = fields.Char(string='Nombre del TXT 5.3')
	ple_xls_03_binary = fields.Binary(string='Excel 5.3', readonly=True)
	ple_xls_03_filename = fields.Char(string='Nombre del Excel 5.3')
	ple_txt_04 = fields.Text(string='Contenido del TXT 5.4')
	ple_txt_04_binary = fields.Binary(string='TXT 5.4', readonly=True)
	ple_txt_04_filename = fields.Char(string='Nombre del TXT 5.4')
	ple_xls_04_binary = fields.Binary(string='Excel 5.4', readonly=True)
	ple_xls_04_filename = fields.Char(string='Nombre del Excel 5.4')
	
	def get_default_filename(self, ple_id='050100', tiene_datos=False) :
		name = super().get_default_filename()
		name_dict = {
			'month': str(self.month).rjust(2,'0'),
			'ple_id': ple_id,
		}
		if not tiene_datos :
			name_dict.update({
				'contenido': '0',
			})
		fill_name_data(name_dict)
		name = name % name_dict
		return name
	
	def update_report(self):
		res = super().update_report()
		start = datetime.date(self.year, int(self.month), 1)
		end = get_last_day(start)

		domain = [
			('company_id', '=', self.company_id.id),
			('move_id.state', '=', 'posted'),
			# display_type en Odoo 19: product, cogs, tax, payment_term, rounding,
			# line_section, line_subsection, line_note.
			# Excluir section/subsection/note (sin cuenta contable ni montos).
			('display_type', 'not in', ['line_section', 'line_subsection', 'line_note']),
			('date', '>=', str(start)),
			('date', '<=', str(end)),
		]

		# El Libro Diario lleva SIEMPRE los asientos completos: excluir las
		# cuentas de efectivo y bancos (como se hacía aquí para los NO
		# eximidos) dejaba cada asiento descuadrado — el PDF del formato
		# físico mostraba debe ≠ haber y el propio PLE lo rechaza, porque
		# la estructura 5.1 no contempla asientos parciales.
		#
		# La exención de la R.S. 234-2006 (art. 13) opera en la dirección
		# contraria: quien lleva el detalle del efectivo en el Diario puede
		# eximirse de llevar el Libro Caja y Bancos (1.1). El check
		# `eximido_presentar_caja_bancos` NO decide qué líneas entran; solo
		# controla —como ya lo hacía bien— si las líneas de bancos llevan
		# los campos extendidos C22-C30 (entidad financiera, cuenta, medio
		# de pago) que SUNAT exige justamente a los eximidos.
		lines = self.env['account.move.line'].search(
			domain, order='date asc, move_id asc, id asc')

		self.line_ids = lines
		return res

	def generate_report(self) :
		# Los campos company-dependent de Odoo 19 (`account.account.code`
		# entre ellos) se leen segun la compañia ACTIVA del entorno, no la
		# del registro: generar el libro parado en otra compañia devolvia
		# `code = False` y el TXT explotaba al unir los campos. Todo el
		# metodo trabaja anclado a la compañia del propio libro.
		self = self.with_company(self.company_id)
		res = super().generate_report()
		lines_to_write_01 = []
		lines_to_write_02 = []
		lines_to_write_03 = []
		lines_to_write_04 = []  # Plan contable del libro simplificado (5.4)
		lines = self.line_ids.sudo()

		fecha_inicio = datetime.date(self.year, int(self.month), 1)

		# Validación previa: facturas de proveedor deben tener 'ref' informado
		# (campo 12 del 5.1 es obligatorio SUNAT). Si la empresa tiene activa
		# la validación estricta, esto lanza UserError y detiene la generación.
		self._validar_facturas_proveedor_con_ref(lines)

		mapa_correlativos = self._construir_mapa_correlativos(lines)

		# Pre-construir cache de moves ya declarados para estado '8'/'9'.
		moves_anteriores_ids = [
			l.move_id.id for l in lines if l.move_id.date < fecha_inicio
		]
		moves_ya_declarados = self._construir_cache_moves_declarados(moves_anteriores_ids)

		# FIX N+1: Pre-cargar mapa de pagos para el bloque eximido banco.
		# Una sola query para todos los pagos del período, indexados por move_id.
		mapa_pagos = {}
		if self.eximido_presentar_caja_bancos:
			move_ids = list({l.move_id.id for l in lines})
			pagos = self.env['account.payment'].search([('move_id', 'in', move_ids)])
			for pago in pagos:
				mapa_pagos[pago.move_id.id] = pago
			# Para asientos manuales de banco (sin account.payment directo),
			# buscar pago vía conciliación — solo en líneas de cuentas bancarias.
			lineas_banco = [l for l in lines if l.account_id.is_bank_account and l.move_id.id not in mapa_pagos]
			for linea in lineas_banco:
				pago_match = (
					linea.matched_debit_ids.mapped('debit_move_id.payment_id')[:1]
					or linea.matched_credit_ids.mapped('credit_move_id.payment_id')[:1]
				)
				if pago_match:
					mapa_pagos[linea.move_id.id] = pago_match[0]

		# Estructuras 5.3 y 5.4 — Plan Contable
		# 5.3 acompaña al Libro Diario regular (5.1) — siempre se genera cuando aplica
		# 5.4 acompaña al Libro Diario Simplificado (5.2) — solo cuando ple_presentar_5_2=True
		# Ambas tienen estructura idéntica (8 campos), período AAAAMMDD.
		# SUNAT: obligatorio en enero de cada año o primera generación del libro.
		es_enero = int(self.month) == 1
		es_primera_vez = not self.env['ple.report.05'].search([
			('company_id', '=', self.company_id.id),
			('state', '=', 'declarado'),
			('id', '!=', self.id),
		], limit=1)

		if es_enero or es_primera_vez:
			cuentas = self.env['account.account'].search(
				[('company_ids', 'child_of', self.company_id.id)],
				order='code',
			)
			periodo_plan = fecha_inicio.strftime('%Y%m%d')  # AAAAMMDD — obligatorio
			for cuenta in cuentas:
				try:
					linea_plan = [
						periodo_plan,
						cuenta.code or '',
						self._formato_glosa(cuenta.name, 100),
						'01',                               # Código plan: 01=PCGE
						'PLAN CONTABLE GENERAL EMPRESARIAL',
						'',                                 # Cuenta corporativa (vacío)
						'',                                 # Desc corporativa (vacío)
						'1',                                # Estado
					]
					lines_to_write_03.append('|'.join(linea_plan))
					# 5.4 tiene exactamente la misma estructura que 5.3
					if self.company_id.ple_presentar_5_2:
						lines_to_write_04.append('|'.join(linea_plan))
				except Exception:
					# A-11/MEJ-11: antes era pass — la cuenta desaparecía del
					# plan declarado (5.3/5.4) sin rastro, y SUNAT rechazaba
					# el 5.1 apuntando al lugar equivocado.
					_logging.exception(
						'PLE 5.3/5.4: la cuenta %s «%s» (id %s) falló al '
						'formatearse y NO entra al plan de cuentas declarado. '
						'El 5.1 que la referencie será rechazado por SUNAT.',
						cuenta.code, cuenta.name, cuenta.id)

		# FIX: Ordenar por (fecha_asiento, move_id, id_linea) para consistencia
		lines_ordenadas = sorted(lines, key=lambda l: (l.move_id.date, l.move_id.id, l.id))

		for move in lines_ordenadas:
			m_01 = []
			m_02 = []
			try:
				factura = move.move_id

				# FIX #1: CUO = ID del asiento (no el número del comprobante)
				# FIX #2: Correlativo desde el mapa pre-construido (no contador frágil)
				cuo, correlativo_asiento = mapa_correlativos[factura.id]

				sunat_partner_code = factura.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code if factura.partner_id else ''
				sunat_partner_vat = factura.partner_id.vat if factura.partner_id else ''

				move_name = move.name or ''
				move_name = self._formato_glosa(move_name, 200) or 'Movimiento'

				date = move.date
				nro_cuenta_contable = move.account_id.code or ''

				# C01-C04
				m_01.extend([
					date.strftime('%Y%m00'),   # C01 Período AAAAMM00
					cuo,                        # C02 CUO — ID del asiento
					correlativo_asiento,        # C03 Correlativo — M + move.id
					nro_cuenta_contable,        # C04 Código cuenta contable
				])
				# C05-C06 (Unidad operación / Centro costos — opcionales)
				m_01.extend(['', ''])
				# C07 Tipo de moneda
				m_01.append(move.currency_id.name or 'PEN')
				# C08-C09 Tipo y número doc del emisor
				if sunat_partner_code and sunat_partner_vat:
					m_01.extend([sunat_partner_code, sunat_partner_vat])
				else:
					m_01.extend(['', ''])
				# C10 Tipo de comprobante
				# FIX #3: Para entries/receipts el campo va vacío, NO '00' (código inválido en Tabla 10)
				# C10 es OBLIGATORIO (long. 2, Estructura 5.1/6.1): para los
				# asientos sin comprobante corresponde '00 — Otros' de la
				# Tabla 10 del Anexo 3. Dejarlo vacío (el «fix» anterior)
				# incumplía la obligatoriedad del campo.
				m_01.append(factura.pe_invoice_code or '00')
				# C11-C12 Serie y número del comprobante
				# Se consumen los campos centralizados solse_pe_serie / solse_pe_numero
				# que ya implementan el split '-' para ventas (l10n_latam_document_number),
				# compras (ref del proveedor) y fallback para entries/receipts.
				if factura.move_type in ('out_invoice', 'out_refund',
										  'in_invoice', 'in_refund'):
					serie = factura.solse_pe_serie or ''
					numero = factura.solse_pe_numero or ''
					# Warning si proveedor sin número (validador estricto ya corrió,
					# si estamos acá es porque el usuario eligió modo tolerante).
					if factura.move_type in ('in_invoice', 'in_refund') and not numero:
						_logging.warning(
							"PLE 5.1: factura de proveedor %s (ID %s) sin serie/número "
							"en campo Referencia. Se incluye con campo 12 vacío "
							"(modo tolerante activo).",
							factura.name, factura.id,
						)
					m_01.extend([serie, numero])
				else:
					# Asientos puros (move_type='entry'): serie vacía, nombre del asiento como número
					m_01.extend(['', factura.name or str(factura.id)])
				# C13-C14 Fecha contable y fecha vencimiento
				# FIX #6 (menor pero aprovechamos): campo 14 con fecha vencimiento real
				# C14 es OPCIONAL: se llena solo para comprobantes con
				# vencimiento real. En los asientos puros y pagos,
				# `invoice_date_due` trae la fecha en que se creó el registro
				# (un dato sin sentido tributario) y el campo va vacío.
				fecha_venc = ''
				if factura.move_type in ('out_invoice', 'out_refund',
										 'in_invoice', 'in_refund') \
						and factura.invoice_date_due:
					fecha_venc = factura.invoice_date_due.strftime('%d/%m/%Y')
				m_01.extend([date.strftime('%d/%m/%Y'), fecha_venc])
				# C15 Fecha de operación/emisión (obligatorio)
				if factura.move_type in ['entry', 'out_receipt', 'in_receipt']:
					m_01.append(date.strftime('%d/%m/%Y'))
				else:
					m_01.append(factura.invoice_date.strftime('%d/%m/%Y'))
				# C16-C17 Glosa
				glosa = self._formato_glosa(
					getattr(factura, 'glosa', None) or move_name, 200
				)
				m_01.extend([glosa, ''])
				# C18-C20 Debe / Haber / Dato estructurado
				dato_est = self._dato_estructurado(factura)
				m_01.extend([format(move.debit, '.2f'), format(move.credit, '.2f'), dato_est])
				# C21 Estado de la operación
				# FIX #5: usar factura.date (fecha contable) para comparar el período,
				# porque invoice_date puede ser False en asientos de diario puros.
				# '1' = operación del período actual
				# '8' = período anterior NO anotado en su momento (omisión)
				# '9' = período anterior YA anotado (corrección posterior)
				# Por defecto usamos '8' para períodos anteriores; módulos que lleven
				# control de declaraciones pueden overridear _obtener_estado_ple().
				estado = self._obtener_estado_ple(factura, fecha_inicio, moves_ya_declarados)
				m_01.append(estado)

				# ------------------------------------------------------------------
				# Campos adicionales para "Eximido de Libro Caja y Bancos" (C22+)
				# SUNAT: los campos libres 22-44 del 5.1 se usan para incluir los
				# datos que normalmente irían en el Libro Caja y Bancos.
				#
				# Estrategia de normalización: TODAS las filas del TXT deben tener
				# el mismo número de columnas para que el Excel quede alineado.
				# Usamos 9 campos extra (C22-C30) para banco, y 9 vacíos para el
				# resto (caja y cuentas regulares). El TXT sigue siendo válido porque
				# SUNAT indica "no incluya los palotes si no aplica" — los vacíos
				# entre pipes son aceptados.
				#
				# 1.2 BANCO (is_bank_account): C22-C30 con datos de la operación bancaria
				# 1.1 EFECTIVO (is_cash_account): C22-C30 vacíos
				# Resto (contrapartidas): C22-C30 vacíos
				# ------------------------------------------------------------------
				if self.eximido_presentar_caja_bancos:
					if move.account_id.is_bank_account:
						# --- Estructura 1.2: cuenta corriente/banco ---

						# C22: código entidad financiera (Tabla 3) — obligatorio, 2 dígitos
						# Usar '99' (otros) como fallback si el banco no tiene código configurado.
						codigo_banco = '99'
						if move.journal_id.bank_account_id and move.journal_id.bank_account_id.bank_id:
							codigo_banco = move.journal_id.bank_account_id.bank_id.l10n_pe_bank_code or '99'
						m_01.append(codigo_banco)

						# C23: número de cuenta bancaria — obligatorio
						# Si el diario no tiene cuenta bancaria configurada, usar el nombre del diario.
						nro_cuenta = ''
						if move.journal_id.bank_account_id:
							nro_cuenta = move.journal_id.bank_account_id.acc_number or ''
						if not nro_cuenta:
							nro_cuenta = move.journal_id.name or str(move.journal_id.id)
						m_01.append(nro_cuenta)

						# C24: fecha de la operación — obligatorio
						# Para pagos bancarios la fecha contable es la fecha de la operación
						m_01.append(date.strftime('%d/%m/%Y'))

						# FIX N+1: usar mapa_pagos pre-cargado (una query para todo el período)
						# en lugar de account.payment.search() por cada línea del loop.
						pago = mapa_pagos.get(factura.id)

						# C25: medio de pago (Tabla 1, 3 dígitos) — obligatorio
						# FIX campo obligatorio vacío: si no hay pago registrado (ajuste manual),
						# usar '999' que SUNAT acepta como "otros medios de pago".
						medio_pago = ''
						if pago:
							medio_pago = pago.l10n_pe_payment_method_code or ''
						if not medio_pago:
							medio_pago = '999'  # Otros — valor SUNAT Tabla 1 para casos sin dato
						m_01.append(medio_pago)

						# C26: descripción de la operación bancaria — obligatorio
						# Prioridad: glosa del asiento > ref del comprobante > texto genérico.
						# Evitamos factura.name (ej. BILL/2024/00001) por ser valor interno
						# de Odoo, no descriptivo para SUNAT.
						descripcion = self._formato_glosa(
							getattr(factura, 'glosa', None) or factura.ref, 200
						)
						# Fallback: si glosa vacía usar descripción genérica (campo obligatorio)
						if not descripcion:
							descripcion = 'MOVIMIENTO BANCARIO'
						m_01.append(descripcion)

						# C27: tipo doc del girador/beneficiario — obligatorio
						# '-' cuando no existe o son operaciones múltiples (norma SUNAT Tabla 2)
						tipo_doc_partner = '-'
						if factura.partner_id:
							tipo_doc_partner = (
								factura.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code
								or '-'
							)
						m_01.append(tipo_doc_partner)

						# C28: número doc del girador/beneficiario — obligatorio
						# '-' cuando no existe (norma SUNAT)
						nro_doc_partner = '-'
						if factura.partner_id and factura.partner_id.vat:
							nro_doc_partner = factura.partner_id.vat
						m_01.append(nro_doc_partner)

						# C29: razón social del girador/beneficiario — obligatorio
						# 'varios' para operaciones múltiples (norma SUNAT)
						razon_social = 'varios'
						if factura.partner_id and factura.partner_id.name:
							razon_social = factura.partner_id.name[:200]
						m_01.append(razon_social)

						# C30: número de transacción bancaria — obligatorio
						# FIX campo obligatorio vacío: si no hay transaction_number,
						# usar el nombre del asiento como referencia interna (no ideal
						# pero evita que SUNAT rechace la línea por campo vacío).
						nro_transaccion = move.transaction_number or ''
						if not nro_transaccion and pago:
							nro_transaccion = pago.transaction_number or ''
						if not nro_transaccion:
							# Último fallback: nombre del asiento contable
							nro_transaccion = factura.name or str(factura.id)
						m_01.append(nro_transaccion)

					elif move.account_id.is_cash_account:
						# --- Estructura 1.1: efectivo (101-103) ---
						# C22-C30 vacíos — misma cantidad que banco para alinear Excel
						m_01.extend(['', '', '', '', '', '', '', '', ''])
					else:
						# --- Contrapartidas y cuentas regulares ---
						# (1213000, 4011, 7xxx, etc.) — tampoco llevan datos de caja/banco.
						# C22-C30 vacíos para mantener el mismo número de columnas.
						m_01.extend(['', '', '', '', '', '', '', '', ''])

				# Campo final vacío (separador de línea PLE)
				m_01.append('')

			except Exception as e:
				_logging.error(
					"PLE 5.1: error generando línea para move.line ID %s (asiento %s): %s",
					move.id, move.move_id.name, e,
				)
				m_01 = []

			if m_01:
				lines_to_write_01.append('|'.join(m_01))
			# 5.2 solo se genera si la empresa está configurada para presentarla
			if m_01 and self.company_id.ple_presentar_5_2:
				m_02.extend(m_01)
			if m_02:
				lines_to_write_02.append('|'.join(m_02))

		# --- Generar archivos TXT y XLSX ---
		headers_51 = [
			'Periodo',
			'Código Único de la Operación (CUO)',
			'Número correlativo del asiento contable',
			'Código de la cuenta contable desagregado en subcuentas al nivel máximo de dígitos utilizado',
			'Código de la Unidad de Operación / Unidad de Negocio',
			'Código del Centro de Costos / Utilidades / Inversión',
			'Tipo de Moneda de origen',
			'Tipo de documento de identidad del emisor',
			'Número de documento de identidad del emisor',
			'Tipo de Comprobante de Pago o Documento asociada a la operación',
			'Número de serie del comprobante de pago o documento',
			'Número del comprobante de pago o documento',
			'Fecha contable',
			'Fecha de vencimiento',
			'Fecha de la operación o emisión',
			'Glosa o descripción de la naturaleza de la operación',
			'Glosa referencial',
			'Movimientos del Debe',
			'Movimientos del Haber',
			'Dato estructurado (Código libro + campos RV/RC)',
			'Indica el estado de la operación',
		]
		if self.eximido_presentar_caja_bancos:
			headers_51 += [
				'Código entidad financiera (Tabla 3)',
				'N° cuenta bancaria',
				'Fecha de la operación',
				'Medio de pago (Tabla 1)',
				'Descripción operación bancaria',
				'Tipo doc girador/beneficiario',
				'N° doc girador/beneficiario',
				'Razón social girador/beneficiario',
				'N° transacción bancaria',
			]

		dict_to_write = {}

		name_01 = self.get_default_filename(ple_id='050100', tiene_datos=bool(lines_to_write_01))
		lines_to_write_01.append('')
		lines_to_write_01 = self._consolidar_llaves_txt(lines_to_write_01)
		txt_string_01 = '\r\n'.join(lines_to_write_01)
		if txt_string_01:
			xlsx_01 = self._generate_xlsx_base64_bytes(txt_string_01, name_01[2:], headers=headers_51)
			dict_to_write.update({
				'ple_txt_01': txt_string_01,
				'ple_txt_01_binary': base64.b64encode(self._codificar_txt(txt_string_01)),
				'ple_txt_01_filename': name_01 + '.txt',
				'ple_xls_01_binary': xlsx_01.encode(),
				'ple_xls_01_filename': name_01 + '.xlsx',
			})
		else:
			dict_to_write.update({
				'ple_txt_01': False, 'ple_txt_01_binary': False,
				'ple_txt_01_filename': False, 'ple_xls_01_binary': False,
				'ple_xls_01_filename': False,
			})

		name_02 = self.get_default_filename(ple_id='050200', tiene_datos=bool(lines_to_write_02))
		lines_to_write_02.append('')
		lines_to_write_02 = self._consolidar_llaves_txt(lines_to_write_02)
		txt_string_02 = '\r\n'.join(lines_to_write_02)
		# Solo generar 5.2 si la empresa está configurada para presentarla
		if self.company_id.ple_presentar_5_2 and txt_string_02:
			xlsx_02 = self._generate_xlsx_base64_bytes(txt_string_02, name_02[2:], headers=headers_51)
			dict_to_write.update({
				'ple_txt_02': txt_string_02,
				'ple_txt_02_binary': base64.b64encode(self._codificar_txt(txt_string_02)),
				'ple_txt_02_filename': name_02 + '.txt',
				'ple_xls_02_binary': xlsx_02.encode(),
				'ple_xls_02_filename': name_02 + '.xlsx',
			})
		else:
			dict_to_write.update({
				'ple_txt_02': False, 'ple_txt_02_binary': False,
				'ple_txt_02_filename': False, 'ple_xls_02_binary': False,
				'ple_xls_02_filename': False,
			})

		headers_53 = [
			'Periodo',
			'Código de la Cuenta Contable desagregada al nivel máximo de dígitos',
			'Descripción de la Cuenta Contable',
			'Código del Plan de Cuentas utilizado',
			'Descripción del Plan de Cuentas',
			'Código de la Cuenta Contable Corporativa',
			'Descripción de la Cuenta Contable Corporativa',
			'Indica el estado de la operación',
		]

		name_03 = self.get_default_filename(ple_id='050300', tiene_datos=bool(lines_to_write_03))
		lines_to_write_03.append('')
		txt_string_03 = '\r\n'.join(lines_to_write_03)
		if txt_string_03.strip():
			xlsx_03 = self._generate_xlsx_base64_bytes(txt_string_03, name_03[2:], headers=headers_53)
			dict_to_write.update({
				'ple_txt_03': txt_string_03,
				'ple_txt_03_binary': base64.b64encode(self._codificar_txt(txt_string_03)),
				'ple_txt_03_filename': name_03 + '.txt',
				'ple_xls_03_binary': xlsx_03.encode(),
				'ple_xls_03_filename': name_03 + '.xlsx',
			})
		else:
			dict_to_write.update({
				'ple_txt_03': False, 'ple_txt_03_binary': False,
				'ple_txt_03_filename': False, 'ple_xls_03_binary': False,
				'ple_xls_03_filename': False,
			})

		# 5.4 — Plan Contable del Libro Diario Simplificado
		# Solo se genera cuando la empresa presenta 5.2. Misma estructura que 5.3.
		name_04 = self.get_default_filename(ple_id='050400', tiene_datos=bool(lines_to_write_04))
		lines_to_write_04.append('')
		txt_string_04 = '\r\n'.join(lines_to_write_04)
		if self.company_id.ple_presentar_5_2 and txt_string_04.strip():
			xlsx_04 = self._generate_xlsx_base64_bytes(txt_string_04, name_04[2:], headers=headers_53)
			dict_to_write.update({
				'ple_txt_04': txt_string_04,
				'ple_txt_04_binary': base64.b64encode(self._codificar_txt(txt_string_04)),
				'ple_txt_04_filename': name_04 + '.txt',
				'ple_xls_04_binary': xlsx_04.encode(),
				'ple_xls_04_filename': name_04 + '.xlsx',
			})
		else:
			dict_to_write.update({
				'ple_txt_04': False, 'ple_txt_04_binary': False,
				'ple_txt_04_filename': False, 'ple_xls_04_binary': False,
				'ple_xls_04_filename': False,
			})

		dict_to_write['date_generated'] = str(fields.Datetime.now())
		self.write(dict_to_write)
		return res

