# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging
_logging = logging.getLogger(__name__)


class AccountAccount(models.Model):
	_inherit = 'account.account'

	is_cash_account = fields.Boolean(string='Es cuenta contable de efectivo')
	is_bank_account = fields.Boolean(string='Es cuenta contable de banco')

	@api.onchange('code')
	def _compute_is_cash_account(self):
		prefijos_caja = ['101', '102', '103']
		self.is_cash_account = bool(
			self.code and len(self.code) >= 3 and self.code[:3] in prefijos_caja
		)

	@api.onchange('code')
	def _compute_is_bank_account(self):
		self.is_bank_account = bool(
			self.code and len(self.code) >= 3 and self.code[:3] == '104'
		)

	def compute_is_cash_or_bank_account(self):
		"""Recalcula los flags manualmente — útil en migraciones o scripts."""
		for record in self:
			record._compute_is_cash_account()
			record._compute_is_bank_account()

	@api.model
	def _solse_ple_init_caja_banco_flags(self):
		"""
		Hook de instalación/actualización del módulo.

		Recorre todas las cuentas existentes en todas las empresas y marca
		is_cash_account / is_bank_account según los prefijos PCGE (101, 102,
		103 → caja; 104 → banco). Sin esto, las cuentas cargadas por el plan
		de cuentas nativo o por import masivo quedan con los flags en False
		y el Libro Caja y Bancos (PLE 01) genera líneas vacías.

		Se dispara una sola vez vía 'post_init_hook' en el manifest. Es
		idempotente: ejecutarlo de nuevo solo recalcula los mismos valores.
		Respeta el valor del usuario si ya lo editó manualmente a True.
		"""
		cuentas = self.sudo().search([])
		prefijos_caja = ('101', '102', '103')
		for cuenta in cuentas:
			codigo = cuenta.code or ''
			if len(codigo) < 3:
				continue
			prefijo = codigo[:3]
			# Solo escribe si cambia — reduce writes y preserva ediciones manuales
			# que hayan puesto un flag en False intencionalmente.
			if prefijo in prefijos_caja and not cuenta.is_cash_account:
				cuenta.is_cash_account = True
			elif prefijo == '104' and not cuenta.is_bank_account:
				cuenta.is_bank_account = True


class AccountMove(models.Model):
	_inherit = 'account.move'

	# Pago de detracción/retención asociado a la factura.
	# Usado en el Libro de Compras (8.1) para campos C32-C33.
	pago_detraccion = fields.Many2one('account.payment', 'Pago de Detracción/Retención')

	# Campos computados de serie y correlativo para uso en PLE y vistas.
	# Fuente única: `l10n_latam_document_number`, tanto en ventas como en
	# compras. En una venta lo genera la secuencia del tipo de documento; en
	# una compra lo captura el usuario con el número del proveedor.
	#
	# `ref` queda solo como respaldo para las bases anteriores a la migración,
	# donde el número de compra se guardaba ahí. No es el campo correcto: es
	# texto libre, sin formato garantizado y sin la restricción de unicidad
	# por proveedor que Odoo aplica sobre el número de documento. Un `ref` mal
	# escrito dejaba la serie y el correlativo vacíos sin avisar, y el SIRE se
	# enviaba incompleto.
	#
	# Esto centraliza en un único lugar la lógica que antes cada libro PLE
	# replicaba (split '-', manejo de casos sin guion, fallback, etc.).
	solse_pe_serie = fields.Char("Serie (PLE)", compute="_compute_correlativo", store=True)
	solse_pe_numero = fields.Char("Correlativo (PLE)", compute="_compute_correlativo", store=True)

	# Tipos de movimiento que llevan un comprobante SUNAT detrás.
	TIPOS_CON_COMPROBANTE = ('out_invoice', 'out_refund',
							 'in_invoice', 'in_refund')

	def get_sunat_number(self):
		"""Número del comprobante, venga de una venta o de una compra.

		El respaldo en `ref` es deliberado y temporal: las bases anteriores a
		la migración guardan ahí el número del proveedor. Una vez migradas,
		esta rama deja de usarse.
		"""
		self.ensure_one()
		if self.move_type in self.TIPOS_CON_COMPROBANTE:
			return self.l10n_latam_document_number or self.ref or ''
		return self.ref or ''

	def tiene_numero_valido(self):
		"""El comprobante tiene serie y correlativo separables.

		Sirve para validar antes de generar un libro, en lugar de descubrir
		en el archivo enviado que una fila salio con la serie en blanco. Es
		lo que `ref` como texto libre no permitia comprobar.
		"""
		self.ensure_one()
		if self.move_type not in ('out_invoice', 'out_refund',
								  'in_invoice', 'in_refund'):
			return True
		serie, numero = self._split_serie_numero(self.get_sunat_number())
		return bool(serie and numero)

	@staticmethod
	def _split_serie_numero(raw, fallback_id=None):
		"""
		Divide 'SERIE-NUMERO' en (serie, numero). Helper puro sin efectos.

		  - 'F001-123'        → ('F001', '123')
		  - '123' (sin guion) → ('', '123')
		  - ''                → ('MOV', '0{id:07}') si se pasa fallback_id
								 ('', '')             si no

		Se usa desde _compute_correlativo y desde los libros PLE.
		"""
		raw = (raw or '').strip()
		if '-' in raw:
			partes = raw.split('-', 1)
			return (partes[0].strip(), partes[1].strip())
		if raw:
			return ('', raw)
		if fallback_id:
			return ('MOV', '0' + str(fallback_id).rjust(7, '0'))
		return ('', '')

	@api.depends('l10n_latam_document_number', 'ref', 'name', 'move_type', 'state')
	def _compute_correlativo(self):
		for move in self:
			if move.move_type in self.TIPOS_CON_COMPROBANTE:
				raw = move.l10n_latam_document_number or move.ref or ''
			else:
				# Asientos puros (entry) y receipts: no hay serie/número de
				# comprobante SUNAT, usar el nombre del asiento como número.
				raw = move.name or ''
			serie, numero = self._split_serie_numero(raw, fallback_id=move.id)
			move.solse_pe_serie = serie
			move.solse_pe_numero = numero


class AccountMoveLine(models.Model):
	_inherit = 'account.move.line'

	# glosa — definida en solse_pe_accountant como related de move_id.glosa store=True.
	# No se redefine aquí para evitar conflicto de campo duplicado.
	# Con accountant como dependencia obligatoria el campo siempre está disponible.
