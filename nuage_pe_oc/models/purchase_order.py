# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import api, fields, models

CODIGO_SECUENCIA = {
    'local': 'nuage.oc.local',
    'importacion': 'nuage.oc.importacion',
}


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    nuage_tipo_oc = fields.Selection([
        ('local', 'Local'),
        ('importacion', 'Importación'),
    ], string='Tipo de OC', default='local', required=True, copy=True,
        help='Define la numeración (PMS/PMI) y el formato PDF de la orden.')

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
                    or 'local')
            numero = self.env['ir.sequence'].with_company(company).next_by_code(
                CODIGO_SECUENCIA[tipo])
            if numero:
                vals['name'] = numero
        return super().create(vals_list)
