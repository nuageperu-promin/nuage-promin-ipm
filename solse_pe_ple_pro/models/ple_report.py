# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from base64 import b64decode, b64encode, encodebytes
import xlsxwriter
import datetime
from io import StringIO, BytesIO
import pandas
import logging
_logging = logging.getLogger(__name__)


DEFAULT_PLE_DATA = '%(month)s%(day)s%(ple_id)s%(report_03)s%(operacion)s%(contenido)s%(moneda)s%(ple)s'
DEFAULT_FORMAT_DICT = {
	'header_format': {
		'bold': True,
		'text_wrap': True,
		'valign': 'top',
		'fg_color': '#D7E4BC',
		'border': 1,
	},
	'text_format': {
		'num_format': '@',
	},
}

def get_last_day(day) :
	first_next = day.replace(day=28) + datetime.timedelta(days=4)
	return (first_next - datetime.timedelta(days=first_next.day))

def fill_name_data(name_dict) :
	common_data = {
		'month': '00',
		'day': '00',
		'report_03': '00',
		'operacion': '1',
		'contenido': '1',
		'moneda': '1',
		'ple': '1',
	}
	common_data_keys = list(common_data)
	for name in common_data_keys :
		if name in name_dict :
			del common_data[name]
	name_dict.update(common_data)

def number_to_ascii_chr(n) :
	try :
		n = int(n)
	except :
		n = 0
	digits = []
	if n > 0 :
		while n :
			digits.append(int(n % 26))
			n //= 26
	else :
		digits.append(0)
	digits = ''.join(chr(numero+65) for numero in digits[::-1])
	return digits

class PLEReportTempl(models.Model) :
	_name = 'ple.report.templ'
	_description = 'Plantilla para Estructuras del PLE'
	
	@api.model
	def _get_default_date(self) :
		date = fields.Date.context_today(self)
		return date
	
	@api.model
	def _get_default_year(self) :
		year = self._get_default_date().year
		return year
	
	@api.model
	def _get_default_month(self) :
		month = str(self._get_default_date().month)
		return month
	
	@api.model
	def _get_default_day(self) :
		day = self._get_default_date().day
		return day

	def convert_field_to_string(self, field):
		if field:
			string_field = str(field)
		else:
			string_field = ''
		return string_field
	
	ple_txt_01 = fields.Text(string='Contenido del TXT')
	ple_txt_01_binary = fields.Binary(string='TXT', readonly=True)
	ple_txt_01_filename = fields.Char(string='Nombre del TXT')
	ple_xls_01_binary = fields.Binary(string='Excel', readonly=True)
	ple_xls_01_filename = fields.Char(string='Nombre del Excel')
	year = fields.Integer(string='Año', default=lambda self: self._get_default_year())
	year_char = fields.Char(string='Año (texto)', compute='_compute_year_char')

	state = fields.Selection([('draft', 'Borrador'), ('declarado', 'Declarado')], default='draft')
		
	month = fields.Selection(
		string='Mes', selection=[
			('1','Enero'),
			('2','Febrero'),
			('3','Marzo'),
			('4','Abril'),
			('5','Mayo'),
			('6','Junio'),
			('7','Julio'),
			('8','Agosto'),
			('9','Setiembre'),
			('10','Octubre'),
			('11','Noviembre'),
			('12','Diciembre'),
		],
		default=lambda self: self._get_default_month(),
	)
	day = fields.Integer(string='Día', default=lambda self: self._get_default_day())
	date = fields.Date(string='Fecha', compute='_compute_date', default=lambda self: self._get_default_date(), store=True, readonly=True)
	date_generated = fields.Datetime(string='Fecha de generación', readonly=True)
	company_id = fields.Many2one(comodel_name='res.company', string='Compañía', required=True, default=lambda self:self.env.user.company_id)

	def declarar_ple(self):
		self.state = 'declarado'

	def regresar_borrador(self):
		self.state = 'draft'
	
	@api.onchange('year', 'month', 'day')
	def _onchange_dates(self) :
		year = self.year
		today = self._get_default_date()
		if self.year <= 0 :
			self.year = today.year
		else :
			month = self.month
			if not self.month :
				self.month = str(today.month)
			else :
				end = get_last_day(datetime.date(year, int(month), 1))
				day = self.day
				if day < 1 :
					self.day = 1
				elif day > end.day :
					self.day = end.day
	
	@api.depends('year', 'month', 'day')
	def _compute_days(self) :
		for record in self :
			record._onchange_dates()
	
	@api.depends('year', 'month', 'day')
	def _compute_date(self) :
		default_date = self._get_default_date()
		for record in self :
			year = record.year
			month = record.month
			day = record.day
			if (year > 0) and month and (day > 0) :
				date = datetime.date(year, int(month), 1)
				record.date = date + datetime.timedelta(days=day-1)
			else :
				record.date = default_date
	
	@api.depends('year')
	def _compute_year_char(self) :
		for record in self :
			record.year_char = str(record.year)
	
	def get_default_filename(self) :
		self.ensure_one()
		name = 'LE' + str(self.company_id.vat) + str(self.year) + DEFAULT_PLE_DATA
		return name
	
	def update_report(self) :
		self.ensure_one()
		res = True
		return res
	
	def generate_report(self) :
		res = self.update_report()
		return res

	# -------------------------------------------------------------------------
	# Helpers PLE compartidos — Libro Diario (05) y Libro Mayor (06)
	# -------------------------------------------------------------------------

	def _construir_mapa_correlativos(self, lineas):
		"""
		Construye {account.move.id: (cuo, correlativo)} para un conjunto de líneas.

		CUO     = str(move.id)  — identificador único del asiento contable.
				  Al usar el ID de BD es único y consistente entre todos los libros
				  que referencien el mismo asiento (Diario ↔ Mayor ↔ Compras ↔ Ventas).

		Correlativo = prefijo + str(move.id).rjust(9, '0')
				  - Longitud máxima 10 chars, dentro del rango 2-10 que exige SUNAT.
				  - Prefijo según SUNAT (campo 3 Libro Diario/Mayor):
					  'A' → asiento de apertura del ejercicio (es_x_apertura de
							solse_pe_accountant).
					  'C' → asiento de cierre del ejercicio (es_x_cierre marcado
							por solse_pe_cierre al ejecutar cierre anual).
					  'M' → asiento de movimiento o ajuste del mes (default).
				  - Ambos campos se leen con getattr para no crear dependencia dura
					con cierre (aunque accountant ya es dependencia obligatoria).

		Al derivar el correlativo del ID del asiento (en lugar de una posición
		secuencial en el query) se garantiza que Libro Diario y Libro Mayor
		asignen el mismo correlativo al mismo asiento, sin importar qué líneas
		filtre cada libro.
		"""
		mapa = {}
		for linea in lineas:
			move = linea.move_id
			if move.id not in mapa:
				cuo = str(move.id)
				es_apertura = getattr(move, 'es_x_apertura', False)
				es_cierre = getattr(move, 'es_x_cierre', False)
				if es_apertura:
					prefijo = 'A'
				elif es_cierre:
					prefijo = 'C'
				else:
					prefijo = 'M'
				correlativo = prefijo + str(move.id).rjust(9, '0')
				mapa[move.id] = (cuo, correlativo)
		return mapa

	def _construir_cache_moves_declarados(self, moves_anteriores_ids):
		"""
		Retorna un set de account.move.id que ya fueron incluidos en algún
		reporte declarado (state='declarado') del mismo modelo y empresa.

		Uso: al generar un PLE, determinar si un asiento de período anterior
		va con estado '8' (omisión, nunca declarado en su momento) o '9'
		(ya fue declarado, ahora se re-anota por corrección).

		Estrategia: buscar reportes declarados del mismo _name para esta empresa,
		cruzar sus line_ids con los moves anteriores usando intersección de sets.
		Una query por reporte declarado, sin N+1 dentro del loop principal.
		Solo se ejecuta si existen moves anteriores al período (caso excepcional).
		"""
		if not moves_anteriores_ids:
			return set()

		reportes_declarados = self.env[self._name].search([
			('company_id', '=', self.company_id.id),
			('state', '=', 'declarado'),
			('id', '!=', self.id),
		])
		if not reportes_declarados:
			return set()

		moves_set = set(moves_anteriores_ids)
		moves_ya_declarados = set()

		for reporte in reportes_declarados:
			# mapped('move_id.id') sobre line_ids: una query por reporte,
			# trae solo IDs sin cargar los records completos.
			move_ids_en_reporte = set(reporte.line_ids.mapped('move_id.id'))
			encontrados = moves_set & move_ids_en_reporte
			moves_ya_declarados |= encontrados
			# Early exit si ya localizamos todos los moves anteriores
			if moves_ya_declarados >= moves_set:
				break

		return moves_ya_declarados

	def _obtener_estado_ple(self, move, fecha_inicio, moves_ya_declarados=None):
		"""
		Determina el campo 21 (estado de la operación) para una línea PLE.

		  '1' -> Operación del período declarado (fecha contable en el período).
		  '8' -> Período anterior, NUNCA declarado (omisión).
		  '9' -> Período anterior, YA declarado (corrección / re-anotación).

		moves_ya_declarados: set pre-construido con _construir_cache_moves_declarados,
		pasado desde generate_report para evitar queries dentro del loop.
		"""
		if move.date >= fecha_inicio:
			return '1'
		if moves_ya_declarados and move.id in moves_ya_declarados:
			return '9'
		return '8'


	def _validar_facturas_proveedor_con_ref(self, lineas):
		"""
		Valida que todas las facturas de proveedor incluidas tengan el campo
		'ref' informado. Campo 12 (número del comprobante) es obligatorio SUNAT
		y llave única; sin él el validador PLE rechaza la línea.

		Comportamiento según flag de empresa:
		  - ple_validacion_estricta_ref = True (default) → UserError listando
			las facturas a corregir. El contador corrige y regenera.
		  - False → permite continuar; solo se loguea warning en el 5.1/6.1 al
			procesar cada línea.

		Retorna True si pasa la validación (o modo tolerante); lanza UserError
		en modo estricto con problema.
		"""
		if not getattr(self.company_id, 'ple_validacion_estricta_ref', True):
			return True

		moves_sin_ref = {}
		for linea in lineas:
			move = linea.move_id
			if move.move_type in ('in_invoice', 'in_refund'):
				if not (move.ref or '').strip():
					moves_sin_ref[move.id] = move

		if not moves_sin_ref:
			return True

		# Ordenar por fecha y nombre para que el mensaje sea legible.
		moves_ordenados = sorted(
			moves_sin_ref.values(),
			key=lambda m: (m.date or datetime.date.min, m.name or ''),
		)
		# Limitar a las primeras 25 para no generar mensajes de pantalla gigantes.
		detalle = '\n'.join(
			f"  • {m.name or '(sin nombre)'} — {m.date or ''} — {m.partner_id.name or ''}"
			for m in moves_ordenados[:25]
		)
		total = len(moves_ordenados)
		mas = f"\n  ... y {total - 25} facturas adicionales" if total > 25 else ''
		raise UserError(_(
			"No se puede generar el libro: hay %(n)s factura(s) de proveedor sin "
			"número de comprobante (campo 'Referencia' vacío).\n\n"
			"SUNAT exige el número del comprobante (campo 12) como obligatorio y "
			"llave única. Corrija las siguientes facturas en Contabilidad → "
			"Facturas de Proveedor → Campo Referencia:\n\n%(detalle)s%(mas)s\n\n"
			"Si excepcionalmente desea generar el libro con estas líneas incompletas, "
			"desactive la opción 'Validación estricta de referencias en facturas de "
			"proveedor' en Configuración → Ajustes → PLE SUNAT.",
		) % {'n': total, 'detalle': detalle, 'mas': mas})

	@api.model
	def _consolidar_llaves_txt(self, lineas):
		"""Una línea por llave SUNAT dentro de cada asiento.

		La estructura del 5.1/6.1 declara llave única la combinación
		(C1 período, C2 CUO, C3 correlativo, C4 cuenta, C12 número): un
		asiento con varias líneas a la MISMA cuenta —una factura de
		comercializadora con tres productos al mismo 6011, por ejemplo—
		repetía la llave y el validador del PLE rechaza el archivo.

		Se consolida sumando debe (C18) y haber (C19) por (C2, C4, C9
		partner, C10, C11, C12) y conservando el resto de campos de la
		primera aparición. La suma del archivo no cambia: solo el número
		de renglones.

		**Por qué la llave de consolidación es MÁS ESTRECHA que la de
		SUNAT** (M-40, y no es un descuido). La llave oficial son cinco
		campos; aquí se agrupa por seis, añadiendo C9, C10 y C11 —el tipo,
		el número de documento de identidad y el nombre del tercero—.

		Se añadieron después de ver el efecto de no tenerlos: con la llave
		oficial a secas, dos líneas del mismo asiento a la misma cuenta
		pero de EMISORES DISTINTOS se fundían en una, y el libro mostraba
		el importe de las dos junto al documento de identidad de una sola.
		El archivo pasaba el validador y decía algo que no era cierto.

		Agrupar de más nunca rompe la unicidad que SUNAT exige —toda llave
		de seis campos es única si la de cinco lo es—, así que la llave
		estrecha es segura por construcción. **No tocar sin este contexto
		delante.**
		"""
		consolidadas = []
		indice = {}
		for linea in lineas:
			campos = linea.split('|')
			if len(campos) < 22:
				consolidadas.append(campos)
				continue
			llave = (campos[1], campos[3], campos[8], campos[9],
					 campos[10], campos[11])
			previa = indice.get(llave)
			if previa is None:
				indice[llave] = campos
				consolidadas.append(campos)
			else:
				previa[17] = '%.2f' % (
					float(previa[17] or 0) + float(campos[17] or 0))
				previa[18] = '%.2f' % (
					float(previa[18] or 0) + float(campos[18] or 0))
		return ['|'.join(campos) for campos in consolidadas]

	# Caracteres tipográficos que Odoo cuela en glosas y referencias y que
	# no existen en latin-1: codificarlos con errors='replace' los volvía
	# «?» en el TXT. Se transliteran a su equivalente simple y el archivo
	# se codifica en cp1252 — el «ANSI» que el validador PLE espera.
	TRANSLITERACION_TXT = {
		'\u2014': '-', '\u2013': '-', '\u2212': '-',		# — – −
		'\u2018': "'", '\u2019': "'",						# ' '
		'\u201c': '"', '\u201d': '"',						# " "
		'\u2026': '...', '\u00a0': ' ',					# … nbsp
	}

	@api.model
	def _codificar_txt(self, texto):
		"""Bytes del TXT PLE: transliterado y en cp1252 (ANSI SUNAT)."""
		for raro, simple in self.TRANSLITERACION_TXT.items():
			texto = texto.replace(raro, simple)
		return texto.encode('cp1252', errors='replace')

	def _formato_glosa(self, texto, max_len=200):
		"""
		Normaliza texto para columnas de glosa del PLE.

		SUNAT (Regla 2.0): los campos de texto no deben contener | / \\
		Se reemplazan por espacio para no perder legibilidad.
		"""
		if not texto:
			return ''
		texto = str(texto)
		for char in ('|', '/', '\\', '\r', '\n'):
			texto = texto.replace(char, ' ')
		return ' '.join(texto.split())[:max_len].strip()

	def _dato_estructurado(self, move):
		"""
		C20 (5.1, 5.2 y 6.1) — Dato Estructurado.

		Decisión de diseño (abril 2026): RETORNAR VACÍO POR DEFECTO.

		Contexto normativo:
		SUNAT contempla dos formatos distintos para este campo según el contribuyente:

		  1. Contribuyentes NO obligados al SIRE/RVIE/RCE (residual, casi nadie):
			 Formato: CODIGO_LIBRO & PERIODO & CUO & CORRELATIVO
			 Ej: 140100&20250300&123&M000000123
			 Códigos: 140100 (Ventas), 080100 (Compras domiciliados),
					  080200 (Compras no domiciliados)

		  2. Contribuyentes obligados al SIRE (caso general en abril 2026):
			 Formato: CAR — Código de Anotación de Registro de 27 dígitos
			 Construcción: RUC emisor(11) + tipo_cp(2) + serie(4) + numero(10)
			 Este CAR NO se construye, SUNAT lo asigna automáticamente al
			 generar el RVIE/RCE en el módulo SIRE. El contribuyente lo recibe
			 en la respuesta del SIRE y debe transcribirlo al Libro Diario.

		Por qué retornamos vacío:
		  a) SUNAT marca el campo 20 como Obligatorio=No, Llave única=No
			 ("Obligatorio solo si el asiento no es consolidado").
		  b) El validador PLE acepta el campo vacío sin observaciones.
		  c) Históricamente SUNAT nunca implementó el cruce real de este campo
			 (ver RS 112-2021 — nueva normativa CAR precisamente porque el
			 formato antiguo no cumplió su objetivo de cruce).
		  d) Generar el formato legacy con '&' sería técnicamente correcto pero
			 no aplica a los clientes actuales (todos obligados al SIRE).
		  e) Generar el CAR requiere propagarlo desde solse_pe_sire_ventas /
			 solse_pe_sire_compra a account.move — work pendiente, ver roadmap.

		Roadmap para completar este campo:
		  1. Agregar campo car_sunat (Char, 27) en account.move — puede ser en
			 solse_pe_accountant o en un módulo de integración SIRE↔PLE.
		  2. En solse_pe_sire_ventas / solse_pe_sire_compra: al procesar la
			 respuesta del RVIE/RCE, vincular el CAR recibido con el account.move
			 correspondiente (match por serie + número + RUC emisor).
		  3. Habilitar aquí: return move.car_sunat if getattr(move, 'car_sunat',
			 None) else ''.

		Mientras tanto: vacío es la decisión más segura, tanto normativa como
		operativamente.
		"""
		return ''

	def _generate_xlsx_base64_bytes(self, txt_string, sheet_name, headers=[], custom_format_dict=dict()):
		xlsx_file = BytesIO()
		xlsx_writer = pandas.ExcelWriter(xlsx_file, engine='xlsxwriter')

		# El formato PLE termina cada línea con '|' (obligatorio SUNAT).
		# pandas lo interpreta como una columna extra vacía al final.
		# La eliminamos antes de construir el DataFrame para que los headers
		# queden alineados con las columnas de datos.
		lineas_limpias = []
		for linea in txt_string.splitlines():
			linea = linea.rstrip('\r')
			if linea.endswith('|'):
				linea = linea[:-1]
			lineas_limpias.append(linea)
		txt_limpio = '\n'.join(lineas_limpias)

		df = pandas.read_csv(StringIO(txt_limpio), sep='|', header=None, dtype=str)
		df.to_excel(xlsx_writer, sheet_name=sheet_name, startrow=1, index=False, header=False)
		
		workbook = xlsx_writer.book
		worksheet = xlsx_writer.sheets[sheet_name]
		format_dict = {k:workbook.add_format(v) for k,v in DEFAULT_FORMAT_DICT.items()}
		
		if custom_format_dict and isinstance(custom_format_dict, dict):
			for custom_format, custom_format_value in custom_format_dict.items():
				format_dict.update({
					custom_format: workbook.add_format(custom_format_value),
				})
		
		len_headers = 0
		if headers and isinstance(headers, list):
			len_headers = len(headers)
		
		for col_num, value in enumerate(df.columns.values):
			col_name = number_to_ascii_chr(col_num)
			header_text = str(value)
			col_format = 'text_format'
			if len_headers:
				if col_num < len_headers:
					csv_file = headers[col_num]
					if not isinstance(csv_file, dict):
						csv_file = {'header_text': str(csv_file)}
					if 'header_text' in csv_file:
						header_text = str(csv_file.get('header_text'))
					if 'col_format' in csv_file:
						col_format = str(csv_file.get('col_format'))
			if col_format not in format_dict:
				col_format = 'text_format'
			col_format = format_dict.get(col_format)
			csv_file = worksheet.write(0, col_num, header_text, format_dict.get('header_format'))
			csv_file = worksheet.set_column(':'.join([col_name, col_name]), max(25, len(header_text) // 2), col_format)
		
		xlsx_writer.close()
		xlsx_file_value = b64encode(xlsx_file.getvalue()).decode()
		return xlsx_file_value

	def generate_physical_xls(self):
		pass
	
	def generate_xlsx_physical_bytes(self, row_values_array, ple_format):
		buffer = BytesIO()
		workbook = xlsxwriter.Workbook(buffer, {
			'in_memory': True,
			'strings_to_formulas': False,
		})

		style_dict = {
			'header_format': workbook.add_format(
			{'font_size': 12, 'align': 'left', 'bold': True}),
			
			'table_header_format': workbook.add_format(
			{'font_size': 10, 'align': 'center', 'bold': True}),

			'bold':  workbook.add_format({
			'bold': True}),

			'bold_center' : workbook.add_format({
			'bold': True,
			'align': 'center',
			'valign': 'vcenter'}),

			'bold_border_cell':  workbook.add_format({
			'bold': True,
			'border': 1}),

			'bold_center_border_cell': workbook.add_format({
			'bold': True,
			'border': 1,
			'align': 'center',
			'valign': 'vcenter',
			'text_wrap': True}),

			'basic_border_cell': workbook.add_format({
			'border': 1})
		}
		sheet = workbook.add_worksheet(ple_format)
		sheet = self.get_physical_content(sheet, ple_format, row_values_array, style_dict)
		
		workbook.close()
		content = buffer.getvalue()
		buffer.close()

		return encodebytes(content)

	def get_physical_content(self, sheet, ple_format, row_values_array, style_dict):
		return sheet
