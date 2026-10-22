# -*- coding: utf-8 -*-
"""Endpoints ADMS (push) que consulta el reloj ZKTeco.

El reloj inicia la conexión; el servidor solo responde. Las rutas usan
auth='public' porque el reloj no tiene sesión: la seguridad es el número de
serie registrado y confirmado en Odoo (dispositivo desconocido -> 403, sin
datos). Mientras el reloj no reciba 'OK' conserva y reintenta sus marcaciones.
"""
import logging

from odoo import http
from odoo.api import SUPERUSER_ID
from odoo.http import request

from .. import zk_protocol as zkp

_logger = logging.getLogger(__name__)

MAX_DEBUG_CHARS = 20000


class ZKAdmsController(http.Controller):

    # ---- rutas ---------------------------------------------------------------
    @http.route('/iclock/cdata', type='http', auth='public',
                methods=['GET', 'POST'], csrf=False, save_session=False)
    def cdata(self, **kw):
        return self._handle('cdata')

    @http.route('/iclock/getrequest', type='http', auth='public',
                methods=['GET', 'POST'], csrf=False, save_session=False)
    def getrequest(self, **kw):
        return self._handle('getrequest')

    @http.route('/iclock/devicecmd', type='http', auth='public',
                methods=['GET', 'POST'], csrf=False, save_session=False)
    def devicecmd(self, **kw):
        return self._handle('devicecmd')

    @http.route('/iclock/registry', type='http', auth='public',
                methods=['GET', 'POST'], csrf=False, save_session=False)
    def registry(self, **kw):
        return self._handle('registry')

    @http.route('/iclock/push', type='http', auth='public',
                methods=['GET', 'POST'], csrf=False, save_session=False)
    def push(self, **kw):
        return self._handle('push')

    @http.route('/iclock/ping', type='http', auth='public',
                methods=['GET', 'POST'], csrf=False, save_session=False)
    def ping(self, **kw):
        return self._handle('ping')

    # ---- lógica común -------------------------------------------------------
    @staticmethod
    def _text(body, status=200):
        return request.make_response(
            body, status=status,
            headers=[('Content-Type', 'text/plain; charset=UTF-8'),
                     ('Cache-Control', 'no-store')])

    def _handle(self, kind):
        httpreq = request.httprequest
        args = httpreq.args
        serial = (args.get('SN') or args.get('sn') or '').strip().upper()
        env = request.env(user=SUPERUSER_ID)
        device = env['zk.device']._find_active(serial)
        if not device:
            _logger.warning('ZK ADMS: petición %s de un reloj no registrado '
                            '(SN=%r, IP=%s)', kind, serial[:40], httpreq.remote_addr)
            return self._text('ERROR: device not registered', status=403)

        # Todo se ejecuta en la compañía del reloj
        env = env(context=dict(env.context, allowed_company_ids=[device.company_id.id]))
        device = device.with_env(env)

        body = ''
        if httpreq.method == 'POST':
            body = httpreq.get_data(as_text=False).decode('utf-8', 'replace')
        push_version = args.get('pushver') or args.get('PushVersion')
        device._touch(ip=httpreq.remote_addr, push_version=push_version)

        text, status = self._respond(
            kind, env, device, args, body, serial, httpreq.method)

        if device.debug:
            env['zk.request.log'].create({
                'device_id': device.id, 'serial': serial,
                'method': httpreq.method, 'path': httpreq.path,
                'query': httpreq.query_string.decode('utf-8', 'replace'),
                'body': body[:MAX_DEBUG_CHARS],
                'response': text[:2000], 'status': status,
            })
        return self._text(text, status=status)

    def _respond(self, kind, env, device, args, body, serial, method):
        if kind == 'cdata':
            if method == 'POST':
                return self._receive(env, device, args, body)
            if args.get('options') or args.get('pushver') or args.get('PushOptionsFlag'):
                return zkp.handshake_response(serial, device.att_stamp), 200
            return 'OK', 200
        if kind == 'registry':
            return zkp.registry_response(), 200
        if kind == 'push':
            return zkp.push_config_response(), 200
        return 'OK', 200  # getrequest, devicecmd, ping

    def _receive(self, env, device, args, body):
        table = (args.get('table') or '').upper()
        if table != 'ATTLOG':
            return 'OK', 200  # OPERLOG, usuarios, etc.: se ignoran en v1
        records, errors = zkp.parse_attlog(body)
        if errors:
            _logger.warning('ZK ADMS %s: %d línea(s) no reconocidas: %r',
                            device.serial_number, len(errors), errors[:3])
        Log = env['zk.attendance.log']
        created = Log._ingest(device, records)
        stamp = args.get('Stamp')
        if stamp and stamp != device.att_stamp:
            device.att_stamp = stamp
        if created:
            try:
                with env.cr.savepoint():
                    created._process()
            except Exception:
                # Quedan 'pendientes' y las toma el proceso programado.
                _logger.exception('ZK ADMS %s: error procesando marcaciones',
                                  device.serial_number)
        return 'OK:%d' % len(records), 200

