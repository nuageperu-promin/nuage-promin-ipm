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

class PLEReport06(models.Model) :
	_name = 'ple.report.06'
	_description = 'PLE 06 - Estructura del Libro Mayor'
	_inherit = 'ple.report.templ'
	
	year = fields.Integer(required=True)
	month = fields.Selection(selection_add=[], required=True)
	
	line_ids = fields.Many2many(comodel_name='account.move.line', string='Movimientos', readonly=True)
	
	ple_txt_01 = fields.Text(string='Contenido del TXT 6.1')
	ple_txt_01_binary = fields.Binary(string='TXT 6.1')
	ple_txt_01_filename = fields.Char(string='Nombre del TXT 6.1')
	ple_xls_01_binary = fields.Binary(string='Excel 6.1')
	ple_xls_01_filename = fields.Char(string='Nombre del Excel 6.1')
	
	# No usamos sql_constraints de unicidad: el usuario debe poder
	# regenerar el mismo período sin restricciones de BD.
	# La unicidad se controla desde la vista (domain en la acción de ventana).

	@api.model_create_multi
	def create(self, vals_list):
		"""
		Upsert por (year, month, company_id): si ya existe el período, actualiza
		en lugar de crear un duplicado. Permite regenerar el mismo mes sin restricciones.
		"""
		nuevos = []
		registros = self.browse()
		for vals in vals_list:
			existente = self.search([
				('year', '=', vals.get('year')),
				('month', '=', str(vals.get('month'))),
				('company_id', '=', vals.get('company_id', self.env.company.id)),
			], limit=1)
			if existente:
				existente.write(vals)
				registros |= existente
			else:
				nuevos.append(vals)
		if nuevos:
			registros |= super().create(nuevos)
		return registros

	def get_default_filename(self, ple_id='060100', tiene_datos=False) :
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
	
	def update_report(self) :
		res = super().update_report()
		start = datetime.date(self.year, int(self.month), 1)
		end = get_last_day(start)

		domain = [
			('company_id', '=', self.company_id.id),
			('move_id.state', '=', 'posted'),
			# display_type en Odoo 19: excluir section/subsection/note (sin cuenta ni montos)
			('display_type', 'not in', ['line_section', 'line_subsection', 'line_note']),
			('date', '>=', str(start)),
			('date', '<=', str(end)),
		]
		lines = self.env['account.move.line'].search(domain, order='date asc, move_id asc, id asc')
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
		lines = self.line_ids.sudo()

		fecha_inicio = datetime.date(self.year, int(self.month), 1)

		# Validación previa: facturas de proveedor deben tener 'ref' informado
		# (campo 12 del 6.1 es obligatorio SUNAT). Consistente con Libro Diario.
		self._validar_facturas_proveedor_con_ref(lines)

		# FIX #1 y #2: Pre-construir mapa de CUO y correlativos.
		# Usa el mismo helper que ple_report_05 → CUO y correlativo son idénticos
		# para el mismo asiento en ambos libros (Diario y Mayor).
		mapa_correlativos = self._construir_mapa_correlativos(lines)

		# Pre-construir cache de moves ya declarados para estado '8'/'9'.
		moves_anteriores_ids = [
			l.move_id.id for l in lines if l.move_id.date < fecha_inicio
		]
		moves_ya_declarados = self._construir_cache_moves_declarados(moves_anteriores_ids)

		for move in lines:
			m_01 = []
			try:
				factura = move.move_id

				# FIX #1: CUO = ID del asiento (no ID de la línea)
				# FIX #2: Correlativo desde mapa (no move.id de la línea)
				cuo, correlativo_asiento = mapa_correlativos[factura.id]

				sunat_partner_code = factura.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code if factura.partner_id else ''
				sunat_partner_vat = factura.partner_id.vat if factura.partner_id else ''

				date = move.date

				# C01-C04
				m_01.extend([
					date.strftime('%Y%m00'),    # C01 Período
					cuo,                         # C02 CUO — ID del asiento
					correlativo_asiento,         # C03 Correlativo — M + move.id
					# FIX #3: código de cuenta SIN .rstrip('0')
					# '401000'.rstrip('0') → '401', lo cual es incorrecto y rechazado por SUNAT
					move.account_id.code,
				])
				# C05-C06
				m_01.extend(['', ''])
				# C07 Tipo de moneda
				m_01.append(move.currency_id.name or 'PEN')
				# C08-C09 Tipo y número doc del emisor
				if sunat_partner_code and sunat_partner_vat:
					m_01.extend([sunat_partner_code, sunat_partner_vat])
				else:
					m_01.extend(['', ''])
				# C10 Tipo de comprobante
				# C10 es OBLIGATORIO (long. 2, Estructura 5.1/6.1): para los
				# asientos sin comprobante corresponde '00 — Otros' de la
				# Tabla 10 del Anexo 3. Dejarlo vacío (el «fix» anterior)
				# incumplía la obligatoriedad del campo.
				m_01.append(factura.pe_invoice_code or '00')
				# C11-C12 Serie y número del comprobante
				# Consume campos centralizados solse_pe_serie / solse_pe_numero.
				# Ventas → l10n_latam_document_number, Compras → ref,
				# Entries/receipts → name del asiento como fallback.
				if factura.move_type in ('out_invoice', 'out_refund',
										  'in_invoice', 'in_refund'):
					serie = factura.solse_pe_serie or ''
					numero = factura.solse_pe_numero or ''
					if factura.move_type in ('in_invoice', 'in_refund') and not numero:
						_logging.warning(
							"PLE 6.1: factura de proveedor %s (ID %s) sin serie/número "
							"en campo Referencia. Se incluye con campo 12 vacío "
							"(modo tolerante activo).",
							factura.name, factura.id,
						)
					m_01.extend([serie, numero])
				else:
					m_01.extend(['', factura.name or str(factura.id)])
				# C13-C14 Fecha contable y vencimiento
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
				# C15 Fecha de la operación/emisión (obligatorio)
				# FIX #5: para facturas usar invoice_date (fecha del comprobante),
				# no date (fecha contable del asiento). Son distintas cuando el
				# contador asienta la factura en fecha diferente a su emisión.
				if factura.move_type in ['entry', 'out_receipt', 'in_receipt']:
					m_01.append(date.strftime('%d/%m/%Y'))
				else:
					m_01.append(factura.invoice_date.strftime('%d/%m/%Y'))
				# C16-C17 Glosa
				# FIX #6: usar glosa del asiento (move_id.glosa de accountant) como
				# primera opción. Si no está disponible, usar ref o name del asiento.
				# NO usar move.name (nombre de la línea, que es el concepto del producto).
				glosa_raw = (
					getattr(factura, 'glosa', None)
					or factura.ref
					or factura.name
					or 'Movimiento'
				)
				glosa = self._formato_glosa(glosa_raw, 200)
				m_01.extend([glosa, ''])
				# C18-C20 Debe / Haber / Dato estructurado
				dato_est = self._dato_estructurado(factura)
				m_01.extend([format(move.debit, '.2f'), format(move.credit, '.2f'), dato_est])
				# C21 Estado de la operación
				# FIX: usar move.date (fecha contable) para determinar período
				estado = self._obtener_estado_ple(factura, fecha_inicio, moves_ya_declarados)
				m_01.extend([estado, ''])

			except Exception as e:
				_logging.error("Error generando línea Libro Mayor para move.line %s: %s", move.id, e)
				m_01 = []

			if m_01:
				lines_to_write_01.append('|'.join(m_01))

		name_01 = self.get_default_filename(ple_id='060100', tiene_datos=bool(lines_to_write_01))
		lines_to_write_01.append('')
		lines_to_write_01 = self._consolidar_llaves_txt(lines_to_write_01)
		txt_string_01 = '\r\n'.join(lines_to_write_01)
		dict_to_write = {}
		if txt_string_01:
			xlsx_01 = self._generate_xlsx_base64_bytes(txt_string_01, name_01[2:], headers=[
				'Periodo',
				'Código Único de la Operación (CUO)',
				'Número correlativo del asiento contable',
				'Código de la cuenta contable desagregado al nivel máximo de dígitos',
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
			])
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

		dict_to_write['date_generated'] = str(fields.Datetime.now())
		self.write(dict_to_write)
		return res

