# -*- coding: utf-8 -*-
from odoo import fields, models


class ZkDeviceCommand(models.Model):
    """Comando que Odoo le pide al reloj en su próxima consulta (getrequest)."""
    _name = 'zk.device.command'
    _description = 'Comando para el reloj ZKTeco'
    _order = 'id desc'

    device_id = fields.Many2one(
        'zk.device', 'Reloj', required=True, ondelete='cascade', index=True)
    name = fields.Char('Descripción', required=True)
    command = fields.Char('Comando', required=True)
    state = fields.Selection([
        ('pending', 'En espera del reloj'),
        ('sent', 'Enviado al reloj'),
        ('done', 'Aceptado por el reloj'),
        ('error', 'Rechazado por el reloj'),
    ], 'Estado', default='pending', required=True, index=True)
    sent_at = fields.Datetime('Enviado')
    return_code = fields.Char('Respuesta del reloj')
    date_from = fields.Datetime('Desde (hora del reloj)')
    date_to = fields.Datetime('Hasta (hora del reloj)')
