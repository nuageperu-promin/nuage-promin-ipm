# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    promin_portal_user_id = fields.Many2one(
        'res.users', 'Usuario del Portal del Empleado', copy=False, index=True,
        ondelete='set null', domain=[('share', '=', True)],
        help='Usuario de portal con el que este empleado ingresa al Portal del Empleado.')
    promin_portal_dato_count = fields.Integer(
        'Datos del portal por aprobar', compute='_compute_promin_portal_dato_count')

    @api.constrains('promin_portal_user_id')
    def _check_promin_portal_user_unico(self):
        for emp in self.filtered('promin_portal_user_id'):
            otro = self.sudo().search([('promin_portal_user_id', '=', emp.promin_portal_user_id.id),
                                       ('id', '!=', emp.id)], limit=1)
            if otro:
                raise ValidationError(_('El usuario %(u)s ya está asignado al empleado %(e)s.',
                                        u=emp.promin_portal_user_id.login, e=otro.name))

    def _compute_promin_portal_dato_count(self):
        datos = self.env['promin.portal.dato']._read_group(
            [('employee_id', 'in', self.ids), ('state', '=', 'pendiente')],
            ['employee_id'], ['__count'])
        cuentas = {emp.id: n for emp, n in datos}
        for emp in self:
            emp.promin_portal_dato_count = cuentas.get(emp.id, 0)

    def action_promin_crear_acceso_portal(self):
        """Crea (o vincula) el usuario de portal de cada empleado y le envía el correo para definir su clave."""
        Users = self.env['res.users'].sudo()
        grupo = self.env.ref('base.group_portal')
        creados, existentes, errores = [], [], []
        for emp in self:
            if emp.promin_portal_user_id:
                existentes.append(emp.name)
                continue
            correo = (emp.work_email or emp.private_email or '').strip().lower()
            if not correo:
                errores.append(_('%s (sin correo)', emp.name))
                continue
            usuario = Users.with_context(active_test=False).search([('login', '=', correo)], limit=1)
            if usuario:
                if not usuario.share:
                    errores.append(_('%(e)s (el correo %(c)s es de un usuario interno)', e=emp.name, c=correo))
                    continue
            else:
                partner = emp.work_contact_id.sudo() or self.env['res.partner'].sudo().create(
                    {'name': emp.name, 'email': correo})
                if not partner.email:
                    partner.email = correo
                usuario = Users.with_context(no_reset_password=True).create({
                    'login': correo, 'email': correo, 'partner_id': partner.id,
                    'group_ids': [(6, 0, [grupo.id])],
                })
                try:
                    usuario.action_reset_password()
                except Exception:  # el correo saliente puede no estar configurado
                    _logger.warning('No se pudo enviar la invitación al portal a %s', correo, exc_info=True)
            emp.sudo().promin_portal_user_id = usuario
            creados.append(emp.name)
        partes = []
        if creados:
            partes.append(_('Accesos creados: %s.', ', '.join(creados)))
        if existentes:
            partes.append(_('Ya tenían acceso: %s.', ', '.join(existentes)))
        if errores:
            partes.append(_('No se pudo: %s.', '; '.join(errores)))
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Portal del Empleado'), 'message': ' '.join(partes),
                           'type': 'warning' if errores else 'success', 'sticky': bool(errores)}}

    def action_promin_ver_datos_portal(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Datos del portal'),
                'res_model': 'promin.portal.dato', 'view_mode': 'list,form',
                'domain': [('employee_id', '=', self.id)],
                'context': {'default_employee_id': self.id}}
