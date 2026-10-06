# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResCompany(models.Model):
	_inherit = 'res.company'

	ple_presentar_5_2 = fields.Boolean(
		string='Presentar Libro Diario Simplificado (5.2)',
		default=False,
		help='Marcar si la empresa tiene ingresos ≤ 150 UIT y está obligada a '
			 'presentar la estructura 5.2 (Libro Diario de Formato Simplificado). '
			 'Requiere aprobación del Gerente PLE para modificar.',
	)
	ple_eximido_caja_bancos = fields.Boolean(
		string='Eximido de presentar Libro Caja y Bancos',
		default=False,
		help='Si está marcado, los nuevos registros del Libro Diario se crearán '
			 'con la opción "Eximido de presentar Libro Caja y Bancos" activada, '
			 'incluyendo los datos de caja/banco en los campos libres del 5.1.',
	)
	ple_validacion_estricta_ref = fields.Boolean(
		string='Validación estricta: bloquear si faltan referencias en facturas de proveedor',
		default=True,
		help='Si está activo (recomendado), la generación del Libro Diario y Libro '
			 'Mayor se detiene con un error listando las facturas de proveedor que '
			 'tienen el campo Referencia vacío. El campo 12 (número de comprobante) '
			 'es obligatorio para SUNAT y sin él el TXT será rechazado. '
			 'Desactivar solo si la empresa acepta generar el TXT con líneas que '
			 'tendrán el campo 12 vacío (y asumir el rechazo posterior en el '
			 'validador PLE).',
	)


class ResConfigSettings(models.TransientModel):
	_inherit = 'res.config.settings'

	ple_presentar_5_2 = fields.Boolean(
		related='company_id.ple_presentar_5_2',
		readonly=False,
		string='Presentar Libro Diario Simplificado (5.2)',
	)
	ple_eximido_caja_bancos = fields.Boolean(
		related='company_id.ple_eximido_caja_bancos',
		readonly=False,
		string='Eximido de presentar Libro Caja y Bancos',
	)
	ple_validacion_estricta_ref = fields.Boolean(
		related='company_id.ple_validacion_estricta_ref',
		readonly=False,
		string='Validación estricta: bloquear si faltan referencias en facturas de proveedor',
	)
