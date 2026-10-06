# -*- coding: utf-8 -*-

# Maestros normativos SUNAT/MTPE para la nómina peruana.
# Fuente de códigos: Anexo 2 - Tablas paramétricas PLAME (T8, T11, T12,
# T17, T19, T24, T30, T33, T35) y Manual T-Registro RM 170-2023-TR.

from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models


class RegimenSalud(models.Model):
	_name = 'health.regime'
	_description = 'Régimen de Salud (T32)'
	_order = 'code'

	code = fields.Char(string='Código')
	health_description = fields.Char(string='Descripción')
	name = fields.Char(string='Abreviatura')


class GradoAcademico(models.Model):
	_name = 'academic.degree'
	_description = 'Situación educativa (T9)'
	_order = 'code'

	code = fields.Char(string='Código')
	academic_description = fields.Char(string='Descripción')
	name = fields.Char(string='Abreviatura')


class MotivoBaja(models.Model):
	_name = 'low.reason'
	_description = 'Motivo fin del periodo (T17)'
	_order = 'code'

	code = fields.Char(string='Código')
	low_reason_description = fields.Char(string='Descripción')
	name = fields.Char(string='Abreviatura')


class ContratoMintra(models.Model):
	_name = 'mintra.contract'
	_description = 'Tipo de Contrato - MINTRA (T12)'
	_order = 'code'

	code = fields.Char(string='Código')
	mintra_description = fields.Char(string='Descripción')

	@api.depends('code', 'mintra_description')
	def _compute_display_name(self):
		for registro in self:
			registro.display_name = "[%s] %s" % (registro.code or '', registro.mintra_description or '')


class SituacionEspecial(models.Model):
	_name = 'special.situation'
	_description = 'Situación especial (T35)'
	_order = 'code'

	code = fields.Char(string='Código')
	situation_description = fields.Char(string='Descripción')
	name = fields.Char(string='Abreviatura')


class TipoContrato(models.Model):
	_name = 'type.contract'
	_description = 'Condición laboral / Tipo de trabajador (T8)'
	_order = 'code'

	code = fields.Char(string='Código')
	contract_type = fields.Char(string='Tipo de Contrato')
	name = fields.Char(string='Abreviatura')


class PagoVariable(models.Model):
	_name = 'variable.payment'
	_description = 'Remuneración variable'
	_order = 'code'

	code = fields.Char(string='Código')
	name = fields.Char(string='Descripción')


class OcupacionLaboral(models.Model):
	_name = 'work.occupation'
	_description = 'Ocupación laboral (T30)'
	_order = 'code'

	code = fields.Char(string='Código')
	name = fields.Char(string='Nombre')
	executive = fields.Boolean(string='Ejecutivo')
	employee = fields.Boolean(string='Empleado')
	worker = fields.Boolean(string='Obrero')


class TipoPago(models.Model):
	_name = 'payment.type'
	_description = 'Tipo de pago (T16)'
	_order = 'code'

	code = fields.Char(string='Código')
	payment_description = fields.Char(string='Descripción')
	name = fields.Char(string='Abreviatura')


class SistemaPensionario(models.Model):
	_name = 'pension.system'
	_description = 'Régimen pensionario (T11)'
	_order = 'code'

	code = fields.Char(string='Código')
	pension_system = fields.Char(string='Régimen Pensionario')
	name = fields.Char(string='Abreviatura')
	private_sector = fields.Boolean(string='Sector Privado')
	public_sector = fields.Boolean(string='Sector Público')
	other_entities = fields.Boolean(string='Otras entidades')
	cuspp = fields.Boolean(
		string='CUSPP',
		help='Indica si el régimen exige CUSPP (afiliados al Sistema Privado de Pensiones).'
	)
	clave_afp = fields.Selection(
		selection=[
			('habitat', 'Habitat'),
			('integra', 'Integra'),
			('prima', 'Prima'),
			('profuturo', 'Profuturo'),
		],
		string='Clave AFP',
		help='Solo para regímenes SPP. Vincula el registro con las tasas de comisión '
			 'del parámetro de nómina pe_afp_comision_flujo; las tasas NO se guardan '
			 'aquí sino en Parámetros de Nómina (hr.rule.parameter) versionados por fecha.'
	)


class VidaLey(models.Model):
	_name = 'life.insurance'
	_description = 'Vida Ley (D.Leg. 688)'

	name = fields.Char(string='Entidad', required=True)
	nro = fields.Char(string='N° Póliza')
	start_date = fields.Date(string='Fecha inicio vigencia')
	end_date = fields.Date(string='Fecha fin vigencia')
	hiring_term = fields.Char(string='Plazo de contratación')
	rate = fields.Float(string='Tasa', digits=(16, 4))
	amount = fields.Float(string='Importe')
	employees_ids = fields.One2many(
		comodel_name='hr.employee',
		inverse_name='life_insurance_id',
		string='Empleados'
	)


class RegimenLaboral(models.Model):
	_name = 'employee.regime'
	_description = 'Régimen laboral (T33)'
	_order = 'code'

	code = fields.Char(string='Código')
	regime_description = fields.Char(string='Descripción')
	name = fields.Char(string='Abreviatura')
	private_sector = fields.Boolean(string='Sector privado')
	public_sector = fields.Boolean(string='Sector público')
	other_entities = fields.Boolean(string='Otras entidades')
	is_mype = fields.Boolean(string='¿Es MYPE?')
	clave_regimen = fields.Selection(
		selection=[
			('general', 'Régimen General'),
			('pequena', 'Pequeña Empresa'),
			('micro', 'Microempresa'),
			('agrario', 'Agrario (Ley 31110)'),
			('otro', 'Otro'),
		],
		string='Clave de cálculo',
		default='general',
		required=True,
		help='Determina los factores de gratificación, CTS y vacaciones que las reglas '
			 'salariales leen del parámetro pe_regimen_factores. El régimen general usa '
			 '(1.0, 30, 30); pequeña empresa (0.5, 15, 15); microempresa (0.0, 0, 15).'
	)


class ParentescoFamiliar(models.Model):
	_name = 'hr.employee.relative.relation'
	_description = 'Vínculo familiar (T19)'

	name = fields.Char(string='Parentesco', required=True, translate=True)


class Derechohabiente(models.Model):
	_name = 'hr.employee.relative'
	_description = 'Derechohabiente / Pariente del empleado'

	employee_id = fields.Many2one(string='Empleado', comodel_name='hr.employee')
	relation_id = fields.Many2one(
		'hr.employee.relative.relation', string='Parentesco', required=True)
	name = fields.Char(string='Nombre', required=True)
	partner_id = fields.Many2one(
		'res.partner', string='Contacto',
		domain=["&", ("is_company", "=", False), ("type", "=", "contact")])
	gender = fields.Selection(
		string='Género',
		selection=[('masculino', 'Masculino'), ('femenino', 'Femenino'), ('otro', 'Otro')])
	date_of_birth = fields.Date(string='Fecha de nacimiento')
	age = fields.Float(string='Edad', compute='_compute_age')
	job = fields.Char(string='Profesión')
	phone_number = fields.Char(string='Teléfono')
	notes = fields.Text(string='Notas')
	percentage_eps = fields.Integer(string='% EPS')
	tax_eps = fields.Integer(string='Imp. EPS')
	payer_eps = fields.Boolean(string='Pagador EPS')
	disability = fields.Boolean(string='Discapacidad')
	max_age = fields.Integer(string='Edad máx.')

	@api.depends('date_of_birth')
	def _compute_age(self):
		for registro in self:
			if not registro.date_of_birth:
				registro.age = 0
				continue
			edad = relativedelta(datetime.now(), registro.date_of_birth)
			registro.age = edad.years + (edad.months / 12)

	@api.onchange('partner_id')
	def _onchange_partner_id(self):
		if self.partner_id:
			self.name = self.partner_id.display_name


class GestionEPS(models.Model):
	_name = 'eps.management'
	_description = 'Gestión EPS'

	star_date = fields.Date(string='Fecha de inicio', required=True)
	finish_date = fields.Date(string='Fecha de finalización', required=True)
	entity = fields.Char(string='Entidad', required=True)
	insurance = fields.Char(string='N° de póliza')
	rate_employer = fields.Float(string='Tasa empleador')
	amount_employer = fields.Float(string='Importe empleador')
	rate_worker = fields.Float(string='Tasa trabajador')
	amount_worker = fields.Float(string='Importe trabajador')
	employeer_ids = fields.One2many('hr.employee', 'management_eps', string='Empleados')


class ConceptoPlame(models.Model):
	_name = 'plame.lines'
	_description = 'Concepto PLAME (T22 - Ingresos, Tributos y Descuentos)'
	_order = 'code'

	code = fields.Char(string='Código')
	name = fields.Char(string='Descripción del concepto')
	essalud_seguro_regular = fields.Boolean(string='ESSALUD Seguro Regular Trabajador')
	essalud_cbssp = fields.Boolean(string='ESSALUD - CBSSP - Seg. Trab. Pesquero')
	essalud_seguro_agrario = fields.Boolean(string='ESSALUD Seguro Agrario / Acuicultor')
	essalud_sctr = fields.Boolean(string='ESSALUD SCTR')
	imp_extra_solidaridad = fields.Boolean(string='Impuesto Extraord. de Solidaridad')
	fondo_der_artista = fields.Boolean(string='Fondo Derechos Sociales del Artista')
	senati = fields.Boolean(string='SENATI')
	sistema_nacional_pensiones = fields.Boolean(string='Sistema Nacional de Pensiones 19990')
	sistema_privado_pensiones = fields.Boolean(string='Sistema Privado de Pensiones')
	fondo_compl_jub = fields.Boolean(string='Fondo Compl. de Jubil. Min., Met. y Sider.')
	reg_esp_pesquero = fields.Boolean(string='Rég. Esp. Pensiones Trab. Pesquero')
	rent5ta = fields.Boolean(string='Renta 5ta Categoría Retenciones')
	essalud_regular_pension = fields.Boolean(string='ESSALUD Seguro Regular Pensionista')
	contrib_sol_asist = fields.Boolean(string='Contrib. Solidaria Asistencia Previs.')

	@api.depends('code', 'name')
	def _compute_display_name(self):
		for registro in self:
			registro.display_name = "[%s] %s" % (registro.code or '', registro.name or '')
