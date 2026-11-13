# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
import re
from datetime import datetime

from odoo import _, fields, models
from odoo.exceptions import UserError

FORMATOS_FECHA = ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y')

# Posición (0 = primera columna) de cada dato según el formato pegado.
FORMATOS = {
    'simple': {'fecha': 0, 'capital': 1, 'interes': 2, 'comision': 3, 'itf': [4]},
    'bbva': {'fecha': 1, 'capital': 3, 'interes': 4, 'comision': 5, 'itf': [6, 7]},
    'bcp': {'fecha': 2, 'capital': 3, 'interes': 4, 'comision': None, 'itf': []},
}


def _fecha(texto):
    for fmt in FORMATOS_FECHA:
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None


def _numero(texto):
    t = (texto or '').strip()
    if not t:
        return 0.0
    if ',' in t and '.' in t:
        if t.rfind(',') > t.rfind('.'):
            t = t.replace('.', '').replace(',', '.')
        else:
            t = t.replace(',', '')
    elif ',' in t:
        partes = t.split(',')
        t = ''.join(partes) if len(partes[-1]) == 3 else '.'.join(partes)
    try:
        return float(t)
    except ValueError:
        return 0.0


class ImportarWizard(models.TransientModel):
    _name = 'promin.obligacion.importar.wizard'
    _description = 'Cargar cronograma de cuotas'

    obligacion_id = fields.Many2one('promin.obligacion', string='Obligación', required=True, readonly=True)
    formato = fields.Selection([
        ('simple', 'Simple: Fecha, Capital, Interés, Comisión, ITF/otros'),
        ('bbva', 'BBVA (cronograma de pagos de BBVA Empresas)'),
        ('bcp', 'BCP (cronograma de financiamiento local)')],
        string='Formato del texto', required=True, default='simple')
    texto = fields.Text(string='Cronograma', required=True,
                        help='Copie y pegue las filas del cronograma (desde Excel o del texto del banco).')
    reemplazar = fields.Boolean(string='Reemplazar las cuotas pendientes', default=True)

    def action_importar(self):
        self.ensure_one()
        obl = self.obligacion_id
        pos = FORMATOS[self.formato]
        filas = []
        for linea in (self.texto or '').splitlines():
            limpio = re.sub(r'(?i)US\$|S/\.?|\$', ' ', linea)
            tokens = [t for t in re.split(r'[\t;]+|\s+', limpio.strip()) if t]
            if len(tokens) <= pos['fecha']:
                continue
            fecha = _fecha(tokens[pos['fecha']])
            if not fecha:
                continue

            def tok(i):
                return _numero(tokens[i]) if i is not None and i < len(tokens) else 0.0
            filas.append({
                'fecha': fecha, 'capital': tok(pos['capital']), 'interes': tok(pos['interes']),
                'comision': tok(pos['comision']), 'itf': sum(tok(i) for i in pos['itf']),
            })
        if not filas:
            raise UserError(_('No se encontraron cuotas en el texto. Revise el formato elegido.'))
        if self.reemplazar:
            obl.cuota_ids.filtered(lambda c: c.estado == 'pendiente').unlink()
        ultimo = max(obl.cuota_ids.mapped('numero') or [0])
        Cuota = self.env['promin.obligacion.cuota']
        for i, fila in enumerate(sorted(filas, key=lambda f: f['fecha']), start=1):
            Cuota.create(dict(fila, obligacion_id=obl.id, numero=ultimo + i))
        capital = sum(f['capital'] for f in filas)
        obl.message_post(body=_('Cronograma cargado: %(n)s cuotas, capital %(c).2f, intereses %(i).2f.',
                                n=len(filas), c=capital, i=sum(f['interes'] for f in filas)))
        if obl.tipo != 'carta_fianza' and abs(sum(obl.cuota_ids.mapped('capital')) - obl.monto) > 0.009:
            obl.message_post(body=_('Atención: el capital del cronograma no coincide con el monto de la obligación.'))
        return {'type': 'ir.actions.act_window_close'}
