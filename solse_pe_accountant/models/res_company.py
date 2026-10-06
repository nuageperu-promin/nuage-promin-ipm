# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Company(models.Model):
	_inherit = "res.company"

	cuenta_detracciones = fields.Many2one("account.account", string="Cuenta de detracciones [Venta]")
	cuenta_detracciones_compra = fields.Many2one("account.account", string="Cuenta de detracciones [Compra]")
	cuenta_detrac_ganancias = fields.Many2one("account.account", string="Cuenta para ganancias por detracción")
	cuenta_detrac_perdidas = fields.Many2one("account.account", string="Cuenta para pérdidas por detracción")

	# Retenciones: naturaleza contable opuesta según rol
	# Compra (agente de retención → pasivo: IGV retenido por pagar a SUNAT)
	cuenta_retenciones = fields.Many2one("account.account", string="Cuenta de retenciones [Compra]")
	# Venta (proveedor retenido → activo: IGV retenido por cobrar / crédito fiscal)
	cuenta_retenciones_venta = fields.Many2one("account.account", string="Cuenta de retenciones [Venta]")

	usar_fecha_vencimiento_detraccion = fields.Boolean(
		string="Gestionar fecha de vencimiento de detracción",
		default=False,
		help="Si está activo, la línea de detracción usará automáticamente el día "
		     "configurado del mes siguiente a la fecha de emisión de la factura.",
	)
	dia_vencimiento_detraccion = fields.Integer(
		string="Día de vencimiento (mes siguiente)",
		default=5,
		help="Día del mes siguiente al de emisión en que vence el pago de la detracción. "
		     "Según normativa SUNAT el plazo máximo es el día 5. Rango permitido: 1-28.",
	)

	# Las cuatro cuentas que este modulo mete DENTRO de los terminos de pago
	# del documento, con fecha de vencimiento. Solo las cuentas por cobrar y
	# por pagar admiten `date_maturity`.
	CUENTAS_EN_TERMINOS_DE_PAGO = {
		'cuenta_detracciones': (
			'asset_receivable',
			'Cuenta de detracciones [Venta]',
			'La detracción de una venta no es efectivo todavía: es el importe '
			'que el cliente debe depositar en el Banco de la Nación. Se '
			'registra como cuenta POR COBRAR y pasa a la cuenta corriente '
			'recién cuando llega la constancia de depósito.'),
		'cuenta_detracciones_compra': (
			'liability_payable',
			'Cuenta de detracciones [Compra]',
			'Es lo que retenemos al proveedor y todavía no hemos depositado: '
			'una cuenta POR PAGAR.'),
		'cuenta_retenciones': (
			'liability_payable',
			'Cuenta de retenciones [Compra]',
			'El IGV retenido al proveedor es una deuda con la SUNAT hasta que '
			'se paga: una cuenta POR PAGAR.'),
		'cuenta_retenciones_venta': (
			'asset_receivable',
			'Cuenta de retenciones [Venta]',
			'El IGV que el cliente nos retiene es un saldo a nuestro favor: '
			'una cuenta POR COBRAR.'),
	}

	@api.constrains('cuenta_detracciones', 'cuenta_detracciones_compra',
					'cuenta_retenciones', 'cuenta_retenciones_venta')
	def _check_cuentas_terminos_de_pago(self):
		"""Las cuentas de detracción y retención tienen que admitir vencimiento.

		Este módulo descompone la línea de vencimiento de la factura en tres
		—neto, detracción y retención— y las tres viven dentro de los
		términos de pago, con `date_maturity`. Odoo solo permite fecha de
		vencimiento en cuentas por cobrar o por pagar.

		Configurar aquí, por ejemplo, la cuenta corriente del Banco de la
		Nación hace que **toda factura con detracción sea rechazada**, y el
		mensaje que muestra Odoo —«cualquier apunte contable en una cuenta
		por cobrar debe tener una fecha límite y viceversa»— no menciona ni
		la detracción ni la cuenta, de modo que el diagnóstico se vuelve muy
		difícil. Se valida aquí para que el problema se vea al guardar la
		configuración y no meses después.
		"""
		for company in self:
			for campo, datos in self.CUENTAS_EN_TERMINOS_DE_PAGO.items():
				exigido, etiqueta, motivo = datos
				cuenta = company[campo]
				if not cuenta or cuenta.account_type == exigido:
					continue
				nombres = dict(
					self.env['account.account']._fields['account_type'].selection)
				raise ValidationError(_(
					'«%(etiqueta)s» está apuntando a la cuenta %(codigo)s '
					'%(nombre)s, que es de tipo «%(real)s».\n\n'
					'Tiene que ser «%(exigido)s».\n\n'
					'%(motivo)s\n\n'
					'Con el tipo actual, toda factura con detracción o '
					'retención sería rechazada por Odoo con un mensaje sobre '
					'fechas de vencimiento que no menciona esta '
					'configuración.',
					etiqueta=etiqueta,
					codigo=cuenta.code,
					nombre=cuenta.name,
					real=nombres.get(cuenta.account_type, cuenta.account_type),
					exigido=nombres.get(exigido, exigido),
					motivo=motivo,
				))

	@api.constrains('usar_fecha_vencimiento_detraccion', 'dia_vencimiento_detraccion')
	def _check_dia_vencimiento_detraccion(self):
		for company in self:
			if company.usar_fecha_vencimiento_detraccion:
				if not (1 <= company.dia_vencimiento_detraccion <= 28):
					raise ValidationError(
						_("El día de vencimiento de detracción debe estar entre 1 y 28 "
						  "(valor ingresado: %d).") % company.dia_vencimiento_detraccion
					)


	# ── Configuración Libros Electrónicos / Estados Financieros ─────────
	sector_contable = fields.Selection(
		selection=[
			('01', 'Diversas (empresas comerciales, industriales y de servicios)'),
			('02', 'Seguros'),
			('03', 'Bancos y Financieras'),
		],
		string='Sector Contable (Tabla 34)',
		default='01',
		help=(
			'Sector al que pertenece la empresa según la Tabla 34 de SUNAT. '
			'Determina qué rubros de Estados Financieros están disponibles para '
			'el Libro de Inventarios y Balances (PLE 03) y los reportes de '
			'Estados Financieros. La gran mayoría de empresas usan "Diversas (01)".'
		),
	)
