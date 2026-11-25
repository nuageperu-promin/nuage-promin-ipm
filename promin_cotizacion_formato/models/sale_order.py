# -*- coding: utf-8 -*-
import base64
from collections import OrderedDict

from odoo import fields, models
from odoo.tools import file_open

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']

BANCOS = [
    ('bcp', ('bcp', 'crédito', 'credito')),
    ('bbva', ('bbva',)),
    ('scotiabank', ('scotia',)),
]

IMPORTANTE_DEFECTO = (
    'Cables sujeto a variación por diferencia de precios de cobre.\n'
    'Monto mínimo de OC USD 1200 para ser entregados en sus almacenes, '
    'caso contrario se debe coordinar el recojo.'
)

_IMG_CACHE = {}


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    promin_lugar_entrega = fields.Char(
        'Lugar de entrega', default='Sus almacenes de Lima',
        help='Texto libre. Se edita en el bloque Entrega y se imprime en «Condiciones de venta» '
             'del reporte Cotización PROMIN.')
    promin_tolerancia = fields.Char(
        'Tolerancia', default='Tolerancia en longitud de cables: +/-10%',
        help='Se imprime en «Condiciones de venta» del reporte Cotización PROMIN.')
    promin_terminos_url = fields.Char(
        'Términos de venta (enlace)',
        default='https://www.proveedoresmineros.com/terminos-y-condiciones/',
        help='Se imprime en «Condiciones de venta» del reporte Cotización PROMIN.')
    promin_importante = fields.Text(
        'Importante', default=IMPORTANTE_DEFECTO,
        help='Bloque «IMPORTANTE» del reporte Cotización PROMIN. Una viñeta por línea.')

    # ---- Datos para el reporte Cotización PROMIN -------------------------------------------

    def _promin_fecha_larga(self):
        """Fecha de la cotización como «12 de mayo del 2027»."""
        self.ensure_one()
        f = fields.Datetime.context_timestamp(self, self.date_order) if self.date_order else False
        if not f:
            return ''
        return '%d de %s del %d' % (f.day, MESES[f.month - 1], f.year)

    def _promin_moneda_nombre(self):
        self.ensure_one()
        nombre = {'USD': 'Dólares Americanos', 'PEN': 'Soles'}
        return nombre.get(self.currency_id.name, self.currency_id.name or '')

    def _promin_filas(self):
        """Filas del reporte, numeradas. Cada fila: {'tipo', 'n', 'line'}.

        tipo = 'producto' (lleva número de ítem), 'seccion' o 'nota'.
        """
        self.ensure_one()
        filas, n = [], 0
        for line in self._get_order_lines_to_report():
            if line.display_type == 'line_section' or line.display_type == 'line_subsection':
                filas.append({'tipo': 'seccion', 'n': 0, 'line': line})
            elif line.display_type == 'line_note':
                filas.append({'tipo': 'nota', 'n': 0, 'line': line})
            else:
                n += 1
                filas.append({'tipo': 'producto', 'n': n, 'line': line})
        return filas

    def _promin_plazos(self):
        """Plazos de entrega por ítem, agrupados por días: lista de textos.

        Ej.: «ITEM N° 1 y N° 3: 3 días hábiles.». Usa el campo «Plazo de entrega» de la línea.
        """
        self.ensure_one()
        grupos = OrderedDict()
        for fila in self._promin_filas():
            if fila['tipo'] != 'producto':
                continue
            dias = int(fila['line'].customer_lead or 0)
            if dias > 0:
                grupos.setdefault(dias, []).append(fila['n'])
        textos = []
        for dias, items in grupos.items():
            etiquetas = ['N° %d' % i for i in items]
            lista = etiquetas[0] if len(etiquetas) == 1 else (
                ', '.join(etiquetas[:-1]) + ' y ' + etiquetas[-1])
            textos.append('ITEM %s: %d %s hábiles.' % (lista, dias, 'día' if dias == 1 else 'días'))
        return textos

    def _promin_igv_etiqueta(self):
        """«IGV (18%)» a partir de los impuestos de las líneas."""
        self.ensure_one()
        tasas = [t.amount for t in self.order_line.tax_ids if t.amount_type == 'percent']
        if not tasas:
            return 'IGV'
        tasa = max(set(tasas), key=tasas.count)
        return 'IGV (%s%%)' % (('%g' % tasa))

    def _promin_cuentas_bancos(self):
        """Cuentas de la compañía por banco (BCP, BBVA, Scotiabank), en Soles y Dólares.

        Lee las cuentas bancarias registradas en la compañía; reconoce el banco por su nombre.
        La cuenta sin moneda cuenta como Soles.
        """
        self.ensure_one()
        cuentas = self.company_id.partner_id.bank_ids.sudo()
        tiene_moneda = 'currency_id' in self.env['res.partner.bank']._fields
        resultado = []
        for clave, palabras in BANCOS:
            del_banco = cuentas.filtered(
                lambda c: c.bank_id and any(p in (c.bank_id.name or '').lower() for p in palabras))

            def numero(moneda):
                for c in del_banco:
                    mon = (c.currency_id.name if tiene_moneda and c.currency_id else 'PEN')
                    if mon == moneda:
                        return c.acc_number or ''
                return ''
            resultado.append({'banco': clave, 'soles': numero('PEN'), 'dolares': numero('USD')})
        return resultado

    def _promin_num(self, valor):
        """Cantidad sin ceros sobrantes: 100 → «100», 2.5 → «2.5»."""
        texto = ('%.2f' % (valor or 0.0)).rstrip('0').rstrip('.')
        return texto or '0'

    def _promin_telefono(self, partner):
        """Teléfono del contacto (usa móvil solo si el campo existe en esta versión)."""
        if not partner:
            return ''
        if partner.phone:
            return partner.phone
        return partner.mobile if 'mobile' in partner._fields and partner.mobile else ''

    def _promin_atencion(self):
        """Persona de atención del cliente que se imprime en «Atención:»."""
        self.ensure_one()
        return ''

    def _promin_validez_dias(self):
        """Días de validez: desde la fecha de la cotización hasta el vencimiento."""
        self.ensure_one()
        if not self.validity_date or not self.date_order:
            return 0
        fecha = fields.Datetime.context_timestamp(self, self.date_order).date()
        return max((self.validity_date - fecha).days, 0)

    def _promin_img(self, nombre):
        """Imagen del módulo como data URI (no depende de que wkhtmltopdf alcance el servidor)."""
        if nombre not in _IMG_CACHE:
            ruta = 'promin_cotizacion_formato/static/img/%s.png' % nombre
            with file_open(ruta, 'rb') as f:
                _IMG_CACHE[nombre] = 'data:image/png;base64,' + base64.b64encode(f.read()).decode()
        return _IMG_CACHE[nombre]

    def _promin_precio_neto(self, line):
        """Precio unitario sin IGV (importe de la línea / cantidad), coherente con el Importe."""
        if line.product_uom_qty:
            return line.price_subtotal / line.product_uom_qty
        return line.price_unit
