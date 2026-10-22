# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    zk_pin = fields.Char(
        'ID en reloj (ZKTeco)', copy=False, groups='hr.group_hr_user',
        help='ID con el que el empleado está registrado en los relojes '
             'marcadores. Debe coincidir exactamente (ej. "0012" y "12" '
             'son distintos).')

    @api.constrains('zk_pin', 'company_id')
    def _check_zk_pin_unique(self):
        for emp in self.filtered('zk_pin'):
            dup = self.sudo().with_context(active_test=False).search_count([
                ('zk_pin', '=', emp.zk_pin),
                ('company_id', '=', emp.company_id.id),
                ('id', '!=', emp.id),
            ])
            if dup:
                raise ValidationError(_(
                    'El ID en reloj %s ya está asignado a otro empleado de la '
                    'compañía.', emp.zk_pin))

    def _zk_reprocess_logs(self):
        """Tras asignar un ID, reprocesa las marcaciones que no tenían empleado."""
        for company, emps in self.filtered('zk_pin').sudo().grouped('company_id').items():
            try:
                with self.env.cr.savepoint():
                    self.env['zk.attendance.log'].sudo()._reprocess_pins(
                        company, emps.mapped('zk_pin'))
            except Exception:
                _logger.exception('ZK: no se pudo reprocesar marcaciones')

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        if any(vals.get('zk_pin') for vals in vals_list):
            employees._zk_reprocess_logs()
        return employees

    def write(self, vals):
        res = super().write(vals)
        if 'zk_pin' in vals or 'company_id' in vals:
            self._zk_reprocess_logs()
        return res
