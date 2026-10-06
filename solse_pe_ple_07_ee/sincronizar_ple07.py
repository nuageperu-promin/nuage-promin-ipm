#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sincroniza las dos variantes del PLE 7.

Odoo no admite ``depends`` alternativos: un módulo depende de A o depende de
B, no de «A o B». Como ``solse_pe_activo_fijo`` (Community) y
``account_asset`` (Enterprise) declaran **el mismo modelo**, el libro 7 tiene
que existir en dos variantes.

La duplicación es real, pero **la diferencia entre ambas es el nombre técnico del módulo en cinco sitios**:

    __manifest__.py                 'solse_pe_activo_fijo' | 'account_asset'
    views/account_asset_views.xml   el ref de la vista heredada
    reports/formato_7_1.xml         el nombre técnico en report_name/file
    reports/formato_7_3_7_4.xml     ídem, más los t-call internos
    reports/formato_7_2.xml         ídem

Todo lo demás —el generador, el PDF 7.1, los 24 campos peruanos, las vistas
del reporte y la seguridad— es idéntico byte a byte.

Por eso **la fuente de verdad es una sola**: ``solse_pe_ple_07`` (Community).
La variante Enterprise se REGENERA desde ella con este script. Editar la
variante Enterprise a mano es el error que este script existe para evitar.

Uso:
    python3 sincronizar_ple07.py            # regenera la variante EE
    python3 sincronizar_ple07.py --verificar  # solo comprueba, no escribe
"""

import filecmp
import os
import shutil
import sys

ORIGEN = 'solse_pe_ple_07'
DESTINO = 'solse_pe_ple_07_ee'

# (archivo, texto en la variante Community, texto en la variante Enterprise)
DIFERENCIAS = [
	('__manifest__.py',
	 "'solse_pe_activo_fijo'",
	 "'account_asset'"),
	('__manifest__.py',
	 "(Community)",
	 "(Enterprise)"),
	('__manifest__.py',
	 "# ⚠ Este modulo es la variante COMMUNITY. Usa solse_pe_activo_fijo, que\n"
	 "\t# declara account.asset en Community.\n"
	 "\t# En Odoo 19 ENTERPRISE hay que instalar solse_pe_ple_07_ee, que usa el\n"
	 "\t# account_asset nativo: los dos modulos de activos declaran el MISMO\n"
	 "\t# modelo y NO pueden convivir.",
	 "# ⚠ Este modulo es la variante ENTERPRISE. Usa el account_asset nativo.\n"
	 "\t# En Odoo 19 COMMUNITY hay que instalar solse_pe_ple_07, que usa\n"
	 "\t# solse_pe_activo_fijo."),
	('views/account_asset_views.xml',
	 'ref="solse_pe_activo_fijo.view_activo_fijo_form"',
	 'ref="account_asset.view_account_asset_form"'),
	# L8.1: el report_name/report_file del PDF 7.1 llevan el nombre técnico
	# del módulo, que es lo único de un ir.actions.report que no puede ser
	# relativo. Sustitución sobre todo el archivo (str.replace).
	('reports/formato_7_1.xml',
	 'solse_pe_ple_07.formato_7_1_documento',
	 'solse_pe_ple_07_ee.formato_7_1_documento'),
	# Físicos 7.3 y 7.4: report_name/report_file y los t-call entre
	# plantillas del propio módulo (estilos y cabecera compartidos).
	('reports/formato_7_3_7_4.xml',
	 'solse_pe_ple_07.formato_7_',
	 'solse_pe_ple_07_ee.formato_7_'),
	# Físico 7.2: ídem (report_name/report_file y t-call a los estilos y la
	# cabecera que define formato_7_3_7_4.xml).
	('reports/formato_7_2.xml',
	 'solse_pe_ple_07.formato_7_',
	 'solse_pe_ple_07_ee.formato_7_'),
]

ARCHIVOS_QUE_DIFIEREN = {archivo for archivo, _ce, _ee in DIFERENCIAS}


def regenerar():
	if not os.path.isdir(ORIGEN):
		print('No se encuentra "%s" en el directorio actual.' % ORIGEN)
		return 2

	# Se conserva la version del manifest Enterprise, que lleva su propio ritmo.
	version_ee = None
	ruta_manifest_ee = os.path.join(DESTINO, '__manifest__.py')
	if os.path.isfile(ruta_manifest_ee):
		import ast
		try:
			version_ee = ast.literal_eval(
				open(ruta_manifest_ee, encoding='utf-8').read()).get('version')
		except Exception:
			version_ee = None

	if os.path.isdir(DESTINO):
		shutil.rmtree(DESTINO)
	shutil.copytree(ORIGEN, DESTINO,
	                ignore=shutil.ignore_patterns('__pycache__'))

	for archivo, texto_ce, texto_ee in DIFERENCIAS:
		ruta = os.path.join(DESTINO, archivo)
		contenido = open(ruta, encoding='utf-8').read()
		if texto_ce not in contenido:
			print('AVISO  no se encontro en %s el texto a sustituir:\n   %s'
			      % (archivo, texto_ce.splitlines()[0]))
			continue
		open(ruta, 'w', encoding='utf-8').write(
			contenido.replace(texto_ce, texto_ee))

	if version_ee:
		ruta = os.path.join(DESTINO, '__manifest__.py')
		import re
		contenido = open(ruta, encoding='utf-8').read()
		contenido = re.sub(r"('version':\s*')[^']*(')",
		                   lambda m: m.group(1) + version_ee + m.group(2),
		                   contenido, count=1)
		open(ruta, 'w', encoding='utf-8').write(contenido)
		print('Version de la variante Enterprise conservada: %s' % version_ee)

	print('Regenerado "%s" desde "%s".' % (DESTINO, ORIGEN))
	return 0


def verificar():
	"""Comprueba que las dos variantes solo difieren en lo previsto."""
	problemas = []
	for base, _dirs, archivos in os.walk(ORIGEN):
		if '__pycache__' in base:
			continue
		for archivo in archivos:
			relativa = os.path.relpath(os.path.join(base, archivo), ORIGEN)
			ruta_ce = os.path.join(ORIGEN, relativa)
			ruta_ee = os.path.join(DESTINO, relativa)
			if not os.path.isfile(ruta_ee):
				problemas.append('Falta en la variante EE: %s' % relativa)
				continue
			if filecmp.cmp(ruta_ce, ruta_ee, shallow=False):
				continue
			if relativa not in ARCHIVOS_QUE_DIFIEREN:
				problemas.append(
					'DIVERGEN y no deberian: %s\n'
					'   Las dos variantes solo pueden diferir en %s.\n'
					'   Alguien edito la variante Enterprise a mano: use\n'
					'   "python3 sincronizar_ple07.py" para regenerarla.'
					% (relativa, ', '.join(sorted(ARCHIVOS_QUE_DIFIEREN))))

	for base, _dirs, archivos in os.walk(DESTINO):
		if '__pycache__' in base:
			continue
		for archivo in archivos:
			relativa = os.path.relpath(os.path.join(base, archivo), DESTINO)
			if not os.path.isfile(os.path.join(ORIGEN, relativa)):
				problemas.append(
					'Sobra en la variante EE: %s' % relativa)

	for problema in problemas:
		print('FALLO  %s' % problema)
	if problemas:
		print('\n%s problema(s)' % len(problemas))
		return 1
	print('Las dos variantes coinciden salvo en %s. Correcto.'
	      % ', '.join(sorted(ARCHIVOS_QUE_DIFIEREN)))
	return 0


if __name__ == '__main__':
	if '--verificar' in sys.argv:
		sys.exit(verificar())
	sys.exit(regenerar())
