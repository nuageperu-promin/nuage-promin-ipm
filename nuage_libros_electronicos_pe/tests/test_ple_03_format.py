# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
"""Pruebas del formato del Libro 3 (estructura 3.1) — no requieren Odoo.

    python3 -m unittest discover -s nuage_libros_electronicos_pe/tests -v
"""
import importlib
import os
import sys
import types
import unittest

_MODELS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models'))
_paquete = types.ModuleType('ple_pkg_03')
_paquete.__path__ = [_MODELS]
sys.modules['ple_pkg_03'] = _paquete
fmt = importlib.import_module('ple_pkg_03.ple_03_format')


def cuenta(naturaleza, debe, haber, rubro='1D0109'):
    return {'naturaleza': naturaleza, 'debe': debe, 'haber': haber, 'rubro': rubro}


class TestNaturaleza(unittest.TestCase):
    def test_por_tipo_de_cuenta_de_odoo(self):
        for tipo in ('asset_cash', 'asset_receivable', 'asset_fixed', 'asset_current'):
            self.assertEqual(fmt.naturaleza_por_tipo(tipo), 'D', tipo)
        for tipo in ('liability_payable', 'liability_current', 'equity', 'equity_unaffected'):
            self.assertEqual(fmt.naturaleza_por_tipo(tipo), 'C', tipo)
        for tipo in ('income', 'expense_direct_cost', 'off_balance', '', None):
            self.assertIsNone(fmt.naturaleza_por_tipo(tipo), tipo)

    def test_cuentas_de_resultado(self):
        self.assertTrue(fmt.es_cuenta_de_resultado('income_other'))
        self.assertTrue(fmt.es_cuenta_de_resultado('expense_depreciation'))
        self.assertFalse(fmt.es_cuenta_de_resultado('equity'))
        self.assertFalse(fmt.es_cuenta_de_resultado(None))


class TestImportes(unittest.TestCase):
    def test_formato_con_negativos(self):
        self.assertEqual(fmt.formatear_saldo(123450), '1234.50')
        self.assertEqual(fmt.formatear_saldo(-123450), '-1234.50')
        self.assertEqual(fmt.formatear_saldo(-5), '-0.05')
        self.assertEqual(fmt.formatear_saldo(0), '0.00')

    def test_saldo_en_su_sentido_natural(self):
        self.assertEqual(fmt.saldo_cuenta('D', 1000, 300), 700)
        self.assertEqual(fmt.saldo_cuenta('C', 300, 1000), 700)
        self.assertEqual(fmt.saldo_cuenta('D', 100, 400), -300)   # activo con saldo acreedor

    def test_periodo_es_el_31_de_diciembre(self):
        self.assertEqual(fmt.periodo_balance(2026), '20261231')


class TestConsolidacion(unittest.TestCase):
    def test_suma_por_rubro(self):
        saldos = fmt.consolidar_rubros([
            cuenta('D', 10000, 0, '1D0109'),
            cuenta('D', 5000, 1000, '1D0109'),
            cuenta('D', 300, 0, '1D0106'),
        ])
        self.assertEqual(saldos, {'1D0109': 14000, '1D0106': 300})

    def test_depreciacion_acumulada_resta_de_su_rubro(self):
        saldos = fmt.consolidar_rubros([
            cuenta('D', 100000, 0, '1D0205'),       # activo fijo
            cuenta('D', 0, 30000, '1D0205'),        # depreciación acumulada
        ])
        self.assertEqual(saldos['1D0205'], 70000)

    def test_pasivo_y_patrimonio_en_sentido_acreedor(self):
        saldos = fmt.consolidar_rubros([
            cuenta('C', 0, 50000, '1D0302'),
            cuenta('C', 0, 80000, '1D0701'),
            cuenta('C', 12000, 0, '1D0707'),        # pérdida acumulada (deudora)
        ])
        self.assertEqual(saldos, {'1D0302': 50000, '1D0701': 80000, '1D0707': -12000})

    def test_cuentas_sin_rubro_o_sin_naturaleza_no_entran(self):
        saldos = fmt.consolidar_rubros([
            cuenta('D', 100, 0, ''),
            cuenta(None, 100, 0, '1D0109'),
            cuenta('D', 100, 0, '1D0109'),
        ])
        self.assertEqual(saldos, {'1D0109': 100})


class TestCuadre(unittest.TestCase):
    def test_estado_balanceado(self):
        cuentas = [cuenta('D', 100000, 0), cuenta('C', 0, 60000), cuenta('C', 0, 40000)]
        self.assertEqual(fmt.totales_situacion(cuentas), (100000, 100000))

    def test_resultado_no_cerrado_va_al_patrimonio(self):
        resultados = [
            {'debe': 0, 'haber': 90000},        # ingresos
            {'debe': 65000, 'haber': 0},        # gastos
        ]
        ganancia = fmt.resultado_no_cerrado(resultados)
        self.assertEqual(ganancia, 25000)
        cuentas = [cuenta('D', 100000, 0), cuenta('C', 0, 75000)]
        activo, pasivo_patrimonio = fmt.totales_situacion(cuentas, ganancia)
        self.assertEqual(activo, pasivo_patrimonio)

    def test_perdida_no_cerrada_resta_del_patrimonio(self):
        self.assertEqual(fmt.resultado_no_cerrado([{'debe': 30000, 'haber': 10000}]), -20000)

    def test_estado_descuadrado_se_detecta(self):
        cuentas = [cuenta('D', 100000, 0), cuenta('C', 0, 99000)]
        activo, pasivo_patrimonio = fmt.totales_situacion(cuentas)
        self.assertNotEqual(activo, pasivo_patrimonio)


class TestEstructura31(unittest.TestCase):
    def test_cinco_campos_y_palote_final(self):
        campos = fmt.linea_31('20261231', '01', '1D0109', 123450).split('|')
        self.assertEqual(len(campos), fmt.CAMPOS_31 + 1)
        self.assertEqual(campos, ['20261231', '01', '1D0109', '1234.50', '1', ''])

    def test_saldo_negativo(self):
        self.assertEqual(fmt.linea_31('20261231', '01', '1D0707', -9900),
                         '20261231|01|1D0707|-99.00|1|')

    def test_rubro_o_catalogo_invalido(self):
        for rubro in ('', None, '1D01090'):
            with self.assertRaises(ValueError):
                fmt.linea_31('20261231', '01', rubro, 100)
        for catalogo in ('', '1', '001', 'AB'):
            with self.assertRaises(ValueError):
                fmt.linea_31('20261231', catalogo, '1D0109', 100)

    def test_filas_ordenadas_y_sin_rubros_en_cero(self):
        filas = fmt.filas_31('20261231', '01',
                             {'1D0701': 80000, '1D0109': 14000, '1D0106': 0})
        self.assertEqual(filas, [
            '20261231|01|1D0109|140.00|1|',
            '20261231|01|1D0701|800.00|1|',
        ])

    def test_llave_unica_una_fila_por_rubro(self):
        filas = fmt.filas_31('20261231', '01', fmt.consolidar_rubros([
            cuenta('D', 100, 0, '1D0109'), cuenta('D', 200, 0, '1D0109')]))
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0], '20261231|01|1D0109|3.00|1|')


if __name__ == '__main__':
    unittest.main()
