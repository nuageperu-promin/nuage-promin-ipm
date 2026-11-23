# -*- coding: utf-8 -*-
from odoo import fields, models


class PortalDocumento(models.Model):
    _name = 'promin.portal.documento'
    _description = 'Documento del empleado publicado por RRHH en el Portal'
    _order = 'fecha desc, id desc'

    name = fields.Char('Título', required=True)
    employee_id = fields.Many2one('hr.employee', 'Empleado', required=True, index=True, ondelete='cascade')
    tipo = fields.Selection([('contrato', 'Contrato de trabajo'), ('otro', 'Otro documento')],
                            'Tipo', default='contrato', required=True)
    fecha = fields.Date('Fecha del documento', default=fields.Date.context_today)
    archivo = fields.Binary('Archivo', attachment=True, required=True)
    archivo_nombre = fields.Char('Nombre del archivo')
    publicado = fields.Boolean(
        'Visible en el portal', default=False,
        help='Si está activo, el empleado ve y descarga este documento en su Portal.')
    primera_lectura = fields.Datetime('Primera apertura', readonly=True, copy=False)
    lecturas = fields.Integer('Veces abierto', readonly=True, copy=False)
