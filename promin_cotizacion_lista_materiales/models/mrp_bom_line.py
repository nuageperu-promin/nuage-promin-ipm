# -*- coding: utf-8 -*-
from odoo import fields, models


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    promin_imp_cot = fields.Boolean(
        'Imp. Cot', default=False,
        help='Si está activo, este componente se imprime en la cotización cuando la cotización '
             'tiene marcado «Se imprime Lista de Materiales».')
