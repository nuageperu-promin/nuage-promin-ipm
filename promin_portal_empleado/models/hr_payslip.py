# -*- coding: utf-8 -*-
from odoo import fields, models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    promin_primera_lectura = fields.Datetime(
        'Primera apertura en el portal', readonly=True, copy=False,
        help='Fecha y hora en que el empleado abrió esta boleta por primera vez en el Portal del Empleado.')
    promin_lecturas = fields.Integer('Veces abierta en el portal', readonly=True, copy=False)

    def _promin_registrar_lectura(self):
        for slip in self.sudo():
            valores = {'promin_lecturas': slip.promin_lecturas + 1}
            if not slip.promin_primera_lectura:
                valores['promin_primera_lectura'] = fields.Datetime.now()
            slip.write(valores)
