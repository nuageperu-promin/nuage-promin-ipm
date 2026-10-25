# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
"""Pruebas del formato del Libro 1 (Caja y Bancos) — no requieren Odoo.

Ejecutar desde la raíz del repositorio:

    python3 -m unittest discover -s nuage_libros_electronicos_pe/tests -v

El directorio no tiene ``__init__.py`` a propósito: Odoo no lo carga como
suite de pruebas del módulo, y estas pruebas no necesitan base de datos.
"""
import importlib.util
import os
import unittest

_RUTA = os.path.join(os.path.dirname(__file__), '..', 'models', 'ple_01_format.py')
_spec = importlib.util.spec_from_file_location('ple_01_format', _RUTA)
fmt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fmt)


def registro_11(**cambios):
    base = {
        'periodo': '20261000', 'cuo': '1234', 'correlativo': 'M000001234',
        'cuenta': '1011001', 'moneda': 'PEN', 'tipo_cp': '', 'serie': '',
        'numero': 'CAJA/2026/00012', 'f_contable': '05/10/2026', 'f_venc': '',
        'f_op': '05/10/2026', 'glosa': 'Cobro de factura', 'debe': 10000,
        'haber': 0, 'estado': '1',
    }
    base.update(cambios)
    return base


def registro_12(**cambios):
    base = {
        'periodo': '20261000', 'cuo': '2001', 'correlativo': 'M000002001',
        'banco': '02', 'cuenta_bancaria': '193-1234567-0-12',
        'f_op': '07/10/2026', 'medio_pago': '008',
        'descripcion': 'Pago a proveedor', 'tipo_doc': '6',
        'nro_doc': '20131312955', 'razon_social': 'PROVEEDOR SAC',
        'nro_transaccion': 'OP-998877', 'debe': 0, 'haber': 50000,
        'estado': '1',
    }
    base.update(cambios)
    return base


class TestImportes(unittest.TestCase):
    def test_centimos_sin_error_de_flotante(self):
        self.assertEqual(fmt.a_centimos(0.1 + 0.2), 30)
        self.assertEqual(fmt.a_centimos(0.285), 29)
        self.assertEqual(fmt.a_centimos(None), 0)

    def test_formato_sin_separador_de_miles(self):
        self.assertEqual(fmt.formatear_importe(123450), '1234.50')
        self.assertEqual(fmt.formatear_importe(5), '0.05')
        self.assertEqual(fmt.formatear_importe(0), '0.00')

    def test_negativo_no_se_formatea(self):
        with self.assertRaises(ValueError):
            fmt.formatear_importe(-1)

    def test_dividir_neto_es_excluyente(self):
        self.assertEqual(fmt.dividir_neto(700), (700, 0))
        self.assertEqual(fmt.dividir_neto(-400), (0, 400))
        self.assertEqual(fmt.dividir_neto(0), (0, 0))


class TestTextoYCatalogos(unittest.TestCase):
    def test_alfanumerico_cambia_barra_por_guion(self):
        self.assertEqual(fmt.sanear_alfanumerico('BNK1/2026/00012', 20), 'BNK1-2026-00012')
        self.assertNotIn('|', fmt.sanear_alfanumerico('a|b\\c', 20))

    def test_recorte_desde_la_cola_conserva_la_parte_unica(self):
        largo = 'DIARIO-BANCO-INTERBANK-2026-00012345'
        self.assertEqual(fmt.sanear_alfanumerico(largo, 10, desde_cola=True), largo[-10:])
        self.assertEqual(fmt.sanear_alfanumerico(largo, 10), largo[:10])

    def test_texto_libre_sin_caracteres_prohibidos(self):
        texto = fmt.sanear_texto('Pago | factura F001/123 \\ saldo\nfinal')
        for prohibido in '|/\\\n':
            self.assertNotIn(prohibido, texto)

    def test_codigos_de_catalogo_con_respaldo(self):
        self.assertEqual(fmt.normalizar_codigo_banco('2'), '02')
        self.assertEqual(fmt.normalizar_codigo_banco(''), '99')
        self.assertEqual(fmt.normalizar_codigo_banco('ABC'), '99')
        self.assertEqual(fmt.normalizar_medio_pago('8'), '008')
        self.assertEqual(fmt.normalizar_medio_pago(False), '999')

    def test_ruc_modulo_11(self):
        self.assertTrue(fmt.ruc_valido('20131312955'))     # RUC de SUNAT
        self.assertFalse(fmt.ruc_valido('20131312954'))
        self.assertFalse(fmt.ruc_valido('2013131295'))
        self.assertFalse(fmt.ruc_valido('2013131295X'))

    def test_documento_girador_segun_reglas_generales(self):
        self.assertEqual(fmt.documento_girador('1', '12345678'), ('1', '12345678'))
        self.assertEqual(fmt.documento_girador('1', '1234567'), ('-', '-'))      # DNI corto
        self.assertEqual(fmt.documento_girador('1', '1234567A'), ('-', '-'))     # no numérico
        self.assertEqual(fmt.documento_girador('6', '20131312955'), ('6', '20131312955'))
        self.assertEqual(fmt.documento_girador('6', '20131312954'), ('-', '-'))  # módulo 11
        self.assertEqual(fmt.documento_girador('4', 'AB123'), ('4', 'AB123'))
        self.assertEqual(fmt.documento_girador('4', 'AB 123'), ('-', '-'))
        self.assertEqual(fmt.documento_girador('9', '123'), ('-', '-'))          # tipo desconocido
        self.assertEqual(fmt.documento_girador('', ''), ('-', '-'))


class TestEstructura11(unittest.TestCase):
    def test_diecinueve_campos_y_palote_final(self):
        campos = fmt.linea_11(registro_11()).split('|')
        self.assertEqual(len(campos), fmt.CAMPOS_11 + 1)
        self.assertEqual(campos[-1], '')

    def test_posiciones_segun_la_hoja_oficial(self):
        c = fmt.linea_11(registro_11()).split('|')
        self.assertEqual(c[0], '20261000')              # C1 periodo AAAAMM00
        self.assertEqual(c[1], '1234')                  # C2 CUO
        self.assertEqual(c[2], 'M000001234')            # C3 correlativo
        self.assertEqual(c[3], '1011001')               # C4 cuenta
        self.assertEqual((c[4], c[5]), ('', ''))        # C5, C6 opcionales
        self.assertEqual(c[6], 'PEN')                   # C7 moneda
        self.assertEqual(c[7], '00')                    # C8 comprobante obligatorio
        self.assertEqual(c[9], 'CAJA-2026-00012')       # C10 sin barras
        self.assertEqual(c[15], '100.00')               # C16 debe
        self.assertEqual(c[16], '0.00')                 # C17 haber
        self.assertEqual(c[17], '')                     # C18 dato estructurado
        self.assertEqual(c[18], '1')                    # C19 estado

    def test_consolida_por_llave_y_netea(self):
        filas = fmt.consolidar_11([
            registro_11(debe=10000, haber=0),
            registro_11(debe=0, haber=3000),
            registro_11(cuenta='1021001', debe=500, haber=0),
        ])
        self.assertEqual(len(filas), 2)
        self.assertEqual((filas[0]['debe'], filas[0]['haber']), (7000, 0))
        self.assertEqual((filas[1]['debe'], filas[1]['haber']), (500, 0))

    def test_neto_negativo_pasa_al_haber(self):
        filas = fmt.consolidar_11([
            registro_11(debe=1000, haber=0), registro_11(debe=0, haber=5000)])
        self.assertEqual((filas[0]['debe'], filas[0]['haber']), (0, 4000))

    def test_misma_cuenta_en_asientos_distintos_no_se_funde(self):
        filas = fmt.consolidar_11([
            registro_11(cuo='1', correlativo='M000000001', numero='A-1'),
            registro_11(cuo='2', correlativo='M000000002', numero='A-2')])
        self.assertEqual(len(filas), 2)

    def test_el_total_neto_no_cambia(self):
        regs = [registro_11(debe=1234, haber=0), registro_11(debe=0, haber=234),
                registro_11(debe=99, haber=0)]
        antes = sum(r['debe'] - r['haber'] for r in regs)
        filas = fmt.consolidar_11(regs)
        self.assertEqual(sum(f['debe'] - f['haber'] for f in filas), antes)


class TestEstructura12(unittest.TestCase):
    def test_quince_campos_y_palote_final(self):
        campos = fmt.linea_12(registro_12()).split('|')
        self.assertEqual(len(campos), fmt.CAMPOS_12 + 1)
        self.assertEqual(campos[-1], '')

    def test_posiciones_segun_la_hoja_oficial(self):
        c = fmt.linea_12(registro_12()).split('|')
        self.assertEqual(c[3], '02')                    # C4 entidad financiera
        self.assertEqual(c[4], '193-1234567-0-12')      # C5 cuenta bancaria
        self.assertEqual(c[5], '07/10/2026')            # C6 fecha de operación
        self.assertEqual(c[6], '008')                   # C7 medio de pago
        self.assertEqual(c[8:11], ['6', '20131312955', 'PROVEEDOR SAC'])  # C9-C11
        self.assertEqual(c[11], 'OP-998877')            # C12 nro de transacción
        self.assertEqual((c[12], c[13]), ('0.00', '500.00'))  # C13 / C14
        self.assertEqual(c[14], '1')                    # C15 estado

    def test_respaldos_cuando_faltan_datos(self):
        c = fmt.linea_12(registro_12(
            banco='', medio_pago='', descripcion='', tipo_doc='', nro_doc='',
            razon_social='')).split('|')
        self.assertEqual(c[3], '99')
        self.assertEqual(c[6], '999')
        self.assertEqual(c[7], 'MOVIMIENTO BANCARIO')
        self.assertEqual(c[8:11], ['-', '-', 'varios'])

    def test_girador_distinto_en_la_misma_llave_es_operacion_multiple(self):
        filas = fmt.consolidar_12([
            registro_12(debe=0, haber=30000),
            registro_12(debe=0, haber=20000, nro_doc='12345678', tipo_doc='1',
                        razon_social='OTRA PERSONA')])
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]['haber'], 50000)
        self.assertEqual((filas[0]['tipo_doc'], filas[0]['nro_doc']), ('-', '-'))
        self.assertEqual(filas[0]['razon_social'], 'varios')

    def test_mismo_girador_conserva_sus_datos(self):
        filas = fmt.consolidar_12([
            registro_12(debe=0, haber=30000), registro_12(debe=0, haber=20000)])
        self.assertEqual(filas[0]['nro_doc'], '20131312955')

    def test_neto_cero_se_descarta(self):
        filas = fmt.consolidar_12([
            registro_12(debe=1000, haber=0), registro_12(debe=0, haber=1000)])
        self.assertEqual(filas, [])

    def test_nunca_salen_debe_y_haber_a_la_vez(self):
        filas = fmt.consolidar_12([
            registro_12(debe=9000, haber=0), registro_12(debe=0, haber=4000)])
        self.assertEqual((filas[0]['debe'], filas[0]['haber']), (5000, 0))


if __name__ == '__main__':
    unittest.main()
