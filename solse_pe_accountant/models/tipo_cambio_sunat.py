# -*- coding: utf-8 -*-

from odoo import api, fields, models, Command, _
import json
from odoo.tools import (
	date_utils,
	float_compare,
	float_is_zero,
	float_repr,
	format_amount,
	format_date,
	formatLang,
	frozendict,
	get_lang,
	is_html_empty,
	sql
)

INCLUIDOS = ['in_invoice', 'out_invoice', 'in_refund', 'out_refund']

class AccountMoveSunat(models.Model):
	_inherit = 'account.move'

	@api.model
	def _get_default_fecha_factura(self):
		move_type = self.env.context.get('default_move_type', 'entry')
		if move_type == 'in_invoice':
			return fields.Date.context_today(self)
		else:
			return False

	invoice_date = fields.Date(
		string='Invoice/Bill Date',
		default=_get_default_fecha_factura,
		# Fix Bug E: readonly y states eliminados — deprecados en Odoo 19.
		# El control de edición se maneja desde la vista con readonly="state != 'draft'".
		index=True,
		copy=False,
	)
	fecha_tipo_cambio = fields.Date(
		"Fecha tipo de cambio",
		compute="_compute_fecha_tipo_cambio",
		help=(
			"Fecha que se toma para el tipo de cambio.\n"
			"Para compras toma la fecha de factura y para los demás movimientos la fecha contable"
		),
	)

	# Fix Bug B: agregado es_x_apertura y fecha_apertura a depends para que el recompute
	# se dispare automáticamente al cambiar esos campos (no solo desde la UI).
	@api.depends('move_type', 'date', 'invoice_date', 'es_x_apertura', 'fecha_apertura')
	def _compute_fecha_tipo_cambio(self):
		for reg in self:
			fecha = reg.invoice_date
			if reg.state in ['posted', 'cancel', 'annull']:
				reg.fecha_tipo_cambio = reg.date
				continue
			if reg.move_type == 'in_invoice':  # Facturas proveedor
				fecha = reg.invoice_date
			elif reg.move_type == 'in_refund':  # Notas de crédito proveedor
				fecha = reg.reversed_entry_id.invoice_date
			elif reg.move_type == 'out_refund':  # Notas de crédito cliente
				fecha = reg.reversed_entry_id.invoice_date
			elif reg.es_x_apertura:
				# Fix Bug B: cubre out_invoice Y entry con apertura (antes solo out_invoice).
				# Usa fecha_apertura si está seteada, sino invoice_date, sino date como fallback.
				fecha = reg.fecha_apertura or reg.invoice_date or reg.date
			else:
				fecha = reg.date

			reg.fecha_tipo_cambio = fecha

	# Fix Bug B: agregado es_x_apertura y fecha_apertura a depends para recompute automático.
	# En Odoo 19 _compute_date agrega taxable_supply_date y move_type como dependencias.
	@api.depends('invoice_date', 'company_id', 'move_type', 'taxable_supply_date',
	             'es_x_apertura', 'fecha_apertura')
	def _compute_date(self):
		self._compute_fecha_tipo_cambio()
		for move in self:
			if not move.invoice_date:
				if not move.date:
					move.date = fields.Date.context_today(self)
				continue
			accounting_date = move.invoice_date
			if not move.is_sale_document(include_receipts=True):
				accounting_date = move._get_accounting_date(move.invoice_date, move._affect_tax_report())
			if accounting_date and accounting_date != move.date:
				fecha_apertura = move.fecha_apertura or accounting_date
				move.date = fecha_apertura if move.es_x_apertura else accounting_date
				# Propagar recómputo a líneas (Odoo 19)
				self.env.add_to_compute(move.line_ids._fields['date'], move.line_ids)
				# might be protected because `_get_accounting_date` requires the `name`
				self.env.add_to_compute(self._fields['name'], move)

	def _compute_payments_widget_to_reconcile_info(self):
		for move in self:
			move.invoice_outstanding_credits_debits_widget = False
			move.invoice_has_outstanding = False

			if move.state != 'posted' \
					or move.payment_state not in ('not_paid', 'partial') \
					or not move.is_invoice(include_receipts=True):
				continue

			pay_term_lines = move.line_ids\
				.filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))

			domain = [
				('account_id', 'in', pay_term_lines.account_id.ids),
				('parent_state', '=', 'posted'),
				('partner_id', '=', move.commercial_partner_id.id),
				('reconciled', '=', False),
				'|', ('amount_residual', '!=', 0.0), ('amount_residual_currency', '!=', 0.0),
			]

			payments_widget_vals = {'outstanding': True, 'content': [], 'move_id': move.id}

			if move.is_inbound():
				domain.append(('balance', '<', 0.0))
				payments_widget_vals['title'] = _('Outstanding credits')
			else:
				domain.append(('balance', '>', 0.0))
				payments_widget_vals['title'] = _('Outstanding debits')

			lineas_buscar = self.env['account.move.line'].search(domain)
			for line in lineas_buscar:
				if line.currency_id == move.currency_id:
					amount = abs(line.amount_residual_currency)
				else:
					fecha_tipo_cambio = line.date if move.move_type not in INCLUIDOS else move.fecha_tipo_cambio
					amount = line.company_currency_id._convert(
						abs(line.amount_residual),
						move.currency_id,
						move.company_id,
						fecha_tipo_cambio,
					)

				if move.currency_id.is_zero(amount):
					continue

				payments_widget_vals['content'].append({
					'journal_name': line.ref or line.move_id.name,
					'amount': amount,
					'currency_id': move.currency_id.id,
					'id': line.id,
					'move_id': line.move_id.id,
					'date': fields.Date.to_string(line.date),
					'account_payment_id': line.payment_id.id,
				})

			if not payments_widget_vals['content']:
				continue

			move.invoice_outstanding_credits_debits_widget = payments_widget_vals
			move.invoice_has_outstanding = True

	# _compute_partner_credit_warning ELIMINADO (v19.0.0.7):
	# Estaba dentro de un docstring triple-comilla (comentado), con indentación
	# rota y mezcla de tabs/espacios. Si en el futuro se requiere el override,
	# escribirlo desde cero contra el nativo v19.


	def _inverse_amount_total(self):
		for move in self:
			if len(move.line_ids) != 2 or move.is_invoice(include_receipts=True):
				continue

			to_write = []
			amount_currency = abs(move.amount_total)
			fecha_tipo_cambio = move.date if move.move_type not in INCLUIDOS else move.fecha_tipo_cambio
			balance = move.currency_id._convert(
				amount_currency, move.company_currency_id, move.company_id, fecha_tipo_cambio
			)

			for line in move.line_ids:
				if not line.currency_id.is_zero(balance - abs(line.balance)):
					to_write.append((1, line.id, {
						'debit': line.balance > 0.0 and balance or 0.0,
						'credit': line.balance < 0.0 and balance or 0.0,
						'amount_currency': line.balance > 0.0 and amount_currency or -amount_currency,
					}))

			move.write({'line_ids': to_write})

	def _recompute_cash_rounding_lines(self):
		"""Override v19.0.0.11 (refactor del original que era copia textual del
		nativo): el único motivo real para sobrescribir este método es la
		conversión de moneda en `_compute_cash_rounding`, donde queremos usar
		`fecha_tipo_cambio` en lugar de `move.date`. En todos los demás casos
		(misma moneda que la empresa, o documento que no sea factura/NC) la
		conversión no aplica y podemos delegar al super sin riesgo.

		Esto reduce drásticamente la superficie de divergencia con el nativo:
		solo replicamos la lógica cuando realmente importa.
		"""
		self.ensure_one()

		# Caso 1: misma moneda que la empresa → no hay conversión, super sirve.
		# Caso 2: move_type no INCLUIDOS → fecha_tipo_cambio == self.date,
		#         resultado idéntico al super.
		if self.currency_id == self.company_id.currency_id or self.move_type not in INCLUIDOS:
			return super(AccountMoveSunat, self)._recompute_cash_rounding_lines()

		# Caso 3 (el único que requiere lógica custom): factura en moneda
		# extranjera donde la fecha del TC SUNAT difiere de self.date.
		# Aquí replicamos la lógica del nativo Odoo 19 con la única diferencia
		# de usar fecha_tipo_cambio en la conversión.

		def _compute_cash_rounding(self, total_amount_currency):
			difference = self.invoice_cash_rounding_id.compute_difference(self.currency_id, total_amount_currency)
			diff_amount_currency = difference
			diff_balance = self.currency_id._convert(
				diff_amount_currency, self.company_id.currency_id, self.company_id,
				self.fecha_tipo_cambio or self.date,
			)
			return diff_balance, diff_amount_currency

		def _apply_cash_rounding(self, diff_balance, diff_amount_currency, cash_rounding_line):
			rounding_line_vals = {
				'balance': diff_balance,
				'partner_id': self.partner_id.id,
				'move_id': self.id,
				'currency_id': self.currency_id.id,
				'company_id': self.company_id.id,
				'company_currency_id': self.company_id.currency_id.id,
				'display_type': 'rounding',
			}

			if self.invoice_cash_rounding_id.strategy == 'biggest_tax':
				biggest_tax_line = None
				for tax_line in self.line_ids.filtered('tax_repartition_line_id'):
					if not biggest_tax_line or tax_line.price_subtotal > biggest_tax_line.price_subtotal:
						biggest_tax_line = tax_line

				if not biggest_tax_line:
					return

				rounding_line_vals.update({
					'name': _('%s (rounding)', biggest_tax_line.name),
					'account_id': biggest_tax_line.account_id.id,
					'tax_repartition_line_id': biggest_tax_line.tax_repartition_line_id.id,
					'tax_tag_ids': [(6, 0, biggest_tax_line.tax_tag_ids.ids)],
					'tax_ids': [Command.set(biggest_tax_line.tax_ids.ids)]
				})

			elif self.invoice_cash_rounding_id.strategy == 'add_invoice_line':
				if diff_balance > 0.0 and self.invoice_cash_rounding_id.loss_account_id:
					account_id = self.invoice_cash_rounding_id.loss_account_id.id
				else:
					account_id = self.invoice_cash_rounding_id.profit_account_id.id
				rounding_line_vals.update({
					'name': self.invoice_cash_rounding_id.name,
					'account_id': account_id,
					'tax_ids': [Command.clear()]
				})

			if cash_rounding_line:
				cash_rounding_line.write(rounding_line_vals)
			else:
				cash_rounding_line = self.env['account.move.line'].create(rounding_line_vals)

		existing_cash_rounding_line = self.line_ids.filtered(lambda line: line.display_type == 'rounding')

		if not self.invoice_cash_rounding_id:
			existing_cash_rounding_line.unlink()
			return

		if self.invoice_cash_rounding_id and existing_cash_rounding_line:
			strategy = self.invoice_cash_rounding_id.strategy
			old_strategy = 'biggest_tax' if existing_cash_rounding_line.tax_line_id else 'add_invoice_line'
			if strategy != old_strategy:
				existing_cash_rounding_line.unlink()
				existing_cash_rounding_line = self.env['account.move.line']

		others_lines = self.line_ids.filtered(
			lambda line: line.account_id.account_type not in ('asset_receivable', 'liability_payable')
		)
		others_lines -= existing_cash_rounding_line
		total_amount_currency = sum(others_lines.mapped('amount_currency'))

		diff_balance, diff_amount_currency = _compute_cash_rounding(self, total_amount_currency)

		if self.currency_id.is_zero(diff_balance) and self.currency_id.is_zero(diff_amount_currency):
			existing_cash_rounding_line.unlink()
			return

		if existing_cash_rounding_line \
			and float_compare(existing_cash_rounding_line.balance, diff_balance, precision_rounding=self.currency_id.rounding) == 0 \
			and float_compare(existing_cash_rounding_line.amount_currency, diff_amount_currency, precision_rounding=self.currency_id.rounding) == 0:
			return

		_apply_cash_rounding(self, diff_balance, diff_amount_currency, existing_cash_rounding_line)


class AccountMoveLineSunat(models.Model):
	_inherit = 'account.move.line'

	parent_move_type = fields.Selection(related='move_id.move_type', store=True, readonly=True)
