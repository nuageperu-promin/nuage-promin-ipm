# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models


class ZkRequestLog(models.Model):
    _name = 'zk.request.log'
    _description = 'Petición cruda recibida del reloj (diagnóstico)'
    _order = 'id desc'

    device_id = fields.Many2one('zk.device', 'Reloj', ondelete='cascade', index=True)
    serial = fields.Char('Serie')
    method = fields.Char('Método')
    path = fields.Char('Ruta')
    query = fields.Char('Parámetros')
    body = fields.Text('Cuerpo')
    response = fields.Text('Respuesta')
    status = fields.Integer('HTTP')

    @api.autovacuum
    def _gc_request_log(self):
        limit = fields.Datetime.now() - timedelta(days=7)
        self.search([('create_date', '<', limit)]).unlink()
