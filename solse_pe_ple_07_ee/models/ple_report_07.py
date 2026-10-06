# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import datetime
import logging

from odoo.addons.solse_pe_ple_pro.models import ple_report

_logging = logging.getLogger(__name__)


def _f2(valor):
	"""Monto SUNAT: hasta 12 enteros y 2 decimales, sin comas de miles.
	Positivo o negativo según la estructura 7.x (no se toma valor absoluto)."""
	return format(valor or 0.0, '.2f')


def _f3(valor):
	"""Tipo de cambio SUNAT: 1 entero y 3 decimales (#.###)."""
	return format(valor or 0.0, '.3f')


def _fecha(valor):
	"""Fecha SUNAT DD/MM/AAAA. Si no existe, 01/01/0001 (valor centinela
	que el PLE rechaza — se valida antes y se lanza UserError, este formato
	nunca debe llegar al TXT)."""
	if not valor:
		return ''
	return valor.strftime('%d/%m/%Y')


class PLEReport07(models.Model):
	_name = 'ple.report.07'
	_description = 'PLE 07 - Registro de Activos Fijos'
	_inherit = 'ple.report.templ'

	year = fields.Integer(required=True)
	# Libro anual: el mes no aplica (MM=00 en el nombre del archivo).
	# Se fija en diciembre solo para satisfacer el required de la plantilla.
	month = fields.Selection(selection_add=[], default='12', required=True)

	asset_ids = fields.Many2many(
		comodel_name='account.asset',
		string='Activos incluidos',
		readonly=True,
	)

	# ── 7.1 ──────────────────────────────────────────────────────────────
	ple_txt_01 = fields.Text(string='Contenido del TXT 7.1')
	ple_txt_01_binary = fields.Binary(string='TXT 7.1', readonly=True)
	ple_txt_01_filename = fields.Char(string='Nombre del TXT 7.1')
	ple_xls_01_binary = fields.Binary(string='Excel 7.1', readonly=True)
	ple_xls_01_filename = fields.Char(string='Nombre del Excel 7.1')

	# ── 7.3 ──────────────────────────────────────────────────────────────
	ple_txt_03 = fields.Text(string='Contenido del TXT 7.3')
	ple_txt_03_binary = fields.Binary(string='TXT 7.3', readonly=True)
	ple_txt_03_filename = fields.Char(string='Nombre del TXT 7.3')
	ple_xls_03_binary = fields.Binary(string='Excel 7.3', readonly=True)
	ple_xls_03_filename = fields.Char(string='Nombre del Excel 7.3')

	# ── 7.4 ──────────────────────────────────────────────────────────────
	ple_txt_04 = fields.Text(string='Contenido del TXT 7.4')
	ple_txt_04_binary = fields.Binary(string='TXT 7.4', readonly=True)
	ple_txt_04_filename = fields.Char(string='Nombre del TXT 7.4')
	ple_xls_04_binary = fields.Binary(string='Excel 7.4', readonly=True)
	ple_xls_04_filename = fields.Char(string='Nombre del Excel 7.4')

	# =====================================================================
	# Nombre de archivo — libro ANUAL: MM=00, DD=00
	# LE + RUC + AAAA + 0000 + 07x100 + 00 + O + I + M + 1
	# =====================================================================
	def get_default_filename(self, ple_id='070100', tiene_datos=False):
		name = super().get_default_filename()
		name_dict = {
			'ple_id': ple_id,
		}
		if not tiene_datos:
			name_dict.update({
				'contenido': '0',
			})
		ple_report.fill_name_data(name_dict)
		name = name % name_dict
		return name

	# =====================================================================
	# Selección de activos
	# =====================================================================
	def _get_dominio_activos(self):
		"""Activos a reportar en el ejercicio:
		  - de la compañía, no modelos, no borradores ni cancelados
		  - con vida en el ejercicio: adquiridos antes del 31/12 y
		    (sin baja, o baja dentro/después del ejercicio)
		  - los hijos (parent_id) NO generan fila propia: se consolidan
		    en el padre como mejora (C17)."""
		inicio = datetime.date(self.year, 1, 1)
		fin = datetime.date(self.year, 12, 31)
		return [
			('company_id', '=', self.company_id.id),
			('state', 'in', ['open', 'paused', 'close']),
			('parent_id', '=', False),
			('acquisition_date', '<=', str(fin)),
			'|',
			('disposal_date', '=', False),
			('disposal_date', '>=', str(inicio)),
		]

	def update_report(self):
		res = super().update_report()
		self.asset_ids = self.env['account.asset'].search(
			self._get_dominio_activos(), order='acquisition_date asc, id asc')
		return res

	# =====================================================================
	# Helpers de datos
	# =====================================================================
	def _obtener_cuo_activo(self, activo, inicio, fin):
		"""CUO/correlativo consistentes con el Libro Diario (ple_pro):
		CUO = str(move.id), correlativo = prefijo + id.rjust(9,'0').

		Prioridad del asiento representativo:
		  1. Asiento de compra (original_move_line_ids) si es del ejercicio.
		  2. Primer asiento de depreciación posteado dentro del ejercicio.
		  3. Asiento de compra aunque sea de ejercicios anteriores.
		  4. Fallback: id del activo (con warning — no cruzará con Diario)."""
		move_compra = activo.original_move_line_ids.mapped('move_id')[:1]
		if move_compra and inicio <= move_compra.date <= fin:
			move = move_compra
		else:
			move = activo.depreciation_move_ids.filtered(
				lambda m: m.state == 'posted' and inicio <= m.date <= fin
			).sorted('date')[:1] or move_compra
		if move:
			move = move[0]
			# Helper compartido de ple_pro: garantiza el mismo CUO/correlativo
			# que asigna el Libro Diario al mismo asiento.
			mapa = self._construir_mapa_correlativos(move.line_ids[:1])
			return mapa[move.id]
		_logging.warning(
			'PLE 7: activo %s (id %s) sin asiento asociado en Diario; '
			'se usa fallback con id del activo.', activo.name, activo.id)
		return (str(activo.id), 'M' + str(activo.id).rjust(9, '0'))

	def _depreciacion_periodo(self, activo, hasta=None, desde=None):
		"""Suma la depreciación registrada contra la cuenta de depreciación
		acumulada del activo (haber - debe) en asientos posteados de
		depreciation_move_ids, del activo y de sus hijos (mejoras).

		No depende de campos de asset sobre el move (depreciation_value,
		asset_remaining_value) que varían entre versiones: lee las líneas."""
		activos = activo | activo.children_ids
		total = 0.0
		for act in activos:
			cuenta_dep = act.account_depreciation_id
			if not cuenta_dep:
				continue
			for move in act.depreciation_move_ids:
				if move.state != 'posted':
					continue
				# B-10 (L9.1): una baja NO es depreciación. En Community el
				# asiento de baja no entra aquí (va en asiento_baja_id, sin
				# asset_id); en Enterprise el nativo sí enlaza la venta o la
				# baja al activo y la marca en asset_move_type. Su cargo a la
				# 39 restaría la acumulada entera de la «depreciación del
				# ejercicio» (C30/C31). Guardia defensiva: sin verificar
				# contra el código EE, que no está en las fuentes.
				if getattr(move, 'asset_move_type', False) in ('sale', 'disposal'):
					continue
				if desde and move.date < desde:
					continue
				if hasta and move.date > hasta:
					continue
				for linea in move.line_ids:
					if linea.account_id == cuenta_dep:
						total += linea.credit - linea.debit
		return total

	def _porcentaje_depreciacion(self, activo):
		"""C28 — %. Prioridad: valor manual > cálculo desde duración.
		method_period en Enterprise es '1' (meses) o '12' (años)."""
		if activo.porcentaje_dep_tributaria:
			return min(activo.porcentaje_dep_tributaria, 100.0)
		try:
			meses = activo.method_number * int(activo.method_period)
			anios = meses / 12.0
			if anios > 0:
				return min(round(100.0 / anios, 2), 100.0)
		except Exception:
			pass
		return 0.0

	def _metodo_tabla20(self, activo):
		"""Tabla 20: 1 línea recta, 2 unidades producidas, 9 otros.
		Odoo Enterprise: linear → 1; degressive / degressive_then_linear → 9."""
		return '1' if activo.method == 'linear' else '9'

	def _limpiar_texto(self, texto, max_len, obligatorio_guion=False):
		"""Texto PLE: sin | / \\ ; recorta a max_len. Si es obligatorio y
		está vacío, SUNAT exige '-'."""
		texto = self._formato_glosa(texto or '', max_len=max_len)
		if not texto and obligatorio_guion:
			return '-'
		return texto

	# =====================================================================
	# Generación
	# =====================================================================
	def generate_report(self):
		# La plantilla (ple_pro) ya llama a update_report() dentro de su
		# generate_report(); la segunda llamada que había aquí repetía la
		# búsqueda de activos sin cambiar nada (L8.1).
		res = super().generate_report()

		inicio = datetime.date(self.year, 1, 1)
		fin = datetime.date(self.year, 12, 31)
		periodo = '%s0000' % self.year

		lineas_71 = []
		lineas_73 = []
		lineas_74 = []
		errores = []

		for activo in self.asset_ids.sudo():
			if not activo.acquisition_date:
				errores.append(_('Activo "%s": sin fecha de adquisición.') % activo.name)
				continue

			cuo, correlativo = self._obtener_cuo_activo(activo, inicio, fin)

			# ── Valores base 7.1 ─────────────────────────────────────────
			adquirido_en_ejercicio = inicio <= activo.acquisition_date <= fin
			baja_en_ejercicio = bool(
				activo.disposal_date and inicio <= activo.disposal_date <= fin)

			# C15 saldo inicial / C16 adquisiciones
			saldo_inicial = 0.0
			adquisiciones = 0.0
			if adquirido_en_ejercicio:
				adquisiciones = activo.original_value
			else:
				saldo_inicial = activo.original_value

			# C17 mejoras: hijos creados en el ejercicio. Hijos anteriores
			# se acumulan al saldo inicial.
			mejoras = 0.0
			for hijo in activo.children_ids:
				fecha_hijo = hijo.acquisition_date or hijo.prorata_date
				if not fecha_hijo:
					continue
				if inicio <= fecha_hijo <= fin:
					mejoras += hijo.original_value
				elif fecha_hijo < inicio:
					saldo_inicial += hijo.original_value

			# C18 retiros/bajas: valor bruto del activo dado de baja
			retiros = 0.0
			if baja_en_ejercicio:
				retiros = activo.original_value + sum(
					h.original_value for h in activo.children_ids
					if (h.acquisition_date or h.prorata_date or fin) <= activo.disposal_date)

			# C29 dep. acumulada al cierre del ejercicio anterior
			dep_acumulada_anterior = self._depreciacion_periodo(
				activo, hasta=inicio - datetime.timedelta(days=1))
			# Saldo importado (activos migrados con depreciación previa)
			dep_acumulada_anterior += getattr(
				activo, 'already_depreciated_amount_import', 0.0) or 0.0

			# C30 / C31 dep. del ejercicio
			dep_ejercicio = self._depreciacion_periodo(
				activo, desde=inicio, hasta=fin)
			dep_ejercicio_normal = 0.0 if baja_en_ejercicio else dep_ejercicio
			dep_ejercicio_bajas = dep_ejercicio if baja_en_ejercicio else 0.0

			cuenta_contable = activo.account_asset_id.code or ''
			if not cuenta_contable:
				errores.append(_('Activo "%s": sin cuenta contable de activo.') % activo.name)
				continue

			fecha_uso = activo.prorata_date or activo.acquisition_date

			# Revaluaciones (C20-C22, C33-C35): acumuladas al 31.12 y solo
			# si ya rigen al cierre del ejercicio (fecha_revaluacion, L9.5).
			rige = not activo.fecha_revaluacion or activo.fecha_revaluacion <= fin
			revaluacion = {campo: (activo[campo] if rige else 0.0) for campo in (
				'valor_revaluacion_voluntaria', 'valor_revaluacion_reorganizacion',
				'valor_otras_revaluaciones', 'dep_revaluacion_voluntaria',
				'dep_revaluacion_reorganizacion', 'dep_otras_revaluaciones')}
			m_71 = [
				periodo,                                              # C01
				cuo,                                                  # C02
				correlativo,                                          # C03
				activo.codigo_catalogo_af or '9',                     # C04 T13
				activo._get_codigo_af(),                              # C05
				# C06/C07: catálogo y código de existencia — solo si el CPE
				# consignó UNSPSC/GTIN. Vacíos en caso contrario.
				(activo.codigo_catalogo_af
					if activo.codigo_existencia_af
					and activo.codigo_catalogo_af in ('1', '3') else ''),  # C06
				activo.codigo_existencia_af or '',                    # C07
				activo.tipo_af or '1',                                # C08 T18
				cuenta_contable,                                      # C09
				activo.estado_af or '9',                              # C10 T19
				self._limpiar_texto(activo.name, 40, True),           # C11
				self._limpiar_texto(activo.marca_af, 20, True),       # C12
				self._limpiar_texto(activo.modelo_af, 20, True),      # C13
				self._limpiar_texto(activo.serie_placa_af, 30, True), # C14
				_f2(saldo_inicial),                                   # C15
				_f2(adquisiciones),                                   # C16
				_f2(mejoras),                                         # C17
				_f2(retiros),                                         # C18
				_f2(0.0),                                             # C19 otros ajustes
				_f2(revaluacion['valor_revaluacion_voluntaria']),             # C20
				_f2(revaluacion['valor_revaluacion_reorganizacion']),         # C21
				_f2(revaluacion['valor_otras_revaluaciones']),                # C22
				_f2(0.0),                                             # C23 ajuste inflación
				_fecha(activo.acquisition_date),                      # C24
				_fecha(fecha_uso),                                    # C25
				self._metodo_tabla20(activo),                         # C26 T20
				self._limpiar_texto(
					activo.num_autorizacion_metodo, 20, True),        # C27
				format(self._porcentaje_depreciacion(activo), '.2f'), # C28
				_f2(dep_acumulada_anterior),                          # C29
				_f2(dep_ejercicio_normal),                            # C30
				_f2(dep_ejercicio_bajas),                             # C31
				_f2(0.0),                                             # C32 dep. otros ajustes
				_f2(revaluacion['dep_revaluacion_voluntaria']),               # C33
				_f2(revaluacion['dep_revaluacion_reorganizacion']),           # C34
				_f2(revaluacion['dep_otras_revaluaciones']),                  # C35
				_f2(0.0),                                             # C36 ajuste inflación dep.
				'1',                                                  # C37 estado operación
				'',                                                   # cierre de línea con |
			]
			lineas_71.append('|'.join(m_71))

			# ── 7.3 — diferencia de cambio (solo adquiridos en M.E.) ─────
			if activo.moneda_adquisicion_id and activo.valor_adquisicion_me:
				valor_me = activo.valor_adquisicion_me
				valor_mn = activo.original_value
				tc_adquisicion = round(valor_mn / valor_me, 3) if valor_me else 0.0
				# TC al 31.12 desde res.currency.rate
				tc_cierre = 0.0
				rate = self.env['res.currency.rate'].search([
					('currency_id', '=', activo.moneda_adquisicion_id.id),
					('company_id', 'in', [self.company_id.id, False]),
					('name', '<=', str(fin)),
				], order='name desc', limit=1)
				if rate and rate.rate:
					# rate de Odoo = unidades de ME por 1 unidad de moneda cía
					tc_cierre = round(1.0 / rate.rate, 3)
				ajuste_dc = round(valor_me * tc_cierre - valor_mn, 2) if tc_cierre else 0.0

				# 7.3: campo 4 solo admite catálogos 3 y 9 (no 1)
				catalogo_73 = activo.codigo_catalogo_af
				if catalogo_73 not in ('3', '9'):
					catalogo_73 = '9'

				m_73 = [
					periodo,                              # C01
					cuo,                                  # C02
					correlativo,                          # C03
					catalogo_73,                          # C04
					activo._get_codigo_af(),              # C05
					_fecha(activo.acquisition_date),      # C06
					_f2(valor_me),                        # C07
					_f3(tc_adquisicion),                  # C08
					_f2(valor_mn),                        # C09
					_f3(tc_cierre),                       # C10
					_f2(ajuste_dc),                       # C11
					_f2(dep_ejercicio_normal),            # C12
					_f2(dep_ejercicio_bajas),             # C13
					_f2(0.0),                             # C14 dep. otros ajustes
					'1',                                  # C15 estado
					'',
				]
				lineas_73.append('|'.join(m_73))

			# ── 7.4 — leasing ────────────────────────────────────────────
			if activo.es_leasing:
				if not (activo.numero_contrato_leasing and activo.fecha_contrato_leasing
						and activo.fecha_inicio_leasing and activo.numero_cuotas_leasing):
					errores.append(_(
						'Activo "%s": marcado como leasing pero faltan datos del '
						'contrato (número, fechas o cuotas).') % activo.name)
					continue
				catalogo_74 = activo.codigo_catalogo_af
				if catalogo_74 not in ('3', '9'):
					catalogo_74 = '9'
				m_74 = [
					periodo,                                          # C01
					cuo,                                              # C02
					correlativo,                                      # C03
					catalogo_74,                                      # C04
					self._limpiar_texto(
						activo.numero_contrato_leasing, 20, True),     # C05
					_fecha(activo.fecha_contrato_leasing),            # C06
					activo._get_codigo_af(),                          # C07
					_fecha(activo.fecha_inicio_leasing),              # C08
					str(activo.numero_cuotas_leasing),                # C09
					_f2(activo.monto_total_leasing),                  # C10
					'1',                                              # C11 estado
					'',
				]
				lineas_74.append('|'.join(m_74))

		if errores:
			raise UserError(_(
				'No se puede generar el PLE 7. Corregir antes de reintentar:\n\n%s'
			) % '\n'.join('• %s' % e for e in errores))

		# ── Escritura TXT + XLSX ─────────────────────────────────────────
		dict_to_write = {}
		estructuras = [
			('070100', lineas_71, '01', self._headers_71()),
			('070300', lineas_73, '03', self._headers_73()),
			('070400', lineas_74, '04', self._headers_74()),
		]
		for ple_id, lineas, sufijo, headers in estructuras:
			name = self.get_default_filename(ple_id=ple_id, tiene_datos=bool(lineas))
			lineas_txt = list(lineas)
			lineas_txt.append('')
			txt_string = '\r\n'.join(lineas_txt)
			if lineas:
				xlsx = self._generate_xlsx_base64_bytes(
					txt_string, name[2:], headers=headers)
				dict_to_write.update({
					'ple_txt_%s' % sufijo: txt_string,
					# L8.1: ANSI (cp1252) con la transliteración de ple_pro,
					# como el resto de libros. Con latin-1 + 'replace' un
					# carácter tipográfico (—, «, ’) salía como «?».
					'ple_txt_%s_binary' % sufijo: base64.b64encode(
						self._codificar_txt(txt_string)),
					'ple_txt_%s_filename' % sufijo: name + '.txt',
					'ple_xls_%s_binary' % sufijo: xlsx.encode(),
					'ple_xls_%s_filename' % sufijo: name + '.xlsx',
				})
			else:
				# Sin datos: TXT vacío con indicador de contenido '0'
				# (obligatorio presentar igual para PRICO con libro afiliado)
				dict_to_write.update({
					'ple_txt_%s' % sufijo: False,
					'ple_txt_%s_binary' % sufijo: base64.b64encode(b''),
					'ple_txt_%s_filename' % sufijo: name + '.txt',
					'ple_xls_%s_binary' % sufijo: False,
					'ple_xls_%s_filename' % sufijo: False,
				})

		self.write(dict_to_write)
		return res

	# =====================================================================
	# Cabeceras Excel
	# =====================================================================
	def _headers_71(self):
		return [
			'Periodo', 'CUO', 'Correlativo', 'Catálogo (T13)',
			'Código del activo', 'Catálogo existencia', 'Código UNSPSC/GTIN',
			'Tipo AF (T18)', 'Cuenta contable', 'Estado AF (T19)',
			'Descripción', 'Marca', 'Modelo', 'N° serie/placa',
			'Saldo inicial', 'Adquisiciones', 'Mejoras', 'Retiros/bajas',
			'Otros ajustes', 'Revaluación voluntaria',
			'Revaluación reorganización', 'Otras revaluaciones',
			'Ajuste por inflación', 'Fecha adquisición', 'Fecha inicio uso',
			'Método dep. (T20)', 'N° autorización', '% depreciación',
			'Dep. acumulada ejercicio anterior', 'Dep. del ejercicio',
			'Dep. retiros/bajas', 'Dep. otros ajustes',
			'Dep. revaluación voluntaria', 'Dep. revaluación reorganización',
			'Dep. otras revaluaciones', 'Ajuste inflación dep.',
			'Estado operación',
		]

	def _headers_73(self):
		return [
			'Periodo', 'CUO', 'Correlativo', 'Catálogo (T13)',
			'Código del activo', 'Fecha adquisición',
			'Valor adquisición M.E.', 'T.C. adquisición',
			'Valor adquisición M.N.', 'T.C. al 31.12',
			'Ajuste dif. cambio', 'Dep. del ejercicio',
			'Dep. retiros/bajas', 'Dep. otros ajustes', 'Estado operación',
		]

	def _headers_74(self):
		return [
			'Periodo', 'CUO', 'Correlativo', 'Catálogo (T13)',
			'N° contrato', 'Fecha contrato', 'Código del activo',
			'Fecha inicio leasing', 'N° cuotas', 'Monto total contrato',
			'Estado operación',
		]
