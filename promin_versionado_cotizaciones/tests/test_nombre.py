# -*- coding: utf-8 -*-
import unittest

from odoo.addons.promin_versionado_cotizaciones.models.nombre import nombre_base, nombre_version


class TestNombreVersion(unittest.TestCase):
    def test_base(self):
        self.assertEqual(nombre_base('S00123-V3'), 'S00123')
        self.assertEqual(nombre_base('S00123'), 'S00123')
        self.assertEqual(nombre_base(' S00123-V10 '), 'S00123')

    def test_version_uno_conserva_el_numero(self):
        self.assertEqual(nombre_version('S00123', 1), 'S00123')

    def test_versiones_siguientes(self):
        self.assertEqual(nombre_version('S00123', 2), 'S00123-V2')
        self.assertEqual(nombre_version('S00123-V2', 3), 'S00123-V3')
        self.assertEqual(nombre_version('S00123-V9', 10), 'S00123-V10')
