# -*- coding: utf-8 -*-

# Las reglas se definen UNA sola vez en la estructura "Reglas Básicas" y
# este inicializador las replica a las estructuras operativas (mensual,
# semanal, etc.) porque en Odoo 19 struct_id es obligatorio y 1:1.
#
# Idempotente: si la regla (por código) ya existe en la estructura destino,
# no se toca — el administrador puede haberla personalizado.

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Estructura destino -> códigos EXCLUIDOS al copiar desde la base.
# (Todo lo demás de la base se replica.)
EXCLUSIONES_POR_ESTRUCTURA = {
	'solse_pe_payroll.hr_payroll_structure_mensual_empleados': ['RBS_002'],
	'solse_pe_payroll.hr_payroll_structure_semanal_obreros': ['RB_001'],
	# Vacaciones: la boleta paga VAC_001 (definida en su estructura) con
	# los aportes replicados; se excluyen los conceptos de la planilla
	# regular. R5TA se excluye para no duplicar la retención del mes (la
	# proyección de la mensual ya incorpora la vacacional vía BAR5_001).
	'solse_pe_payroll.hr_payroll_structure_vacaciones': [
		'RB_001', 'RBS_002', 'ASF_001', 'HE25_001', 'HE35_001', 'MOV_001',
		'DESC_ADEL_001', 'DJ_001', 'SIND_001', 'R5TA_001'],
}


class SolsePayrollInicializador(models.AbstractModel):
	_name = 'solse.payroll.inicializador'
	_description = 'Inicializador de estructuras salariales PE'

	ESTRUCTURAS_XMLIDS = [
		'solse_pe_payroll.hr_payroll_structure_base',
		'solse_pe_payroll.hr_payroll_structure_mensual_empleados',
		'solse_pe_payroll.hr_payroll_structure_semanal_obreros',
		'solse_pe_payroll.hr_payroll_structure_quincenal_adelanto',
		'solse_pe_payroll.hr_payroll_structure_gratificaciones',
		'solse_pe_payroll.hr_payroll_structure_cts',
		'solse_pe_payroll.hr_payroll_structure_vacaciones',
		'solse_pe_payroll.hr_payroll_structure_liquidacion',
	]

	@api.model
	def estructuras_solse(self):
		estructuras = self.env['hr.payroll.structure']
		for xmlid in self.ESTRUCTURAS_XMLIDS:
			registro_id = self.env.ref(xmlid, raise_if_not_found=False)
			if registro_id:
				estructuras |= registro_id
		return estructuras

	# Campos que se mantienen sincronizados desde la regla de la estructura
	# base hacia sus copias en las estructuras operativas. El código de
	# cálculo es responsabilidad del módulo: los fixes de fórmulas deben
	# llegar a las copias en cada actualización.
	CAMPOS_SINCRONIZADOS = [
		'name', 'sequence', 'category_id', 'amount_select',
		'amount_python_compute', 'appears_on_payslip', 'note', 'utilities',
		'condition_select', 'condition_python',
	]

	@api.model
	def replicar_reglas_base(self):
		base_id = self.env.ref(
			'solse_pe_payroll.hr_payroll_structure_base', raise_if_not_found=False)
		if not base_id or not base_id.rule_ids:
			return
		for xmlid, excluidos in EXCLUSIONES_POR_ESTRUCTURA.items():
			destino_id = self.env.ref(xmlid, raise_if_not_found=False)
			if not destino_id:
				continue
			reglas_destino = {r.code: r for r in destino_id.rule_ids}
			nuevas, sincronizadas = 0, 0
			for regla_id in base_id.rule_ids:
				if regla_id.code in excluidos:
					continue
				copia_id = reglas_destino.get(regla_id.code)
				if not copia_id:
					regla_id.copy(default={
						'struct_id': destino_id.id,
						'name': regla_id.name,  # evitar sufijo "(copy)"
					})
					nuevas += 1
					continue
				# Sincronizar definicion desde la base (fixes de formulas)
				valores = {}
				for campo in self.CAMPOS_SINCRONIZADOS:
					valor_base = regla_id[campo]
					if campo == 'category_id':
						if copia_id.category_id != valor_base:
							valores[campo] = valor_base.id
					elif copia_id[campo] != valor_base:
						valores[campo] = valor_base
				# m2m de conceptos PLAME (las copias no lo heredan)
				if set(copia_id.plame_ids.ids) != set(regla_id.plame_ids.ids):
					valores['plame_ids'] = [(6, 0, regla_id.plame_ids.ids)]
				if valores:
					copia_id.write(valores)
					sincronizadas += 1
			if nuevas or sincronizadas:
				_logger.info(
					'Nómina PE: estructura "%s": %s reglas nuevas, %s sincronizadas.',
					destino_id.name, nuevas, sincronizadas)

	@api.model
	def asignar_inputs(self):
		"""Publica los tipos de input PE en las estructuras (el dropdown de
		'Entradas salariales' del payslip filtra por struct_id.input_line_type_ids).
		Idempotente: los link (4) de m2m no duplican."""
		inputs_por_estructura = {
			'solse_pe_payroll.hr_payroll_structure_base': [
				'RBM_001', 'RBS_002', 'ASF_001', 'MOV_001', 'HE25_001', 'HE35_001'],
			'solse_pe_payroll.hr_payroll_structure_mensual_empleados': [
				'RBM_001', 'ASF_001', 'MOV_001', 'HE25_001', 'HE35_001'],
			'solse_pe_payroll.hr_payroll_structure_semanal_obreros': [
				'RBS_002', 'ASF_001', 'MOV_001', 'HE25_001', 'HE35_001'],
			'solse_pe_payroll.hr_payroll_structure_gratificaciones': [
				'GRATI_001'],
			'solse_pe_payroll.hr_payroll_structure_cts': [
				'CTS_001'],
			'solse_pe_payroll.hr_payroll_structure_quincenal_adelanto': [
				'ADEL_001'],
			'solse_pe_payroll.hr_payroll_structure_vacaciones': [
				'VAC_001'],
			'solse_pe_payroll.hr_payroll_structure_liquidacion': [
				'VAC_TRUNCA_001', 'GRATI_TRUNCA_001', 'CTS_TRUNCA_001'],
		}
		TipoInput = self.env['hr.payslip.input.type']
		for xmlid, codigos in inputs_por_estructura.items():
			estructura_id = self.env.ref(xmlid, raise_if_not_found=False)
			if not estructura_id:
				continue
			tipos = TipoInput.search([('code', 'in', codigos)])
			faltantes = tipos - estructura_id.input_line_type_ids
			if faltantes:
				estructura_id.input_line_type_ids = [(4, t.id) for t in faltantes]

	@api.model
	def asignar_diarios(self):
		"""Asigna el diario de salarios (company_dependent) a las estructuras
		SOLSE en cada compañía peruana donde esté vacío. Toma el diario de la
		estructura nativa (creado por el chart template de hr_payroll_account)
		y, en su defecto, busca un diario general de nómina."""
		estructura_nativa_id = self.env.ref(
			'hr_payroll.default_structure', raise_if_not_found=False)
		estructuras = self.estructuras_solse()
		if not estructuras:
			return
		# res.company.country_id no es almacenado en v19: filtrar en Python
		pe_id = self.env.ref('base.pe')
		companias = self.env['res.company'].search([]).filtered(
			lambda c: c.country_id == pe_id)
		for compania in companias:
			diario_id = estructura_nativa_id.with_company(compania).journal_id \
				if estructura_nativa_id else self.env['account.journal']
			if not diario_id:
				diario_id = self.env['account.journal'].with_company(compania).search([
					('type', '=', 'general'),
					('company_id', '=', compania.id),
					'|', ('code', '=ilike', 'SLR%'),
					('name', 'ilike', 'nómina'),
				], limit=1)
			if not diario_id:
				continue
			# Cuenta predeterminada del diario: requerida por el motor
			# contable de nómina (redondeos y conceptos sin mapear caen
			# ahí). Default razonable: gasto de remuneraciones 6211.
			if not diario_id.default_account_id:
				cuenta_id = self.env['account.account'].with_company(
					compania).search([
						('code', '=like', '6211%'),
						('company_ids', 'in', compania.id),
					], order='code asc', limit=1)
				if cuenta_id:
					diario_id.default_account_id = cuenta_id
			for estructura_id in estructuras.with_company(compania):
				if not estructura_id.journal_id:
					estructura_id.journal_id = diario_id

	# Catálogos SUNAT con códigos numéricos de 2 dígitos que deben llevar
	# cero inicial (los archivos PLAME/T-Registro los exigen así).
	MODELOS_CODIGO_2_DIGITOS = [
		'pension.system', 'type.contract', 'academic.degree',
		'low.reason', 'employee.regime',
	]

	@api.model
	def normalizar_codigos_catalogos(self):
		"""Corrige códigos sin cero inicial en bases ya instaladas (la data
		de catálogos es noupdate=1 y la actualización del XML no los toca)."""
		for modelo in self.MODELOS_CODIGO_2_DIGITOS:
			registros = self.env[modelo].search([])
			for registro_id in registros:
				codigo = registro_id.code or ''
				if codigo.isdigit() and len(codigo) == 1:
					registro_id.code = codigo.zfill(2)

	# Códigos de reglas de INGRESO: en el motor contable v19 cada regla
	# genera una línea por cada cuenta configurada, por lo que los ingresos
	# deben llevar SOLO cuenta débito (el crédito del neto lo pone NET y el
	# de las retenciones cada regla de descuento). Un crédito 4111 en los
	# ingresos duplica el pasivo y fuerza la línea de ajuste del diario.
	CODIGOS_INGRESO_SOLO_DEBITO = [
		'RB_001', 'RBS_002', 'ASF_001', 'HE25_001', 'HE35_001', 'MOV_001',
	]

	@api.model
	def corregir_mapeo_ingresos(self):
		"""Migración idempotente: retira el prefijo crédito de los mapeos
		de ingresos y limpia el account_credit 41xx que corridas previas
		hubieran escrito en esas reglas (solo si apunta a 4111, para no
		tocar configuraciones manuales distintas)."""
		Mapeo = self.env['solse.payroll.mapeo.contable']
		mapeos = Mapeo.search([
			('codigo_regla', 'in', self.CODIGOS_INGRESO_SOLO_DEBITO),
			('prefijo_credito', '=', '4111'),
		])
		if mapeos:
			mapeos.prefijo_credito = False
		estructuras = self.estructuras_solse()
		reglas = self.env['hr.salary.rule'].search([
			('code', 'in', self.CODIGOS_INGRESO_SOLO_DEBITO),
			('struct_id', 'in', estructuras.ids),
		])
		pe_id = self.env.ref('base.pe')
		companias = self.env['res.company'].search([]).filtered(
			lambda c: c.country_id == pe_id)
		for compania in companias:
			for regla_id in reglas.with_company(compania):
				cuenta_id = regla_id.account_credit
				if cuenta_id and (cuenta_id.code or '').startswith('4111'):
					regla_id.account_credit = False

	@api.model
	def configurar_vacaciones_no_pagadas(self):
		"""Marca el work entry "Vacaciones PE" como NO pagado en las
		estructuras mensual y semanal: el mes del goce descuenta esos días
		(la boleta de vacaciones separada es la que los paga)."""
		tipo_id = self.env.ref(
			'solse_pe_payroll.work_entry_type_vacaciones_pe',
			raise_if_not_found=False)
		if not tipo_id:
			return
		for xmlid in (
			'solse_pe_payroll.hr_payroll_structure_mensual_empleados',
			'solse_pe_payroll.hr_payroll_structure_semanal_obreros',
		):
			estructura_id = self.env.ref(xmlid, raise_if_not_found=False)
			if estructura_id and tipo_id not in estructura_id.unpaid_work_entry_type_ids:
				estructura_id.unpaid_work_entry_type_ids = [(4, tipo_id.id)]

	@api.model
	def inicializar_todo(self):
		"""Punto de entrada único, invocado por el post_init_hook y por el tag
		<function> del data (que sí corre en cada actualización del módulo)."""
		self.normalizar_codigos_catalogos()
		self.corregir_mapeo_ingresos()
		self.replicar_reglas_base()
		self.configurar_vacaciones_no_pagadas()
		self.asignar_inputs()
		self.asignar_diarios()
		self.env['solse.payroll.mapeo.contable'].aplicar_todas_las_companias()
		_logger.info('Nómina PE: inicialización de estructuras completada.')
