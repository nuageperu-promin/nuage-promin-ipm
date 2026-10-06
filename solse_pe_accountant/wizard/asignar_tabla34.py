# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

# ─────────────────────────────────────────────────────────────────────────────
# MAPEO PCGE → TABLA 34
#
# Clave: prefijo del código de cuenta (2, 3 o 4 dígitos).
#         Se evalúa del más específico al más general.
# Valor: (código_tabla34, sector, campo_destino)
#   sector: 'ALL' para todos
#   campo_destino: 'esf' | 'resultado' | 'flujos' | 'patrimonio'
#
# Los prefijos más largos tienen prioridad (ej: '104' antes que '10').
# ─────────────────────────────────────────────────────────────────────────────

MAPEO_PCGE = [
    # ── ACTIVOS CORRIENTES ───────────────────────────────────────────────────
    # Efectivo y equivalentes
    ('101', '1D0109', 'ALL', 'esf'),   # Caja
    ('102', '1D0109', 'ALL', 'esf'),   # Fondos fijos
    ('103', '1D0109', 'ALL', 'esf'),   # Dinero en tránsito
    ('104', '1D0109', 'ALL', 'esf'),   # Cuentas corrientes en instituciones financieras
    ('105', '1D0109', 'ALL', 'esf'),   # Otros equivalentes al efectivo
    # Cuentas por cobrar comerciales
    ('121', '1D0103', 'ALL', 'esf'),   # Facturas, boletas - emitidas
    ('122', '1D0103', 'ALL', 'esf'),   # Anticipos de clientes (cobrar)
    ('123', '1D0103', 'ALL', 'esf'),   # Letras por cobrar
    ('124', '1D0103', 'ALL', 'esf'),   # Honorarios por cobrar
    ('129', '1D0103', 'ALL', 'esf'),   # Otras cuentas por cobrar comerciales
    ('12', '1D0103', 'ALL', 'esf'),   # Cuentas por cobrar comerciales - terceros
    ('13', '1D0103', 'ALL', 'esf'),   # Cuentas por cobrar comerciales - relacionadas
    # Cuentas por cobrar personal / accionistas
    ('14', '1D0104', 'ALL', 'esf'),   # Cuentas por cobrar accionistas / socios / personal
    # Cuentas por cobrar diversas
    ('16', '1D0105', 'ALL', 'esf'),   # Cuentas por cobrar diversas - terceros
    ('17', '1D0105', 'ALL', 'esf'),   # Cuentas por cobrar diversas - relacionadas
    # Estimación cobranza dudosa (activo corrector — va en mismo rubro)
    ('19', '1D0103', 'ALL', 'esf'),   # Estimación de cuentas de cobranza dudosa
    # Inventarios
    ('20', '1D0106', 'ALL', 'esf'),   # Mercaderías
    ('21', '1D0106', 'ALL', 'esf'),   # Productos terminados
    ('22', '1D0106', 'ALL', 'esf'),   # Subproductos, desechos y desperdicios
    ('23', '1D0106', 'ALL', 'esf'),   # Productos en proceso
    ('24', '1D0106', 'ALL', 'esf'),   # Materias primas
    ('25', '1D0106', 'ALL', 'esf'),   # Materiales auxiliares, suministros y repuestos
    ('26', '1D0112', 'ALL', 'esf'),   # Envases y embalajes
    ('27', '1D0106', 'ALL', 'esf'),   # Activos no corrientes mantenidos para la venta
    ('28', '1D0106', 'ALL', 'esf'),   # Existencias por recibir
    ('29', '1D0106', 'ALL', 'esf'),   # Desvalorización de existencias
    # Servicios pagados por anticipado / otros activos corrientes
    ('18', '1D0113', 'ALL', 'esf'),   # Servicios y otros contratados por anticipado

    # ── ACTIVOS NO CORRIENTES ────────────────────────────────────────────────
    ('30', '1D0217', 'ALL', 'esf'),   # Inversiones mobiliarias
    ('31', '1D0211', 'ALL', 'esf'),   # Inversiones inmobiliarias
    ('32', '1D0205', 'ALL', 'esf'),   # Activos adquiridos en arrendamiento financiero
    ('333', '1D0205', 'ALL', 'esf'),   # Maquinaria y equipo
    ('334', '1D0205', 'ALL', 'esf'),   # Unidades de transporte
    ('335', '1D0205', 'ALL', 'esf'),   # Muebles y enseres
    ('336', '1D0205', 'ALL', 'esf'),   # Equipos diversos
    ('337', '1D0205', 'ALL', 'esf'),   # Herramientas y unidades de reemplazo
    ('338', '1D0205', 'ALL', 'esf'),   # Unidades por recibir
    ('339', '1D0205', 'ALL', 'esf'),   # Otras propiedades
    ('331', '1D0205', 'ALL', 'esf'),   # Terrenos
    ('332', '1D0205', 'ALL', 'esf'),   # Edificios y otras construcciones
    ('33', '1D0205', 'ALL', 'esf'),   # Inmuebles, maquinaria y equipo (general)
    ('34', '1D0206', 'ALL', 'esf'),   # Intangibles
    ('35', '1D0216', 'ALL', 'esf'),   # Activos biológicos
    ('36', '1D0205', 'ALL', 'esf'),   # Desvalorización de activo inmovilizado
    ('37', '1D0207', 'ALL', 'esf'),   # Activo diferido
    ('38', '1D0208', 'ALL', 'esf'),   # Otros activos
    ('391', '1D0205', 'ALL', 'esf'),   # Depreciación acumulada
    ('392', '1D0206', 'ALL', 'esf'),   # Amortización acumulada
    ('39', '1D0205', 'ALL', 'esf'),   # Depreciación/amortización acumulada

    # ── PASIVOS CORRIENTES ───────────────────────────────────────────────────
    ('40', '1D0311', 'ALL', 'esf'),   # Tributos y aportes al sistema de pensiones por pagar
    ('41', '1D0313', 'ALL', 'esf'),   # Remuneraciones y participaciones por pagar
    ('421', '1D0302', 'ALL', 'esf'),   # Facturas, boletas - emitidas por pagar
    ('422', '1D0302', 'ALL', 'esf'),   # Anticipos a proveedores
    ('423', '1D0302', 'ALL', 'esf'),   # Letras por pagar
    ('424', '1D0302', 'ALL', 'esf'),   # Honorarios por pagar
    ('42', '1D0302', 'ALL', 'esf'),   # Cuentas por pagar comerciales - terceros
    ('43', '1D0302', 'ALL', 'esf'),   # Cuentas por pagar comerciales - relacionadas
    ('44', '1D0304', 'ALL', 'esf'),   # Cuentas por pagar accionistas/socios/directores
    ('451', '1D0309', 'ALL', 'esf'),   # Préstamos de instituciones financieras CP
    ('452', '1D0309', 'ALL', 'esf'),   # Contratos de arrendamiento financiero CP
    ('45', '1D0309', 'ALL', 'esf'),   # Obligaciones financieras
    ('46', '1D0304', 'ALL', 'esf'),   # Cuentas por pagar diversas - terceros
    ('47', '1D0313', 'ALL', 'esf'),   # Beneficios sociales de los trabajadores
    ('48', '1D0310', 'ALL', 'esf'),   # Provisiones
    ('49', '1D0317', 'ALL', 'esf'),   # Pasivo diferido

    # ── PASIVOS NO CORRIENTES ────────────────────────────────────────────────
    # (Odoo diferencia CP/LP por cuenta, no por fecha — se usa el mismo prefijo)
    # En empresas que usan subcuentas LP (45x con diferente nivel) se puede ajustar

    # ── PATRIMONIO ───────────────────────────────────────────────────────────
    ('501', '1D0701', 'ALL', 'patrimonio'),   # Capital social
    ('502', '1D0711', 'ALL', 'patrimonio'),   # Acciones en tesorería
    ('50', '1D0701', 'ALL', 'patrimonio'),   # Capital
    ('511', '1D0703', 'ALL', 'patrimonio'),   # Acciones de inversión
    ('51', '1D0703', 'ALL', 'patrimonio'),   # Acciones de inversión
    ('52', '1D0702', 'ALL', 'patrimonio'),   # Capital adicional
    ('561', '1D0708', 'ALL', 'patrimonio'),   # Excedente de revaluación
    ('563', '1D0708', 'ALL', 'patrimonio'),   # Diferencias de conversión
    ('564', '1D0708', 'ALL', 'patrimonio'),   # Ajustes al patrimonio
    ('56', '1D0708', 'ALL', 'patrimonio'),   # Resultados no realizados / Otras reservas patrimonio
    ('571', '1D0712', 'ALL', 'patrimonio'),   # Reserva legal
    ('572', '1D0712', 'ALL', 'patrimonio'),   # Reserva estatutaria
    ('573', '1D0712', 'ALL', 'patrimonio'),   # Reserva facultativa
    ('57', '1D0712', 'ALL', 'patrimonio'),   # Excedente de revaluación
    ('58', '1D0712', 'ALL', 'patrimonio'),   # Reservas
    ('591', '1D0707', 'ALL', 'patrimonio'),   # Utilidades no distribuidas
    ('592', '1D0707', 'ALL', 'patrimonio'),   # Pérdidas acumuladas
    ('59', '1D0707', 'ALL', 'patrimonio'),   # Resultados acumulados

    # ── INGRESOS (Estado de Resultados) ─────────────────────────────────────
    ('70', '2D01ST', 'ALL', 'resultado'),   # Ventas
    ('71', '2D01ST', 'ALL', 'resultado'),   # Variación de la producción almacenada
    ('72', '2D01ST', 'ALL', 'resultado'),   # Producción de activo inmovilizado
    ('73', '2D01ST', 'ALL', 'resultado'),   # Descuentos, rebajas y bonificaciones obtenidas
    ('74', '2D01ST', 'ALL', 'resultado'),   # Descuentos, rebajas y bonificaciones concedidos
    ('75', '2D0403', 'ALL', 'resultado'),   # Otros ingresos de gestión
    ('76', '2D0403', 'ALL', 'resultado'),   # Ganancia por medición a valor razonable
    ('77', '2D0401', 'ALL', 'resultado'),   # Ingresos financieros

    # ── COSTOS Y GASTOS ──────────────────────────────────────────────────────
    ('69', '2D0201', 'ALL', 'resultado'),   # Costo de ventas
    ('62', '2D0301', 'ALL', 'resultado'),   # Gastos de personal, directores y gerentes
    ('63', '2D0301', 'ALL', 'resultado'),   # Gastos de servicios prestados por terceros
    ('64', '2D0301', 'ALL', 'resultado'),   # Gastos por tributos
    ('65', '2D0404', 'ALL', 'resultado'),   # Otros gastos de gestión
    ('66', '2D0404', 'ALL', 'resultado'),   # Pérdida por medición a valor razonable
    ('67', '2D0402', 'ALL', 'resultado'),   # Gastos financieros
    ('68', '2D0201', 'ALL', 'resultado'),   # Valuación y deterioro de activos y provisiones
    # 60 y 61 son compras/variación inventarios — no van directo a EEFF
]


class WizardAsignarTabla34(models.TransientModel):
	_name = 'solse.wizard.asignar.tabla34'
	_description = 'Asignación masiva de Rubros EEFF (Tabla 34) al Plan de Cuentas'

	sector = fields.Selection(
		related='company_id.sector_contable',
		readonly=True,
		string='Sector contable',
	)
	company_id = fields.Many2one(
		comodel_name='res.company',
		string='Empresa',
		default=lambda self: self.env.company,
		required=True,
	)
	solo_sin_rubro = fields.Boolean(
		string='Solo asignar cuentas sin rubro',
		default=True,
		help=(
			'Activo: solo se asigna rubro a las cuentas que aún no tienen ninguno. '
			'Inactivo: sobreescribe todas las cuentas, incluyendo las ya configuradas.'
		),
	)
	# Campos informativos (calculados al confirmar preview)
	total_cuentas = fields.Integer(string='Total cuentas en el plan', readonly=True)
	cuentas_sin_rubro = fields.Integer(string='Cuentas sin rubro', readonly=True)
	cuentas_a_asignar = fields.Integer(string='Cuentas que se asignarán', readonly=True)
	preview_calculado = fields.Boolean(default=False)

	def _calcular_preview(self):
		"""Calcula cuántas cuentas se verán afectadas."""
		sector = self.company_id.sector_contable or '01'
		todas = self.env['account.account'].search([
			('company_ids', 'in', [self.company_id.id]),
		])
		sin_rubro = todas.filtered(lambda a: not a.pe_t34_esf and not a.pe_t34_resultado and not a.pe_t34_flujos and not a.pe_t34_patrimonio)

		# Simular cuántas matchean el mapeo
		a_asignar = self._simular_mapeo(
			sin_rubro if self.solo_sin_rubro else todas,
			sector,
		)
		self.total_cuentas = len(todas)
		self.cuentas_sin_rubro = len(sin_rubro)
		self.cuentas_a_asignar = a_asignar
		self.preview_calculado = True

	def _simular_mapeo(self, cuentas, sector):
		"""Retorna cuántas cuentas matchean el mapeo sin aplicar cambios."""
		cache_rubros = self._cargar_cache_rubros(sector)
		total = 0
		for cuenta in cuentas:
			rubro, _ = self._buscar_rubro(cuenta.code or '', cache_rubros)
			if rubro:
				total += 1
		return total

	def _cargar_cache_rubros(self, sector):
		"""
		Carga todos los rubros PE.TABLA34 del sector en un dict {code: record}
		para evitar queries dentro del loop de cuentas.
		"""
		rubros = self.env['pe.datas'].search([
			('table_code', '=', 'PE.TABLA34'),
			('un_ece_code', '=', sector),
		])
		return {r.code: r for r in rubros}

	def _buscar_rubro(self, codigo_cuenta, cache_rubros):
		"""
		Busca el rubro y campo destino para el código de cuenta dado.
		Retorna (record_pe_datas, campo_destino) o (False, False).
		campo_destino: 'esf' | 'resultado' | 'flujos' | 'patrimonio'
		"""
		if not codigo_cuenta:
			return False, False
		mapeo_ordenado = sorted(MAPEO_PCGE, key=lambda x: len(x[0]), reverse=True)
		for prefijo, codigo_t34, sector_t34, campo_destino in mapeo_ordenado:
			if codigo_cuenta.startswith(prefijo):
				rubro = cache_rubros.get(codigo_t34)
				if rubro:
					return rubro, campo_destino
		return False, False

	def action_preview(self):
		"""Calcula el preview sin aplicar cambios."""
		self._calcular_preview()
		# Reabrir el wizard para mostrar resultados
		return {
			'type': 'ir.actions.act_window',
			'res_model': self._name,
			'res_id': self.id,
			'view_mode': 'form',
			'target': 'new',
		}

	def action_asignar(self):
		"""Aplica el mapeo masivo."""
		sector = self.company_id.sector_contable or '01'
		cache_rubros = self._cargar_cache_rubros(sector)

		if not cache_rubros:
			raise UserError(
				'No se encontraron rubros de la Tabla 34 para el sector "%s". '
				'Verifique que el archivo pe_datas_tabla28_tabla34.xml esté '
				'instalado en el módulo solse_pe_catalogo.' % sector
			)

		cuentas = self.env['account.account'].search([
			('company_ids', 'in', [self.company_id.id]),
		])
		if self.solo_sin_rubro:
			cuentas = cuentas.filtered(lambda a: not a.pe_t34_esf and not a.pe_t34_resultado and not a.pe_t34_flujos and not a.pe_t34_patrimonio)

		asignadas = 0
		sin_match = 0
		conteo_campo = {
			'pe_t34_esf': 0,
			'pe_t34_resultado': 0,
			'pe_t34_patrimonio': 0,
			'pe_t34_flujos': 0,
		}

		CAMPO_MAP = {
			'esf':        'pe_t34_esf',
			'resultado':  'pe_t34_resultado',
			'flujos':     'pe_t34_flujos',
			'patrimonio': 'pe_t34_patrimonio',
		}
		for cuenta in cuentas:
			rubro, campo_destino = self._buscar_rubro(cuenta.code or '', cache_rubros)
			if rubro and campo_destino in CAMPO_MAP:
				nombre_campo = CAMPO_MAP[campo_destino]
				setattr(cuenta, nombre_campo, rubro)
				conteo_campo[nombre_campo] += 1
				asignadas += 1
			else:
				sin_match += 1

		# Mensaje de resultado con desglose por campo
		mensaje = (
			f'Asignación completada — {asignadas} cuentas procesadas:\n\n'
			f'• Situación Financiera (3.1): {conteo_campo["pe_t34_esf"]} cuentas (activos/pasivos)\n'
			f'• Estado de Resultados (3.20/3.24): {conteo_campo["pe_t34_resultado"]} cuentas (ingresos/gastos)\n'
			f'• Cambios en Patrimonio (3.19): {conteo_campo["pe_t34_patrimonio"]} cuentas (ctas. 50x-59x)\n'
			f'• Flujos de Efectivo (3.18/3.25): {conteo_campo["pe_t34_flujos"]} cuentas (configuración manual)\n\n'
			f'⚠️  {sin_match} sin coincidencia (cuentas de orden 0x u otras fuera del PCGE).\n\n'
			f'Cada cuenta recibe UN campo según su tipo. '
			f'Verifique una cuenta 70xx para ver pe_t34_resultado, '
			f'y una cuenta 50xx para pe_t34_patrimonio.'
		)

		return {
			'type': 'ir.actions.client',
			'tag': 'display_notification',
			'params': {
				'title': 'Tabla 34 — Asignación masiva completada',
				'message': mensaje,
				'type': 'success',
				'sticky': True,
			},
		}
