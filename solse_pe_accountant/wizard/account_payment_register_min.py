# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logging = logging.getLogger(__name__)


class AccountPaymentRegister(models.TransientModel):
	_inherit = 'account.payment.register'

	es_detraccion_retencion = fields.Boolean(
		"Es por Detracción/Retención",
		help="Marcar si el pago es por la detracción o retención",
	)
	tipo = fields.Selection(
		[("normal", "Normal"), ("detraccion", "Detracción"), ("retencion", "Retención")],
		default="normal",
		string="Tipo pago",
	)
	transaction_number = fields.Char(string='Número de operación')
	mostrar_check = fields.Boolean("Mostrar check", compute="_compute_mostrar_check", store=True)
	autodetraccion = fields.Boolean("Autodetracción")
	monto_autodetraccion = fields.Monetary(currency_field='currency_id', string="Importe", default=0.00)

	# ----------------------------------------------------------
	# Helpers internos
	# ----------------------------------------------------------

	def _cuenta_detraccion_id(self):
		"""Devuelve el ID de la cuenta de detracción según el tipo de factura."""
		if not self.line_ids:
			return 0
		factura = self.line_ids[0].move_id
		if factura.move_type == 'out_invoice':
			return int(factura.company_id.cuenta_detracciones.id or 0)
		return int(factura.company_id.cuenta_detracciones_compra.id or 0)

	def _cuenta_retencion_id(self):
		"""Devuelve el ID de la cuenta de retención según el tipo de factura.
		Venta (out_invoice): activo, IGV retenido por cobrar.
		Compra (in_invoice): pasivo, IGV retenido por pagar a SUNAT.
		"""
		if not self.line_ids:
			return 0
		factura = self.line_ids[0].move_id
		if factura.move_type == 'out_invoice':
			return int(factura.company_id.cuenta_retenciones_venta.id or 0)
		return int(factura.company_id.cuenta_retenciones.id or 0)

	# ----------------------------------------------------------
	# Computes
	# ----------------------------------------------------------

	# _compute_group_payment ELIMINADO (v19.0.0.11):
	# El override original tenía `return False` dentro del for, lo que dejaba
	# group_payment como missing cached en lugar de asignar Boolean.
	# El compute nativo (account_payment_register.py:478) hace correctamente:
	#   wizard.group_payment = len(...) == 1 if can_edit_wizard else False
	# No hay razón en el módulo para sobrescribirlo, así que se elimina.

	@api.depends('line_ids', 'line_ids.move_id')
	def _compute_mostrar_check(self):
		for reg in self:
			facturas = reg.mapped("line_ids.move_id")
			mostrar_check = False
			pagadas_detrac = facturas.filtered(lambda r: r.pago_detraccion)
			if len(facturas) == len(pagadas_detrac) and len(pagadas_detrac):
				mostrar_check = False
			else:
				for factura in facturas:
					if factura.tiene_detraccion or factura.tiene_retencion:
						mostrar_check = True
			reg.mostrar_check = mostrar_check

	# En Odoo 19 communication usa _compute_communication como compute.
	@api.depends('can_edit_wizard', 'line_ids')
	def _compute_communication(self):
		for wizard in self:
			facturas = wizard.mapped("line_ids.move_id")
			if facturas:
				dato_array = []
				for factura in facturas:
					dato = factura.name
					partes = dato.split(" ")
					dato = partes[1] if len(partes) == 2 else partes[0]
					dato_array.append(dato)
				wizard.communication = ",".join(dato_array)
			elif wizard.can_edit_wizard and wizard.batches:
				wizard.communication = wizard._get_communication(wizard.batches[0]['lines'])
			else:
				wizard.communication = False

	# Sobreescribimos para forzar diferencia=0 en autodetraccion
	@api.depends('can_edit_wizard', 'amount', 'es_detraccion_retencion', 'payment_date')
	def _compute_payment_difference(self):
		for wizard in self:
			if wizard.autodetraccion:
				wizard.payment_difference = 0.0
				continue
			if wizard.payment_date and wizard.batches:
				total_amount_values = wizard._get_total_amounts_to_pay(wizard.batches)
				wizard.payment_difference = total_amount_values['amount_for_difference'] - wizard.amount
			else:
				wizard.payment_difference = 0.0

	# ----------------------------------------------------------
	# Onchanges
	# ----------------------------------------------------------

	@api.onchange('es_detraccion_retencion', 'tipo', 'autodetraccion')
	def _onchange_detraccion_retencion(self):
		if not self.line_ids:
			return
		factura = self.line_ids[0].move_id
		self.payment_difference_handling = "open"
		facturas_con_detraccion = self.mapped("line_ids.move_id").filtered(lambda r: r.tiene_detraccion)
		facturas_con_detra_y_pago_detr = facturas_con_detraccion.filtered(lambda r: r.pago_detraccion)

		if self.es_detraccion_retencion:
			if self.tipo == 'normal':
				self.tipo = 'detraccion'
		else:
			self.tipo = 'normal'

		if self.autodetraccion:
			self.monto_autodetraccion = self.source_amount_currency
			self.currency_id = factura.currency_id.id

		if self.es_detraccion_retencion:
			if self.tipo == 'normal':
				self.tipo = 'detraccion'
			self.currency_id = self.env.ref('base.PEN')
			total_detraccion = sum(
				self.mapped("line_ids.move_id").filtered(lambda r: not r.pago_detraccion).mapped('monto_detraccion')
			)
			total_retencion = sum(
				self.mapped("line_ids.move_id").filtered(lambda r: not r.pago_detraccion).mapped('monto_retencion')
			)
			self.amount = total_detraccion + total_retencion

		elif len(facturas_con_detraccion) and len(facturas_con_detra_y_pago_detr):
			source_amount_currency = self.source_amount_currency
			monto_comparar = sum(facturas_con_detraccion.mapped('monto_neto_pagar_base'))
			if factura.company_id.currency_id.id == self.currency_id.id:
				monto_comparar = sum(facturas_con_detraccion.mapped('monto_neto_pagar'))
			total_descontar = monto_comparar if (source_amount_currency + 1) > monto_comparar else source_amount_currency
			self.amount = total_descontar

		elif factura.company_id.currency_id.id == self.currency_id.id:
			source_amount = self.source_amount
			total_detraccion = sum(self.mapped("line_ids.move_id").mapped('monto_detraccion'))
			total_retencion = 0  # hasta crear lineas contables por retencion
			self.amount = source_amount - total_detraccion - total_retencion
		else:
			source_amount_currency = self.source_amount_currency
			total_detraccion_base = sum(self.mapped("line_ids.move_id").mapped('monto_detraccion_base'))
			total_retencion_base = 0  # hasta crear lineas contables por retencion
			self.amount = source_amount_currency - total_detraccion_base - total_retencion_base

	@api.depends(
		'can_edit_wizard', 'source_amount', 'source_amount_currency', 'source_currency_id',
		'company_id', 'currency_id', 'payment_date', 'installments_mode',
		'mostrar_check', 'es_detraccion_retencion', 'tipo', 'autodetraccion',
	)
	def _compute_amount(self):
		for wizard in self:
			if not wizard.line_ids:
				continue
			if wizard.mostrar_check or wizard.es_detraccion_retencion:
				wizard._onchange_detraccion_retencion()
			else:
				if not wizard.journal_id or not wizard.currency_id or not wizard.payment_date or wizard.custom_user_amount:
					wizard.amount = wizard.amount
				elif wizard.batches:
					total_amount_values = wizard._get_total_amounts_to_pay(wizard.batches)
					wizard.amount = total_amount_values['amount_by_default']

	@api.onchange('amount')
	def _onchange_amount(self):
		if not self.line_ids:
			return
		payment_difference_handling = 'open'
		factura = self.line_ids[0].move_id
		if self.tipo == 'detraccion' and factura.move_type == 'in_invoice':
			amount_total_signed = sum(self.mapped("line_ids.move_id").mapped('amount_total_signed'))
			monto_neto_pagar = sum(self.mapped("line_ids.move_id").mapped('monto_neto_pagar'))
			monto_detraccion = abs(amount_total_signed) - monto_neto_pagar
			if monto_detraccion - self.amount:
				payment_difference_handling = 'reconcile'
		elif self.tipo == 'detraccion' and factura.move_type == 'out_invoice':
			amount_total_signed = sum(self.mapped("line_ids.move_id").mapped('amount_total_signed'))
			monto_neto_pagar = sum(self.mapped("line_ids.move_id").mapped('monto_neto_pagar'))
			monto_detraccion = abs(amount_total_signed) - monto_neto_pagar
			if self.amount - monto_detraccion:
				payment_difference_handling = 'reconcile'
		self.payment_difference_handling = payment_difference_handling

	@api.onchange('payment_difference_handling')
	def _onchange_payment_difference_handling(self):
		if self.payment_difference_handling == 'reconcile':
			if self.payment_difference > 0:
				cuenta_diferencia = int(self.company_id.cuenta_detrac_ganancias.id or 0)
			else:
				cuenta_diferencia = int(self.company_id.cuenta_detrac_perdidas.id or 0)
			self.writeoff_account_id = cuenta_diferencia

	# ----------------------------------------------------------
	# Creacion de pagos
	# ----------------------------------------------------------

	def _create_payment_vals_from_wizard(self, batch_result):
		payment_vals = super(AccountPaymentRegister, self)._create_payment_vals_from_wizard(batch_result)
		payment_vals['transaction_number'] = self.transaction_number
		factura = self.line_ids[0].move_id

		conversion_rate = self.env['res.currency']._get_conversion_rate(
			self.currency_id,
			self.company_id.currency_id,
			self.company_id,
			self.payment_date,
		)

		crear_diferencia = (
			not self.currency_id.is_zero(self.payment_difference)
			and self.payment_difference_handling == 'reconcile'
		)

		def _write_off_vals(diferencia):
			if diferencia > 0:
				cuenta = int(self.company_id.cuenta_detrac_ganancias.id or 0)
			else:
				cuenta = int(self.company_id.cuenta_detrac_perdidas.id or 0)
			wof_amount = self.payment_difference if self.payment_type == 'inbound' else -self.payment_difference
			return [{
				'account_id': cuenta,
				'partner_id': self.partner_id.id,
				'currency_id': self.currency_id.id,
				'amount_currency': wof_amount,
				'balance': self.company_id.currency_id.round(wof_amount * conversion_rate),
			}]

		if self.tipo == 'detraccion' and factura.move_type == 'in_invoice':
			cuenta_det_id = int(self.company_id.cuenta_detracciones_compra.id or 0)
			payment_vals['destination_account_id'] = cuenta_det_id
			amount_total_signed = sum(self.mapped("line_ids.move_id").mapped('amount_total_signed'))
			monto_neto_pagar = sum(self.mapped("line_ids.move_id").mapped('monto_neto_pagar'))
			diferencia = (abs(amount_total_signed) - monto_neto_pagar) - self.amount
			if diferencia and not crear_diferencia:
				payment_vals['write_off_line_vals'] = _write_off_vals(diferencia)

		elif self.tipo == 'detraccion' and factura.move_type == 'out_invoice':
			cuenta_det_id = int(self.company_id.cuenta_detracciones.id or 0)
			payment_vals['destination_account_id'] = cuenta_det_id
			amount_total_signed = sum(self.mapped("line_ids.move_id").mapped('amount_total_signed'))
			monto_neto_pagar = sum(self.mapped("line_ids.move_id").mapped('monto_neto_pagar'))
			diferencia = (abs(amount_total_signed) - monto_neto_pagar) - self.amount
			if diferencia and not crear_diferencia:
				payment_vals['write_off_line_vals'] = _write_off_vals(diferencia)

		elif self.tipo == 'retencion':
			# Compra: pasivo (IGV retenido por pagar a SUNAT) | Venta: activo (IGV retenido por cobrar)
			if factura.move_type == 'in_invoice':
				cuenta_ret_id = int(self.company_id.cuenta_retenciones.id or 0)
			elif factura.move_type == 'out_invoice':
				cuenta_ret_id = int(self.company_id.cuenta_retenciones_venta.id or 0)
			else:
				cuenta_ret_id = int(self.company_id.cuenta_retenciones.id or 0)
			if not cuenta_ret_id:
				raise UserError('No se ha configurado la cuenta de retenciones correspondiente')
			payment_vals['destination_account_id'] = cuenta_ret_id

		_logging.info("_create_payment_vals resultado: %s", payment_vals)
		return payment_vals

	def _create_payments(self):
		self.ensure_one()

		# En Odoo 19 'batches' es campo computado, no metodo _get_batches()
		batches = self.batches
		batch_result = batches[0]
		factura = self.line_ids[0].move_id

		if self.autodetraccion and not factura.company_id.cuenta_detraccion:
			raise UserError("No se ha establecido una cuenta de detracción en la empresa")

		cuenta_det_id = self._cuenta_detraccion_id()
		cuenta_ret_id = self._cuenta_retencion_id()

		facturas_con_detraccion_con_pago = self.mapped("line_ids.move_id").filtered(lambda r: r.pago_detraccion)

		if self.tipo == 'detraccion':
			if facturas_con_detraccion_con_pago:
				raise UserError('Ya existe un pago por detracción')
			for lot in batches:
				if lot['payment_values']['account_id'] == cuenta_det_id:
					batch_result = lot
					break

		elif self.tipo == 'retencion':
			if facturas_con_detraccion_con_pago:
				raise UserError('Ya existe un pago por detracción')
			for lot in batches:
				if lot['payment_values']['account_id'] == cuenta_ret_id:
					batch_result = lot
					break

		else:
			for lot in batches:
				if lot['payment_values']['account_id'] != cuenta_det_id:
					batch_result = lot
					break

		edit_mode = self.can_edit_wizard and (len(batch_result['lines']) == 1 or self.group_payment)
		to_process = []

		if edit_mode:
			payment_vals = self._create_payment_vals_from_wizard(batch_result)
			to_process.append({
				'create_vals': payment_vals,
				'to_reconcile': batch_result['lines'],
				'batch': batch_result,
			})
		else:
			if not self.group_payment:
				new_batches = []
				for batch_result in batches:
					for line in batch_result['lines']:
						new_batches.append({**batch_result, 'lines': line})
				batches = new_batches

			for batch_result in batches:
				if self.tipo == 'detraccion' and batch_result['payment_values']['account_id'] != cuenta_det_id:
					continue
				if self.tipo == 'normal' and batch_result['payment_values']['account_id'] == cuenta_det_id:
					continue
				to_process.append({
					'create_vals': self._create_payment_vals_from_batch(batch_result),
					'to_reconcile': batch_result['lines'],
					'batch': batch_result,
				})

		if self.autodetraccion and not self.group_payment:
			self._crear_autodetraccion_independiente(cuenta_det_id, to_process, edit_mode)

		if self.autodetraccion and self.group_payment:
			raise UserError("Por el momento la autodetracción no se permite cuando se agrupan los pagos")

		payments = self._init_payments(to_process, edit_mode=edit_mode)
		self._post_payments(to_process, edit_mode=edit_mode)
		self._reconcile_payments(to_process, edit_mode=edit_mode)

		if payments and self.tipo == 'detraccion' and not self.autodetraccion and not self.group_payment:
			if len(payments) == 1:
				factura.pago_detraccion = payments[0].id
			else:
				for pago in payments:
					# En Odoo 19 el campo ref del pago pasó a llamarse memo
					factura_p = self.env['account.move'].search([
						('name', '=', pago.memo),
						('company_id', '=', pago.company_id.id),
					])
					if factura_p:
						factura_p.pago_detraccion = pago.id

		if payments and self.tipo == 'retencion' and not self.group_payment:
			if len(payments) == 1:
				factura.pago_retencion = payments[0].id
			else:
				for pago in payments:
					factura_p = self.env['account.move'].search([
						('name', '=', pago.memo),
						('company_id', '=', pago.company_id.id),
					])
					if factura_p:
						factura_p.pago_retencion = pago.id

		return payments

	def _crear_autodetraccion_independiente(self, cuenta_det_id, to_process, edit_mode):
		"""
		Crea el pago de autodetraccion de forma independiente.

		NOTA Odoo 19: is_internal_transfer y destination_journal_id ya no existen en
		account.payment. El pago pendiente se crea con destination_account_id apuntando
		al default_account_id del diario de detracciones (cuenta_detraccion en res.company).
		"""
		factura = self.line_ids[0].move_id

		lote_detraccion = False
		for lot in self.batches:
			if lot['payment_values']['account_id'] == cuenta_det_id:
				lote_detraccion = lot
				break

		if not lote_detraccion:
			raise UserError("No se pudo establecer el asiento para la detracción")

		to_process_detraccion = []
		for linea in lote_detraccion['lines']:
			amount_total_signed = linea.move_id.amount_total_signed
			monto_neto_pagar = linea.move_id.monto_neto_pagar
			monto_detraccion = abs(amount_total_signed) - monto_neto_pagar
			if linea.currency_id.id != self.company_id.currency_id.id:
				monto_detraccion = (
					abs(linea.move_id.amount_total_in_currency_signed) - linea.move_id.monto_neto_pagar_base
				)

			create_vals = {
				'date': to_process[0]['create_vals']['date'],
				'amount': monto_detraccion,
				'payment_type': to_process[0]['create_vals']['payment_type'],
				'partner_type': to_process[0]['create_vals']['partner_type'],
				'memo': linea.move_id.name,
				'journal_id': to_process[0]['create_vals']['journal_id'],
				'currency_id': to_process[0]['create_vals']['currency_id'],
				'partner_id': to_process[0]['create_vals']['partner_id'],
				'partner_bank_id': to_process[0]['create_vals']['partner_bank_id'],
				'payment_method_line_id': to_process[0]['create_vals']['payment_method_line_id'],
				'destination_account_id': cuenta_det_id,
				'write_off_line_vals': to_process[0]['create_vals'].get('write_off_line_vals', []),
				'payment_token_id': to_process[0]['create_vals'].get('payment_token_id', False),
				'team_id': to_process[0]['create_vals'].get('team_id', False),
				'transaction_number': to_process[0]['create_vals'].get('transaction_number', False),
			}
			to_process_detraccion.append({
				'create_vals': create_vals,
				'to_reconcile': linea,
				'batch': {
					'lines': linea,
					'payment_values': lote_detraccion['payment_values'],
				},
			})

		if not to_process_detraccion:
			return

		payments_detrac = self._init_payments(to_process_detraccion, edit_mode=edit_mode)
		self._post_payments(to_process_detraccion, edit_mode=edit_mode)
		self._reconcile_payments(to_process_detraccion, edit_mode=edit_mode)

		if factura.move_type == 'out_invoice':
			for linea in lote_detraccion['lines']:
				monto_detraccion = linea.move_id.monto_detraccion
				journal_detraccion = factura.company_id.cuenta_detraccion
				cuenta_banco_detraccion = (
					journal_detraccion.default_account_id.id if journal_detraccion else False
				)
				datos_pago_pendiente = {
					'es_x_autodetraccion': True,
					'payment_type': 'outbound',
					'amount': monto_detraccion,
					'date': to_process[0]['create_vals']['date'],
					'memo': 'Por pago de autodetracción para factura: %s' % linea.move_id.name,
					'journal_id': to_process[0]['create_vals']['journal_id'],
					'destination_account_id': cuenta_banco_detraccion or cuenta_det_id,
				}
				pago_pendiente = self.env['account.payment'].create(datos_pago_pendiente)
				linea.move_id.write({'pago_detraccion': pago_pendiente.id})

	@api.depends('line_ids')
	def _compute_from_lines(self):
		for wizard in self:
			if not wizard.line_ids:
				continue
			batches = wizard.batches
			if not batches:
				continue

			factura = wizard.line_ids[0].move_id
			cuenta_det_id = wizard._cuenta_detraccion_id()
			cuenta_ret_id = wizard._cuenta_retencion_id()

			if factura.move_type in ('in_invoice', 'out_invoice'):
				batch_result = batches[0]
				tiene_detraccion = False
				cuenta_con_detraccion = any(
					lot['payment_values']['account_id'] == cuenta_det_id for lot in batches
				)

				if wizard.tipo == 'detraccion':
					for lot in batches:
						if lot['payment_values']['account_id'] == cuenta_det_id:
							batch_result = lot
							tiene_detraccion = True
							break
				elif wizard.tipo == 'retencion' and factura.move_type == 'in_invoice':
					for lot in batches:
						if lot['payment_values']['account_id'] == cuenta_ret_id:
							batch_result = lot
							break
				else:
					for lot in batches:
						if lot['payment_values']['account_id'] != cuenta_det_id:
							batch_result = lot
							break

				wizard_values_from_batch = wizard._get_wizard_values_from_batch(batch_result)

				if len(batches) == 1 and not tiene_detraccion:
					wizard.update(wizard_values_from_batch)
					wizard.can_edit_wizard = True

				elif tiene_detraccion:
					for lot in batches:
						if lot == batch_result:
							continue
						if lot['payment_values']['account_id'] != cuenta_det_id:
							continue
						temp = wizard._get_wizard_values_from_batch(lot)
						wizard_values_from_batch['source_amount'] += temp['source_amount']
						wizard_values_from_batch['source_amount_currency'] += temp['source_amount_currency']

					if len(batches) > 2:
						wizard_values_from_batch['partner_id'] = False
						wizard_values_from_batch['partner_type'] = False

					wizard.update(wizard_values_from_batch)
					wizard.can_edit_wizard = False

				elif cuenta_con_detraccion:
					for lot in batches:
						if lot == batch_result:
							continue
						if lot['payment_values']['account_id'] != cuenta_det_id:
							continue
						temp = wizard._get_wizard_values_from_batch(lot)
						wizard_values_from_batch['source_amount'] += temp['source_amount']
						wizard_values_from_batch['source_amount_currency'] += temp['source_amount_currency']

					wizard.update(wizard_values_from_batch)
					cant_batches_val = sum(
						1 for lot in batches
						if lot['payment_values']['account_id'] != cuenta_det_id
					)
					wizard.can_edit_wizard = cant_batches_val == 1

				else:
					source_amount_temp = sum(
						wizard._get_wizard_values_from_batch(lot)['source_amount'] for lot in batches
					)
					source_amount_currency_temp = sum(
						wizard._get_wizard_values_from_batch(lot)['source_amount_currency'] for lot in batches
					)
					wizard.update({
						'company_id': batches[0]['lines'][0].company_id.id,
						'partner_id': False,
						'partner_type': False,
						'payment_type': wizard_values_from_batch['payment_type'],
						'source_currency_id': False,
						'source_amount': source_amount_temp,
						'source_amount_currency': source_amount_currency_temp,
					})
					wizard.can_edit_wizard = False

			else:
				# Comportamiento nativo para otros tipos
				batch_result = batches[0]
				wizard_values_from_batch = wizard._get_wizard_values_from_batch(batch_result)
				if len(batches) == 1:
					wizard.update(wizard_values_from_batch)
					wizard.can_edit_wizard = True
				else:
					wizard.update({
						'company_id': batches[0]['lines'][0].company_id.id,
						'partner_id': False,
						'partner_type': False,
						'payment_type': wizard_values_from_batch['payment_type'],
						'source_currency_id': False,
						'source_amount': False,
						'source_amount_currency': False,
					})
					wizard.can_edit_wizard = False
