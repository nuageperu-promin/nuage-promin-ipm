# -*- coding: utf-8 -*-

from odoo import fields, models

from .catalogos_plame import REGIMEN_PENSIONARIO


class ResCompany(models.Model):
	_inherit = 'res.company'

	plame_regimen_pensionario = fields.Selection(
		selection=REGIMEN_PENSIONARIO,
		string='Régimen pensionario PS 4ta (campo 10)',
		default='',
		help="Valor que se escribe en el campo 10 del archivo .4ta.\n"
		     "Los archivos aceptados por el PDT en producción lo envían "
		     "vacío. Solo cambiar a 1 (ONP) o 2 (SPP) si algún prestador "
		     "tiene aporte pensionario retenido, en cuyo caso el campo 11 "
		     "pasa a ser obligatorio.",
	)
	plame_rellenar_numero = fields.Boolean(
		string='Rellenar número con ceros a la izquierda',
		default=False,
		help="Si está activo, el número del comprobante se completa a 8 "
		     "posiciones con ceros (00000075). Desactivado escribe el número "
		     "tal cual (75), que es el formato de los archivos verificados "
		     "contra el PDT.",
	)
	plame_dias_tolerancia_emision = fields.Integer(
		string='Días de antigüedad máxima de emisión',
		default=0,
		help="Solo para la validación previa: si es mayor a cero, advierte "
		     "cuando la fecha de emisión de un recibo pagado en el periodo "
		     "es anterior a esa cantidad de días. Cero desactiva el aviso.",
	)
