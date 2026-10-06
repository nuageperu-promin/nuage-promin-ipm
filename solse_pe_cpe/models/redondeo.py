# -*- coding: utf-8 -*-
"""Redondeo de importes del CPE — LEER ANTES DE TOCAR.

M-17 · **Los nombres mienten y NO se pueden arreglar.**

``round_up`` NO redondea hacia arriba y ``round_down`` NO redondea hacia
abajo: las dos son el redondeo de FORMATO de Python (``"%.<n>f" % valor``,
half-to-even sobre la representación binaria del float). Los ``math.ceil``
/ ``math.floor`` que sí harían honor al nombre están comentados dentro
desde el origen del módulo.

¿Por qué no se corrige? ``round_up`` se usa ~19 veces y ``round_down`` 2,
todas en la composición de importes del XML del CPE. Cambiar la semántica
cambiaría céntimos de comprobantes YA EMITIDOS y aceptados por SUNAT: el
mismo comprobante regenerado dejaría de coincidir con su CDR. La auditoría
del registro (tercera tanda) lo dejó decidido: se documenta en grande y
NO se toca. Si algún día hace falta un ceiling de verdad, se escribe una
función NUEVA con un nombre honesto.

M-27 · La definición estaba duplicada byte a byte en ``cpe_xml.py`` y
``account_tax.py``; ahora vive aquí y los dos la importan.
"""


def round_up(n, decimals=0):
	"""Redondeo de formato a ``decimals`` (NO es ceiling — ver cabecera)."""
	return float(("%." + str(decimals) + "f") % n)
	# multiplier = 10 ** decimals
	# return math.ceil(n * multiplier) / multiplier


def round_down(n, decimals=0):
	"""Redondeo de formato a ``decimals`` (NO es floor — ver cabecera)."""
	return float(("%." + str(decimals) + "f") % n)
	# multiplier = 10 ** decimals
	# return math.floor(n * multiplier) / multiplier
