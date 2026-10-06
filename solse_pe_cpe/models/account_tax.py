# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _
from odoo.osv import expression
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round as round
from collections import defaultdict
#se cambio email_re por email_normalize para odoo 18
from odoo.tools import (
	date_utils,
	email_normalize,
	email_split,
	float_compare,
	float_is_zero,
	format_amount,
	format_date,
	formatLang,
	frozendict,
	get_lang,
	is_html_empty,
	sql
)

import math
import logging
_logging = logging.getLogger(__name__)

TYPE_TAX_USE = [
	('sale', 'Sales'),
	('purchase', 'Purchases'),
	('none', 'None'),
]	

# M-17/M-27: definición única en `redondeo.py` (leer su cabecera).
from .redondeo import round_up  # noqa: E402


class AccountTaxGroup(models.Model):
	_inherit = 'account.tax.group'

	mostrar_base = fields.Boolean('Mostrar base')
	
class AccountTax(models.Model):
	_inherit = 'account.tax'

	incluir_monto_completo = fields.Boolean("Incluir monto completo")

	@api.model
	def _prepare_tax_totals_pe(self, base_lines, currency, tax_lines=None):
		to_process = []
		total_impuestos_completos = 0
		for base_line in base_lines:
			to_update_vals, tax_values_list = self._compute_taxes_for_single_line(base_line)
			to_process.append((base_line, to_update_vals, tax_values_list))

		def grouping_key_generator(base_line, tax_values):
			source_tax = tax_values['tax_repartition_line'].tax_id
			return {'tax_group': source_tax.tax_group_id}

		global_tax_details = self._aggregate_taxes(to_process, grouping_key_generator=grouping_key_generator)

		tax_group_vals_list = []
		for tax_detail in global_tax_details['tax_details'].values():
			tax_group_vals = {
				'tax_group': tax_detail['tax_group'],
				'base_amount': tax_detail['base_amount_currency'],
				'tax_amount': tax_detail['tax_amount_currency'],
			}

			# Handle a manual edition of tax lines.
			if tax_lines is not None:
				matched_tax_lines = [
					x
					for x in tax_lines
					if (x['group_tax'] or x['tax_repartition_line'].tax_id).tax_group_id == tax_detail['tax_group']
				]
				if matched_tax_lines:
					tax_group_vals['tax_amount'] = sum(x['tax_amount'] for x in matched_tax_lines)

			tax_group_vals_list.append(tax_group_vals)

		tax_group_vals_list = sorted(tax_group_vals_list, key=lambda x: (x['tax_group'].sequence, x['tax_group'].id))

		# ==== Partition the tax group values by subtotals ====

		amount_untaxed = global_tax_details['base_amount_currency']
		amount_tax = 0.0

		subtotal_order = {}
		groups_by_subtotal = defaultdict(list)
		for tax_group_vals in tax_group_vals_list:
			tax_group = tax_group_vals['tax_group']

			subtotal_title = tax_group.preceding_subtotal or "Op. Gravadas"
			sequence = tax_group.sequence

			monto_asignar = tax_group_vals['tax_amount']
			monto_base = tax_group_vals['base_amount']
			if not monto_asignar:
				monto_asignar = tax_group_vals['base_amount']
				total_impuestos_completos = total_impuestos_completos + monto_asignar
				monto_base = 0

			subtotal_order[subtotal_title] = min(subtotal_order.get(subtotal_title, float('inf')), sequence)
			groups_by_subtotal[subtotal_title].append({
				'group_key': tax_group.id,
				'tax_group_id': tax_group.id,
				'tax_group_name': tax_group.name,
				'tax_group_amount': monto_asignar,
				'tax_group_base_amount': monto_base,
				'formatted_tax_group_amount': formatLang(self.env, monto_asignar, currency_obj=currency),
				'formatted_tax_group_base_amount': formatLang(self.env, monto_base, currency_obj=currency),
			})

		amount_untaxed = amount_untaxed - total_impuestos_completos

		# ==== Build the final result ====

		subtotals = []
		for subtotal_title in sorted(subtotal_order.keys(), key=lambda k: subtotal_order[k]):
			amount_total = (amount_untaxed + amount_tax)
			subtotals.append({
				'name': subtotal_title,
				'amount': amount_total,
				'formatted_amount': formatLang(self.env, amount_total, currency_obj=currency),
			})
			amount_tax += sum(x['tax_group_amount'] for x in groups_by_subtotal[subtotal_title])

		amount_total = (amount_untaxed + amount_tax)

		display_tax_base = (len(global_tax_details['tax_details']) == 1 and currency.compare_amounts(tax_group_vals_list[0]['base_amount'], amount_untaxed) != 0)\
						   or len(global_tax_details['tax_details']) > 1

		return {
			'amount_untaxed': currency.round(amount_untaxed) if currency else amount_untaxed,
			'amount_total': currency.round(amount_total) if currency else amount_total,
			'formatted_amount_total': formatLang(self.env, amount_total, currency_obj=currency),
			'formatted_amount_untaxed': formatLang(self.env, amount_untaxed, currency_obj=currency),
			'groups_by_subtotal': groups_by_subtotal,
			'subtotals': subtotals,
			'subtotals_order': sorted(subtotal_order.keys(), key=lambda k: subtotal_order[k]),
			'display_tax_base': display_tax_base
		}


	def compute_all_sunat(self, price_unit, currency=None, quantity=1.0, product=None, partner=None, is_refund=False, handle_price_include=True, include_caba_tags=False, rounding_method=None):

		if not self:
			company = self.env.company
		else:
			company = self[0].company_id._accessible_branches()[:1] or self[0].company_id

		# Compute tax details for a single line.
		currency = currency or company.currency_id
		if 'force_price_include' in self.env.context:
			special_mode = 'total_included' if self.env.context['force_price_include'] else 'total_excluded'
		elif not handle_price_include:
			special_mode = 'total_excluded'
		else:
			special_mode = False
		base_line = self._prepare_base_line_for_taxes_computation(
			None,
			partner_id=partner,
			currency_id=currency,
			product_id=product,
			tax_ids=self,
			price_unit=price_unit,
			quantity=quantity,
			is_refund=is_refund,
			special_mode=special_mode,
		)
		self._add_tax_details_in_base_line(base_line, company, rounding_method=rounding_method)
		#self._add_accounting_data_to_base_line_tax_details(base_line, company, include_caba_tags=include_caba_tags)
		self.with_context(
			compute_all_use_raw_base_lines=True,
		)._add_accounting_data_to_base_line_tax_details(base_line, company, include_caba_tags=include_caba_tags)

		tax_details = base_line['tax_details']
		if 'total_excluded_currency' in tax_details:
			total_void = total_excluded = tax_details['total_excluded_currency']
			total_included = tax_details['total_included_currency']
		elif 'raw_total_excluded_currency' in tax_details:
			total_void = total_excluded = tax_details['raw_total_excluded_currency']
			total_included = tax_details['raw_total_included_currency']
		else:
			raise UserError("No se pudo procesar el json de impuestos: %s" % str(tax_details))

		# Convert to the 'old' compute_all api.
		taxes = []
		for tax_data in tax_details['taxes_data']:
			tax = tax_data['tax']
			for tax_rep_data in tax_data['tax_reps_data']:
				rep_line = tax_rep_data['tax_rep']
				base_amount_currency = 0
				if 'base_amount_currency' in tax_data:
					base_amount_currency = tax_data['base_amount_currency']
				else:
					base_amount_currency = tax_data['raw_base_amount_currency']

				taxes.append({
					'id': tax.id,
					'name': partner and tax.with_context(lang=partner.lang).name or tax.name,
					'amount': tax_rep_data['tax_amount_currency'],
					'base': base_amount_currency,
					'sequence': tax.sequence,
					'account_id': tax_rep_data['account'].id,
					'analytic': tax.analytic,
					'use_in_tax_closing': rep_line.use_in_tax_closing,
					'price_include': tax.price_include,
					'tax_exigibility': tax.tax_exigibility,
					'tax_repartition_line_id': rep_line.id,
					'group': tax_data['group'],
					'tag_ids': tax_rep_data['tax_tags'].ids,
					'tax_ids': tax_rep_data['taxes'].ids,
				})
				if not rep_line.account_id:
					total_void += tax_rep_data['tax_amount_currency']

		if self.env.context.get('round_base', True):
			total_excluded = currency.round(total_excluded)
			total_included = currency.round(total_included)

		return {
			'base_tags': base_line['tax_tag_ids'].ids,
			'taxes': taxes,
			'total_excluded': total_excluded,
			'total_included': total_included,
			'total_void': total_void,
		}