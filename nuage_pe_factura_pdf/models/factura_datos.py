# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
"""Datos para el PDF de factura (formato PROMIN). Sin dependencias de Odoo
para poder probarlo con objetos simples."""

MONEDAS = {'PEN': ('Soles', 'S/'), 'USD': ('Dólares Americanos', 'US$'), 'EUR': ('Euros', 'EUR')}
TITULOS = {'factura': 'FACTURA ELECTRÓNICA', 'nc': 'NOTA DE CRÉDITO ELECTRÓNICA',
           'nd': 'NOTA DE DÉBITO ELECTRÓNICA'}
NOMBRE_DOC = {'factura': 'la Factura Electrónica', 'nc': 'la Nota de Crédito Electrónica',
              'nd': 'la Nota de Débito Electrónica'}


def tipo_comprobante(move):
    codigo = getattr(move, 'pe_invoice_code', '') or ''
    if codigo == '07' or move.move_type == 'out_refund':
        return 'nc'
    if codigo == '08' or getattr(move, 'debit_origin_id', False):
        return 'nd'
    return 'factura'

CAMPOS_UM = ('l10n_pe_edi_measure_unit_code', 'unece_code', 'pe_unit_code', 'sunat_code', 'code')
ETIQUETA_DOC = {'6': 'RUC', '1': 'DNI', '4': 'C.E.', '7': 'PASAPORTE'}


def monto(valor):
    return '{:,.2f}'.format(valor or 0.0)


def precio(valor):
    texto = '{:,.4f}'.format(valor or 0.0)
    entero, _, dec = texto.partition('.')
    return '%s.%s' % (entero, dec.rstrip('0').ljust(2, '0'))


def fecha(valor):
    return valor.strftime('%d/%m/%Y') if valor else ''


def codigo_um(uom):
    if not uom:
        return ''
    for campo in CAMPOS_UM:
        valor = getattr(uom, campo, None)
        if valor and isinstance(valor, str):
            return valor
    return uom.name or ''


def _precios(linea):
    """(valor unitario sin IGV, precio unitario con IGV) con descuento aplicado."""
    base = (linea.price_unit or 0.0) * (1 - (getattr(linea, 'discount', 0.0) or 0.0) / 100.0)
    taxes = getattr(linea, 'tax_ids', None)
    if taxes is not None and hasattr(taxes, 'compute_all'):
        res = taxes.compute_all(base, currency=linea.currency_id, quantity=1.0,
                                product=linea.product_id, partner=linea.partner_id)
        return res['total_excluded'], res['total_included']
    return base, base


def _descuento(linea):
    valor = getattr(linea, 'amount_discount', None)
    if valor is None:
        valor = (linea.price_unit or 0.0) * (linea.quantity or 0.0) * (getattr(linea, 'discount', 0.0) or 0.0) / 100.0
    return valor


def _direccion(partner):
    if not partner:
        return ''
    partes = [partner.street, getattr(partner, 'street2', ''), partner.city,
              partner.state_id.name if partner.state_id else '']
    return ' - '.join(p for p in partes if p)


def preparar_datos(move, cuotas=None, guia='', observacion_sunat='', tipo_nota='', doc_origen=''):
    company = move.company_id
    partner = move.partner_id
    codigo = move.currency_id.name
    nombre_mon, simbolo = MONEDAS.get(codigo, (codigo, codigo))
    tipo = tipo_comprobante(move)
    es_nota = tipo != 'factura'
    credito = getattr(move, 'tipo_transaccion', '') == 'credito' and not es_nota

    items = []
    n = 0
    for linea in move.invoice_line_ids:
        if linea.display_type != 'product':
            continue
        n += 1
        v_unit, p_unit = _precios(linea)
        prod = linea.product_id
        items.append({
            'n': n,
            'codigo': prod.default_code if prod and prod.default_code else '',
            'desc': linea.name or '',
            'um': codigo_um(getattr(linea, 'product_uom_id', None)),
            'cant': '{:,.2f}'.format(linea.quantity or 0.0),
            'v_unit': precio(v_unit),
            'p_unit': precio(p_unit),
            'dscto': monto(_descuento(linea)),
            'valor': monto(linea.price_subtotal),
        })

    gravada = getattr(move, 'pe_taxable_amount', 0.0) or 0.0
    inafecta = getattr(move, 'pe_unaffected_amount', 0.0) or 0.0
    exonerada = getattr(move, 'pe_exonerated_amount', 0.0) or 0.0
    exportacion = getattr(move, 'pe_export_amount', 0.0) or 0.0
    if not (gravada or inafecta or exonerada or exportacion):
        gravada = move.amount_untaxed
    base = gravada
    tasa = int(round(move.amount_tax / base * 100)) if base and move.amount_tax else 18

    termino = move.invoice_payment_term_id.name if move.invoice_payment_term_id else ''
    info = []
    if es_nota:
        if tipo == 'nc':
            info.append(('Condiciones de pago / Payment Conditions', (termino or 'Contado').upper()))
        else:
            info.append(('Forma de Pago', (termino or 'Contado').upper()))
    else:
        if company.nuage_fac_mensaje_retencion:
            info.append(('Mensaje Retención', company.nuage_fac_mensaje_retencion))
        if termino:
            info.append(('Condiciones de pago / Payment Conditions', termino.upper()))

    return {
        'tipo': tipo,
        'es_nota': es_nota,
        'titulo': TITULOS[tipo],
        'doc_origen': doc_origen or '',
        'motivo': (getattr(move, 'ref', '') or getattr(move, 'glosa', '') or '') if es_nota else '',
        'tipo_nota': tipo_nota or '',
        'pie_consulta': ('Representación Impresa de %s, consulte en %s' % (NOMBRE_DOC[tipo], company.nuage_fac_url_consulta)
                         if es_nota and company.nuage_fac_url_consulta else ''),
        'pie_powered': company.nuage_fac_powered if es_nota else '',
        'numero': getattr(move, 'l10n_latam_document_number', '') or move.name or '',
        'ruc_emisor': company.vat or '',
        'emisor': company.name or '',
        'emisor_dir': _direccion(company.partner_id),
        'cliente': partner.name or '',
        'doc_label': ETIQUETA_DOC.get(getattr(partner, 'doc_type', ''), 'RUC'),
        'doc_num': getattr(partner, 'doc_number', '') or partner.vat or '',
        'cliente_dir': partner.street or '',
        'fecha': fecha(move.invoice_date),
        'moneda': nombre_mon,
        'simbolo': simbolo,
        'forma_pago': 'Crédito' if credito else 'Contado',
        'orden_compra': getattr(move, 'orden_compra', '') or '',
        'guia': guia or '',
        'items': items,
        'son': getattr(move, 'amount_text', '') or '',
        'gravada': monto(gravada), 'igv': monto(move.amount_tax), 'tasa': tasa,
        'inafecta': monto(inafecta), 'exonerada': monto(exonerada),
        'exportacion': monto(exportacion), 'total': monto(move.amount_total),
        'cuotas': [{'n': i + 1, 'fecha': fecha(c.get('date_maturity')) if not isinstance(c.get('date_maturity'), str) else c.get('date_maturity'),
                    'moneda': nombre_mon.split()[0] if codigo == 'USD' else nombre_mon,
                    'monto': monto(c.get('amount'))} for i, c in enumerate(cuotas or [])] if credito else [],
        'observacion_sunat': observacion_sunat,
        'info': info,
        'autorizacion': company.nuage_fac_autorizacion or '',
    }
