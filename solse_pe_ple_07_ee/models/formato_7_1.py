# -*- coding: utf-8 -*-
"""Formato físico 7.1 — «REGISTRO DE ACTIVOS FIJOS - DETALLE DE LOS ACTIVOS
FIJOS» (R.S. 234-2006/SUNAT, art. 13 num. 7.3 a).

EL FÍSICO NO ES EL TXT MAQUETADO. Contrastado contra la plantilla oficial
(`234_formato71.xls`, hoja «F 7.1 Det bs AF») y el texto de la norma:

* Omite periodo, CUO, correlativo, catálogos, tipo y estado del activo, las
  tres revaluaciones (C20-C22 y C33-C35, que son del FORMATO 7.2) y el
  estado de la operación.
* Tiene tres columnas DERIVADAS que el TXT no trae, más la fila de totales:

	(xii)	valor histórico al 31.12		= C15 + C16 + C17 − C18 + C19
	(xiv)	valor ajustado al 31.12			= histórico + C23
	(xxiv)	depreciación acumulada histórica = C29 + C30 + C31 + C32
	(xxvi)	depreciación ajustada			= histórica + C36

  La norma no da fórmulas: las columnas se derivan de su orden y de su
  nombre. Lo único oficial es el signo: C18, C19, C29-C32 admiten
  «positivo o negativo» (Estructura_del_PLE.xls, hoja 7), es decir, el
  registro es una SUMA ALGEBRAICA.

B-9 · CÓMO SE PRESENTA UNA BAJA — configurable
(`ir.config_parameter` «solse_pe_ple_07.dep_historica_bajas»):

  'descontar' (POR DEFECTO) — la baja retira el costo Y la depreciación
	acumulada del bien (NIC 16 párr. 67-72, que la doctrina cita para los
	retiros del registro). Solo en las filas con retiro (C18 ≠ 0):
	  retiros			→ −C18
	  dep. del ejercicio	→ C30 + C31 (lo depreciado en el año, hasta la baja)
	  dep. de retiros		→ −(C29 + C31) (toda la acumulada que sale)
	  ⇒ el bien dado de baja queda en 0 / 0 y los totales del registro
		cuadran con los saldos de la 33 y la 39 al 31.12.
  'acumular' — la lectura literal de L8.1: C31 como concepto del ejercicio
	que se SUMA, retiros restando del valor; el bien retirado sale con
	valor 0 y su depreciación completa.

  Las columnas del TXT (C29-C32) NO cambian: esto es solo presentación del
  físico. Decisión del 2026-09-19, a confirmar con el contador de Gabriel.

El PDF se construye leyendo `ple_txt_01` — el mismo contenido que se
declara —, como hacen los formatos de solse_pe_ple_pdf: lo que se imprime
no puede diferir de lo que se presenta.

Vive en el propio libro 7 y no en solse_pe_ple_pdf porque el libro 7 tiene
dos variantes excluyentes (Community y Enterprise): meterlo en ple_pdf
obligaría a depender de una de ellas. La variante Enterprise se regenera
con `sincronizar_ple07.py`.
"""

from odoo import models, _
from odoo.exceptions import UserError

PARAMETRO_BAJAS = 'solse_pe_ple_07.dep_historica_bajas'
MODOS_BAJAS = ('descontar', 'acumular')
MODO_BAJAS_POR_DEFECTO = 'descontar'

# Tabla 20 del Anexo 3 (PLEAnexo3TABLASfinal.xls, hoja TABLA_20).
TABLA_20 = {'1': 'LÍNEA RECTA', '2': 'UNIDADES PRODUCIDAS', '9': 'OTROS'}

# Columnas numéricas del físico, en orden: las que llevan total.
COLUMNAS_VALOR = ['saldo_inicial', 'adquisiciones', 'mejoras', 'retiros',
				  'otros_ajustes', 'valor_historico', 'ajuste_inflacion',
				  'valor_ajustado']
COLUMNAS_DEPRECIACION = ['dep_anterior', 'dep_ejercicio', 'dep_retiros',
						 'dep_otros', 'dep_historica', 'dep_ajuste_inflacion',
						 'dep_ajustada']


def _miles(valor):
	return '{:,.2f}'.format(valor or 0.0)


class PLEReport07Formato71(models.Model):
	_inherit = 'ple.report.07'

	def _modo_bajas(self):
		"""'descontar' | 'acumular' (B-9). Un valor desconocido cae al
		defecto: un parámetro mal escrito no debe cambiar el registro."""
		modo = self.env['ir.config_parameter'].sudo().get_param(
			PARAMETRO_BAJAS, MODO_BAJAS_POR_DEFECTO)
		return modo if modo in MODOS_BAJAS else MODO_BAJAS_POR_DEFECTO

	@staticmethod
	def _columnas_fisico(v, modo):
		"""Las columnas numéricas del físico para una fila del TXT.

		`v(n)` devuelve el campo n del TXT como número. Ver la cabecera del
		módulo (B-9) para el porqué de cada fórmula.
		"""
		retiro = v(18)
		columnas = {
			'saldo_inicial': v(15),
			'adquisiciones': v(16),
			'mejoras': v(17),
			'retiros': -abs(retiro),
			'otros_ajustes': v(19),
			'ajuste_inflacion': v(23),
			'dep_anterior': v(29),
			'dep_ejercicio': v(30),
			'dep_retiros': v(31),
			'dep_otros': v(32),
			'dep_ajuste_inflacion': v(36),
		}
		if modo == 'descontar' and retiro:
			columnas['dep_ejercicio'] = v(30) + v(31)
			columnas['dep_retiros'] = -(v(29) + v(31))
		historico = (columnas['saldo_inicial'] + columnas['adquisiciones']
					 + columnas['mejoras'] + columnas['retiros']
					 + columnas['otros_ajustes'])
		dep_historica = (columnas['dep_anterior'] + columnas['dep_ejercicio']
						 + columnas['dep_retiros'] + columnas['dep_otros'])
		columnas.update({
			'valor_historico': historico,
			'valor_ajustado': historico + columnas['ajuste_inflacion'],
			'dep_historica': dep_historica,
			'dep_ajustada': dep_historica + columnas['dep_ajuste_inflacion'],
		})
		return columnas

	def datos_formato_7_1(self):
		"""Cabecera, filas y totales del físico 7.1, desde el TXT 7.1."""
		self.ensure_one()
		if not self.ple_txt_01:
			raise UserError(_(
				'No hay TXT 7.1 para el ejercicio %s. Pulse primero '
				'«Generar Estructuras».', self.year))
		filas = []
		modo = self._modo_bajas()
		# L9.4: la descripción del físico no tiene el tope de 40 caracteres
		# del C11 del TXT («Montacargas eléctrico (arrendamiento fin»). Se
		# toma el nombre completo del activo del propio libro, cruzando por
		# el código del C5; si no aparece, la del TXT.
		nombres = {activo._get_codigo_af(): activo.name
				   for activo in self.asset_ids.sudo()}
		totales = dict.fromkeys(COLUMNAS_VALOR + COLUMNAS_DEPRECIACION, 0.0)
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

			fila = {
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
			}
			fila.update(self._columnas_fisico(v, modo))
			for columna in totales:
				totales[columna] += fila[columna]
			fila.update({'%s_fmt' % columna: _miles(fila[columna])
						 for columna in totales})
			filas.append(fila)
		return {
			'modo_bajas': modo,
			'cabecera': {
				'periodo': str(self.year),
				'ruc': self.company_id.vat or '',
				'razon_social': self.company_id.name or '',
			},
			'filas': filas,
			'totales': {columna: _miles(valor)
						for columna, valor in totales.items()},
		}
