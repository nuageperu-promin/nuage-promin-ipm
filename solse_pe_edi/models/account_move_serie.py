# -*- coding: utf-8 -*-

import calendar
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError, RedirectWarning
import logging
import re
_logging = logging.getLogger(__name__)


class AccountMoveSerie(models.Model):
	_inherit = 'account.move'

	es_primera_en_secuencia = fields.Boolean("Es primera en secuencia")

	def _must_check_constrains_date_sequence(self):
		"""Si Odoo debe exigir coherencia entre la fecha y la secuencia.

		La comprobacion sirve para las secuencias PROPIAS: detecta que se
		intercale un asiento con fecha anterior en una numeracion correlativa.

		En compras no aplica y ademas hace dano: el numero lo pone el
		proveedor y no sigue ninguna secuencia nuestra. Odoo intenta deducir
		un patron del texto —«INV-2026-0918» le parece una secuencia con año
		2026— y rechaza la factura porque la fecha es de 2024. El proveedor
		numera como quiere, incluso con su propio año dentro del correlativo.

		Es la misma razon por la que `_is_manual_document_number` devuelve
		True en compras: ahi el numero es un dato que se captura, no una
		secuencia que se administra.
		"""
		if self.move_type in ('in_invoice', 'in_refund'):
			return False
		if self.l10n_latam_document_type_id.usar_prefijo_personalizado:
			return False
		return True

	def _is_manual_document_number(self):
		"""Quien escribe el numero del comprobante.

		En una VENTA el numero es nuestro: lo genera la secuencia del tipo de
		documento (serie F001, B001...). En una COMPRA el numero lo emitio el
		proveedor: se captura, no se genera.

		Antes esto devolvia False siempre, tambien en compras. La consecuencia
		era que `l10n_latam_document_number` quedaba con el correlativo
		interno del diario y el numero real del proveedor no tenia donde
		vivir, asi que terminaba en `ref` — un campo de texto libre, sin
		formato garantizado y sin la restriccion de unicidad por proveedor que
		Odoo trae de fabrica. De ahi salian dos problemas silenciosos: el SIRE
		se enviaba con serie y correlativo vacios cuando el texto no tenia el
		formato exacto, y nada impedia registrar dos veces la misma factura de
		compra.
		"""
		if self.move_type in ('in_invoice', 'in_refund'):
			return True
		return False

	# =========================================================================
	# Núcleo: tres modos de generación del name
	# -------------------------------------------------------------------------
	# 1) usar_prefijo_personalizado=True   → secuencia ir.sequence propia del
	#    tipo de documento (ej. 'F F001-00000073'). Lo gestiona solse en
	#    _set_next_sequence y _get_last_sequence_domain.
	# 2) usar_prefijo_sin_localizacion=True → solo override del starting
	#    sequence para que arranque con el formato nativo de account
	#    (ej. 'BILL/2026/06/0000' → +1 = '...0001'). El dominio se delega al
	#    super, que pasa por l10n_latam_invoice_document e inyecta
	#    no_anti_regex=True en el context. ADEMÁS, override de
	#    _deduce_sequence_number_reset para que NO se fuerce 'never' (eso
	#    hace que la secuencia se resetee correctamente por mes según
	#    el regex del name BILL/YYYY/MM/XXXXX).
	# 3) Ninguno (default) → comportamiento estándar Odoo+LATAM. Si el diario
	#    tiene l10n_latam_use_documents=True saldrá 'F 00000001'; si no, el
	#    nativo puro 'BILL/2026/06/0000'.
	# =========================================================================

	@api.model
	def _deduce_sequence_number_reset(self, name):
		"""
		Override: en modo "sin localización" bypaseamos el forzado a 'never'
		que aplica l10n_latam_invoice_document cuando l10n_latam_use_documents
		es True. Sin este bypass:
		  - El correlativo nunca se resetea por mes.
		  - El `prefix1` del último name se conserva, así que una nueva
			factura con fecha contable abril seguiría tomando 'COM/2026/03/...'
			en vez de 'COM/2026/04/...'.

		Replicamos la lógica de sequence_mixin._deduce_sequence_number_reset
		(no podemos llamarla directo porque el MRO pasa por l10n_latam).
		"""
		if self and self[:1].usar_prefijo_sin_localizacion:
			for regex, ret_val, requirements in [
				(self._sequence_year_range_monthly_regex, 'year_range_month', ['seq', 'year', 'year_end', 'month']),
				(self._sequence_monthly_regex, 'month', ['seq', 'month', 'year']),
				(self._sequence_year_range_regex, 'year_range', ['seq', 'year', 'year_end']),
				(self._sequence_yearly_regex, 'year', ['seq', 'year']),
				(self._sequence_fixed_regex, 'never', ['seq']),
			]:
				match = re.match(regex, name or '')
				if match:
					groupdict = match.groupdict()
					if (
						groupdict.get('year_end') and groupdict.get('year')
						and (
							len(groupdict['year']) < len(groupdict['year_end'])
							or self._truncate_year_to_length(
								(int(groupdict['year']) + 1),
								len(groupdict['year_end'])
							) != int(groupdict['year_end'])
						)
					):
						# year y year_end no son compatibles para year_range
						continue
					if all(groupdict.get(req) is not None for req in requirements):
						return ret_val
			return 'never'
		return super()._deduce_sequence_number_reset(name)

	def _get_last_sequence_domain(self, relaxed=False):
		"""
		Dominio para localizar la última secuencia y derivar la siguiente.

		- Modo 1 (prefijo personalizado): filtro por company + tipo de doc
		  (correlativo independiente del diario).
		- Modos 2 (sin localización) y 3 (default): delegamos al super.
		  l10n_latam_invoice_document inyecta `no_anti_regex=True` en el
		  context cuando l10n_latam_use_documents=True, lo cual es CRÍTICO
		  para el modo 2: nuestros names tienen formato monthly
		  (COM/2026/03/00001) y el anti_regex nativo los excluiría porque
		  _deduce_sequence_number_reset retorna 'never' (también forzado
		  por l10n_latam_invoice_document). Sin el bypass del anti_regex,
		  `_get_last_sequence` retornaría None en cada factura y el
		  correlativo se quedaría siempre en 00001.
		"""
		self.ensure_one()
		if not self.date or not self.journal_id:
			return "WHERE FALSE", {}

		# Las compras no consumen secuencia propia: su numero es el del
		# proveedor y se captura a mano.
		if self.move_type in ('in_invoice', 'in_refund'):
			return super()._get_last_sequence_domain(relaxed=relaxed)

		# Modo 1: prefijo personalizado → filtro por tipo de documento
		if self.usar_prefijo_personalizado and self.l10n_latam_document_type_id:
			where_string = " WHERE company_id = %(company_id)s AND name != '/'"
			param = {'company_id': self.company_id.id}
			where_string += " AND l10n_latam_document_type_id = %(l10n_latam_document_type_id)s"
			param['l10n_latam_document_type_id'] = self.l10n_latam_document_type_id.id
			return where_string, param

		# Modos 2 y 3 → delegar al super
		return super()._get_last_sequence_domain(relaxed=relaxed)

	def _get_starting_sequence(self):
		"""
		Retorna el correlativo base para name_placeholder y para el cálculo
		del siguiente cuando no hay movimientos previos.
		"""
		# Modo 1: prefijo personalizado (solo ventas: la compra no numera)
		if (self.usar_prefijo_personalizado
				and self.l10n_latam_document_type_id
				and self.move_type not in ('in_invoice', 'in_refund')):
			doctype = self.l10n_latam_document_type_id
			numero = doctype.correlativo_inicial or 1
			prefijo_doc = doctype.prefijo

			if prefijo_doc:
				if doctype.secuencia_id and doctype.secuencia_id.prefix:
					prefijo_con_guion = doctype.secuencia_id.prefix
				else:
					prefijo_base = prefijo_doc.strip().rstrip('-')
					prefijo_con_guion = "%s-" % prefijo_base
				correlativo = str(numero - 1).zfill(8)
				base = "%s%s" % (prefijo_con_guion, correlativo)
				if doctype.doc_code_prefix:
					return "%s %s" % (doctype.doc_code_prefix, base)
				return base

		# Modo 2: sin localización → formato nativo puro de account
		if self.usar_prefijo_sin_localizacion:
			return self._get_starting_sequence_nativo_account()

		# Modo 3 (default): delega al nativo
		return super()._get_starting_sequence()

	def _get_starting_sequence_nativo_account(self):
		"""
		Réplica del _get_starting_sequence de account/models/account_move.py
		(Odoo 19). Se usa cuando usar_prefijo_sin_localizacion=True para
		bypassear el override de l10n_latam_invoice_document, que de otra
		manera forzaría el formato '<doc_code_prefix> 00000000'.

		Resultado típico para compras: 'BILL/2026/06/0000'
		Para ventas:                   'INV/2026/0000'
		"""
		self.ensure_one()
		move_date = self.date or self.invoice_date or fields.Date.context_today(self)
		year_part = "%04d" % move_date.year
		last_day = int(self.company_id.fiscalyear_last_day)
		last_month = int(self.company_id.fiscalyear_last_month)
		is_staggered_year = last_month != 12 or last_day != 31
		if is_staggered_year:
			max_last_day = calendar.monthrange(move_date.year, last_month)[1]
			last_day = min(last_day, max_last_day)
			if move_date > date(move_date.year, last_month, last_day):
				year_part = "%s-%s" % (
					move_date.strftime('%y'),
					(move_date + relativedelta(years=1)).strftime('%y'),
				)
			else:
				year_part = "%s-%s" % (
					(move_date + relativedelta(years=-1)).strftime('%y'),
					move_date.strftime('%y'),
				)
		# Sales/bank/cash/credit = anual; compras y demás = mensual
		if self.journal_id.type in ['sale', 'bank', 'cash', 'credit']:
			starting_sequence = "%s/%s/%s" % (
				self.journal_id.code,
				year_part,
				'0000' if is_staggered_year else '00000',
			)
		else:
			if self.journal_id.is_self_billing:
				partner_identifier = (
					str(self.partner_id.commercial_partner_id.id)
					if self.partner_id else _('[Partner id]')
				)
				starting_sequence = "%s%s/%s/%02d/0000" % (
					self.journal_id.code,
					partner_identifier.zfill(5),
					year_part,
					move_date.month,
				)
			else:
				starting_sequence = "%s/%s/%02d/0000" % (
					self.journal_id.code, year_part, move_date.month,
				)

		if self.journal_id.refund_sequence and self.move_type in ('out_refund', 'in_refund'):
			starting_sequence = "R" + starting_sequence
		if (self.journal_id.payment_sequence and self.origin_payment_id
				or self.env.context.get('is_payment')):
			starting_sequence = "P" + starting_sequence
		return starting_sequence

	def obtener_correlativo_inicial(self, prefijo, numero):
		"""MANTENIDO por compatibilidad. Ya no se usa internamente."""
		prefijo = prefijo.strip().rstrip('-')
		correlativo = str(numero).zfill(8)
		return "%s-%s" % (prefijo, correlativo)

	def _set_next_sequence(self):
		"""
		En posted con name == '/' se invoca desde super()._compute_name().
		"""
		self.ensure_one()

		# Modo 1: prefijo personalizado → secuencia propia
		if self.usar_prefijo_personalizado:
			secuencia_obj = self.l10n_latam_document_type_id.secuencia_id
			if not secuencia_obj:
				raise UserError(
					_('Defina una secuencia en el tipo de documento "%s".')
					% self.l10n_latam_document_type_id.display_name
				)
			numero = secuencia_obj.with_context(ir_sequence_date=self.date).next_by_id()
			doc_code_prefix = self.l10n_latam_document_type_id.doc_code_prefix
			if doc_code_prefix:
				self[self._sequence_field] = "%s %s" % (doc_code_prefix, numero)
			else:
				self[self._sequence_field] = numero
			self._compute_split_sequence()
			return

		# Modos 2 y 3 → delegan al nativo (que usa _locked_increment y
		# triggers de compute fields). La diferencia entre modo 2 y 3 vive
		# en _get_starting_sequence y _get_last_sequence_domain.
		return super()._set_next_sequence()

	def _get_sequence(self):
		"""
		Solo retorna la secuencia cuando el tipo de documento usa prefijo
		personalizado; en caso contrario devuelve False para que los
		consumidores de solse no operen sobre una secuencia inexistente.
		"""
		self.ensure_one()
		if not self.usar_prefijo_personalizado:
			return False
		return self.l10n_latam_document_type_id.secuencia_id

	@api.depends('posted_before', 'state', 'journal_id', 'date', 'l10n_latam_document_type_id')
	def _compute_name(self):
		"""
		Override: si en borrador el name actual no corresponde al prefijo del
		tipo de documento actual, lo reseteamos a '/'. Luego delega al super
		para que en posted se invoque _set_next_sequence().
		"""
		for move in self:
			if move.move_type in ('in_invoice', 'in_refund'):
				# El numero de una compra lo pone el proveedor y su serie no
				# tiene por que coincidir con la nuestra: resetear el name
				# porque el prefijo no cuadra borraria el numero capturado.
				continue
			if (move.state == 'draft'
					and not move.posted_before
					and move.usar_prefijo_personalizado
					and move.l10n_latam_document_type_id
					and move.name not in ['/', '//', '/0', False, None]):
				prefijo_serie = self._obtener_prefijo_para_comparar(move)
				if prefijo_serie and prefijo_serie not in move.name:
					move.name = '/'

		super(AccountMoveSerie, self)._compute_name()

	def _obtener_prefijo_para_comparar(self, move):
		"""
		Retorna el prefijo de la serie (sin doc_code_prefix ni guión final)
		para validar via 'in' si el name actual corresponde al tipo de
		documento.
		"""
		if move.l10n_latam_document_type_id.secuencia_id:
			return move.l10n_latam_document_type_id.secuencia_id.prefix.strip().rstrip('-')
		return (move.l10n_latam_document_type_id.prefijo or '').strip().rstrip('-')
