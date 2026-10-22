# -*- coding: utf-8 -*-
"""Flujo completo: peticiones HTTP del reloj -> bitácora -> Asistencias."""
from odoo import fields
from odoo.tests import HttpCase, tagged

SERIAL = 'UFS2254801685'


@tagged('post_install', '-at_install', 'nuage_zk')
class TestZkFlow(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.device = cls.env['zk.device'].create({
            'name': 'Prueba', 'serial_number': SERIAL.lower(),  # se normaliza
            'timezone': 'America/Lima', 'state': 'confirmed',
            'process_from': '2020-01-01 00:00:00',
        })
        cls.emp = cls.env['hr.employee'].create({'name': 'Juan Prueba', 'zk_pin': '12'})

    def _post(self, body, serial=SERIAL, extra=''):
        return self.url_open(
            '/iclock/cdata?SN=%s&table=ATTLOG&Stamp=9999%s' % (serial, extra),
            data=body.encode(), headers={'Content-Type': 'application/push;charset=UTF-8'})

    def _atts(self):
        return self.env['hr.attendance'].search(
            [('employee_id', '=', self.emp.id)], order='check_in')

    def test_00_serial_normalized(self):
        self.assertEqual(self.device.serial_number, SERIAL)

    def test_01_handshake(self):
        res = self.url_open('/iclock/cdata?SN=%s&options=all&pushver=3.0.4S' % SERIAL)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.text.startswith('GET OPTION FROM: %s' % SERIAL))
        self.assertEqual(self.device.push_version, '3.0.4S')
        self.assertTrue(self.device.last_activity)

    def test_02_unknown_and_draft_rejected(self):
        self.assertEqual(self.url_open('/iclock/cdata?SN=NOEXISTE&options=all').status_code, 403)
        self.assertEqual(self.url_open('/iclock/cdata').status_code, 403)
        self.device.state = 'draft'
        self.assertEqual(self.url_open('/iclock/getrequest?SN=%s' % SERIAL).status_code, 403)

    def test_03_getrequest_ok(self):
        res = self.url_open('/iclock/getrequest?SN=%s' % SERIAL)
        self.assertEqual((res.status_code, res.text), (200, 'OK'))

    def test_04_in_out_and_resend(self):
        body = ('12\t2026-10-21 07:58:12\t0\t1\t0\n'
                '12\t2026-10-21 17:03:40\t1\t1\t0\n')
        res = self._post(body)
        self.assertEqual((res.status_code, res.text), (200, 'OK:2'))
        att = self._atts()
        self.assertEqual(len(att), 1)
        self.assertEqual(att.check_in, fields.Datetime.from_string('2026-10-21 12:58:12'))
        self.assertEqual(att.check_out, fields.Datetime.from_string('2026-10-21 22:03:40'))
        self.assertEqual(att.in_mode, 'technical')
        logs = self.env['zk.attendance.log'].search([('device_id', '=', self.device.id)])
        self.assertEqual(set(logs.mapped('state')), {'processed'})
        self.assertEqual(self.device.att_stamp, '9999')
        # reenvío idéntico: no duplica nada
        res = self._post(body)
        self.assertEqual(res.text, 'OK:2')
        self.assertEqual(len(self._atts()), 1)
        self.assertEqual(self.env['zk.attendance.log'].search_count(
            [('device_id', '=', self.device.id)]), 2)

    def test_05_duplicate_window(self):
        self._post('12\t2026-10-21 07:58:12\t0\t1\t0\n12\t2026-10-21 07:58:40\t0\t1\t0\n')
        self.assertEqual(len(self._atts()), 1)
        self.assertFalse(self._atts().check_out)
        states = self.env['zk.attendance.log'].search(
            [('device_id', '=', self.device.id)], order='punch_datetime').mapped('state')
        self.assertEqual(states, ['processed', 'duplicate'])

    def test_06_unmapped_pin_then_mapped(self):
        self._post('99\t2026-10-21 08:00:00\t0\t1\t0\n')
        log = self.env['zk.attendance.log'].search([('pin', '=', '99')])
        self.assertEqual(log.state, 'no_employee')
        emp2 = self.env['hr.employee'].create({'name': 'Otro', 'zk_pin': '99'})
        self.assertEqual(log.state, 'processed')
        self.assertEqual(log.employee_id, emp2)
        self.assertEqual(self.env['hr.attendance'].search_count(
            [('employee_id', '=', emp2.id)]), 1)

    def test_07_before_process_from_ignored(self):
        self.device.process_from = '2026-10-22 00:00:00'
        self._post('12\t2026-10-21 07:58:12\t0\t1\t0\n')
        self.assertFalse(self._atts())
        log = self.env['zk.attendance.log'].search([('pin', '=', '12')])
        self.assertEqual(log.state, 'ignored')

    def test_08_stale_open_shift_needs_review(self):
        self._post('12\t2026-10-18 07:58:12\t0\t1\t0\n')
        self._post('12\t2026-10-21 07:58:12\t0\t1\t0\n')
        logs = self.env['zk.attendance.log'].search([('pin', '=', '12')], order='punch_datetime')
        self.assertEqual(logs.mapped('state'), ['processed', 'review'])
        self.assertEqual(len(self._atts()), 1)

    def test_09_unique_pin_per_company(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.env['hr.employee'].create({'name': 'Duplicado', 'zk_pin': '12'})

    def test_10_debug_logs_requests(self):
        self.device.debug = True
        self._post('12\t2026-10-21 07:58:12\t0\t1\t0\n')
        reqs = self.env['zk.request.log'].search([('device_id', '=', self.device.id)])
        self.assertTrue(reqs)
        self.assertIn('ATTLOG', reqs[0].query)
        self.assertIn('12\t2026-10-21', reqs[0].body)

    def test_11_other_tables_ignored(self):
        res = self.url_open('/iclock/cdata?SN=%s&table=OPERLOG' % SERIAL,
                            data=b'USER PIN=12\tName=Juan', headers={'Content-Type': 'text/plain'})
        self.assertEqual((res.status_code, res.text), (200, 'OK'))

    def test_12_offline_cron_and_recovery(self):
        self.device.last_activity = fields.Datetime.subtract(fields.Datetime.now(), hours=2)
        self.env['zk.device']._cron_check_offline()
        self.assertTrue(self.device.offline_notified)
        self.url_open('/iclock/getrequest?SN=%s' % SERIAL)
        self.assertFalse(self.device.offline_notified)
