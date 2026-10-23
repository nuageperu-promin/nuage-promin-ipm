# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
"""Arma los datos que imprime el reporte de la orden de compra.

No importa nada de Odoo: recibe la orden (o un objeto con los mismos atributos)
y devuelve un diccionario. Así se puede probar el formato con los datos de los
PDF reales sin levantar una base de datos.
"""
import math
import re

# Textos fijos del formato de PROMIN, transcritos de los PDF de Alicia Quispe.
# Se conservan tal cual (incluidas sus erratas). Cada compañía puede
# reemplazarlos desde la pestaña «Órdenes de compra (Nuage)».
NOTAS_LOCAL = """* Los materiales deben estar correctamente embalados
* Adjuntar copia de la OC y Factura, caso contrario no se recepcionarán los materiales
* El correlativo de su guía y factura debe ser el que figura en la OC caso contrario detallar con una nota
* Coordinar previamente con almacén para entregas que requieran uso de montacargas: 989085108
*Junto con su factura debe de enviar la "Validación del comprobante en SUNAT" caso contrario la factura no será aceptada
* La fecha de pago se contabilizará desde el momento en que se recibe la factura junto con la validación del comprobante de SUNAT"""

PIE_LOCAL = """SOMOS AGENTE DE RETENCION SEGUN R.S.
N° 378-2013-SUNAT"""

NOTAS_IMPORTACION = """* All export documents must show our purchase order.
* The goods must be shipped to the forwarder with its packing list.
* Send technical specifications, country of origin and certificate of compliance.
* After shipment Pls., to send us the original invoice and a copy to the forwarder"""

PIE_IMPORTACION = """Peruvian goverment has revised its important regulation for wood packing material (WPM). The regulation requires WPM coming into Perú to be treated and market."""

MONEDAS = {
    'PEN': ('SOLES', 'S/'),
    'USD': ('DOLARES AMERICANOS', 'US$'),
    'EUR': ('EUROS', 'EUR'),
}


def _vacio(valor):
    return valor in (False, None, '')


def fmt_monto(valor):
    return '{:,.2f}'.format(valor or 0.0)


def fmt_precio(valor):
    """Dos decimales como mínimo y hasta cuatro si el precio los tiene."""
    texto = '{:,.4f}'.format(valor or 0.0)
    entero, _, decimales = texto.partition('.')
    decimales = decimales.rstrip('0').ljust(2, '0')
    return '%s.%s' % (entero, decimales)


def fmt_fecha(valor):
    return valor.strftime('%d/%m/%y') if valor else ''


def lineas_texto(texto):
    return [linea for linea in (texto or '').splitlines() if linea.strip()]


def direccion(partner):
    """Dirección en una línea: calle, calle 2, ciudad y departamento."""
    if not partner:
        return ''
    estado = partner.state_id
    partes = [
        partner.street,
        partner.street2,
        partner.city,
        estado.name if estado else '',
    ]
    return ' - '.join(p for p in partes if not _vacio(p))


def _nombre_uom(linea):
    uom = getattr(linea, 'product_uom_id', None) or getattr(linea, 'product_uom', None)
    if not uom:
        return ''
    return getattr(uom, 'unece_code', None) or uom.name or ''


def _descripcion(linea):
    # Odoo antepone «[código] » al nombre de la línea; el formato lo muestra aparte.
    return re.sub(r'^\[[^\]]*\]\s*', '', linea.name or '')


def _columnas(lineas):
    mitad = int(math.ceil(len(lineas) / 2.0))
    return [lineas[:mitad], lineas[mitad:]]


def preparar_datos(orden):
    """Devuelve el diccionario que consume la plantilla del reporte."""
    company = orden.company_id
    partner = orden.partner_id
    tipo = getattr(orden, 'nuage_tipo_oc', None) or 'local'
    moneda_codigo = orden.currency_id.name
    moneda_nombre, simbolo = MONEDAS.get(moneda_codigo, (moneda_codigo, moneda_codigo))

    # Entrega: dirección de entrega directa, almacén del tipo de operación o la compañía.
    destino = orden.dest_address_id
    if not destino and orden.picking_type_id and orden.picking_type_id.warehouse_id:
        destino = orden.picking_type_id.warehouse_id.partner_id
    destino = destino or company.partner_id

    if tipo == 'importacion':
        notas = lineas_texto(company.nuage_oc_notas_importacion or NOTAS_IMPORTACION)
        pie = lineas_texto(company.nuage_oc_pie_importacion or PIE_IMPORTACION)
    else:
        notas = lineas_texto(company.nuage_oc_notas_local or NOTAS_LOCAL)
        pie = lineas_texto(company.nuage_oc_pie_local or PIE_LOCAL)

    items = []
    numero = 0
    for linea in orden.order_line:
        if linea.display_type == 'line_section':
            continue
        if linea.display_type == 'line_note':
            items.append({'nota': True, 'desc': linea.name or '', 'n': '', 'cant': '', 'um': '', 'cat': '', 'entrega': '', 'pu': '', 'total': ''})
            continue
        numero += 1
        producto = linea.product_id
        items.append({
            'nota': False,
            'n': numero,
            'cant': '{:,.2f}'.format(linea.product_qty or 0.0),
            'um': _nombre_uom(linea),
            'desc': _descripcion(linea),
            'cat': producto.default_code if producto and producto.default_code else '',
            'entrega': fmt_fecha(linea.date_planned),
            'pu': fmt_precio(linea.price_unit),
            'total': fmt_monto(linea.price_subtotal),
        })

    bruto = orden.amount_untaxed
    igv = orden.amount_tax
    porcentaje = int(round(igv / bruto * 100)) if bruto and igv else 18

    contacto = []
    if company.phone:
        contacto.append('Telf: %s' % company.phone)
    if getattr(company, 'nuage_oc_fax', None):
        contacto.append('Fax: %s' % company.nuage_oc_fax)
    contacto_2 = []
    if company.vat:
        contacto_2.append('RUC: %s' % company.vat)
    if company.website:
        contacto_2.append('Web: %s' % re.sub(r'^https?://(www\.)?', '', company.website))

    return {
        'tipo': tipo,
        'numero': orden.name or '',
        'fecha': fmt_fecha(orden.date_order),
        'proveedor': {
            'nombre': partner.name or '',
            'ruc': partner.vat or '',
            'direccion': direccion(partner),
            'telefono': partner.phone or '',
            'contacto': '',
        },
        'forma_pago': orden.payment_term_id.name if orden.payment_term_id else '',
        'moneda': moneda_nombre,
        'simbolo': simbolo,
        'incoterm': orden.incoterm_id.code if orden.incoterm_id else '',
        'cotizacion': orden.partner_ref or '',
        # Campos que Alicia aún debe definir (referencia, registro, método de envío, aprobador).
        'referencia': '',
        'registro': '',
        'metodo_envio': '',
        'aprobado_por': '',
        'entrega_nombre': destino.name or '',
        'entrega_direccion': direccion(destino),
        'facturar': {
            'nombre': company.name or '',
            'direccion': direccion(company.partner_id),
            'ruc': company.vat or '',
        },
        'contacto_1': ', '.join(contacto),
        'contacto_2': '. '.join(contacto_2),
        'notas': notas,
        'notas_columnas': _columnas(notas),
        'pie': pie,
        'items': items,
        'bruto': fmt_monto(bruto),
        'igv': fmt_monto(igv),
        'porcentaje_igv': porcentaje,
        'total': fmt_monto(orden.amount_total),
        'comprador': (orden.user_id.name or '').upper() if orden.user_id else '',
    }
