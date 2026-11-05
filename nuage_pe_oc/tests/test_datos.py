# -*- coding: utf-8 -*-
import datetime
import unittest
from types import SimpleNamespace as NS

from odoo.addons.nuage_pe_oc.models import oc_datos


def _orden(tipo='pml'):
    company = NS(
        name='PROVEEDORES MINEROS SAC', vat='20100000001', phone='01 1234567',
        website='https://www.promin.pe', logo=False,
        partner_id=NS(name='PROVEEDORES MINEROS SAC', street='Av. X 123', street2='', city='Lima', state_id=NS(name='Lima')),
        nuage_oc_notas_local='', nuage_oc_pie_local='',
        nuage_oc_notas_importacion='', nuage_oc_pie_importacion='')
    partner = NS(name='PROVEEDOR SA', vat='20555555555', phone='',
                 street='Jr. Y 45', street2='', city='Callao', state_id=NS(name='Callao'))
    linea = NS(display_type=False, product_qty=3, product_uom_id=NS(name='Unidades'),
               name='[AB-1] Perno 1/2', product_id=NS(default_code='AB-1'),
               date_planned=datetime.date(2026, 10, 30), price_unit=14.8333,
               price_subtotal=44.50)
    return NS(
        company_id=company, partner_id=partner, nuage_tipo_oc=tipo, name='PMS-0000561',
        currency_id=NS(name='PEN'), dest_address_id=False,
        picking_type_id=False, order_line=[linea], date_order=datetime.date(2026, 10, 22),
        payment_term_id=NS(name='30 días'), incoterm_id=False, partner_ref='C-1',
        amount_untaxed=44.50, amount_tax=8.01, amount_total=52.51,
        user_id=NS(name='juan perez'))


class TestDatos(unittest.TestCase):
    def test_precio_hasta_cuatro_decimales(self):
        self.assertEqual(oc_datos.fmt_precio(14.8333), '14.8333')
        self.assertEqual(oc_datos.fmt_precio(10), '10.00')
        self.assertEqual(oc_datos.fmt_precio(10.5), '10.50')

    def test_local(self):
        d = oc_datos.preparar_datos(_orden())
        self.assertEqual(d['items'][0]['desc'], 'Perno 1/2')
        self.assertEqual(d['porcentaje_igv'], 18)
        self.assertEqual(d['total'], '52.51')
        self.assertEqual(d['comprador'], 'JUAN PEREZ')
        self.assertTrue(d['notas'])

    def test_importacion(self):
        d = oc_datos.preparar_datos(_orden('pms'), 'importacion')
        self.assertEqual(len(d['notas_columnas']), 2)
        self.assertIn('WPM', d['pie'][0])
