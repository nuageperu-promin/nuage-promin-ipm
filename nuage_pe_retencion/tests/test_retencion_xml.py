# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
"""Pruebas del XML de retención (UBL 2.0, tipo 20). No usan base de datos.

El caso principal es el ejemplo de la guía oficial de SUNAT (sección 1.5):
emisor 20100113612, proveedor 20100070970, retenido 517.50, pagado 16732.50,
con un documento en soles (0001-14) y otro en dólares (E001-457, TC 3.25).
"""
import copy
import os
import shutil
import subprocess
import tempfile
from datetime import date

from lxml import etree
from odoo.tests.common import BaseCase, tagged

from ..models.retencion_xml import (
    NS_CAC, NS_CBC, NS_DS, NS_EXT, NS_RETENCION, NS_SAC,
    construir_xml, nombre_archivo, validar)

NS = {'r': NS_RETENCION, 'cac': NS_CAC, 'cbc': NS_CBC, 'sac': NS_SAC, 'ds': NS_DS, 'ext': NS_EXT}


def datos_guia():
    return {
        'serie_numero': 'R001-00000123',
        'fecha_emision': date(2026, 11, 3),
        'agente': {
            'ruc': '20100113612', 'razon_social': 'PROVEEDORES MINEROS S.A.C.',
            'nombre_comercial': 'PROMIN',
            'direccion': {'ubigeo': '150101', 'calle': 'CALLE SALAVERRY 352',
                          'urbanizacion': 'EL PINO', 'provincia': 'LIMA',
                          'departamento': 'LIMA', 'distrito': 'SAN LUIS'}},
        'proveedor': {'ruc': '20100070970', 'razon_social': 'EMPRESA PROVEEDORA S.A.'},
        'codigo_regimen': '01', 'tasa': 3.0, 'nota': 'Observación de prueba',
        'moneda': 'PEN', 'total_retenido': 517.50, 'total_pagado': 16732.50,
        'documentos': [
            {'tipo': '01', 'serie_numero': '0001-14', 'fecha_emision': date(2026, 10, 20),
             'moneda': 'PEN', 'importe_total': 14000.0, 'pago_nro': 1, 'pago_importe': 14000.0,
             'pago_fecha': date(2026, 11, 2), 'retencion': 420.0,
             'retencion_fecha': date(2026, 11, 2), 'neto': 13580.0, 'tipo_cambio': None},
            {'tipo': '01', 'serie_numero': 'E001-457', 'fecha_emision': date(2026, 10, 21),
             'moneda': 'USD', 'importe_total': 1000.0, 'pago_nro': 1, 'pago_importe': 1000.0,
             'pago_fecha': date(2026, 11, 2), 'retencion': 97.5,
             'retencion_fecha': date(2026, 11, 2), 'neto': 3152.5, 'tipo_cambio': 3.25},
        ],
    }


def _hijos(elem):
    return [etree.QName(h).localname for h in elem if isinstance(h.tag, str)]


@tagged('post_install', '-at_install')
class TestRetencionXml(BaseCase):

    def _raiz(self, datos=None):
        return etree.fromstring(construir_xml(datos or datos_guia()))

    def test_orden_de_elementos_segun_la_guia(self):
        raiz = self._raiz()
        self.assertEqual(etree.QName(raiz).localname, 'Retention')
        self.assertEqual(etree.QName(raiz).namespace, NS_RETENCION)
        self.assertEqual(_hijos(raiz), [
            'UBLExtensions', 'UBLVersionID', 'CustomizationID', 'Signature', 'ID', 'IssueDate',
            'AgentParty', 'ReceiverParty', 'SUNATRetentionSystemCode', 'SUNATRetentionPercent',
            'Note', 'TotalInvoiceAmount', 'SUNATTotalPaid',
            'SUNATRetentionDocumentReference', 'SUNATRetentionDocumentReference'])

    def test_cabecera(self):
        raiz = self._raiz()
        txt = lambda xp: raiz.xpath(xp, namespaces=NS)[0].text  # noqa: E731
        self.assertEqual(txt('cbc:UBLVersionID'), '2.0')
        self.assertEqual(txt('cbc:CustomizationID'), '1.0')
        self.assertEqual(txt('cbc:ID'), 'R001-00000123')
        self.assertEqual(txt('cbc:IssueDate'), '2026-11-03')
        self.assertEqual(txt('sac:SUNATRetentionSystemCode'), '01')
        self.assertEqual(txt('sac:SUNATRetentionPercent'), '3.00')
        self.assertEqual(txt('cbc:TotalInvoiceAmount'), '517.50')
        self.assertEqual(txt('sac:SUNATTotalPaid'), '16732.50')
        self.assertEqual(raiz.xpath('cbc:TotalInvoiceAmount/@currencyID', namespaces=NS), ['PEN'])
        self.assertEqual(raiz.xpath('cac:AgentParty/cac:PartyIdentification/cbc:ID/@schemeID',
                                    namespaces=NS), ['6'])
        self.assertEqual(txt('cac:ReceiverParty/cac:PartyIdentification/cbc:ID'), '20100070970')

    def test_agente_con_direccion_y_proveedor_sin_ella(self):
        raiz = self._raiz()
        self.assertEqual(_hijos(raiz.xpath('cac:AgentParty/cac:PostalAddress', namespaces=NS)[0]), [
            'ID', 'StreetName', 'CitySubdivisionName', 'CityName', 'CountrySubentity',
            'District', 'Country'])
        self.assertFalse(raiz.xpath('cac:ReceiverParty/cac:PostalAddress', namespaces=NS))

    def test_documento_en_soles_no_lleva_tipo_de_cambio(self):
        ref = self._raiz().xpath('sac:SUNATRetentionDocumentReference', namespaces=NS)[0]
        self.assertEqual(ref.xpath('cbc:ID/@schemeID', namespaces=NS), ['01'])
        self.assertEqual(ref.xpath('cbc:ID', namespaces=NS)[0].text, '0001-14')
        self.assertEqual(_hijos(ref), ['ID', 'IssueDate', 'TotalInvoiceAmount', 'Payment',
                                       'SUNATRetentionInformation'])
        self.assertEqual(_hijos(ref.xpath('cac:Payment', namespaces=NS)[0]),
                         ['ID', 'PaidAmount', 'PaidDate'])
        info = ref.xpath('sac:SUNATRetentionInformation', namespaces=NS)[0]
        self.assertEqual(_hijos(info), ['SUNATRetentionAmount', 'SUNATRetentionDate',
                                        'SUNATNetTotalPaid'])

    def test_documento_en_dolares_lleva_tipo_de_cambio(self):
        ref = self._raiz().xpath('sac:SUNATRetentionDocumentReference', namespaces=NS)[1]
        self.assertEqual(ref.xpath('cbc:TotalInvoiceAmount/@currencyID', namespaces=NS), ['USD'])
        self.assertEqual(ref.xpath('cac:Payment/cbc:PaidAmount/@currencyID', namespaces=NS), ['USD'])
        self.assertEqual(ref.xpath('sac:SUNATRetentionInformation/sac:SUNATRetentionAmount/@currencyID',
                                   namespaces=NS), ['PEN'])
        cambio = ref.xpath('sac:SUNATRetentionInformation/cac:ExchangeRate', namespaces=NS)[0]
        self.assertEqual(_hijos(cambio), ['SourceCurrencyCode', 'TargetCurrencyCode',
                                          'CalculationRate', 'Date'])
        self.assertEqual([c.text for c in cambio],
                         ['USD', 'PEN', '3.250000', '2026-11-02'])

    def test_importes_con_dos_decimales_exactos(self):
        datos = datos_guia()
        datos['documentos'] = datos['documentos'][:1]
        datos['documentos'][0].update(importe_total=1000.0, pago_importe=1000.0, retencion=30.0,
                                      neto=970.0)
        datos.update(total_retenido=30.0, total_pagado=970.0)
        raiz = self._raiz(datos)
        self.assertEqual(raiz.xpath('cbc:TotalInvoiceAmount', namespaces=NS)[0].text, '30.00')
        self.assertEqual(raiz.xpath('sac:SUNATTotalPaid', namespaces=NS)[0].text, '970.00')

    def test_nota_es_opcional(self):
        datos = datos_guia()
        datos['nota'] = ''
        self.assertFalse(self._raiz(datos).xpath('cbc:Note', namespaces=NS))

    def test_nombre_de_archivo(self):
        self.assertEqual(nombre_archivo('20100113612', 'R001-123'), '20100113612-20-R001-123')

    def test_firma_vacia_y_referencia_coinciden(self):
        raiz = self._raiz()
        firma = raiz.xpath('ext:UBLExtensions//ds:Signature', namespaces=NS)[0]
        self.assertEqual(raiz.xpath('cac:Signature/cac:DigitalSignatureAttachment/'
                                    'cac:ExternalReference/cbc:URI', namespaces=NS)[0].text,
                         '#' + firma.get('Id'))

    # ---- validaciones ----
    def _errores(self, **cambios):
        datos = copy.deepcopy(datos_guia())
        datos.update(cambios)
        return validar(datos)

    def test_datos_de_la_guia_son_validos(self):
        self.assertEqual(self._errores(), [])

    def test_serie_debe_empezar_con_r(self):
        self.assertTrue(self._errores(serie_numero='F001-00000123'))

    def test_totales_deben_cuadrar(self):
        self.assertTrue(any('total retenido' in e for e in self._errores(total_retenido=500.0)))
        self.assertTrue(any('total pagado' in e for e in self._errores(total_pagado=1.0)))

    def test_proveedor_sin_ruc(self):
        prov = {'ruc': '10123456', 'razon_social': 'X'}
        self.assertTrue(any('RUC' in e for e in self._errores(proveedor=prov)))

    def test_solo_tasa_3(self):
        self.assertTrue(any('3%' in e for e in self._errores(tasa=6.0)))

    def test_moneda_extranjera_exige_tipo_de_cambio(self):
        datos = copy.deepcopy(datos_guia())
        datos['documentos'][1]['tipo_cambio'] = None
        self.assertTrue(any('tipo de cambio' in e for e in validar(datos)))

    def test_construir_levanta_valueerror_con_todos_los_problemas(self):
        datos = datos_guia()
        datos['serie_numero'] = 'X'
        datos['total_pagado'] = 1.0
        with self.assertRaises(ValueError) as cm:
            construir_xml(datos)
        self.assertIn('R###', str(cm.exception))
        self.assertIn('total pagado', str(cm.exception))

    # ---- firma real (mismos pasos que solse_pe_cpe.cpe_core.get_sign_document) ----
    def test_firma_xmlsec(self):
        try:
            import xmlsec
        except ImportError:
            self.skipTest('xmlsec no está instalado')
        if not shutil.which('openssl'):
            self.skipTest('openssl no está disponible')
        carpeta = tempfile.mkdtemp()
        try:
            key, crt = os.path.join(carpeta, 'k.pem'), os.path.join(carpeta, 'c.pem')
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', key,
                            '-out', crt, '-days', '2', '-subj', '/CN=PROMIN PRUEBA/O=NUAGE'],
                           check=True, capture_output=True)
            raiz = etree.fromstring(construir_xml(datos_guia()))
            nodo = xmlsec.tree.find_node(raiz, xmlsec.Node.SIGNATURE)
            ctx = xmlsec.SignatureContext()
            llave = xmlsec.Key.from_memory(open(key, 'rb').read(), xmlsec.KeyFormat.PEM)
            llave.load_cert_from_memory(open(crt, 'rb').read(), xmlsec.KeyFormat.PEM)
            ctx.key = llave
            ctx.sign(nodo)
            firmado = etree.tostring(raiz)
            # el digest, la firma y el certificado quedaron llenos
            raiz2 = etree.fromstring(firmado)
            for tag in ('DigestValue', 'SignatureValue', 'X509Certificate'):
                self.assertTrue(raiz2.xpath('//ds:%s' % tag, namespaces=NS)[0].text.strip(), tag)
            # y la firma verifica
            nodo2 = xmlsec.tree.find_node(raiz2, xmlsec.Node.SIGNATURE)
            ctx2 = xmlsec.SignatureContext()
            llave2 = xmlsec.Key.from_memory(open(crt, 'rb').read(), xmlsec.KeyFormat.CERT_PEM)
            ctx2.key = llave2
            ctx2.verify(nodo2)
            # alterar un importe invalida la firma
            alterado = etree.fromstring(firmado.replace(b'517.50', b'999.99'))
            ctx3 = xmlsec.SignatureContext()
            ctx3.key = xmlsec.Key.from_memory(open(crt, 'rb').read(), xmlsec.KeyFormat.CERT_PEM)
            with self.assertRaises(xmlsec.Error):
                ctx3.verify(xmlsec.tree.find_node(alterado, xmlsec.Node.SIGNATURE))
        finally:
            shutil.rmtree(carpeta, ignore_errors=True)
