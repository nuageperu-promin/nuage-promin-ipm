# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    promin_ejecutivo_tecnico_id = fields.Many2one(
        'res.users', string='Ejecutivo Técnico', tracking=True, copy=True, index=True,
        domain=[('share', '=', False)],
        help='Usuario interno que da el soporte técnico de esta cotización/orden de venta. '
             'Se elige de los mismos usuarios que el Vendedor.')
