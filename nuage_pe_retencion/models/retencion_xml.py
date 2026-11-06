# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
"""XML del Comprobante de Retención Electrónico (UBL 2.0, tipo 20) de SUNAT.

Función pura, sin dependencias de Odoo, para probarla con casos reales sin
levantar una base de datos. Sigue la «Guía de elaboración de documentos
electrónicos XML – Comprobante de Retención Electrónico» v1.2 de SUNAT.

El XML que se devuelve lleva el bloque de firma VACÍO (como hace Solse con las
facturas); la firma la completa `get_sign_document` de solse_pe_cpe con el
certificado de la compañía.
"""
import re
from collections import OrderedDict
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from lxml import etree

NS_RETENCION = 'urn:sunat:names:specification:ubl:peru:schema:xsd:Retention-1'
NS_CAC = 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
NS_CBC = 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
NS_CCTS = 'urn:un:unece:uncefact:documentation:2'
NS_DS = 'http://www.w3.org/2000/09/xmldsig#'
NS_EXT = 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2'
NS_QDT = 'urn:oasis:names:specification:ubl:schema:xsd:QualifiedDatatypes-2'
NS_SAC = 'urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1'
NS_UDT = 'urn:un:unece:uncefact:data:specification:UnqualifiedDataTypesSchemaModule:2'
NS_XSI = 'http://www.w3.org/2001/XMLSchema-instance'

ID_FIRMA = 'signatureNuage'
CODIGO_TIPO_DOCUMENTO = '20'          # Comprobante de retención (catálogo 01)
CODIGO_REGIMEN_TASA_3 = '01'          # Régimen de retención, tasa 3%
TIPOS_REFERENCIA = {'01', '07', '08', '12'}   # factura, NC, ND, ticket
CENTIMO = Decimal('0.01')
TOLERANCIA = Decimal('0.005')


def _d(valor):
    return Decimal(str(valor))


def _monto(valor):
    """Importe con dos decimales exactos (SUNAT observa '3036.0')."""
    return str(_d(valor).quantize(CENTIMO, rounding=ROUND_HALF_UP))


def _fecha(valor):
    if isinstance(valor, datetime):
        valor = valor.date()
    if not isinstance(valor, date):
        raise ValueError('Fecha inválida: %r' % (valor,))
    return valor.strftime('%Y-%m-%d')


def _texto(valor, largo):
    return (valor or '').strip()[:largo]


def nombre_archivo(ruc, serie_numero):
    """Nombre base del archivo: RUC-20-SERIE-CORRELATIVO (sin extensión)."""
    return '%s-%s-%s' % (ruc, CODIGO_TIPO_DOCUMENTO, serie_numero)


def validar(datos):
    """Valida el diccionario de entrada; devuelve la lista de problemas (vacía si todo bien)."""
    errores = []
    if not re.fullmatch(r'R\d{3}-\d{1,8}', datos.get('serie_numero') or ''):
        errores.append('El número del comprobante debe tener el formato R###-########; '
                       'la serie de retención empieza con R.')
    agente = datos.get('agente') or {}
    if not re.fullmatch(r'\d{11}', agente.get('ruc') or ''):
        errores.append('El RUC de la compañía (agente de retención) debe tener 11 dígitos.')
    if not _texto(agente.get('razon_social'), 100):
        errores.append('Falta la razón social de la compañía.')
    prov = datos.get('proveedor') or {}
    if not re.fullmatch(r'\d{11}', prov.get('ruc') or ''):
        errores.append('El proveedor %s no tiene un RUC válido de 11 dígitos; la retención '
                       'electrónica solo se emite a proveedores con RUC.' % (prov.get('razon_social') or ''))
    if not _texto(prov.get('razon_social'), 100):
        errores.append('Falta la razón social del proveedor.')
    if datos.get('codigo_regimen') != CODIGO_REGIMEN_TASA_3 or abs(_d(datos.get('tasa', 0)) - 3) > TOLERANCIA:
        errores.append('SUNAT solo admite la tasa de retención del 3% (régimen 01).')
    if datos.get('moneda') != 'PEN':
        errores.append('Los importes de retención se expresan en soles (PEN).')
    docs = datos.get('documentos') or []
    if not docs:
        errores.append('El comprobante no tiene documentos relacionados.')
    suma_ret = Decimal('0')
    suma_neto = Decimal('0')
    pagos_vistos = set()
    for i, doc in enumerate(docs, 1):
        etiqueta = doc.get('serie_numero') or 'línea %d' % i
        if doc.get('tipo') not in TIPOS_REFERENCIA:
            errores.append('%s: tipo de comprobante %r no admitido (01, 07, 08 o 12).' % (etiqueta, doc.get('tipo')))
        if doc.get('tipo') in ('01', '07', '08') and not re.fullmatch(
                r'[A-Za-z0-9]{4}-\d{1,8}', doc.get('serie_numero') or ''):
            errores.append('%s: la serie debe tener 4 caracteres y el correlativo hasta 8 dígitos.' % etiqueta)
        clave = (doc.get('serie_numero'), doc.get('pago_nro'))
        if clave in pagos_vistos:
            errores.append('%s: el número de pago %s se repite para el mismo comprobante.'
                           % (etiqueta, doc.get('pago_nro')))
        pagos_vistos.add(clave)
        if _d(doc.get('pago_importe', 0)) > _d(doc.get('importe_total', 0)) + TOLERANCIA:
            errores.append('%s: el pago sin retención no puede ser mayor que el total del comprobante.' % etiqueta)
        if doc.get('moneda') != 'PEN' and not doc.get('tipo_cambio'):
            errores.append('%s: falta el tipo de cambio (el comprobante no está en soles).' % etiqueta)
        suma_ret += _d(doc.get('retencion', 0))
        suma_neto += _d(doc.get('neto', 0))
    if abs(suma_ret - _d(datos.get('total_retenido', 0))) > TOLERANCIA:
        errores.append('El total retenido (%s) no coincide con la suma de las retenciones de los '
                       'documentos (%s).' % (_monto(datos.get('total_retenido', 0)), _monto(suma_ret)))
    if abs(suma_neto - _d(datos.get('total_pagado', 0))) > TOLERANCIA:
        errores.append('El total pagado (%s) no coincide con la suma de los netos pagados de los '
                       'documentos (%s).' % (_monto(datos.get('total_pagado', 0)), _monto(suma_neto)))
    return errores


def _sub(padre, ns, nombre, texto=None, **atributos):
    elem = etree.SubElement(padre, '{%s}%s' % (ns, nombre), **atributos)
    if texto is not None:
        elem.text = texto
    return elem


def _parte(padre, nombre_tag, p, con_direccion):
    """AgentParty / ReceiverParty. `p`: ruc, razon_social, nombre_comercial, direccion."""
    parte = _sub(padre, NS_CAC, nombre_tag)
    ident = _sub(parte, NS_CAC, 'PartyIdentification')
    _sub(ident, NS_CBC, 'ID', p['ruc'], schemeID='6')
    comercial = _texto(p.get('nombre_comercial'), 100)
    if comercial and comercial != '-':
        _sub(_sub(parte, NS_CAC, 'PartyName'), NS_CBC, 'Name', comercial)
    dire = p.get('direccion') or {}
    if con_direccion and dire.get('ubigeo') and dire.get('calle'):
        postal = _sub(parte, NS_CAC, 'PostalAddress')
        _sub(postal, NS_CBC, 'ID', _texto(dire.get('ubigeo'), 6))
        _sub(postal, NS_CBC, 'StreetName', _texto(dire.get('calle'), 100))
        if dire.get('urbanizacion'):
            _sub(postal, NS_CBC, 'CitySubdivisionName', _texto(dire['urbanizacion'], 30))
        _sub(postal, NS_CBC, 'CityName', _texto(dire.get('provincia'), 30))
        _sub(postal, NS_CBC, 'CountrySubentity', _texto(dire.get('departamento'), 30))
        _sub(postal, NS_CBC, 'District', _texto(dire.get('distrito'), 30))
        _sub(_sub(postal, NS_CAC, 'Country'), NS_CBC, 'IdentificationCode', 'PE')
    _sub(_sub(parte, NS_CAC, 'PartyLegalEntity'), NS_CBC, 'RegistrationName',
         _texto(p['razon_social'], 100))


def _bloque_firma(contenido):
    """ds:Signature vacío; xmlsec completa digest, firma y certificado."""
    firma = etree.SubElement(contenido, '{%s}Signature' % NS_DS, Id=ID_FIRMA, nsmap={'ds': NS_DS})
    info = _sub(firma, NS_DS, 'SignedInfo')
    _sub(info, NS_DS, 'CanonicalizationMethod', Algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
    _sub(info, NS_DS, 'SignatureMethod', Algorithm='http://www.w3.org/2000/09/xmldsig#rsa-sha1')
    ref = _sub(info, NS_DS, 'Reference', URI='')
    transforms = _sub(ref, NS_DS, 'Transforms')
    _sub(transforms, NS_DS, 'Transform', Algorithm='http://www.w3.org/2000/09/xmldsig#enveloped-signature')
    _sub(ref, NS_DS, 'DigestMethod', Algorithm='http://www.w3.org/2000/09/xmldsig#sha1')
    _sub(ref, NS_DS, 'DigestValue')
    _sub(firma, NS_DS, 'SignatureValue')
    key_info = _sub(firma, NS_DS, 'KeyInfo')
    x509 = _sub(key_info, NS_DS, 'X509Data')
    _sub(x509, NS_DS, 'X509SubjectName')
    _sub(x509, NS_DS, 'X509Certificate')


def construir_xml(datos):
    """Devuelve los bytes del XML (sin firmar) o levanta ValueError con todos los problemas.

    `datos` (ver `validar`):
        serie_numero      'R001-00000012'
        fecha_emision     date
        agente            {ruc, razon_social, nombre_comercial, direccion{ubigeo, calle, urbanizacion,
                           provincia, departamento, distrito}}
        proveedor         {ruc, razon_social, nombre_comercial}
        codigo_regimen    '01'            tasa 3.0
        nota              texto opcional (hasta 250)
        moneda            'PEN'           total_retenido, total_pagado
        documentos        [{tipo, serie_numero, fecha_emision, moneda, importe_total,
                            pago_nro, pago_importe, pago_fecha,
                            retencion, retencion_fecha, neto, tipo_cambio}]
    """
    errores = validar(datos)
    if errores:
        raise ValueError('\n'.join(errores))

    nsmap = OrderedDict([
        (None, NS_RETENCION), ('cac', NS_CAC), ('cbc', NS_CBC), ('ccts', NS_CCTS), ('ds', NS_DS),
        ('ext', NS_EXT), ('qdt', NS_QDT), ('sac', NS_SAC), ('udt', NS_UDT), ('xsi', NS_XSI)])
    raiz = etree.Element('{%s}Retention' % NS_RETENCION, nsmap=nsmap)

    ext = _sub(_sub(_sub(raiz, NS_EXT, 'UBLExtensions'), NS_EXT, 'UBLExtension'), NS_EXT, 'ExtensionContent')
    _bloque_firma(ext)
    _sub(raiz, NS_CBC, 'UBLVersionID', '2.0')
    _sub(raiz, NS_CBC, 'CustomizationID', '1.0')

    agente = datos['agente']
    firma = _sub(raiz, NS_CAC, 'Signature')
    _sub(firma, NS_CBC, 'ID', datos['serie_numero'])
    firmante = _sub(firma, NS_CAC, 'SignatoryParty')
    _sub(_sub(firmante, NS_CAC, 'PartyIdentification'), NS_CBC, 'ID', agente['ruc'])
    _sub(_sub(firmante, NS_CAC, 'PartyName'), NS_CBC, 'Name', _texto(agente['razon_social'], 100))
    adjunto = _sub(_sub(firma, NS_CAC, 'DigitalSignatureAttachment'), NS_CAC, 'ExternalReference')
    _sub(adjunto, NS_CBC, 'URI', '#' + ID_FIRMA)

    _sub(raiz, NS_CBC, 'ID', datos['serie_numero'])
    _sub(raiz, NS_CBC, 'IssueDate', _fecha(datos['fecha_emision']))
    _parte(raiz, 'AgentParty', agente, con_direccion=True)
    _parte(raiz, 'ReceiverParty', datos['proveedor'], con_direccion=False)
    _sub(raiz, NS_SAC, 'SUNATRetentionSystemCode', datos['codigo_regimen'])
    _sub(raiz, NS_SAC, 'SUNATRetentionPercent', _monto(datos['tasa']))
    nota = _texto(datos.get('nota'), 250)
    if nota:
        _sub(raiz, NS_CBC, 'Note', nota)
    _sub(raiz, NS_CBC, 'TotalInvoiceAmount', _monto(datos['total_retenido']), currencyID='PEN')
    _sub(raiz, NS_SAC, 'SUNATTotalPaid', _monto(datos['total_pagado']), currencyID='PEN')

    for doc in datos['documentos']:
        ref = _sub(raiz, NS_SAC, 'SUNATRetentionDocumentReference')
        _sub(ref, NS_CBC, 'ID', doc['serie_numero'], schemeID=doc['tipo'])
        _sub(ref, NS_CBC, 'IssueDate', _fecha(doc['fecha_emision']))
        _sub(ref, NS_CBC, 'TotalInvoiceAmount', _monto(doc['importe_total']), currencyID=doc['moneda'])
        pago = _sub(ref, NS_CAC, 'Payment')
        _sub(pago, NS_CBC, 'ID', str(int(doc['pago_nro'])))
        _sub(pago, NS_CBC, 'PaidAmount', _monto(doc['pago_importe']), currencyID=doc['moneda'])
        _sub(pago, NS_CBC, 'PaidDate', _fecha(doc['pago_fecha']))
        info = _sub(ref, NS_SAC, 'SUNATRetentionInformation')
        _sub(info, NS_SAC, 'SUNATRetentionAmount', _monto(doc['retencion']), currencyID='PEN')
        _sub(info, NS_SAC, 'SUNATRetentionDate', _fecha(doc['retencion_fecha']))
        _sub(info, NS_SAC, 'SUNATNetTotalPaid', _monto(doc['neto']), currencyID='PEN')
        if doc['moneda'] != 'PEN':
            cambio = _sub(info, NS_CAC, 'ExchangeRate')
            _sub(cambio, NS_CBC, 'SourceCurrencyCode', doc['moneda'])
            _sub(cambio, NS_CBC, 'TargetCurrencyCode', 'PEN')
            _sub(cambio, NS_CBC, 'CalculationRate', str(_d(doc['tipo_cambio']).quantize(
                Decimal('0.000001'), rounding=ROUND_HALF_UP)))
            _sub(cambio, NS_CBC, 'Date', _fecha(doc['pago_fecha']))

    return etree.tostring(raiz, pretty_print=True, xml_declaration=True,
                          encoding='utf-8', standalone=False)
