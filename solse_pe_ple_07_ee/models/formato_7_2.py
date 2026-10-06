# -*- coding: utf-8 -*-
"""Formato físico 7.2 — «REGISTRO DE ACTIVOS FIJOS - DETALLE DE LOS ACTIVOS
FIJOS REVALUADOS» (R.S. 234-2006/SUNAT, art. 13 num. 7.3 b).

Contrastado contra la plantilla oficial (`234_formato71.xls`, hoja «F 7.2
Det bs AF Revaluad»: 32 columnas y TOTALES). El 7.2 NO tiene TXT propio en
el PLE: sus datos son los del TXT 7.1 (revaluaciones en C20-C22 y su
depreciación en C33-C35). Se imprimen solo los activos con alguna
revaluación vigente en el ejercicio.

Los importes de revaluación son ACUMULADOS al 31.12 (decisión de Gabriel,
2026-09-20) y rigen desde `account.asset.fecha_revaluacion`. Derivadas:

	valor histórico al 31.12 = C15 + C16 + C17 + retiros + C19 + C20 + C21 + C22
	valor ajustado			 = histórico + C23
	dep. acumulada histórica = C29 + dep. del ejercicio + de retiros + C32
							   + C33 + C34 + C35
	dep. ajustada			 = histórica + C36

Las columnas sin revaluación (saldo, adquisiciones, retiros, depreciación
sin revaluación) se calculan con `_columnas_fisico` del 7.1: mismo signo de
los retiros y mismo parámetro B-9 para las bajas. Lo que el 7.1 dice de un
bien, el 7.2 lo repite y le suma la revaluación.
"""

from odoo import models, _
from odoo.exceptions import UserError

from .formato_7_1 import TABLA_20

COLUMNAS_TOTAL_72 = [
	'saldo_inicial', 'adquisiciones', 'mejoras', 'retiros', 'otros_ajustes',
	'rev_voluntaria', 'rev_reorganizacion', 'rev_otras', 'valor_historico',
	'ajuste_inflacion', 'valor_ajustado', 'dep_anterior', 'dep_ejercicio',
	'dep_retiros', 'dep_otros', 'dep_rev_voluntaria',
	'dep_rev_reorganizacion', 'dep_rev_otras', 'dep_historica',
	'dep_ajuste_inflacion', 'dep_ajustada',
]


def _miles(valor):
	return '{:,.2f}'.format(valor or 0.0)


class PLEReport07Formato72(models.Model):
	_inherit = 'ple.report.07'

	def datos_formato_7_2(self):
		"""Cabecera, filas y totales del físico 7.2 (desde el TXT 7.1)."""
		self.ensure_one()
		if not self.ple_txt_01:
			raise UserError(_(
				'No hay TXT 7.1 para el ejercicio %s. Pulse primero '
				'«Generar Estructuras».', self.year))
		modo = self._modo_bajas()
		nombres = {activo._get_codigo_af(): activo.name
				   for activo in self.asset_ids.sudo()}
		filas = []
		totales = dict.fromkeys(COLUMNAS_TOTAL_72, 0.0)
		for linea in self.ple_txt_01.splitlines():
			if not linea.strip():
				continue
			c = linea.split('|')

			def texto(n, c=c):
				return c[n - 1] if len(c) >= n else ''

			def v(n, c=c):
				try:
					return float(c[n - 1] or 0.0) if len(c) >= n else 0.0
				except ValueError:
					return 0.0

			revaluaciones = (v(20), v(21), v(22), v(33), v(34), v(35))
			if not any(revaluaciones):
				continue
			fila = self._columnas_fisico(v, modo)
			fila.update({
				'rev_voluntaria': v(20),
				'rev_reorganizacion': v(21),
				'rev_otras': v(22),
				'dep_rev_voluntaria': v(33),
				'dep_rev_reorganizacion': v(34),
				'dep_rev_otras': v(35),
			})
			fila['valor_historico'] += v(20) + v(21) + v(22)
			fila['valor_ajustado'] = fila['valor_historico'] + fila['ajuste_inflacion']
			fila['dep_historica'] += v(33) + v(34) + v(35)
			fila['dep_ajustada'] = fila['dep_historica'] + fila['dep_ajuste_inflacion']
			fila.update({
				'codigo': texto(5),
				'cuenta': texto(9),
				'descripcion': nombres.get(texto(5)) or texto(11),
				'marca': texto(12),
				'modelo': texto(13),
				'serie': texto(14),
				'fecha_adquisicion': texto(24),
				'fecha_uso': texto(25),
				'metodo': TABLA_20.get(texto(26), texto(26)),
				'documento': texto(27),
				'porcentaje': texto(28),
			})
			for columna in totales:
				totales[columna] += fila[columna]
			fila.update({'%s_fmt' % col: _miles(fila[col]) for col in totales})
			filas.append(fila)
		return {
			'modo_bajas': modo,
			'cabecera': self._cabecera_fisico(),
			'filas': filas,
			'totales': {col: _miles(valor) for col, valor in totales.items()},
		}
