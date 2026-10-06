# -*- coding: utf-8 -*-
"""Formatos físicos 7.3 y 7.4 — R.S. 234-2006/SUNAT, art. 13 num. 7.3 c) y d).

Contrastados contra la plantilla oficial (`234_formato71.xls`, hojas
«F 7.3 Diferencia de Cambio» y «F 7.4 AF Leasing») y la estructura TXT
(`Estructura_del_PLE.xls`, hoja 7: 15 campos el 7.3, 11 el 7.4). Como el
7.1, se construyen leyendo el TXT que se declara.

7.3 — «DETALLE DE LA DIFERENCIA DE CAMBIO», 12 columnas:

	código (C05) · fecha de adquisición (C06) · valor en M.E. (C07) · TC de
	adquisición (C08) · valor en M.N. (C09) · TC al 31.12 (C10) · ajuste por
	diferencia de cambio (C11) · VALOR EN M.N. AL 31.12 = C09 + C11 ·
	depreciación del ejercicio (C12) · de retiros (C13) · de otros ajustes
	(C14) · DEPRECIACIÓN ACUMULADA HISTÓRICA.

	La acumulada histórica NO sale del TXT 7.3: le falta la depreciación de
	ejercicios anteriores. Se toma del C29 del 7.1 del MISMO reporte,
	cruzando por código de activo (decisión de Gabriel, 2026-09-20), y se
	aplica el mismo parámetro B-9 (`solse_pe_ple_07.dep_historica_bajas`)
	que en el 7.1: los dos físicos dicen lo mismo del mismo activo.
	La baja se detecta en el 7.1 (C18 ≠ 0), que es donde está.

	Totales: solo columnas en moneda nacional. Sumar valores en monedas
	extranjeras distintas, o tipos de cambio, no significa nada.

7.4 — «ACTIVOS FIJOS BAJO LA MODALIDAD DE ARRENDAMIENTO FINANCIERO AL
31.12», 5 columnas: fecha del contrato (C06) · número (C05) · fecha de
inicio (C08) · cuotas pactadas (C09) · monto total (C10), con TOTAL del
monto.
"""

from odoo import models, _
from odoo.exceptions import UserError

COLUMNAS_TOTAL_73 = ['valor_mn', 'ajuste', 'valor_mn_3112', 'dep_ejercicio',
					 'dep_retiros', 'dep_otros', 'dep_historica']


def _miles(valor):
	return '{:,.2f}'.format(valor or 0.0)


def _filas(texto):
	"""Filas del TXT (Text del reporte) como listas, sin líneas vacías."""
	return [linea.split('|') for linea in (texto or '').splitlines()
			if linea.strip()]


def _lector(celdas):
	"""(texto(n), numero(n)) sobre una fila, con n en base 1."""
	def texto(n):
		return celdas[n - 1] if len(celdas) >= n else ''

	def numero(n):
		try:
			return float(texto(n) or 0.0)
		except ValueError:
			return 0.0
	return texto, numero


class PLEReport07Formato73y74(models.Model):
	_inherit = 'ple.report.07'

	def _cabecera_fisico(self):
		return {
			'periodo': str(self.year),
			'ruc': self.company_id.vat or '',
			'razon_social': self.company_id.name or '',
		}

	def datos_formato_7_3(self):
		"""Cabecera, filas y totales del físico 7.3."""
		self.ensure_one()
		if not self.ple_txt_03:
			raise UserError(_(
				'No hay TXT 7.3 para el ejercicio %s (ningún activo adquirido '
				'en moneda extranjera, o falta «Generar Estructuras»).',
				self.year))
		modo = self._modo_bajas()
		del_71 = {}
		for celdas in _filas(self.ple_txt_01):
			texto, _numero = _lector(celdas)
			del_71[texto(5)] = celdas
		filas = []
		totales = dict.fromkeys(COLUMNAS_TOTAL_73, 0.0)
		for celdas in _filas(self.ple_txt_03):
			texto, v = _lector(celdas)
			codigo = texto(5)
			dep_anterior = 0.0
			retirado = False
			if codigo in del_71:
				_texto71, v71 = _lector(del_71[codigo])
				dep_anterior = v71(29)
				retirado = bool(v71(18))
			dep_ejercicio, dep_retiros = v(12), v(13)
			if modo == 'descontar' and retirado:
				dep_ejercicio = v(12) + v(13)
				dep_retiros = -(dep_anterior + v(13))
			fila = {
				'codigo': codigo,
				'fecha_adquisicion': texto(6),
				'valor_me': v(7),
				'tc_adquisicion': texto(8),
				'valor_mn': v(9),
				'tc_cierre': texto(10),
				'ajuste': v(11),
				'valor_mn_3112': v(9) + v(11),
				'dep_ejercicio': dep_ejercicio,
				'dep_retiros': dep_retiros,
				'dep_otros': v(14),
				'dep_historica': dep_anterior + dep_ejercicio + dep_retiros
								 + v(14),
				'sin_7_1': codigo not in del_71,
			}
			for columna in totales:
				totales[columna] += fila[columna]
			fila['valor_me_fmt'] = _miles(fila['valor_me'])
			fila.update({'%s_fmt' % c: _miles(fila[c]) for c in totales})
			filas.append(fila)
		return {
			'modo_bajas': modo,
			'cabecera': self._cabecera_fisico(),
			'filas': filas,
			'totales': {c: _miles(valor) for c, valor in totales.items()},
		}

	def datos_formato_7_4(self):
		"""Cabecera, filas y total del físico 7.4."""
		self.ensure_one()
		if not self.ple_txt_04:
			raise UserError(_(
				'No hay TXT 7.4 para el ejercicio %s (ningún activo en '
				'arrendamiento financiero, o falta «Generar Estructuras»).',
				self.year))
		filas = []
		total = 0.0
		for celdas in _filas(self.ple_txt_04):
			texto, v = _lector(celdas)
			filas.append({
				'fecha_contrato': texto(6),
				'numero_contrato': texto(5),
				'fecha_inicio': texto(8),
				'cuotas': texto(9),
				'monto': v(10),
				'monto_fmt': _miles(v(10)),
				'codigo': texto(7),
			})
			total += v(10)
		return {
			'cabecera': self._cabecera_fisico(),
			'filas': filas,
			'total': _miles(total),
		}
