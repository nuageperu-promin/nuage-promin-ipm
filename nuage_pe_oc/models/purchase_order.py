# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import api, fields, models

TIPOS_OC = [
    ('pma', 'PMA - Activo'),
    ('pmc', 'PMC - Consumibles'),
    ('pmi', 'PMI - Importación'),
    ('pml', 'PML - Local'),
    ('pms', 'PMS - Stock'),
    ('pmt', 'PMT - Tableros'),
    ('srv', 'SRV - Servicios'),
]


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    nuage_tipo_oc = fields.Selection(
        TIPOS_OC, string='Tipo de OC', default='pml', required=True, copy=True,
        help='Define el prefijo de la numeración (PMA, PMC, PMI, PML, PMS, PMT, SRV). '
             'El formato PDF (local o importación) se elige al imprimir.')

    @api.model_create_multi
    def create(self, vals_list):
        """Numera con PMS/PMI si la compañía lo tiene activo.

        Se asigna el nombre antes de llamar al create nativo, que solo numera
        cuando el nombre sigue siendo «New».
        """
        for vals in vals_list:
            if vals.get('name', 'New') not in ('New', '/', False):
                continue
            company = self.env['res.company'].browse(
                vals.get('company_id') or self.env.company.id)
            if not company.nuage_oc_usar_formato:
                continue
            tipo = (vals.get('nuage_tipo_oc')
                    or self.env.context.get('default_nuage_tipo_oc')
                    or 'pml')
            numero = self.env['ir.sequence'].with_company(company).next_by_code(
                'nuage.oc.%s' % tipo)
            if numero:
                vals['name'] = numero
        return super().create(vals_list)
