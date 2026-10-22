# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .. import zk_protocol as zkp

_logger = logging.getLogger(__name__)

PROCESSABLE = ('pending', 'no_employee', 'review', 'error', 'ignored')


class ZkAttendanceLog(models.Model):
    _name = 'zk.attendance.log'
    _description = 'Marcación recibida del reloj'
    _order = 'punch_datetime desc, id desc'

    device_id = fields.Many2one(
        'zk.device', 'Reloj', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(
        related='device_id.company_id', store=True, index=True)
    pin = fields.Char('ID en reloj', required=True, index=True)
    punch_datetime = fields.Datetime('Fecha y hora', required=True, index=True)
    status_code = fields.Char('Estado (reloj)')
    verify_type = fields.Char('Verificación')
    workcode = fields.Char('Workcode')
    raw_line = fields.Text('Línea original')
    employee_id = fields.Many2one('hr.employee', 'Empleado', index=True)
    attendance_id = fields.Many2one(
        'hr.attendance', 'Asistencia', ondelete='set null', index=True)
    action = fields.Selection(
        [('check_in', 'Entrada'), ('check_out', 'Salida')], 'Acción')
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('processed', 'Procesada'),
        ('no_employee', 'Sin empleado'),
        ('duplicate', 'Duplicada'),
        ('ignored', 'Ignorada'),
        ('review', 'Revisar'),
        ('error', 'Error'),
    ], 'Estado', default='pending', required=True, index=True)
    message = fields.Char('Detalle')

    def init(self):
        self.env.cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS zk_attendance_log_punch_uniq "
            "ON zk_attendance_log (device_id, pin, punch_datetime)")

    # ---- ingreso ------------------------------------------------------------
    @api.model
    def _ingest(self, device, records):
        """Guarda las marcaciones nuevas del reloj (sin duplicar reenvíos)."""
        if not records:
            return self.browse()
        items = {}
        for rec in records:
            punch_utc = zkp.local_to_utc(rec['punch'], device.timezone)
            items.setdefault((rec['pin'], punch_utc), rec)
        pins = list({k[0] for k in items})
        dates = [k[1] for k in items]
        existing = self.search([
            ('device_id', '=', device.id),
            ('pin', 'in', pins),
            ('punch_datetime', '>=', min(dates)),
            ('punch_datetime', '<=', max(dates)),
        ])
        known = {(log.pin, log.punch_datetime) for log in existing}
        vals_list = []
        for (pin, punch_utc), rec in items.items():
            if (pin, punch_utc) in known:
                continue
            vals = {
                'device_id': device.id,
                'pin': pin,
                'punch_datetime': punch_utc,
                'status_code': rec['status'],
                'verify_type': rec['verify'],
                'workcode': rec['workcode'],
                'raw_line': rec['raw'],
            }
            if device.process_from and punch_utc < device.process_from:
                vals.update(state='ignored',
                            message=_('Anterior a la fecha de inicio del reloj.'))
            vals_list.append(vals)
        if not vals_list:
            return self.browse()
        try:
            with self.env.cr.savepoint():
                return self.create(vals_list)
        except Exception:  # carrera con otro reenvío: se guarda una por una
            _logger.info('ZK: alta en bloque falló, reintentando una por una')
            created = self.browse()
            for vals in vals_list:
                try:
                    with self.env.cr.savepoint():
                        created |= self.create(vals)
                except Exception:
                    continue
            return created

    # ---- procesamiento ------------------------------------------------------
    def _set(self, vals):
        """Escribe solo si algo cambió (evita escrituras inútiles)."""
        self.ensure_one()
        changed = {}
        for key, value in vals.items():
            current = self[key]
            if hasattr(current, 'id'):
                current = current.id
            if current != value and not (current is False and value in (False, None)):
                changed[key] = value
        if changed:
            self.write(changed)

    def _process(self):
        """Convierte marcaciones en asistencias, en orden cronológico."""
        Attendance = self.env['hr.attendance'].with_context(
            mail_notrack=True, tracking_disable=True)
        Employee = self.env['hr.employee'].sudo()
        employees = {}
        ordered = self.sorted(
            key=lambda l: (l.company_id.id, l.pin, l.punch_datetime, l.id))
        for log in ordered:
            dev = log.device_id
            punch = log.punch_datetime
            if dev.process_from and punch < dev.process_from:
                log._set({'state': 'ignored',
                          'message': _('Anterior a la fecha de inicio del reloj.')})
                continue
            key = (log.company_id.id, log.pin)
            if key not in employees:
                employees[key] = Employee.search([
                    ('zk_pin', '=', log.pin),
                    ('company_id', '=', log.company_id.id),
                ], limit=1)
            emp = employees[key]
            if not emp:
                log._set({'state': 'no_employee', 'employee_id': False,
                          'message': _('Ningún empleado tiene el ID en reloj %s.', log.pin)})
                continue

            last = Attendance.search([
                ('employee_id', '=', emp.id), ('check_in', '<=', punch)],
                order='check_in desc, id desc', limit=1)
            later = Attendance.search([
                ('employee_id', '=', emp.id), ('check_in', '>', punch)],
                order='check_in asc', limit=1)
            action, msg = zkp.decide_punch(
                punch,
                last.check_in or None,
                last.check_out or None,
                later.check_in or None,
                status=log.status_code or '',
                mode=dev.punch_mode,
                dedupe_seconds=dev.dedupe_seconds,
                max_shift_hours=dev.max_shift_hours,
                auto_close_stale=dev.auto_close_stale,
            )
            if action == 'duplicate':
                log._set({'state': 'duplicate', 'employee_id': emp.id, 'message': msg})
                continue
            if action == 'review':
                log._set({'state': 'review', 'employee_id': emp.id, 'message': msg})
                continue

            in_vals = {
                'employee_id': emp.id, 'check_in': punch,
                'in_mode': 'technical', 'in_location': dev.name,
            }
            try:
                with self.env.cr.savepoint():
                    if action == 'check_in':
                        att = Attendance.create(in_vals)
                        act = 'check_in'
                    elif action == 'check_out':
                        last.write({'check_out': punch, 'out_mode': 'technical',
                                    'out_location': dev.name})
                        att, act = last, 'check_out'
                    else:  # close_stale_and_check_in
                        last.write({
                            'check_out': last.check_in + timedelta(hours=dev.max_shift_hours),
                            'out_mode': 'technical', 'out_location': dev.name})
                        att = Attendance.create(in_vals)
                        act = 'check_in'
            except (ValidationError, UserError) as exc:
                log._set({'state': 'error', 'employee_id': emp.id,
                          'message': str(exc)[:500]})
                continue
            log._set({'state': 'processed', 'employee_id': emp.id,
                      'attendance_id': att.id, 'action': act, 'message': msg})
        return True

    # ---- invocaciones -------------------------------------------------------
    def action_reprocess(self):
        self.filtered(lambda l: l.state in PROCESSABLE)._process()
        return True

    @api.model
    def _reprocess_pins(self, company, pins):
        """Reprocesa las marcaciones 'sin empleado' cuyo ID acaba de asignarse."""
        logs = self.search([
            ('state', '=', 'no_employee'),
            ('company_id', '=', company.id),
            ('pin', 'in', list(pins)),
        ])
        logs._process()

    @api.model
    def _cron_process(self, limit=1000):
        self.search([('state', '=', 'pending')],
                    order='punch_datetime asc', limit=limit)._process()
