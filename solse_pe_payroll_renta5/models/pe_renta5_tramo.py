# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC

from odoo import fields, models


class PeRenta5Tramo(models.Model):
	"""Un tramo de la escala progresiva aplicado en el detalle de 5ta de un
	recibo. Se regenera cada vez que se actualiza el detalle."""
	_name = 'pe.renta5.tramo'
	_description = 'Tramo aplicado en el detalle de renta de 5ta'
	_order = 'payslip_id, secuencia'

	payslip_id = fields.Many2one(
		'hr.payslip', string='Recibo', required=True, ondelete='cascade', index=True)
	currency_id = fields.Many2one(related='payslip_id.currency_id')
	secuencia = fields.Integer(string='N.°')
	desde = fields.Monetary(string='Desde (S/)')
	hasta = fields.Monetary(string='Hasta (S/)', help='Vacío en el último tramo, que no tiene tope.')
	limite_uit = fields.Float(string='Hasta (UIT)', help='0 = sin tope.')
	tasa = fields.Float(string='Tasa (%)')
	base_tramo = fields.Monetary(string='Renta en el tramo')
	impuesto = fields.Monetary(string='Impuesto del tramo')
