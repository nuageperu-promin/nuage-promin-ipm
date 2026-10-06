# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
	_inherit = 'res.config.settings'

	cuenta_detracciones = fields.Many2one("account.account", string="Cuenta de detracciones [Venta]", related="company_id.cuenta_detracciones", store=True, readonly=False)
	cuenta_detracciones_compra = fields.Many2one("account.account", string="Cuenta de detracciones [Compra]", related="company_id.cuenta_detracciones_compra", store=True, readonly=False)
	cuenta_detrac_ganancias = fields.Many2one("account.account", string="Cuenta para ganancias por detracción", related="company_id.cuenta_detrac_ganancias", store=True, readonly=False)
	cuenta_detrac_perdidas = fields.Many2one("account.account", string="Cuenta para pérdidas por detracción", related="company_id.cuenta_detrac_perdidas", store=True, readonly=False)
	cuenta_retenciones = fields.Many2one("account.account", string="Cuenta de retenciones [Compra]", related="company_id.cuenta_retenciones", store=True, readonly=False)
	cuenta_retenciones_venta = fields.Many2one("account.account", string="Cuenta de retenciones [Venta]", related="company_id.cuenta_retenciones_venta", store=True, readonly=False)
	usar_fecha_vencimiento_detraccion = fields.Boolean(string="Gestionar fecha de vencimiento de detracción", related="company_id.usar_fecha_vencimiento_detraccion", store=True, readonly=False)
	dia_vencimiento_detraccion = fields.Integer(string="Día de vencimiento (mes siguiente)", related="company_id.dia_vencimiento_detraccion", store=True, readonly=False)

	sector_contable = fields.Selection(
		related='company_id.sector_contable',
		readonly=False,
		string='Sector Contable (Tabla 34)',
	)
