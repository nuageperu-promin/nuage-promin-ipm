# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
"""Arma los datos que imprime la guía de remisión remitente (formato PROMIN).

No importa nada de Odoo: recibe el picking (o un objeto con los mismos
atributos) y devuelve un diccionario, de modo que se prueba sin base de datos.
"""
import re


def _vacio(valor):
    return valor in (False, None, '')


def si_no(valor):
    return 'SI' if valor else 'NO'


def fmt_fecha(valor):
    return valor.strftime('%d/%m/%Y') if valor else ''


def fmt_cantidad(valor):
    return '{:,.2f}'.format(valor or 0.0)


def fmt_peso(valor):
    return '{:.3f}'.format(valor or 0.0)


def direccion(partner):
    """Calle y segunda línea, luego distrito - provincia - departamento."""
    if not partner:
        return ''
    distrito = getattr(partner, 'l10n_pe_district', False)
    estado = getattr(partner, 'state_id', False)
    calle = ', '.join(p for p in (partner.street, partner.street2) if not _vacio(p))
    partes = [
        calle,
        distrito.name if distrito else '',
        partner.city,
        estado.name if estado else '',
    ]
    return ' - '.join(p for p in partes if not _vacio(p))


def texto_plano(html):
    """Quita etiquetas HTML y devuelve las líneas con texto."""
    if _vacio(html):
        return []
    texto = re.sub(r'</(p|div|li|tr)>|<br\s*/?>', '\n', str(html))
    texto = re.sub(r'<[^>]+>', '', texto)
    texto = texto.replace('&nbsp;', ' ').replace('&amp;', '&')
    return [linea.strip() for linea in texto.splitlines() if linea.strip()]


def punto_partida(picking, company):
    """Misma regla que usa Solse para el punto de partida."""
    tipo = picking.picking_type_id.code if picking.picking_type_id else ''
    origen = getattr(picking, 'almacen_origen', False)
    partner = company.partner_id
    if tipo in ('internal', 'outgoing') and origen:
        partner = origen.partner_id
    if tipo == 'incoming':
        partner = picking.partner_id
    if picking.pe_transfer_code == '02':
        partner = picking.partner_id
    return partner


def punto_llegada(picking, company):
    tipo = picking.picking_type_id.code if picking.picking_type_id else ''
    destino = getattr(picking, 'almacen_destino', False)
    partner = picking.partner_id
    if tipo == 'internal' and destino:
        partner = destino.partner_id
    if tipo == 'incoming':
        partner = company.partner_id
    if picking.pe_transfer_code == '02':
        partner = company.partner_id
    return partner


def _sin_codigo(texto):
    """Odoo antepone «[código] » al nombre; el formato lo muestra en otra columna."""
    return re.sub(r'^\[[^\]]*\]\s*', '', texto or '')


def _unidad(move):
    uom = getattr(move, 'product_uom', None)
    if not uom:
        return ''
    return getattr(uom, 'sunat_code', None) or getattr(uom, 'unece_code', None) or uom.name or ''


def preparar_datos(picking, etiquetas, orden_compra='', facturas=(), observaciones=(),
                   conductores=(), hoy=None):
    """Devuelve el diccionario que consume la plantilla.

    etiquetas: {'motivo': 'Venta', 'modalidad': 'Transporte Privado'}
    facturas: lista de (tipo_documento, numero, ruc_emisor)
    conductores: lista de dicts ya resueltos (placa, dni, nombre, licencia, tuce, principal)
    """
    company = picking.company_id
    partner = picking.partner_id
    publico = picking.pe_transport_mode == '01'
    numero = picking.pe_guide_number if picking.pe_guide_number not in ('/', False, None) else (picking.name or '')

    items = []
    for n, move in enumerate(picking.move_ids, start=1):
        producto = move.product_id
        items.append({
            'n': n,
            'codigo': producto.default_code or '',
            'desc': _sin_codigo(move.description_picking or producto.name),
            'um': _unidad(move),
            'cant': fmt_cantidad(move.quantity or move.product_uom_qty),
        })

    return {
        'numero': numero,
        'ruc_emisor': company.vat or '',
        'emisor': company.name or '',
        'destinatario': partner.name or '',
        'destinatario_ruc': partner.vat or '',
        'fecha_emision': fmt_fecha(picking.pe_date_issue or hoy),
        'fecha_traslado': '' if publico else fmt_fecha(picking.scheduled_date),
        'fecha_entrega': fmt_fecha(picking.pe_delivery_date) if publico else '',
        'publico': publico,
        'partida': direccion(punto_partida(picking, company)),
        'llegada': direccion(punto_llegada(picking, company)),
        'motivo': (etiquetas.get('motivo') or '').capitalize(),
        'modalidad': (etiquetas.get('modalidad') or '').title(),
        'peso': '%s KGM' % fmt_peso(picking.pe_gross_weight or getattr(picking, 'weight', 0.0)),
        'ind_m1l': si_no(picking.pe_vehiculos_m1_l),
        'ind_envases': si_no(picking.pe_retorno_envase_vacio),
        'ind_transbordo': si_no(picking.pe_transbordo_programado),
        'ind_retorno': si_no(picking.pe_retorno_vehiculo_vacio),
        'items': items,
        'conductores': list(conductores),
        'facturas': [{'tipo': t, 'numero': n, 'ruc': r} for t, n, r in facturas],
        'observaciones': list(observaciones),
        'orden_compra': orden_compra,
        'hash': picking.pe_digest or '',
    }
