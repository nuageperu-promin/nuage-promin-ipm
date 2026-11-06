# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    nuage_libro_impreso = fields.Selection(
        [('01', '01 - Caja y Bancos'), ('05', '05 - Diario'),
         ('08', '08 - Compras'), ('14', '14 - Ventas')],
        string='Libro en impresos (Tabla 8)',
        help='Código de libro que se imprime en el Libro Diario y el Libro Mayor para los asientos '
             'de este diario. Vacío = automático: bancos y caja 01, compras 08, ventas 14, otros 05.')
