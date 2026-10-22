# -*- coding: utf-8 -*-
from datetime import timedelta
from urllib.parse import urlparse

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


def _tz_get(self):
    return [(tz, tz) for tz in sorted(pytz.common_timezones)]


class ZkDevice(models.Model):
    _name = 'zk.device'
    _description = 'Reloj marcador ZKTeco (ADMS)'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char('Nombre', required=True, tracking=True)
    serial_number = fields.Char(
        'Número de serie', required=True, copy=False, index=True, tracking=True,
        help='Número de serie del reloj (menú Información del Equipo). '
             'Identifica de qué equipo llega cada marcación.')
    model_name = fields.Char('Modelo')
    location = fields.Char('Ubicación')
    company_id = fields.Many2one(
        'res.company', 'Compañía', required=True,
        default=lambda self: self.env.company)
    timezone = fields.Selection(
        _tz_get, 'Zona horaria del reloj', required=True, default='America/Lima',
        help='Zona horaria en la que el reloj registra la hora de las marcaciones.')
    state = fields.Selection(
        [('draft', 'Borrador'), ('confirmed', 'Confirmado')],
        'Estado', default='draft', required=True, tracking=True)
    active = fields.Boolean(default=True)

    # Reglas de procesamiento
    punch_mode = fields.Selection(
        [('toggle', 'Alternar entrada / salida'),
         ('device', 'Usar el estado que envía el reloj')],
        'Modo de marcación', default='toggle', required=True,
        help='Alternar: la primera marcación abre la asistencia y la siguiente '
             'la cierra. Estado del reloj: se respeta el botón de entrada/salida '
             'del equipo y las inconsistencias quedan para revisión.')
    dedupe_seconds = fields.Integer(
        'Ventana de duplicados (s)', default=60,
        help='Marcaciones del mismo empleado dentro de esta ventana se ignoran.')
    max_shift_hours = fields.Float(
        'Duración máxima de turno (h)', default=16.0,
        help='Una asistencia abierta más tiempo que esto se considera con '
             'salida olvidada.')
    auto_close_stale = fields.Boolean(
        'Cerrar turnos olvidados automáticamente',
        help='Si se activa, el turno abierto se cierra con la duración máxima '
             'y se abre uno nuevo. Si no, la marcación queda en "Revisar".')
    process_from = fields.Datetime(
        'Procesar marcaciones desde',
        help='Las marcaciones anteriores a esta fecha se guardan pero no generan '
             'asistencias. Al confirmar el reloj se completa con la fecha actual '
             'para no importar el historial del equipo.')
    debug = fields.Boolean(
        'Modo diagnóstico',
        help='Guarda cada petición cruda del reloj (Configuración → '
             'Peticiones del reloj). Útil para validar el formato real. '
             'Desactivar al terminar.')

    # Estado de conexión (solo lectura)
    last_activity = fields.Datetime('Última conexión', readonly=True, copy=False)
    last_ip = fields.Char('Última IP', readonly=True, copy=False)
    push_version = fields.Char('Versión Push', readonly=True, copy=False)
    att_stamp = fields.Char('Marca de sincronización', readonly=True, copy=False)
    offline_notified = fields.Boolean(readonly=True, copy=False)
    is_online = fields.Boolean('En línea', compute='_compute_is_online')

    # Datos para configurar el reloj
    server_host = fields.Char('Dirección del servidor', compute='_compute_server')
    server_port = fields.Char('Puerto del servidor', compute='_compute_server')
    server_https = fields.Boolean('Usar HTTPS', compute='_compute_server')
    log_count = fields.Integer('Marcaciones', compute='_compute_log_count')

    def init(self):
        self.env.cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS zk_device_serial_uniq "
            "ON zk_device (serial_number)")

    # ---- cálculos -----------------------------------------------------------
    def _offline_minutes(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'nuage_zk_attendance.offline_minutes', '15')
        try:
            return max(1, int(param))
        except ValueError:
            return 15

    @api.depends('last_activity')
    def _compute_is_online(self):
        limit = fields.Datetime.now() - timedelta(minutes=self._offline_minutes())
        for dev in self:
            dev.is_online = bool(dev.last_activity and dev.last_activity >= limit)

    def _compute_server(self):
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        parsed = urlparse(base)
        host = parsed.hostname or ''
        # Detrás de un proxy (nginx, Odoo.sh) web.base.url suele quedar en http://
        # aunque el acceso público sea HTTPS. Solo servidores locales usan HTTP.
        local = host in ('localhost', '127.0.0.1', '::1') or host.replace('.', '').isdigit()
        https = parsed.scheme == 'https' or not local
        port = parsed.port or (443 if https else 80)
        for dev in self:
            dev.server_host = parsed.hostname or ''
            dev.server_port = str(port)
            dev.server_https = https

    def _compute_log_count(self):
        data = self.env['zk.attendance.log']._read_group(
            [('device_id', 'in', self.ids)], ['device_id'], ['__count'])
        counts = {dev.id: count for dev, count in data}
        for dev in self:
            dev.log_count = counts.get(dev.id, 0)

    # ---- validaciones y normalización --------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('serial_number'):
                vals['serial_number'] = vals['serial_number'].strip().upper()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('serial_number'):
            vals['serial_number'] = vals['serial_number'].strip().upper()
        return super().write(vals)

    @api.constrains('serial_number')
    def _check_serial_unique(self):
        for dev in self:
            dup = self.with_context(active_test=False).search_count([
                ('serial_number', '=', dev.serial_number), ('id', '!=', dev.id)])
            if dup:
                raise ValidationError(_(
                    'Ya existe un reloj con el número de serie %s.', dev.serial_number))

    @api.constrains('dedupe_seconds', 'max_shift_hours')
    def _check_rules(self):
        for dev in self:
            if dev.dedupe_seconds < 0 or dev.max_shift_hours <= 0:
                raise ValidationError(_(
                    'La ventana de duplicados no puede ser negativa y la '
                    'duración máxima de turno debe ser mayor a cero.'))

    # ---- acciones -----------------------------------------------------------
    def action_confirm(self):
        for dev in self:
            if not dev.process_from:
                dev.process_from = fields.Datetime.now()
        self.write({'state': 'confirmed'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_view_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Marcaciones de %s', self.name),
            'res_model': 'zk.attendance.log',
            'view_mode': 'list,form',
            'domain': [('device_id', '=', self.id)],
            'context': {'default_device_id': self.id},
        }

    # ---- uso desde el controlador ------------------------------------------
    @api.model
    def _find_active(self, serial):
        serial = (serial or '').strip().upper()
        if not serial:
            return self.browse()
        return self.search([
            ('serial_number', '=', serial),
            ('state', '=', 'confirmed'),
            ('active', '=', True),
        ], limit=1)

    def _touch(self, ip=None, push_version=None):
        """Registra actividad sin escribir en la base en cada petición."""
        self.ensure_one()
        now = fields.Datetime.now()
        vals = {}
        if not self.last_activity or (now - self.last_activity).total_seconds() > 60:
            vals['last_activity'] = now
        if ip and ip != self.last_ip:
            vals['last_ip'] = ip
        if push_version and push_version != self.push_version:
            vals['push_version'] = push_version
        if self.offline_notified:
            vals['offline_notified'] = False
            self.message_post(body=_('El reloj volvió a estar en línea.'))
        if vals:
            self.write(vals)

    # ---- tareas programadas -------------------------------------------------
    @api.model
    def _cron_check_offline(self):
        limit = fields.Datetime.now() - timedelta(minutes=self._offline_minutes())
        devices = self.search([
            ('state', '=', 'confirmed'),
            ('offline_notified', '=', False),
            ('last_activity', '!=', False),
            ('last_activity', '<', limit),
        ])
        for dev in devices:
            dev.message_post(body=_(
                'El reloj "%(name)s" no reporta desde %(last)s (más de %(min)s min).',
                name=dev.name, last=dev.last_activity, min=self._offline_minutes()))
            dev.offline_notified = True
