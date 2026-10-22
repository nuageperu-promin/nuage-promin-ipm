# -*- coding: utf-8 -*-
"""Lógica pura del protocolo ADMS (push) de ZKTeco y de las reglas de marcación.

Este archivo NO importa Odoo a propósito: se puede probar con Python solo
(ver tests/test_protocol.py) y mantener aparte del ORM.

IMPORTANTE: el formato exacto depende del firmware del reloj. Lo implementado
sigue la referencia habitual del protocolo Push 2.x / 3.x y debe validarse con
el tráfico real de los equipos de PROMIN (ver "Modo diagnóstico" del
dispositivo).
"""
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Estados del reloj (campo "Status" de ATTLOG)
STATUS_IN = {'0', '4'}      # Check-In, Overtime-In
STATUS_OUT = {'1', '5'}     # Check-Out, Overtime-Out
# 2 = Break-Out, 3 = Break-In: se tratan como alternancia

_TIME_RE = re.compile(r'^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}$')
_LOOSE_RE = re.compile(
    r'^(?P<pin>\S+)\s+(?P<time>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})\s*(?P<rest>.*)$')


def parse_attlog(body):
    """Interpreta el cuerpo de un POST table=ATTLOG.

    Cada línea: PIN <tab> fecha-hora <tab> estado <tab> verificación <tab> workcode ...
    Devuelve (registros, errores). Registro = dict con pin, punch (datetime
    naive en hora LOCAL del reloj), status, verify, workcode, raw.
    """
    records, errors = [], []
    if not body:
        return records, errors
    for raw in body.replace('\r', '').split('\n'):
        line = raw.strip('\x00 \t')
        if not line:
            continue
        parts = line.split('\t')
        rec = None
        if len(parts) >= 2 and _TIME_RE.match(parts[1].strip()):
            pin, tstr = parts[0].strip(), parts[1].strip()
            rest = [p.strip() for p in parts[2:]]
        else:
            m = _LOOSE_RE.match(line)
            if not m:
                errors.append(raw)
                continue
            pin, tstr = m.group('pin'), m.group('time')
            rest = m.group('rest').split()
        if not pin:
            errors.append(raw)
            continue
        try:
            punch = datetime.strptime(tstr.replace('T', ' '), '%Y-%m-%d %H:%M:%S')
        except ValueError:
            errors.append(raw)
            continue
        rec = {
            'pin': pin,
            'punch': punch,
            'status': rest[0] if len(rest) > 0 else '',
            'verify': rest[1] if len(rest) > 1 else '',
            'workcode': rest[2] if len(rest) > 2 else '',
            'raw': line,
        }
        records.append(rec)
    return records, errors


def local_to_utc(naive_local, tzname):
    """Hora local del reloj (naive) -> UTC naive (como guarda Odoo)."""
    tz = ZoneInfo(tzname or 'UTC')
    aware = naive_local.replace(tzinfo=tz)
    return aware.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)


# ---- Respuestas que espera el reloj ---------------------------------------

def handshake_response(serial, att_stamp='None'):
    """Respuesta al GET /iclock/cdata?SN=..&options=all (Push 2.x)."""
    lines = [
        'GET OPTION FROM: %s' % serial,
        'Stamp=%s' % (att_stamp or 'None'),
        'ATTLOGStamp=%s' % (att_stamp or 'None'),
        'OPERLOGStamp=9999',
        'ATTPHOTOStamp=None',
        'ErrorDelay=60',
        'Delay=30',
        'TransTimes=00:00;14:05',
        'TransInterval=1',
        'TransFlag=TransData AttLog\tOpLog',
        'Realtime=1',
        'Encrypt=None',
    ]
    return '\n'.join(lines) + '\n'


def registry_response(registry_code='ODOO0001'):
    """Respuesta al POST /iclock/registry (Push 3.x)."""
    return 'RegistryCode=%s\n' % registry_code


def push_config_response(session_id='ODOO0001'):
    """Respuesta al GET /iclock/push (Push 3.x)."""
    lines = [
        'ServerVersion=3.1.2',
        'ServerName=ADMS',
        'ErrorDelay=60',
        'RequestDelay=30',
        'TransTimes=00:00;14:05',
        'TransInterval=1',
        'TransTables=User Transaction',
        'Realtime=1',
        'SessionID=%s' % session_id,
        'TimeoutSec=10',
    ]
    return '\n'.join(lines) + '\n'


# ---- Reglas de marcación ---------------------------------------------------

def decide_punch(punch, last_in, last_out, later_check_in, status='',
                 mode='toggle', dedupe_seconds=60, max_shift_hours=16.0,
                 auto_close_stale=False):
    """Decide qué hacer con una marcación (todas las fechas en UTC naive).

    punch: instante de la marcación.
    last_in / last_out: entrada y salida de la ÚLTIMA asistencia del empleado
        cuya entrada es <= punch (last_out=None si sigue abierta); last_in=None
        si no existe ninguna.
    later_check_in: entrada de una asistencia posterior a la marcación (o None).
    Devuelve (accion, mensaje) con accion en:
        'check_in', 'check_out', 'close_stale_and_check_in',
        'duplicate', 'review'.
    """
    # Odoo devuelve False (no None) para fechas vacías
    last_in = last_in or None
    last_out = last_out or None
    later_check_in = later_check_in or None
    dedupe = timedelta(seconds=dedupe_seconds)
    max_shift = timedelta(hours=max_shift_hours)

    if later_check_in is not None:
        if abs(later_check_in - punch) <= dedupe:
            return 'duplicate', 'Marcación repetida de una entrada existente.'
        return 'review', ('Hay asistencias posteriores a esta marcación; '
                          'revisar el orden de los registros.')

    says_in = status in STATUS_IN
    says_out = status in STATUS_OUT
    device_mode = (mode == 'device') and (says_in or says_out)

    if last_in is None:
        if device_mode and says_out:
            return 'review', 'El reloj indica salida pero no existe una entrada.'
        return 'check_in', ''

    if last_out is None:  # asistencia abierta
        delta = punch - last_in
        if delta <= dedupe:
            return 'duplicate', 'Marcación repetida dentro de la ventana de duplicados.'
        if delta > max_shift:
            if auto_close_stale:
                return 'close_stale_and_check_in', (
                    'Turno anterior abierto más de %.1f h: se cerró '
                    'automáticamente con la duración máxima.' % max_shift_hours)
            return 'review', ('Turno abierto desde hace más de %.1f h '
                              '(falta una salida). Corrija la asistencia '
                              'abierta y reprocese.' % max_shift_hours)
        if device_mode and says_in:
            return 'review', 'El reloj indica entrada pero ya hay una entrada abierta.'
        return 'check_out', ''

    # última asistencia cerrada
    if punch < last_out:
        if abs(punch - last_out) <= dedupe:
            return 'duplicate', 'Marcación repetida de una salida existente.'
        return 'review', 'La marcación es anterior a la última salida registrada.'
    if punch - last_out <= dedupe:
        return 'duplicate', 'Marcación repetida dentro de la ventana de duplicados.'
    if device_mode and says_out:
        return 'review', 'El reloj indica salida pero no hay una entrada abierta.'
    return 'check_in', ''
