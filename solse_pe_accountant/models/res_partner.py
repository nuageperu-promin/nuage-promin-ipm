# -*- coding: utf-8 -*-

# Extensión de res.partner para detracción por proveedor.
# Mismo patrón que product.template.aplica_detraccion en solse_pe_edi.

from odoo import api, fields, models


class ResPartner(models.Model):
	_inherit = "res.partner"

	@api.model
	def _get_pe_type_detraccion(self):
		"""Lista de códigos de detracción del catálogo SUNAT 54."""
		return self.env['pe.datas'].get_selection("PE.CPE.CATALOG54")

	aplica_detraccion = fields.Selection(
		'_get_pe_type_detraccion',
		string="Aplicar detracción (default)",
		help="Código de detracción que se aplica por defecto cuando este "
		     "partner es proveedor en una factura de compra. Editable luego "
		     "en la cabecera de la factura.",
	)
	detraccion_id = fields.Many2one(
		'pe.datas',
		string="Id de detracción",
		compute="_compute_porc_detraccion",
		store=True,
	)
	porc_detraccion = fields.Float(
		string='% Detracción',
		compute="_compute_porc_detraccion",
		store=True,
	)

	@api.depends('aplica_detraccion')
	def _compute_porc_detraccion(self):
		for reg in self:
			if reg.aplica_detraccion:
				reg_det = self.env['pe.datas'].search([
					('code', '=', reg.aplica_detraccion),
					('table_code', '=', 'PE.CPE.CATALOG54'),
				], limit=1)
				reg.porc_detraccion = reg_det.value
				reg.detraccion_id = reg_det.id
			else:
				reg.porc_detraccion = 0
				reg.detraccion_id = False
