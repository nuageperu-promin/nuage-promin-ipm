# -*- coding: utf-8 -*-
from odoo import fields, models


class ProminNuevaVersion(models.TransientModel):
    _name = 'promin.cotizacion.nueva.version'
    _description = 'Nueva versión de cotización'

    order_id = fields.Many2one('sale.order', 'Cotización', required=True, readonly=True)
    motivo = fields.Text('Motivo de la revisión',
                         help='Opcional. Queda registrado en la versión nueva y en el historial.')

    def action_crear(self):
        self.ensure_one()
        nuevo = self.order_id._promin_nueva_version(self.motivo)
        return {
            'type': 'ir.actions.act_window', 'res_model': 'sale.order',
            'res_id': nuevo.id, 'view_mode': 'form', 'target': 'current',
        }
