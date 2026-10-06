# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class SaleOrder(models.Model):
	_inherit = "sale.order"
	
	session_id = fields.Many2one('pos.session', string='Sesión', readonly=True, copy=False)
	pos_order_count = fields.Integer(string='Pos Order Count', compute='_count_pos_order', readonly=True, groups="point_of_sale.group_pos_user")
