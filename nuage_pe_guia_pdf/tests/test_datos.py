# -*- coding: utf-8 -*-
import datetime
import unittest
from types import SimpleNamespace as NS

from odoo.addons.nuage_pe_guia_pdf.models import guia_datos


def _picking(modo='02'):
    partner_cia = NS(street='CAL. FELIPE SANTIAGO SALAVERRY 352', street2='', city='LIMA',
                     state_id=NS(name='LIMA'), l10n_pe_district=NS(name='JESUS MARIA'))
    cliente = NS(name='MINERA SOTRAMI S.A.', vat='20258699239', street='AV. SEPARADORA 147',
                 street2='URB. MONTERRICO', city='LIMA', state_id=NS(name='LIMA'),
                 l10n_pe_district=NS(name='LA MOLINA'))
    move = NS(product_id=NS(default_code='MA9345', name='COUPLER'), description_picking=False,
              product_uom=NS(sunat_code='NIU', name='Unidades'), quantity=4, product_uom_qty=4)
    return NS(
        company_id=NS(vat='20497219940', name='PROVEEDORES MINEROS SAC', partner_id=partner_cia),
        partner_id=cliente, picking_type_id=NS(code='outgoing'), almacen_origen=False,
        almacen_destino=False, pe_transfer_code='01', pe_transport_mode=modo,
        pe_guide_number='TG01-00003667', name='WH/OUT/1', pe_date_issue=datetime.date(2026, 10, 21),
        scheduled_date=datetime.date(2026, 10, 21), pe_delivery_date=datetime.date(2026, 10, 21),
        pe_gross_weight=40, pe_vehiculos_m1_l=False, pe_retorno_envase_vacio=False,
        pe_transbordo_programado=False, pe_retorno_vehiculo_vacio=False,
        move_ids=[move], pe_digest='abc=')


class TestDatos(unittest.TestCase):
    def test_privado(self):
        d = guia_datos.preparar_datos(_picking('02'), {'motivo': 'Venta', 'modalidad': 'Transporte Privado'})
        self.assertEqual(d['peso'], '40.000 KGM')
        self.assertEqual(d['fecha_traslado'], '21/10/2026')
        self.assertEqual(d['fecha_entrega'], '')
        self.assertEqual(d['items'][0]['um'], 'NIU')
        self.assertIn('LA MOLINA', d['llegada'])

    def test_publico(self):
        d = guia_datos.preparar_datos(_picking('01'), {})
        self.assertEqual(d['fecha_traslado'], '')
        self.assertEqual(d['fecha_entrega'], '21/10/2026')
        self.assertEqual(d['ind_m1l'], 'NO')

    def test_texto_plano(self):
        self.assertEqual(guia_datos.texto_plano('<p>OC 1</p><p>2 BULTOS</p>'), ['OC 1', '2 BULTOS'])
