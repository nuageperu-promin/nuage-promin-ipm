# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo.tests.common import BaseCase, tagged

from ..models.calculo import asignar_pago, calcular_retencion


@tagged('post_install', '-at_install')
class TestCalculoRetencion(BaseCase):

    def test_ejemplo_rt08_00002878(self):
        """Dos facturas de METAL GRAF pagadas juntas: 708,94 supera 700."""
        retenidos, total = calcular_retencion(
            [('a', 494.18, True), ('b', 214.76, True)], 3.0, 700.0)
        self.assertEqual(retenidos, {'a': 14.83, 'b': 6.44})
        self.assertEqual(total, 21.27)

    def test_una_sola_factura_bajo_umbral(self):
        retenidos, total = calcular_retencion([('a', 494.18, True)], 3.0, 700.0)
        self.assertEqual((retenidos, total), ({}, 0.0))

    def test_umbral_estricto(self):
        self.assertEqual(calcular_retencion([('a', 700.0, True)], 3.0, 700.0), ({}, 0.0))
        retenidos, total = calcular_retencion([('a', 700.01, True)], 3.0, 700.0)
        self.assertEqual(total, 21.0)

    def test_no_retenibles_no_suman(self):
        retenidos, total = calcular_retencion(
            [('a', 494.18, True), ('b', 214.76, False)], 3.0, 700.0)
        self.assertEqual((retenidos, total), ({}, 0.0))

    def test_asignar_pago(self):
        self.assertEqual(asignar_pago([500, 300], 600), [500.0, 100.0])
        self.assertEqual(asignar_pago([100], 150), [100.0])
        self.assertEqual(asignar_pago([100, 100], 0), [0.0, 0.0])

    def test_ejemplo_rt08_00002911_usd(self):
        """Factura en USD: el umbral se evalúa en soles (1,660.26 USD x 3.4309 = S/ 5,696)."""
        retenidos, total = calcular_retencion([('a', 1660.26, True)], 3.0, 700.0, 3.4309)
        self.assertEqual(retenidos, {'a': 49.81})
        from ..models.calculo import retenido_en_soles
        self.assertEqual(retenido_en_soles(1660.26, 3.4309, 3.0), 170.89)

    def test_usd_bajo_umbral_en_soles(self):
        # 150 USD x 3.43 = S/ 514.5, no supera 700
        self.assertEqual(calcular_retencion([('a', 150, True)], 3.0, 700.0, 3.43), ({}, 0.0))
