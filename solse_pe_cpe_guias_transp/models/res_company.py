# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


# Modalidad de guía electrónica. Este selector NO es excluyente a nivel de
# base de datos: solo define un valor por defecto; la empresa puede emitir
# guías de remisión (09) y de transportista (31) a la vez.
MODALIDAD_GUIA = [
	('sender', 'Remitente (09)'),
	('carrier', 'Transportista (31)'),
]


class Company(models.Model):
	_inherit = "res.company"

	pe_cpe_eguide_transport_server_id = fields.Many2one(
		comodel_name="cpe.server",
		string="Servidor para Guía Transportista",
		domain="[('state', '=', 'done')]",
		help="Servidor SUNAT/OSE usado para enviar las Guías de Remisión "
			 "Transportista (tipo 31). Si se deja vacío se usa el servidor de "
			 "guías de remisión: el endpoint GRE de SUNAT es el mismo para la "
			 "09 y la 31.",
	)
	pe_guide_mode = fields.Selection(
		selection=MODALIDAD_GUIA,
		string='Modalidad de guía por defecto',
		default='sender',
		help="Modalidad usada cuando el Tipo de Operación no define una. "
			 "No restringe la emisión: la empresa puede emitir ambas.",
	)

	@api.constrains('pe_cpe_eguide_transport_server_id')
	def _check_servidor_guias_transporte_de_la_compania(self):
		# Mismo criterio que B-4/M-51 del módulo de guías: el servidor de
		# guías debe ser de la propia compañía.
		for compania in self:
			servidor = compania.pe_cpe_eguide_transport_server_id
			if servidor and servidor.company_id and \
					servidor.company_id != compania:
				raise ValidationError(_(
					'El servidor de guías transportista «%s» pertenece a la '
					'compañía «%s» y no puede asignarse a «%s».',
					servidor.display_name,
					servidor.company_id.display_name,
					compania.display_name))

	# ------------------------------------------------------------------
	# Secuencias por compañía (criterio de la suite: sin correlativos
	# globales para comprobantes electrónicos).
	# ------------------------------------------------------------------
	@api.model
	def pe_asegurar_secuencias_guias_transporte_todas(self):
		"""Todas las compañías. La invoca el `<function>` del data."""
		self.env['res.company'].sudo().search([]).pe_asegurar_secuencias_guias_transporte()

	def pe_asegurar_secuencias_guias_transporte(self):
		# La numeración de la GRT exige V + 3 alfanuméricos + correlativo
		# (ERR-3441: [V][A-Z0-9]{3}-[0-9]{1,8}).
		for compania in self._pe_companias_con_cpe():
			compania.pe_asegurar_secuencia(
				'pe.eguide.transport.sync', 'Guía de Remisión Transportista',
				prefix='V001-', padding=5)
			compania.pe_asegurar_secuencia(
				'pe.eguide.transport.cancel', 'Anulación de Guía Transportista',
				prefix='VG01-')
