# -*- coding: utf-8 -*-

from odoo import api, fields, models

from .catalogos_plame import (
	CODIGO_SUNAT_NOTA_CREDITO,
	CODIGO_SUNAT_RECIBO_HONORARIOS,
	TABLA_23_TIPO_COMPROBANTE,
	partir_serie_numero,
)

# Tipos de cuenta cuya conciliación representa la cancelación del comprobante.
CUENTAS_CONCILIABLES = ('liability_payable', 'asset_receivable')


class AccountMove(models.Model):
	_inherit = 'account.move'

	es_recibo_honorarios = fields.Boolean(
		string='Es recibo por honorarios',
		compute='_calcular_es_recibo_honorarios',
		store=True,
		help="Se marca automáticamente cuando el tipo de documento es "
		     "Recibo por Honorarios (02), o es una nota de crédito que "
		     "revierte uno.",
	)
	plame_tipo_comprobante = fields.Selection(
		selection=TABLA_23_TIPO_COMPROBANTE,
		string='Tipo comprobante PLAME',
		copy=False,
		help="Solo para casos que no se deducen del tipo de documento, como "
		     "dietas de directorio (D) u otros comprobantes (O). Si se deja "
		     "vacío se usa R para los recibos y N para las notas de crédito.",
	)

	@api.depends('l10n_latam_document_type_id', 'move_type', 'reversed_entry_id')
	def _calcular_es_recibo_honorarios(self):
		for registro in self:
			codigo = registro.l10n_latam_document_type_id.code or ''
			if registro.move_type == 'in_invoice':
				registro.es_recibo_honorarios = (
					codigo == CODIGO_SUNAT_RECIBO_HONORARIOS
				)
			elif registro.move_type == 'in_refund':
				# Una nota de crédito de honorarios se reconoce por el
				# documento que revierte, porque el código 07 es común a
				# todas las notas de crédito.
				origen = registro.reversed_entry_id
				codigo_origen = origen.l10n_latam_document_type_id.code or ''
				registro.es_recibo_honorarios = (
					codigo_origen == CODIGO_SUNAT_RECIBO_HONORARIOS
					or (codigo == CODIGO_SUNAT_NOTA_CREDITO
					    and origen.move_type == 'in_invoice'
					    and codigo_origen == CODIGO_SUNAT_RECIBO_HONORARIOS)
				)
			else:
				registro.es_recibo_honorarios = False

	# ── Datos del comprobante para el archivo .4ta ──────────────────────

	def obtener_tipo_comprobante_plame(self):
		"""Devuelve el código de la Tabla 23 que corresponde al documento."""
		self.ensure_one()
		if self.plame_tipo_comprobante:
			return self.plame_tipo_comprobante
		return 'N' if self.move_type == 'in_refund' else 'R'

	def obtener_serie_numero_plame(self):
		"""Devuelve (serie, numero) del comprobante del proveedor.

		Se prioriza el campo de la localización y se usa la referencia como
		respaldo, porque en varias instalaciones el número real se captura
		en `ref`.
		"""
		self.ensure_one()
		referencia = False
		if 'l10n_latam_document_number' in self._fields:
			referencia = self.l10n_latam_document_number
		referencia = referencia or self.ref
		serie, numero = partir_serie_numero(referencia)
		if numero and self.company_id.plame_rellenar_numero:
			numero = numero.rjust(8, '0')
		return serie, numero

	def tiene_retencion_cuarta(self):
		"""Indica si el comprobante lleva retención de renta de 4ta categoría."""
		self.ensure_one()
		lineas_retencion = self.line_ids.filtered(
			lambda linea: linea.tax_line_id.es_retencion_cuarta
		)
		if lineas_retencion and not self.currency_id.is_zero(
			sum(lineas_retencion.mapped('amount_currency'))
		):
			return True
		# Respaldo: impuesto aplicado en la línea pero aún sin línea de
		# impuesto generada (facturas en borrador).
		return any(
			impuesto.es_retencion_cuarta
			for impuesto in self.invoice_line_ids.mapped('tax_ids')
		)

	def obtener_monto_bruto_plame(self):
		"""Monto total del servicio, en la moneda del comprobante.

		Es el importe antes de la retención, que corresponde a la base
		imponible del documento.
		"""
		self.ensure_one()
		return abs(self.amount_untaxed)

	# ── Tipo de cambio ─────────────────────────────────────────────────

	def obtener_tc_compra_plame(self, fecha):
		"""Tipo de cambio COMPRA vigente en la fecha indicada.

		El PLAME se declara con el tipo de cambio compra de la fecha de
		pago, mientras que el registro contable conserva el tipo de cambio
		con el que se emitió el asiento. Por eso no se puede reutilizar
		`amount_total_signed`.
		"""
		self.ensure_one()
		compania = self.company_id
		if self.currency_id == compania.currency_id:
			return 1.0

		Moneda = self.env['res.currency']
		moneda_compra = Moneda.search([
			('name', '=', self.currency_id.name),
			('rate_type', '=', 'compra'),
		], limit=1)
		moneda_aplicable = moneda_compra or self.currency_id
		return moneda_aplicable._convert(
			1.0, compania.currency_id, compania, fecha, round=False
		)

	def convertir_a_soles_plame(self, importe, fecha):
		"""Convierte un importe de la moneda del comprobante a soles."""
		self.ensure_one()
		if self.currency_id == self.company_id.currency_id:
			return round(importe, 2)
		return round(importe * self.obtener_tc_compra_plame(fecha), 2)

	# ── Pagos del periodo ──────────────────────────────────────────────

	def obtener_pagos_plame(self, fecha_inicio, fecha_fin):
		"""Importe cancelado dentro del periodo y fecha del último pago.

		Devuelve (importe_en_moneda_del_comprobante, fecha_ultimo_pago).
		Se excluyen las conciliaciones contra notas de crédito de recibos
		por honorarios, porque esas se declaran como comprobante propio y
		contarlas aquí duplicaría el importe.
		"""
		self.ensure_one()
		lineas = self.line_ids.filtered(
			lambda linea: linea.account_id.account_type in CUENTAS_CONCILIABLES
		)
		importe_total = 0.0
		fecha_ultimo_pago = False

		for linea in lineas:
			# La línea del comprobante es el lado crédito de la conciliación.
			for parcial in linea.matched_debit_ids:
				contraparte = parcial.debit_move_id
				importe = parcial.credit_amount_currency or parcial.amount
				importe_total, fecha_ultimo_pago = self._acumular_parcial_plame(
					contraparte, importe, fecha_inicio, fecha_fin,
					importe_total, fecha_ultimo_pago,
				)
			# La línea del comprobante es el lado débito (notas de crédito).
			for parcial in linea.matched_credit_ids:
				contraparte = parcial.credit_move_id
				importe = parcial.debit_amount_currency or parcial.amount
				importe_total, fecha_ultimo_pago = self._acumular_parcial_plame(
					contraparte, importe, fecha_inicio, fecha_fin,
					importe_total, fecha_ultimo_pago,
				)

		importe_total, fecha_ultimo_pago = self._pagos_sin_asiento_plame(
			fecha_inicio, fecha_fin, importe_total, fecha_ultimo_pago)
		return abs(importe_total), fecha_ultimo_pago

	# ── Pagos sin asiento (Odoo 18+) ───────────────────────────────────

	def _pagos_sin_asiento_v19(self):
		"""Pagos enlazados al comprobante que NO tienen asiento contable.

		Desde Odoo 18, un pago cuyo método no tiene cuenta pendiente
		(outstanding) no genera asiento: `account.payment.
		_generate_journal_entry` (account/models/account_payment.py:997 en
		19.0) solo lo crea si hay `outstanding_account_id`. Ese pago se
		enlaza a la factura por `matched_payment_ids` y NO por
		conciliación, así que la lectura de `matched_debit_ids` de la v17
		no lo veía y el recibo pagado no entraba al PLAME. Los pagos CON
		asiento siguen leyéndose por conciliación (no se cuentan dos veces).
		"""
		self.ensure_one()
		if 'matched_payment_ids' not in self._fields:
			return self.env['account.payment']
		return self.matched_payment_ids.filtered(
			lambda pago: not pago.move_id
			and pago.state in ('in_process', 'paid'))

	def _pagos_sin_asiento_plame(self, fecha_inicio, fecha_fin,
								 importe_total, fecha_ultimo_pago):
		"""Suma los pagos sin asiento del periodo (criterio de percepción)."""
		for pago in self._pagos_sin_asiento_v19():
			fecha = pago.date
			if not fecha or fecha < fecha_inicio or fecha > fecha_fin:
				continue
			importe = pago.amount
			if pago.currency_id and pago.currency_id != self.currency_id:
				importe = pago.currency_id._convert(
					importe, self.currency_id, self.company_id, fecha)
			importe_total += abs(importe)
			if not fecha_ultimo_pago or fecha > fecha_ultimo_pago:
				fecha_ultimo_pago = fecha
		return importe_total, fecha_ultimo_pago

	def _acumular_parcial_plame(self, contraparte, importe, fecha_inicio,
	                            fecha_fin, importe_total, fecha_ultimo_pago):
		"""Suma una conciliación si cae dentro del periodo y es un pago real."""
		documento_contrario = contraparte.move_id
		if documento_contrario.es_recibo_honorarios:
			return importe_total, fecha_ultimo_pago

		fecha = contraparte.date
		if not fecha or fecha < fecha_inicio or fecha > fecha_fin:
			return importe_total, fecha_ultimo_pago

		importe_total += abs(importe)
		if not fecha_ultimo_pago or fecha > fecha_ultimo_pago:
			fecha_ultimo_pago = fecha
		return importe_total, fecha_ultimo_pago

	def obtener_fecha_pago_origen_plame(self):
		"""Última fecha de pago del recibo que originó esta nota de crédito.

		El criterio contable definido es que la nota de crédito se declara
		con la misma fecha de pago del recibo que la origina.
		"""
		self.ensure_one()
		origen = self.reversed_entry_id
		if not origen:
			return False
		lineas = origen.line_ids.filtered(
			lambda linea: linea.account_id.account_type in CUENTAS_CONCILIABLES
		)
		fecha_ultimo_pago = False
		for linea in lineas:
			for parcial in linea.matched_debit_ids:
				contraparte = parcial.debit_move_id
				if contraparte.move_id.es_recibo_honorarios:
					continue
				if contraparte.date and (
					not fecha_ultimo_pago or contraparte.date > fecha_ultimo_pago
				):
					fecha_ultimo_pago = contraparte.date
		# Odoo 18+: pagos del recibo origen sin asiento (ver
		# `_pagos_sin_asiento_v19`).
		for pago in origen._pagos_sin_asiento_v19():
			if pago.date and (not fecha_ultimo_pago
							  or pago.date > fecha_ultimo_pago):
				fecha_ultimo_pago = pago.date
		return fecha_ultimo_pago
