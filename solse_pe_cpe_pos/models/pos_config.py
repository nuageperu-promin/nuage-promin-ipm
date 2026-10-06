# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

class PosConfig(models.Model):
	_inherit = 'pos.config'
	
	documento_venta_ids = fields.Many2many("l10n_latam.document.type", string="Documentos de venta", domain="[('sub_type', '=', 'sale'), ('company_id', '=', company_id)]")
	doc_venta_defecto = fields.Many2one('l10n_latam.document.type', string="Documento de venta Defecto", domain='[("id", "in", documento_venta_ids)]')
	cliente_varios = fields.Many2one('res.partner', string="Cliente Varios")
	

