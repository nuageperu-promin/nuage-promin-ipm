from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    promin_empresa_relacionada = fields.Boolean(
        string='Empresa relacionada',
        help='Marca al cliente como empresa relacionada. Los tableros gerenciales la excluyen por defecto.',
    )
    promin_sector = fields.Selection(
        [('privado', 'Privado'), ('estado', 'Estado'), ('exterior', 'Exterior')],
        string='Sector (tableros)',
        help='Si se deja vacío, el cliente se considera Exterior cuando su país no es Perú y Privado en caso contrario.',
    )
