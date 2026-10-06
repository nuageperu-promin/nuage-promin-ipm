# -*- coding: utf-8 -*-

from odoo import api, fields, models,_
from odoo.exceptions import UserError
import logging
_logging = logging.getLogger(__name__)

class InheritedAccountMove(models.Model):
	_inherit = 'account.move'

	venta_id = fields.Many2one("sale.order", "Venta id")
	orden_compra = fields.Char("Orden de compra")
	nro_ruc_dni = fields.Char(related="partner_id.vat", store=True)


class AccountMoveLine(models.Model):
	_inherit = "account.move.line"

	nro_comprobante = fields.Char("Nro Comprobante", related="move_id.l10n_latam_document_number", store=True)
	cliente = fields.Many2one('res.partner',string='Cliente', related='move_id.partner_id', store=True)
	nro_ruc_dni = fields.Char(related="move_id.partner_id.vat", store=True)
	fecha_pedido = fields.Date("Fecha Pedido", related="move_id.invoice_date", store=True)
	user_id = fields.Many2one(related="move_id.user_id", store=True)