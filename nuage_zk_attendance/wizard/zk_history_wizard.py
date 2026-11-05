# -*- coding: utf-8 -*-
import base64
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .. import zk_protocol as zkp

MAX_DAYS = 92


class ZkHistoryWizard(models.TransientModel):
    _name = 'zk.history.wizard'
    _description = 'Traer el historial guardado en el reloj'

    device_id = fields.Many2one('zk.device', 'Reloj', required=True, readonly=True)
    source = fields.Selection([
        ('device', 'Pedirlo al reloj (por red)'),
        ('file', 'Importar archivo attlog.dat (memoria USB)'),
    ], 'Origen', default='device', required=True)
    date_from = fields.Date(
        'Desde', required=True,
        default=lambda self: fields.Date.context_today(self) - timedelta(days=14))
    date_to = fields.Date(
        'Hasta', required=True, default=fields.Date.context_today)
    file = fields.Binary('Archivo del reloj')
    filename = fields.Char('Nombre del archivo')

    # ---- comunes -----------------------------------------------------------
    def _check_dates(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_('"Desde" no puede ser posterior a "Hasta".'))
        if (self.date_to - self.date_from).days > MAX_DAYS:
            raise UserError(_('Pida como máximo %s días por vez.', MAX_DAYS))

    def _local_range(self):
        start = datetime.combine(self.date_from, time.min)
        end = datetime.combine(self.date_to, time.max.replace(microsecond=0))
        return start, end

    def _open_cutoff(self, start_local):
        """Baja la fecha de inicio del reloj para que el historial no se ignore."""
        dev = self.device_id
        start_utc = zkp.local_to_utc(start_local, dev.timezone)
        if dev.process_from and start_utc < dev.process_from:
            old = dev.process_from
            dev.process_from = start_utc
            dev.message_post(body=_(
                'La fecha "Procesar marcaciones desde" se adelantó de %(old)s a %(new)s '
                'para traer el historial solicitado.', old=old, new=start_utc))
        # Lo que ya llegó y quedó ignorado dentro del rango vuelve a pendiente
        ignored = self.env['zk.attendance.log'].search([
            ('device_id', '=', dev.id), ('state', '=', 'ignored'),
            ('punch_datetime', '>=', start_utc)])
        ignored.write({'state': 'pending', 'message': False})
        return start_utc

    def _notify(self, title, message, kind='success'):
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'type': kind,
                       'sticky': True,
                       'next': {'type': 'ir.actions.act_window_close'}},
        }

    # ---- por red ------------------------------------------------------------
    def action_request_device(self):
        self.ensure_one()
        self._check_dates()
        dev = self.device_id
        start, end = self._local_range()
        self._open_cutoff(start)
        cmd = self.env['zk.device.command'].create({
            'device_id': dev.id,
            'name': _('Historial del %(a)s al %(b)s', a=self.date_from, b=self.date_to),
            'command': zkp.history_command(start, end),
            'date_from': start, 'date_to': end,
        })
        dev.message_post(body=_(
            'Se pidió al reloj el historial del %(a)s al %(b)s (comando %(id)s).',
            a=self.date_from, b=self.date_to, id=cmd.id))
        return self._notify(
            _('Solicitud en cola'),
            _('El reloj la recibirá en su próxima consulta (entre 30 y 60 segundos) y '
              'enviará sus marcaciones. Revise "Marcaciones del reloj" en unos minutos. '
              'Si el reloj no admite esta consulta, se le avisará en el chatter del reloj.'))

    # ---- por archivo ----------------------------------------------------------
    def action_import_file(self):
        self.ensure_one()
        self._check_dates()
        if not self.file:
            raise UserError(_('Seleccione el archivo attlog.dat descargado del reloj.'))
        dev = self.device_id
        start, end = self._local_range()
        body = base64.b64decode(self.file).decode('utf-8', 'replace')
        records, errors = zkp.parse_attlog(body)
        total = len(records)
        records = [r for r in records if start <= r['punch'] <= end]
        if not records:
            raise UserError(_(
                'El archivo trae %(total)s marcaciones, pero ninguna entre %(a)s y %(b)s.',
                total=total, a=self.date_from, b=self.date_to))
        self._open_cutoff(start)
        Log = self.env['zk.attendance.log']
        created = Log._ingest(dev, records)
        done = Log._process_pending(dev, limit=2000)
        pending = Log.search_count([('device_id', '=', dev.id), ('state', '=', 'pending')])
        dev.message_post(body=_(
            'Importación de %(file)s: %(n)s marcaciones en el rango, %(new)s nuevas, '
            '%(bad)s líneas no reconocidas.',
            file=self.filename or 'attlog.dat', n=len(records),
            new=len(created), bad=len(errors)))
        msg = _('%(n)s marcaciones en el rango; %(new)s nuevas; %(done)s procesadas.',
                n=len(records), new=len(created), done=done)
        if pending:
            msg += ' ' + _('Quedan %s pendientes: use "Procesar pendientes" en el reloj.', pending)
        return self._notify(_('Importación terminada'), msg)
