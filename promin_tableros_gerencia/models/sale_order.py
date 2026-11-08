from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    promin_integrador = fields.Selection(
        [('interno', 'Interno'), ('externo', 'Externo')],
        string='Integrador',
        help='Para tableros y proyectos: indica si el tablerista que integra es interno o externo.',
    )
