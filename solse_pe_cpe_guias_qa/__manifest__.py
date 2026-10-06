# -*- coding: utf-8 -*-

{
	'name': 'SOLSE CPE Guias - Laboratorio QA',
	'summary': 'Casos de prueba para la Guía de Remisión Remitente (09) y la Guía de Transportista (31)',
	'description': """
		Laboratorio QA de guías electrónicas (NO instalar en producción).

		Cada caso siembra sus propios datos (contactos, vehículos, conductores,
		transferencia validada), genera el XML por el mismo camino que el
		usuario y lo verifica campo a campo contra la estructura SUNAT
		(hojas Guía-Remitente2_0 y Guía-Transportista2_0). Un botón aparte
		envía la guía al beta configurado en la compañía y registra el CDR.

		Versión 19.0.1.0.0
		- 4 casos de GRR (09): venta privado, contenedor sin bultos
		  (regresión 19.0.4.19), público con transportista, importación con
		  DAM + traslado total + contenedor (regresión ERR-3631).
		- 4 casos de GRT (31): mínimo, completo (2 vehículos, subcontratador,
		  pagador tercero, MTC, TUCE, ERR-2571), exportación con DAM
		  régimen 40 y detalle de bienes, y factura física con traslado
		  total, línea 0 y autorización especial (AgentParty). Todos los
		  casos son aceptables por SUNAT; los negativos se retiraron para no
		  confundir al cliente.
		- Botones: Sembrar / Verificar XML / Enviar a beta / Limpiar, y
		  "Actualizar casos precargados" para recargar las definiciones.

		Versión 19.0.1.0.1
		- Los contactos sembrados llevan país, departamento y provincia
		  derivados del ubigeo (los exige solse_pe_edi al crear contactos
		  peruanos).
		Versión 19.0.1.0.2
		- stock.move v19: sin `name` ni unidad explícita al sembrar.
	""",
	'maintainer': 'Nuage Peru S.A.C.',
	'category': 'Financial',
	'version': '19.0.1.0.6',
	'license': 'Other proprietary',
	'depends': ['solse_pe_cpe_guias', 'solse_pe_cpe_guias_transp'],
	'data': [
		'security/ir.model.access.csv',
		'views/qa_caso_view.xml',
		'data/casos_precargados.xml',
	],
	'installable': True,
	'application': False,
}
