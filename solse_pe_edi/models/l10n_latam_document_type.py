# -*- coding: utf-8 -*-

from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError, RedirectWarning
import logging
_logging = logging.getLogger(__name__)


class L10nLatamDocumentType(models.Model):
	_inherit = 'l10n_latam.document.type'

	company_id = fields.Many2one(
		comodel_name='res.company',
		string='Compañía',
		required=True,
		default=lambda self: self.env.user.company_id
	)
	is_cpe = fields.Boolean('Es un CPE', help="Es un comprobante electrónico")
	sub_type = fields.Selection(
		[('sale', 'Ventas'), ('purchase', 'Compras')],
		string="Sub tipo"
	)
	is_synchronous = fields.Boolean("Es síncrono", default=True)
	is_synchronous_anull = fields.Boolean("Anulación síncrona", default=True)
	nota_credito = fields.Many2one(
		'l10n_latam.document.type',
		string='Nota crédito',
		domain="[('code', '=', '07'), ('company_id', '=', company_id)]"
	)
	nota_debito = fields.Many2one(
		'l10n_latam.document.type',
		string='Nota débito',
		domain="[('code', '=', '08'), ('company_id', '=', company_id)]"
	)
	usar_prefijo_personalizado = fields.Boolean('Personalizar prefijo')
	usar_prefijo_sin_localizacion = fields.Boolean(
		'Usar prefijo sin localización',
		help="Si está marcado, el comprobante usará el formato nativo de Odoo "
			 "según el diario (ej. BILL/2026/06/00001), sin pasar por la "
			 "localización LATAM (que normalmente fuerza el formato "
			 "'<doc_code_prefix> <correlativo>'). Útil para facturas de compra "
			 "donde el correlativo interno debe ser por diario. "
			 "Mutuamente excluyente con 'Personalizar prefijo'."
	)
	prefijo = fields.Char('Prefijo', copy=False)
	correlativo_inicial = fields.Integer(
		'Correlativo inicial',
		default=1,
		help="Correlativo usado para el primer comprobante emitido con este tipo de documento"
	)
	secuencia_id = fields.Many2one("ir.sequence", string="Secuencia", copy=False)
	sequence_number_next = fields.Integer(
		string='Número siguiente',
		help='El siguiente número de secuencia se utilizará para el próximo comprobante.',
		compute='_compute_seq_number_next',
		inverse='_inverse_seq_number_next'
	)

	@api.depends('secuencia_id.use_date_range', 'secuencia_id.number_next_actual')
	def _compute_seq_number_next(self):
		for reg in self:
			if reg.secuencia_id:
				sequence = reg.secuencia_id._get_current_sequence()
				reg.sequence_number_next = sequence.number_next_actual
			else:
				reg.sequence_number_next = 1

	def _inverse_seq_number_next(self):
		"""Invierte 'sequence_number_next' para editar el siguiente número de la secuencia actual."""
		for reg in self:
			if reg.secuencia_id and reg.sequence_number_next:
				sequence = reg.secuencia_id._get_current_sequence()
				sequence.sudo().number_next = reg.sequence_number_next

	@api.model_create_multi
	def create(self, vals_list):
		for vals in vals_list:
			if not vals.get('secuencia_id') and vals.get('usar_prefijo_personalizado') and vals.get('prefijo'):
				vals.update({'secuencia_id': self.sudo()._create_sequence(vals).id})

		return super(L10nLatamDocumentType, self).create(vals_list)

	def crear_secuencia(self):
		if not self.prefijo:
			raise UserError("No tiene un prefijo establecido")
		if self.usar_prefijo_personalizado and not self.secuencia_id and self.prefijo:
			datos_prefijo = {'prefijo': self.prefijo}
			ultimo_numero = self.obtener_ultimo_numero()
			if ultimo_numero:
				datos_prefijo['sequence_number_next'] = ultimo_numero + 1
			seq = self._create_sequence(datos_prefijo)
			self.secuencia_id = seq

	def obtener_ultimo_numero(self):
		"""
		CORREGIDO para Odoo 19:
		- l10n_latam_document_number ya no está stored
		- sequence_number no existe
		- Usar name para ordenar y extraer número
		"""
		# Buscar facturas con este tipo de documento
		facturas = self.env['account.move'].search([
			('state', '!=', 'draft'),
			('l10n_latam_document_type_id', '=', self.id),
			('name', '!=', False),
			('name', '!=', '/')
		], order="id desc", limit=100)  # Obtener últimas 100 para filtrar
		
		if not facturas:
			return 0
		
		# Filtrar y obtener el número más alto
		numeros = []
		for factura in facturas:
			try:
				# El formato típico es: SERIE-NUMERO (ej: F001-00000123)
				if factura.name and '-' in factura.name:
					partes = factura.name.split('-')
					if len(partes) >= 2:
						numero_str = partes[-1]  # Última parte después del guión
						numero = int(numero_str)
						numeros.append(numero)
			except (ValueError, IndexError):
				continue
		
		if numeros:
			return max(numeros)
		
		return 0

	def reasignar_ultimo_numero(self):
		"""CORREGIDO para Odoo 19"""
		ultimo_numero = self.obtener_ultimo_numero()
		self.sequence_number_next = ultimo_numero + 1 if ultimo_numero else 1

	@api.model
	def _get_sequence_prefix(self, code):
		prefix = code.upper()
		return prefix + '-'

	@api.model
	def _create_sequence(self, vals):
		"""Crear secuencia sin gap para cada tipo de documento"""
		prefix = self._get_sequence_prefix(vals['prefijo'])
		seq_name = vals['prefijo']
		seq = {
			'name': '%s Secuencia' % seq_name,
			'implementation': 'no_gap',
			'prefix': prefix,
			'padding': 8,
			'number_increment': 1,
			'use_date_range': False,
		}
		if 'company_id' in vals:
			seq['company_id'] = vals['company_id']
		
		seq = self.env['ir.sequence'].create(seq)
		seq_date_range = seq._get_current_sequence()
		seq_date_range.number_next = vals.get('sequence_number_next', 1)
		return seq

	@api.constrains('usar_prefijo_personalizado', 'usar_prefijo_sin_localizacion')
	def _check_exclusividad_prefijos(self):
		"""No tiene sentido marcar ambos checks: uno fuerza secuencia propia
		y el otro fuerza el nativo puro de Odoo bypasseando LATAM."""
		for record in self:
			if record.usar_prefijo_personalizado and record.usar_prefijo_sin_localizacion:
				raise UserError(_(
					"En el tipo de documento '%s' no puede marcar a la vez "
					"'Personalizar prefijo' y 'Usar prefijo sin localización'. "
					"Solo uno de los dos."
				) % record.display_name)