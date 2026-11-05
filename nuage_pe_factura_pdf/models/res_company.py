# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import fields, models

MENSAJE_RETENCION = ('Incorporado al Régimen de Agentes de Retención de IGV '
                     '(R.S.378-2013) a partir del 01/03/2014')


class ResCompany(models.Model):
    _inherit = 'res.company'

    nuage_fac_mensaje_retencion = fields.Char(
        'Mensaje de retención', default=MENSAJE_RETENCION,
        help='Aparece en «Información adicional». Vacío = no se imprime.')
    nuage_fac_autorizacion = fields.Char(
        'Texto de autorización SUNAT',
        default='Autorizado a ser emisor electrónico mediante R.I. SUNAT Nº520050000049',
        help='Pie del PDF. Cambia cuando la empresa pase a otro OSE.')
    nuage_fac_url_consulta = fields.Char(
        'URL de consulta (notas)', default='https://sfe.bizlinks.com.pe',
        help='Pie de las notas de crédito/débito. Vacío = no se imprime.')
    nuage_fac_powered = fields.Char(
        'Texto «Powered by» (notas)', default='Powered by Bizlinks')
