# -*- coding: utf-8 -*-
"""Prueba dorada ESTRUCTURAL del formato .ps4 / .4ta (se ejecuta sin Odoo).

	python3 herramientas/prueba_formato.py

Las FORMAS de referencia se extrajeron de archivos reales aceptados por el
PDT PLAME (periodo 2026-06, entregados por Gabriel el 2026-09-20). Solo se
conserva la forma —cantidad de campos y tipo de cada uno—: los archivos
traen datos de personas y NO se guardan en el repositorio ni en la biblia.

Cada campo se clasifica como ENTERO, MONTO_DEC (con dos decimales), FECHA
(DD/MM/AAAA), TEXTO o VACIO; el último VACIO es el «|» de cierre de línea.
"""
import datetime
import importlib.util
import os
import re

FORMAS_PS4 = {
	('ENTERO', 'ENTERO', 'TEXTO', 'TEXTO', 'TEXTO', 'ENTERO', 'ENTERO', 'VACIO'),
}
FORMAS_4TA = {
	# monto sin decimales cuando son cero (750) y con decimales (169.44)
	('ENTERO', 'ENTERO', 'TEXTO', 'TEXTO', 'ENTERO', 'ENTERO', 'FECHA',
	 'FECHA', 'ENTERO', 'VACIO', 'VACIO', 'VACIO'),
	('ENTERO', 'ENTERO', 'TEXTO', 'TEXTO', 'ENTERO', 'MONTO_DEC', 'FECHA',
	 'FECHA', 'ENTERO', 'VACIO', 'VACIO', 'VACIO'),
}


def _forma(linea):
	def tipo(valor):
		if valor == '':
			return 'VACIO'
		if re.fullmatch(r'\d{2}/\d{2}/\d{4}', valor):
			return 'FECHA'
		if re.fullmatch(r'\d+\.\d{2}', valor):
			return 'MONTO_DEC'
		if re.fullmatch(r'\d+', valor):
			return 'ENTERO'
		return 'TEXTO'
	return tuple(tipo(valor) for valor in linea.split('|'))


def main():
	ruta = os.path.join(os.path.dirname(__file__), '..', 'models',
						'catalogos_plame.py')
	spec = importlib.util.spec_from_file_location('catalogos_plame', ruta)
	c = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(c)
	ps4 = c.armar_linea([
		'06', '10123456789', c.normalizar_texto('Pérez', 40),
		c.normalizar_texto('Ñúñez', 40), c.normalizar_texto('José María', 40),
		'1', '0'])
	lineas_4ta = [
		c.armar_linea(['06', '10123456789', 'R', 'E001', '75',
					   c.formato_monto(750.0),
					   c.formato_fecha(datetime.date(2026, 6, 9)),
					   c.formato_fecha(datetime.date(2026, 6, 11)), '0', '', '']),
		c.armar_linea(['06', '10123456789', 'R', 'E001', '31',
					   c.formato_monto(169.44),
					   c.formato_fecha(datetime.date(2026, 5, 22)),
					   c.formato_fecha(datetime.date(2026, 6, 22)), '0', '', '']),
	]
	errores = []
	if _forma(ps4) not in FORMAS_PS4:
		errores.append('.ps4 %s → %s' % (ps4, _forma(ps4)))
	for linea in lineas_4ta:
		if _forma(linea) not in FORMAS_4TA:
			errores.append('.4ta %s → %s' % (linea, _forma(linea)))
	if not ps4.isascii() or ps4 != ps4.upper():
		errores.append('.ps4 no es ASCII en mayúsculas: %s' % ps4)
	if c.FIN_DE_LINEA != '\r\n':
		errores.append('fin de línea distinto de CRLF')
	print('\n'.join(errores) if errores else
		  'OK: .ps4 y .4ta con la forma de los archivos aceptados por el PDT')
	return not errores


if __name__ == '__main__':
	raise SystemExit(0 if main() else 1)
