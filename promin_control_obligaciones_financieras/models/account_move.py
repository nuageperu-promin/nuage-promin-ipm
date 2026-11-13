# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    promin_obligacion_id = fields.Many2one(
        'promin.obligacion', string='Obligación financiera', copy=False, index=True, readonly=True)
    promin_cuota_id = fields.Many2one(
        'promin.obligacion.cuota', string='Cuota de obligación', copy=False, readonly=True)
