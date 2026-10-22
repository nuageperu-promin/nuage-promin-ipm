# -*- coding: utf-8 -*-
"""Pruebas del protocolo y de las reglas (sin Odoo).

Ejecutar solo con Python:  python3 tests/test_protocol.py
"""
import importlib.util
import os
import unittest
from datetime import datetime, timedelta

_spec = importlib.util.spec_from_file_location(
    'zk_protocol_under_test',
    os.path.join(os.path.dirname(__file__), '..', 'zk_protocol.py'))
zkp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(zkp)

T0 = datetime(2026, 10, 21, 12, 58, 12)


class TestParse(unittest.TestCase):
    def test_tab_separated(self):
        body = '12\t2026-10-21 07:58:12\t0\t1\t0\t0\t0\n7\t2026-10-21 08:00:00\t1\t15\t0\n'
        recs, errs = zkp.parse_attlog(body)
        self.assertEqual(errs, [])
        self.assertEqual([r['pin'] for r in recs], ['12', '7'])
        self.assertEqual(recs[0]['punch'], datetime(2026, 10, 21, 7, 58, 12))
        self.assertEqual(recs[0]['status'], '0')
        self.assertEqual(recs[1]['verify'], '15')

    def test_crlf_blank_and_nul(self):
        body = '12\t2026-10-21 07:58:12\t0\t1\r\n\r\n\x00\n'
        recs, errs = zkp.parse_attlog(body)
        self.assertEqual(len(recs), 1)
        self.assertEqual(errs, [])

    def test_space_separated_fallback(self):
        recs, errs = zkp.parse_attlog('12 2026-10-21 07:58:12 0 1')
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]['status'], '0')

    def test_garbage_goes_to_errors(self):
        recs, errs = zkp.parse_attlog('hola\n12\t2026-13-45 99:00:00\t0\n')
        self.assertEqual(recs, [])
        self.assertEqual(len(errs), 2)

    def test_empty(self):
        self.assertEqual(zkp.parse_attlog(''), ([], []))
        self.assertEqual(zkp.parse_attlog(None), ([], []))


class TestTimezone(unittest.TestCase):
    def test_lima_to_utc(self):
        self.assertEqual(
            zkp.local_to_utc(datetime(2026, 10, 21, 7, 58, 12), 'America/Lima'),
            datetime(2026, 10, 21, 12, 58, 12))

    def test_utc_noop(self):
        d = datetime(2026, 1, 1, 0, 0, 0)
        self.assertEqual(zkp.local_to_utc(d, 'UTC'), d)


class TestResponses(unittest.TestCase):
    def test_handshake(self):
        txt = zkp.handshake_response('ABC123', '555')
        self.assertTrue(txt.startswith('GET OPTION FROM: ABC123\n'))
        self.assertIn('ATTLOGStamp=555', txt)
        self.assertIn('Realtime=1', txt)
        self.assertIn('ATTLOGStamp=None', zkp.handshake_response('ABC123'))

    def test_push_3x(self):
        self.assertIn('RegistryCode=', zkp.registry_response())
        self.assertIn('ServerVersion=', zkp.push_config_response())


class TestDecide(unittest.TestCase):
    def d(self, **kw):
        base = dict(punch=T0, last_in=None, last_out=None, later_check_in=None)
        base.update(kw)
        return zkp.decide_punch(**base)

    def test_first_punch_is_check_in(self):
        self.assertEqual(self.d()[0], 'check_in')

    def test_false_means_empty(self):
        # Odoo entrega False para fechas vacías
        self.assertEqual(self.d(last_in=T0 - timedelta(hours=9), last_out=False,
                                later_check_in=False)[0], 'check_out')
        self.assertEqual(self.d(last_in=False, last_out=False)[0], 'check_in')

    def test_open_shift_closes(self):
        a = self.d(last_in=T0 - timedelta(hours=9))
        self.assertEqual(a[0], 'check_out')

    def test_closed_then_new_in(self):
        a = self.d(last_in=T0 - timedelta(hours=20), last_out=T0 - timedelta(hours=10))
        self.assertEqual(a[0], 'check_in')

    def test_duplicate_after_in(self):
        a = self.d(last_in=T0 - timedelta(seconds=20))
        self.assertEqual(a[0], 'duplicate')

    def test_duplicate_after_out(self):
        a = self.d(last_in=T0 - timedelta(hours=9), last_out=T0 - timedelta(seconds=30))
        self.assertEqual(a[0], 'duplicate')

    def test_stale_shift_review_or_autoclose(self):
        stale = T0 - timedelta(hours=30)
        self.assertEqual(self.d(last_in=stale)[0], 'review')
        self.assertEqual(
            self.d(last_in=stale, auto_close_stale=True)[0], 'close_stale_and_check_in')

    def test_before_last_out_review(self):
        a = self.d(last_in=T0 - timedelta(hours=9), last_out=T0 + timedelta(hours=1))
        self.assertEqual(a[0], 'review')

    def test_later_attendance_review_or_duplicate(self):
        self.assertEqual(self.d(later_check_in=T0 + timedelta(hours=2))[0], 'review')
        self.assertEqual(self.d(later_check_in=T0 + timedelta(seconds=10))[0], 'duplicate')

    def test_device_mode(self):
        # el reloj dice SALIDA pero no hay entrada -> revisar
        self.assertEqual(self.d(mode='device', status='1')[0], 'review')
        # el reloj dice ENTRADA con turno abierto -> revisar
        self.assertEqual(
            self.d(mode='device', status='0', last_in=T0 - timedelta(hours=3))[0], 'review')
        # coherente -> normal
        self.assertEqual(self.d(mode='device', status='0')[0], 'check_in')
        self.assertEqual(
            self.d(mode='device', status='1', last_in=T0 - timedelta(hours=3))[0], 'check_out')
        # break (2/3) en modo reloj -> alterna
        self.assertEqual(
            self.d(mode='device', status='2', last_in=T0 - timedelta(hours=3))[0], 'check_out')


if __name__ == '__main__':
    unittest.main()
