# -*- coding: utf-8 -*-
"""Pre-migración 19.0.1.3 (corrección del seed tras el QA de instalación) —
solse_pe_catalogo.

Dos trabajos, en orden:

1. LIMPIAR LOS DUPLICADOS QUE SEMBRÓ EL PROPIO MÓDULO. Hasta 19.0.1.2 el
   archivo pe_datas_tabla28_tabla34.xml traía:
   - 142 duplicados reales en PE.TABLA34 (los conceptos de flujos de
     efectivo aparecen en las estructuras 3.18 y 3.25 del origen y se
     aplanaron dos veces al catálogo, con xmlids distintos);
   - la TABLA28 entera con code/name invertidos, la cabecera del Excel
     como registro y coerción float en los códigos.
   En bases donde el módulo se instaló con la constraint muerta, esas
   filas EXISTEN. Se eliminan por xmlid (solo las sembradas por este
   módulo — ir_model_data.module = 'solse_pe_catalogo'); las filas T28
   corregidas se recrean al cargar el XML nuevo (xmlids por código,
   noupdate solo impide ACTUALIZAR las existentes, no crear las nuevas).

2. DETECTAR DUPLICADOS DE USUARIO. Igual que antes: si tras la limpieza
   quedan duplicados (creados a mano), se DETIENE la actualización
   nombrándolos. No se borra nada que no haya sembrado el módulo.

Nota de versión: el pre-migrate de 19.0.1.2 (solo-detección, publicado
en L2) se RETIRÓ y este lo sustituye en 19.0.1.3. Es seguro: ninguna
base puede haber quedado en 19.0.1.2 con datos sucios — la instalación
limpia fallaba por la constraint y la actualización quedaba bloqueada
por aquel script. Una base que salte de <1.2 a 1.3 ejecuta solo este.
"""
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

XMLIDS_T34_DUPLICADOS = {
	'pe_datas_t34_01_3_25_3D0103',
	'pe_datas_t34_01_3_25_3D0107',
	'pe_datas_t34_01_3_25_3D0111',
	'pe_datas_t34_01_3_25_3D0116',
	'pe_datas_t34_01_3_25_3D0120',
	'pe_datas_t34_01_3_25_3D0121',
	'pe_datas_t34_01_3_25_3D01ST',
	'pe_datas_t34_01_3_25_3D0201',
	'pe_datas_t34_01_3_25_3D0202',
	'pe_datas_t34_01_3_25_3D0203',
	'pe_datas_t34_01_3_25_3D0205',
	'pe_datas_t34_01_3_25_3D0206',
	'pe_datas_t34_01_3_25_3D0207',
	'pe_datas_t34_01_3_25_3D0209',
	'pe_datas_t34_01_3_25_3D0210',
	'pe_datas_t34_01_3_25_3D0211',
	'pe_datas_t34_01_3_25_3D0212',
	'pe_datas_t34_01_3_25_3D0218',
	'pe_datas_t34_01_3_25_3D0219',
	'pe_datas_t34_01_3_25_3D0220',
	'pe_datas_t34_01_3_25_3D0221',
	'pe_datas_t34_01_3_25_3D0222',
	'pe_datas_t34_01_3_25_3D0223',
	'pe_datas_t34_01_3_25_3D0225',
	'pe_datas_t34_01_3_25_3D0226',
	'pe_datas_t34_01_3_25_3D0227',
	'pe_datas_t34_01_3_25_3D0229',
	'pe_datas_t34_01_3_25_3D0231',
	'pe_datas_t34_01_3_25_3D0232',
	'pe_datas_t34_01_3_25_3D0233',
	'pe_datas_t34_01_3_25_3D0234',
	'pe_datas_t34_01_3_25_3D02ST',
	'pe_datas_t34_01_3_25_3D0305',
	'pe_datas_t34_01_3_25_3D0310',
	'pe_datas_t34_01_3_25_3D0311',
	'pe_datas_t34_01_3_25_3D0319',
	'pe_datas_t34_01_3_25_3D0321',
	'pe_datas_t34_01_3_25_3D0322',
	'pe_datas_t34_01_3_25_3D0323',
	'pe_datas_t34_01_3_25_3D0325',
	'pe_datas_t34_01_3_25_3D0326',
	'pe_datas_t34_01_3_25_3D0327',
	'pe_datas_t34_01_3_25_3D0328',
	'pe_datas_t34_01_3_25_3D0329',
	'pe_datas_t34_01_3_25_3D0330',
	'pe_datas_t34_01_3_25_3D0331',
	'pe_datas_t34_01_3_25_3D0332',
	'pe_datas_t34_01_3_25_3D0333',
	'pe_datas_t34_01_3_25_3D03ST',
	'pe_datas_t34_01_3_25_3D0401',
	'pe_datas_t34_01_3_25_3D0402',
	'pe_datas_t34_01_3_25_3D0404',
	'pe_datas_t34_01_3_25_3D0405',
	'pe_datas_t34_01_3_25_3D04ST',
	'pe_datas_t34_03_3_25_3G0103',
	'pe_datas_t34_03_3_25_3G0107',
	'pe_datas_t34_03_3_25_3G0111',
	'pe_datas_t34_03_3_25_3G0116',
	'pe_datas_t34_03_3_25_3G0120',
	'pe_datas_t34_03_3_25_3G0121',
	'pe_datas_t34_03_3_25_3G01ST',
	'pe_datas_t34_03_3_25_3G0201',
	'pe_datas_t34_03_3_25_3G0202',
	'pe_datas_t34_03_3_25_3G0203',
	'pe_datas_t34_03_3_25_3G0205',
	'pe_datas_t34_03_3_25_3G0206',
	'pe_datas_t34_03_3_25_3G0207',
	'pe_datas_t34_03_3_25_3G0209',
	'pe_datas_t34_03_3_25_3G0210',
	'pe_datas_t34_03_3_25_3G0211',
	'pe_datas_t34_03_3_25_3G0212',
	'pe_datas_t34_03_3_25_3G0218',
	'pe_datas_t34_03_3_25_3G0219',
	'pe_datas_t34_03_3_25_3G0220',
	'pe_datas_t34_03_3_25_3G0221',
	'pe_datas_t34_03_3_25_3G0222',
	'pe_datas_t34_03_3_25_3G0223',
	'pe_datas_t34_03_3_25_3G0225',
	'pe_datas_t34_03_3_25_3G0226',
	'pe_datas_t34_03_3_25_3G0227',
	'pe_datas_t34_03_3_25_3G0229',
	'pe_datas_t34_03_3_25_3G0231',
	'pe_datas_t34_03_3_25_3G0232',
	'pe_datas_t34_03_3_25_3G0233',
	'pe_datas_t34_03_3_25_3G0234',
	'pe_datas_t34_03_3_25_3G02ST',
	'pe_datas_t34_03_3_25_3G0305',
	'pe_datas_t34_03_3_25_3G0310',
	'pe_datas_t34_03_3_25_3G0311',
	'pe_datas_t34_03_3_25_3G0319',
	'pe_datas_t34_03_3_25_3G0321',
	'pe_datas_t34_03_3_25_3G0322',
	'pe_datas_t34_03_3_25_3G0323',
	'pe_datas_t34_03_3_25_3G0325',
	'pe_datas_t34_03_3_25_3G0326',
	'pe_datas_t34_03_3_25_3G0327',
	'pe_datas_t34_03_3_25_3G0328',
	'pe_datas_t34_03_3_25_3G0329',
	'pe_datas_t34_03_3_25_3G0330',
	'pe_datas_t34_03_3_25_3G0331',
	'pe_datas_t34_03_3_25_3G0332',
	'pe_datas_t34_03_3_25_3G0333',
	'pe_datas_t34_03_3_25_3G03ST',
	'pe_datas_t34_03_3_25_3G0401',
	'pe_datas_t34_03_3_25_3G0402',
	'pe_datas_t34_03_3_25_3G0404',
	'pe_datas_t34_03_3_25_3G0405',
	'pe_datas_t34_03_3_25_3G04ST',
	'pe_datas_t34_03_3_25_4519_0',
	'pe_datas_t34_03_3_25_4520_0',
	'pe_datas_t34_03_3_25_4523_0',
	'pe_datas_t34_03_3_25_4524_0',
	'pe_datas_t34_03_3_25_4525_0',
	'pe_datas_t34_03_3_25_4528_0',
	'pe_datas_t34_03_3_25_4529_0',
	'pe_datas_t34_03_3_25_4530_0',
	'pe_datas_t34_03_3_25_4531_0',
	'pe_datas_t34_03_3_25_4532_0',
	'pe_datas_t34_03_3_25_4533_0',
	'pe_datas_t34_03_3_25_4534_0',
	'pe_datas_t34_03_3_25_4535_0',
	'pe_datas_t34_03_3_25_4537_0',
	'pe_datas_t34_03_3_25_4538_0',
	'pe_datas_t34_03_3_25_4539_0',
	'pe_datas_t34_03_3_25_4540_0',
	'pe_datas_t34_03_3_25_4541_0',
	'pe_datas_t34_03_3_25_4543_0',
	'pe_datas_t34_03_3_25_4546_0',
	'pe_datas_t34_03_3_25_4547_0',
	'pe_datas_t34_03_3_25_4548_0',
	'pe_datas_t34_03_3_25_4549_0',
	'pe_datas_t34_03_3_25_4550_0',
	'pe_datas_t34_03_3_25_4551_0',
	'pe_datas_t34_03_3_25_4552_0',
	'pe_datas_t34_03_3_25_4553_0',
	'pe_datas_t34_03_3_25_4554_0',
	'pe_datas_t34_03_3_25_4555_0',
	'pe_datas_t34_03_3_25_4556_0',
	'pe_datas_t34_03_3_25_4560_0',
	'pe_datas_t34_03_3_25_4562_0',
	'pe_datas_t34_03_3_25_4564_0',
	'pe_datas_t34_03_3_25_4565_0',
}

XMLIDS_T28_VIEJOS = {
	'pe_datas_t28_50_CAPITAL',
	'pe_datas_t28_51_ACCIONES_DE_INVERSI_N',
	'pe_datas_t28_52_CAPITAL_ADICIONAL',
	'pe_datas_t28_56_RESULTADOS_NO_REALIZADOS',
	'pe_datas_t28_57_EXCEDENTE_DE_REVALUACI_N',
	'pe_datas_t28_58_RESERVAS',
	'pe_datas_t28_59_RESULTADOS_ACUMULADOS',
	'pe_datas_t28_Acciones',
	'pe_datas_t28_Acciones_de_inversi_n',
	'pe_datas_t28_Acciones_de_inversi_n_en_tesorer_a',
	'pe_datas_t28_Acciones_en_tesorer_a',
	'pe_datas_t28_Acreencias',
	'pe_datas_t28_Aportes',
	'pe_datas_t28_Capital_social',
	'pe_datas_t28_Capitalizaciones_en_tr_mite',
	'pe_datas_t28_Contractuales',
	'pe_datas_t28_DESCRIPCI_N',
	'pe_datas_t28_Diferencia_en_cambio_de_inversiones_permanentes_en_entidades_extranjeras',
	'pe_datas_t28_Estatutarias',
	'pe_datas_t28_Excedente_de_revaluaci_n',
	'pe_datas_t28_Excedente_de_revaluaci_n___Acciones_liberadas_recibidas',
	'pe_datas_t28_Facultativas',
	'pe_datas_t28_Ganancia',
	'pe_datas_t28_Ganancia_o_p_rdida_en_activos_o_pasivos_financieros_disponibles_para_la_venta',
	'pe_datas_t28_Ganancia_o_p_rdida_en_activos_o_pasivos_financieros_disponibles_para_la_venta___Compra_o_venta_convencional_fecha_de_liquidaci_n',
	'pe_datas_t28_Gastos_de_a_os_anteriores',
	'pe_datas_t28_Ingresos_de_a_os_anteriores',
	'pe_datas_t28_Inmuebles__maquinaria_y_equipos',
	'pe_datas_t28_Instrumentos_financieros___Cobertura_de_flujo_de_efectivo',
	'pe_datas_t28_Intangibles',
	'pe_datas_t28_Inversiones_inmobiliarias',
	'pe_datas_t28_Legal',
	'pe_datas_t28_Otras_reservas',
	'pe_datas_t28_P_rdida',
	'pe_datas_t28_P_rdidas_acumuladas',
	'pe_datas_t28_Participaci_n_en_excedente_de_revaluaci_n___Inversiones_en_entidades_relacionadas',
	'pe_datas_t28_Participaciones',
	'pe_datas_t28_Primas__descuento__de_acciones',
	'pe_datas_t28_Reducciones_de_capital_pendientes_de_formalizaci_n',
	'pe_datas_t28_Reinversi_n',
	'pe_datas_t28_Reservas',
	'pe_datas_t28_Utilidades',
	'pe_datas_t28_Utilidades_acumuladas',
	'pe_datas_t28_Utilidades_no_distribuidas',
}


def _eliminar_sembrados(cr, xmlids, motivo):
	cr.execute(
		"""
		SELECT imd.id, imd.res_id
		FROM ir_model_data imd
		WHERE imd.module = 'solse_pe_catalogo'
		  AND imd.model = 'pe.datas'
		  AND imd.name = ANY(%s)
		""", (list(xmlids),))
	filas = cr.fetchall()
	if not filas:
		return 0
	imd_ids = [f[0] for f in filas]
	res_ids = [f[1] for f in filas if f[1]]
	if res_ids:
		cr.execute("DELETE FROM pe_datas WHERE id = ANY(%s)", (res_ids,))
	cr.execute("DELETE FROM ir_model_data WHERE id = ANY(%s)", (imd_ids,))
	_logger.info(
		"solse_pe_catalogo pre-migrate: %d registros pe.datas eliminados (%s).",
		len(res_ids), motivo)
	return len(res_ids)


def migrate(cr, version):
	cr.execute(
		"SELECT 1 FROM information_schema.tables WHERE table_name = 'pe_datas'")
	if not cr.fetchone():
		return

	_eliminar_sembrados(
		cr, XMLIDS_T34_DUPLICADOS,
		'duplicados de TABLA34 sembrados por el módulo')
	_eliminar_sembrados(
		cr, XMLIDS_T28_VIEJOS,
		'TABLA28 con code/name invertidos; se recrea corregida al cargar')

	# El xmlid pe_tabla06_62 estaba REPETIDO en pe_datas.xml: definía la
	# unidad YDK (TABLA06) y luego lo pisaba «00 Otros» (TABLA10) — en toda
	# base instalada la fila quedó con los valores del segundo y la unidad
	# YDK no existe. Se restauran los valores correctos en la fila existente
	# (noupdate la dejará en paz) y «00 Otros» se recrea al cargar el XML
	# con su id previsto, pe_tabla10_00. Idempotente: solo si aún tiene los
	# valores pisados.
	cr.execute(
		"""
		UPDATE pe_datas d
		SET code = 'YDK', name = 'YARDA CUADRADA', table_code = 'PE.TABLA06'
		FROM ir_model_data imd
		WHERE imd.module = 'solse_pe_catalogo' AND imd.name = 'pe_tabla06_62'
		  AND imd.model = 'pe.datas' AND imd.res_id = d.id
		  AND d.code = '00' AND d.table_code = 'PE.TABLA10'
		""")
	if cr.rowcount:
		_logger.info(
			'solse_pe_catalogo pre-migrate: restaurada la unidad YDK '
			'(TABLA06) pisada por el xmlid repetido pe_tabla06_62.')

	cr.execute(
		"""
		SELECT code, table_code, count(*)
		FROM pe_datas
		GROUP BY code, table_code
		HAVING count(*) > 1
		""")
	duplicados = cr.fetchall()
	if duplicados:
		detalle = '\n'.join(
			'  - (%s, %s) x%s' % fila for fila in duplicados)
		raise UserError(
			'No se puede actualizar: el catálogo pe.datas tiene registros '
			'duplicados creados fuera del módulo que la restricción de '
			'unicidad (code, table_code) no admite. Resolverlos a mano y '
			'reintentar. Duplicados:\n' + detalle)
	_logger.info(
		'solse_pe_catalogo pre-migrate: pe_datas sin duplicados en '
		'(code, table_code).')
