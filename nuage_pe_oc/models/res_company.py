# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    nuage_oc_usar_formato = fields.Boolean(
        'Numerar OC como PMS/PMI (PROMIN)', default=False,
        help='Si está activo, las órdenes de compra nuevas se numeran con las '
             'secuencias PMS-0000000 (local) y PMI-0000000 (importación). El '
             'reporte PDF está disponible aunque esta casilla esté apagada.')
    nuage_oc_notas_local = fields.Text(
        'Notas OC local', help='Una nota por línea. Vacío = texto de PROMIN.')
    nuage_oc_pie_local = fields.Text(
        'Leyenda al pie OC local', help='Vacío = «Somos agente de retención…».')
    nuage_oc_notas_importacion = fields.Text(
        'Notas OC importación', help='Una nota por línea. Vacío = texto de PROMIN.')
    nuage_oc_pie_importacion = fields.Text(
        'Leyenda al pie OC importación', help='Vacío = aviso sobre embalaje de madera (WPM).')
