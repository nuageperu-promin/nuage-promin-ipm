# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.addons.solse_pe_edi.models.account_move import (
	DEPENDS_DETRACCION_RETENCION)
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError
from odoo.tools import frozendict

class AccountPayment(models.Model):
	_inherit = 'account.payment'

	transaction_number = fields.Char(string='Número de operación')
	glosa = fields.Char('Glosa', compute="_compute_glosa", store=True)
	es_x_autodetraccion = fields.Boolean("Es por autodetracción")

	@api.depends('reconciled_invoice_ids', 'reconciled_bill_ids')
	def _compute_glosa(self):
		for reg in self:
			factura = False
			if reg.reconciled_invoice_ids:
				factura = reg.reconciled_invoice_ids[0]
			elif reg.reconciled_bill_ids:
				factura = reg.reconciled_bill_ids[0]
			reg.glosa = factura.glosa if factura else ''
			# La propagacion a move_id se maneja via AccountMove._compute_glosa_move

class AccountMoveLine(models.Model):
	_inherit = 'account.move.line'

	# En Odoo 19 account.move.line ya tiene payment_id como related de move_id.origin_payment_id
	transaction_number = fields.Char(related='payment_id.transaction_number', store=True)
	glosa = fields.Char("Glosa", related="move_id.glosa", store=True)

	@api.ondelete(at_uninstall=False)
	def _prevent_automatic_line_deletion(self):
		if not self.env.context.get('dynamic_unlink'):
			for line in self:
				if line.display_type == 'tax' and line.move_id.line_ids.tax_ids:
					raise ValidationError(_(
						"You cannot delete a tax line as it would impact the tax report"
					))

	@api.depends('date_maturity', 'account_id')
	def _compute_term_key(self):
		"""
		Bug 2+4 fix: en Odoo 19 el term_key nativo no incluye account_id, lo que
		provoca colisión entre la línea de pago normal y la línea de detracción
		cuando ambas tienen la misma fecha (ej: factura al contado o fecha de
		vencimiento igual a fecha de emisión).
		Solución: agregar account_id al key SOLO para líneas que usan la cuenta
		de detracción, preservando compatibilidad con el comportamiento nativo
		de Odoo para el resto de líneas.
		"""
		for line in self:
			if line.display_type == 'payment_term':
				company = line.company_id
				cuenta_det_id = int(company.cuenta_detracciones.id or 0)
				cuenta_det_compra_id = int(company.cuenta_detracciones_compra.id or 0)
				es_linea_detraccion = (
					line.account_id.id
					and line.account_id.id in [cuenta_det_id, cuenta_det_compra_id]
				)
				key = {
					'move_id': line.move_id.id,
					'date_maturity': fields.Date.to_date(line.date_maturity),
					'discount_date': line.discount_date,
				}
				if es_linea_detraccion:
					# Diferenciador: la línea de detracción siempre incluye account_id
					# para que nunca colisione con una cuota de pago de igual fecha
					key['account_id'] = line.account_id.id
				line.term_key = frozendict(key)
			else:
				line.term_key = False

	@api.depends('display_type', 'company_id')
	def _compute_account_id(self):
		"""
		Adaptado a Odoo 19 (v19.0.0.13):

		Estrategia:
		1. term_lines: lógica CUSTOM. Mantiene el fix v19.0.0.7 que evita el
		   desbalance del asiento al respetar la cuenta especial (detracción /
		   retención) inyectada por _compute_needed_terms.
		2. Resto de líneas (product_lines + fallback final): se DELEGAN al
		   super() pasando un subset (self - term_lines). Esto permite que la
		   extensión nativa de `stock_account` se ejecute y asigne la cuenta de
		   inventario (`accounts['stock_valuation']`) en facturas de compra de
		   productos almacenables con valoración en tiempo real (anglo-saxon).

		Fix v19.0.0.13: el override previo duplicaba el método nativo completo
		SIN llamar a super(), por lo que la cuenta de inventario de
		stock_account nunca se aplicaba en facturas de compra. Como
		stock_account vive en Community, esta solución no introduce
		dependencias Enterprise.
		"""
		term_lines = self.filtered(lambda line: line.display_type == 'payment_term')

		# === 1. Procesamiento custom de term_lines ===
		if term_lines:
			# La iteración previa para detectar company_id era inútil: se usaba
			# solo la última. Tomamos la company del primer registro.
			company_id = term_lines[0].company_id or self.env.company

			cuenta_det_id = int(company_id.cuenta_detracciones.id or 0)
			cuenta_det_compra_id = int(company_id.cuenta_detracciones_compra.id or 0)
			cuenta_ret_id = int(company_id.cuenta_retenciones.id or 0)
			cuenta_ret_venta_id = int(company_id.cuenta_retenciones_venta.id or 0)

			cuentas_especiales = set(filter(None, [
				cuenta_det_id, cuenta_det_compra_id,
				cuenta_ret_id, cuenta_ret_venta_id,
			]))

			# Excluir las líneas que ya tienen cuenta de detracción o retención:
			# no queremos recomputar su account_id.
			term_lines_filtro = term_lines.filtered(
				lambda line: line.account_id.id not in cuentas_especiales
			)

			if term_lines_filtro:
				moves = term_lines_filtro.move_id
				# current_ids: TODAS las term_lines del move (no solo el filtro).
				# Esto excluye también las líneas con cuenta especial de la
				# subquery `previous`, evitando que sean usadas como referencia
				# para reasignar el resto de term_lines.
				self.env.cr.execute("""
					WITH previous AS (
						SELECT DISTINCT ON (line.move_id)
							   'account.move' AS model,
							   line.move_id AS id,
							   NULL AS account_type,
							   line.account_id AS account_id
						  FROM account_move_line line
						 WHERE line.move_id = ANY(%(move_ids)s)
						   AND line.display_type = 'payment_term'
						   AND line.id != ANY(%(current_ids)s)
						   -- QA-13: una linea con cuenta ESPECIAL (SPOT /
						   -- retencion) jamas puede ser la referencia para
						   -- reasignar cuotas normales. current_ids solo
						   -- excluye las lineas del lote ACTUAL: cuando un
						   -- write posterior (cambiar la fecha de la
						   -- factura, por ejemplo) re-sincroniza la cuota
						   -- normal SOLA, la linea de detraccion ya
						   -- persistida quedaba como "previous" y la cuota
						   -- entera acababa en la 12123 — el residual
						   -- completo en la cuenta de detraccion y la 1212
						   -- en cero.
						   AND (line.account_id IS NULL
								OR line.account_id != ALL(%(cuentas_especiales)s))
					),
					fallback AS (
						SELECT DISTINCT ON (account_companies.res_company_id, account.account_type)
							   'res.company' AS model,
							   account_companies.res_company_id AS id,
							   account.account_type AS account_type,
							   account.id AS account_id
						  FROM account_account account
						  JOIN account_account_res_company_rel account_companies
							   ON account_companies.account_account_id = account.id
						 WHERE account_companies.res_company_id = ANY(%(company_ids)s)
						   AND account.account_type IN ('asset_receivable', 'liability_payable')
						   AND account.active = 't'
					)
					SELECT * FROM previous
					UNION ALL
					SELECT * FROM fallback
				""", {
					'company_ids': moves.company_id.ids,
					'move_ids': moves.ids,
					'current_ids': term_lines.ids,
					# [0] evita el ALL() sobre lista vacia cuando la
					# compañia no configuro cuentas especiales.
					'cuentas_especiales': list(cuentas_especiales) or [0],
				})
				accounts = {
					(model, id, account_type): account_id
					for model, id, account_type, account_id in self.env.cr.fetchall()
				}
				# Iterar SOLO las líneas con cuenta normal. Las líneas con cuenta
				# especial (SPOT / retención) ya las dejó bien _compute_needed_terms.
				for line in term_lines_filtro:
					account_type = 'asset_receivable' if line.move_id.is_sale_document(include_receipts=True) else 'liability_payable'
					move = line.move_id
					campo_propiedad = (
						'property_account_receivable_id'
						if account_type == 'asset_receivable'
						else 'property_account_payable_id'
					)
					account_id = (
						accounts.get(('account.move', move.id, None))
						or move.with_company(move.company_id).commercial_partner_id[campo_propiedad].id
						or move.with_company(move.company_id).company_id.partner_id[campo_propiedad].id
						or accounts.get(('res.company', move.company_id.id, account_type))
					)
					if line.move_id.fiscal_position_id:
						account_id = move.fiscal_position_id.map_account(self.env['account.account'].browse(account_id))
					line.account_id = account_id

		# === 2. Delegar product_lines y fallback al super() ===
		# Pasamos (self - term_lines): el super() ejecutará la lógica nativa de
		# Odoo para product_lines + el fallback final, Y permitirá que
		# stock_account._compute_account_id (si está instalado) sobreescriba el
		# account_id con la cuenta de inventario (stock_valuation) en compras
		# de productos almacenables con valoración en tiempo real.
		lineas_resto = self - term_lines
		if lineas_resto:
			super(AccountMoveLine, lineas_resto)._compute_account_id()

		# === 3. Fallback final SOLO para term_lines ===
		# El super() del paso 2 solo aplica el fallback a las líneas que le
		# pasamos. Para term_lines (que procesamos en el paso 1) replicamos el
		# fallback nativo por si alguna quedó sin cuenta asignada.
		for line in term_lines:
			if not line.account_id and line.display_type not in ('line_section', 'line_subsection', 'line_note'):
				previous_two_accounts = line.move_id.line_ids.filtered(
					lambda l: l.account_id and l.display_type == line.display_type
				)[-2:].account_id
				if len(previous_two_accounts) == 1 and len(line.move_id.line_ids) > 2:
					line.account_id = previous_two_accounts
				else:
					line.account_id = line.move_id.journal_id.default_account_id


class StatementLine(models.Model):
	_inherit = 'account.bank.statement.line'

	transaction_number = fields.Char(string='Número de transacción')


class AccountMove(models.Model):
	_inherit = 'account.move'

	# En Odoo 19, account.move ya no tiene payment_id directamente;
	# ahora se llama origin_payment_id.
	transaction_number = fields.Char(related='origin_payment_id.transaction_number', store=True)
	asiento_det_ret = fields.Many2one('account.move', string='Asiento retención/detracción')
	pago_detraccion = fields.Many2one('account.payment', 'Pago de Detracción', copy=False)
	pago_retencion  = fields.Many2one('account.payment', 'Pago de Retención',  copy=False)

	es_x_apertura = fields.Boolean("Movimiento por Apertura")
	fecha_apertura = fields.Date(
		"Fecha Apertura",
		default=fields.Date.context_today,
		# Fix Bug A: readonly eliminado — en Odoo 19 readonly=True sin states bloquea
		# el campo permanentemente. El control de edición se maneja desde la vista
		# con readonly="state != 'draft'".
	)
	glosa = fields.Char(
		'Glosa',
		compute='_compute_glosa_move',
		store=True,
		readonly=False,
	)
	tipo_cambio_dolar_sistema = fields.Float("Tipo Cambio ($)", compute="_compute_tipo_cambio_sistema", store=False, digits=(16, 3))

	fecha_vencimiento_detraccion = fields.Date(
		string="Vencimiento detracción",
		compute="_compute_fecha_vencimiento_detraccion",
		store=False,
		help="Fecha límite de pago de la detracción calculada según la configuración de empresa. "
			 "Solo aplica si 'Gestionar fecha de vencimiento de detracción' está activo.",
	)

	# === Detracción en cabecera (v19.0.0.10) ===
	# Cascada A+B para facturas de proveedor: cabecera manual > producto en línea > partner.
	# Para ventas el comportamiento sigue siendo el de solse_pe_edi (producto en línea).
	@api.model
	def _get_pe_type_detraccion(self):
		return self.env['pe.datas'].get_selection("PE.CPE.CATALOG54")

	aplica_detraccion = fields.Selection(
		'_get_pe_type_detraccion',
		string="Aplicar detracción",
		help="Código de detracción del catálogo SUNAT 54. Para facturas de "
		     "proveedor: si se llena, fuerza la detracción con este código; "
		     "si se deja vacío, el sistema busca primero en el producto de "
		     "alguna línea y luego en el partner (proveedor).",
	)

	@api.onchange('partner_id', 'move_type')
	def _onchange_partner_aplica_detraccion(self):
		"""En compras, precarga el código de detracción del proveedor si el
		usuario no lo ha tocado a mano. Si ya hay valor, no se sobrescribe.
		Si el partner no tiene default, el campo se limpia para evitar
		arrastrar valores de un partner anterior."""
		if self.move_type in ('in_invoice', 'in_refund'):
			self.aplica_detraccion = self.partner_id.aplica_detraccion or False

	# Override del compute heredado de solse_pe_edi para agregar dependencias
	# nuevas (aplica_detraccion en cabecera y partner). El @api.depends de un
	# override REEMPLAZA al del padre, no lo extiende, así que hay que
	# repetirlas todas.
	#
	# M-35: hasta 19.0.1.2 estaban COPIADAS A MANO, y eran las seis viejas.
	# Cuando A-5 completó la lista del padre a catorce, esta copia se quedó
	# atrás y la corrección no llegaba a ninguna base con la suite contable
	# instalada — o sea a ninguna real. Ahora se importan por referencia: lo
	# que se añada en `solse_pe_edi` llega aquí solo.
	@api.depends(
		*DEPENDS_DETRACCION_RETENCION,
		'aplica_detraccion',                  # nuevo: cabecera manual
		'partner_id.aplica_detraccion',       # nuevo: default del proveedor
	)
	def _compute_detraccion_retencion(self):
		# Toda la lógica de redondeo y cálculo de neto_pagar la hace el super.
		# Mi cascada se inyecta en _validar_detraccion_retencion (que es lo
		# que el compute llama internamente).
		return super(AccountMove, self)._compute_detraccion_retencion()

	def _validar_detraccion_retencion(self, forzar_retencion):
		"""Override de solse_pe_edi para soportar facturas de compra sin
		producto en líneas. Cascada para determinar el código de detracción:

		  1. self.aplica_detraccion (manual en cabecera)
		  2. invoice_line_ids.product_id.aplica_detraccion (retrocompat)
		  3. self.partner_id.aplica_detraccion (default del proveedor)

		Para facturas de venta, delega al super tal cual (no cambia nada).
		Para entries / refunds que no sean factura, también delega.
		"""
		self.ensure_one()
		if self.move_type not in ('in_invoice', 'in_refund'):
			return super(AccountMove, self)._validar_detraccion_retencion(forzar_retencion)

		# Esqueleto del retorno (igual estructura que en solse_pe_edi)
		datos_rpt = {
			"tiene_detraccion": False,
			"detraccion_id": False,
			"porc_detraccion": 0.0,
			"monto_detraccion": 0.0,
			"monto_detraccion_base": 0.0,
			"tiene_retencion": False,
			"monto_retencion": 0.0,
			"monto_retencion_base": 0.0,
		}

		# Validaciones base idénticas al super
		if (abs(self.amount_total_signed) < self.company_id.monto_detraccion
				or self.partner_id.doc_type != "6"):
			return datos_rpt

		# === Cascada A+B ===
		reg_det = self.env['pe.datas']
		PeDatas = self.env['pe.datas']

		# 1) Cabecera manual
		if self.aplica_detraccion:
			reg_det = PeDatas.search([
				('code', '=', self.aplica_detraccion),
				('table_code', '=', 'PE.CPE.CATALOG54'),
			], limit=1)

		# 2) Producto en alguna línea (primero que tenga, no el último como hacía el super)
		if not reg_det:
			for linea in self.invoice_line_ids:
				if linea.product_id and linea.product_id.aplica_detraccion:
					reg_det = linea.product_id.detraccion_id
					break

		# 3) Default del proveedor
		if not reg_det and self.partner_id.aplica_detraccion:
			reg_det = PeDatas.search([
				('code', '=', self.partner_id.aplica_detraccion),
				('table_code', '=', 'PE.CPE.CATALOG54'),
			], limit=1)

		# Si encontró código con porcentaje válido, retornar dict de detracción
		if reg_det and reg_det.value > 0:
			monto_detraccion = abs(self.amount_total_signed) * (reg_det.value / 100.0)
			monto_detraccion_base = abs(self.amount_total) * (reg_det.value / 100.0)
			return {
				"tiene_detraccion": True,
				"detraccion_id": reg_det.code,
				"porc_detraccion": reg_det.value,
				"monto_detraccion": monto_detraccion,
				"monto_detraccion_base": monto_detraccion_base,
				"tiene_retencion": False,
				"monto_retencion": 0.0,
				"monto_retencion_base": 0.0,
			}

		# Sin detracción: evaluar retención (lógica idéntica al super para compras).
		if self.partner_id.buen_contribuyente:
			return datos_rpt

		porc_retencion = self.porc_retencion
		monto_retencion = abs(self.amount_total_signed) * (porc_retencion / 100.0)
		monto_retencion = self.redondear_decimales_retencion(monto_retencion)
		monto_retencion_base = abs(self.amount_total) * (porc_retencion / 100.0)
		if self.currency_id.id == self.company_id.currency_id.id:
			monto_retencion_base = self.redondear_decimales_retencion(monto_retencion_base)

		if self.company_id.agente_retencion:
			return {
				"tiene_detraccion": False,
				"detraccion_id": False,
				"porc_detraccion": 0.0,
				"monto_detraccion": 0.0,
				"monto_detraccion_base": 0.0,
				"tiene_retencion": True,
				"monto_retencion": monto_retencion,
				"monto_retencion_base": monto_retencion_base,
			}
		return datos_rpt

	es_x_cierre = fields.Boolean("Movimiento por Cierre")

	@api.onchange('es_x_cierre')
	def _onchange_es_x_cierre(self):
		if self.es_x_cierre and self.date:
			# Proponer 31/12 del año del asiento como conveniencia
			self.date = self.date.replace(month=12, day=31)

	def _calcular_fecha_detraccion(self, fecha_base):
		"""
		Retorna la fecha de vencimiento de la detracción según configuración de empresa.
		Si usar_fecha_vencimiento_detraccion está activo, calcula el día N del mes
		siguiente a fecha_base, con cap al último día del mes (manejo correcto de febrero).
		Si no está activo, devuelve fecha_base sin modificar.
		"""
		company = self.company_id
		if not company.usar_fecha_vencimiento_detraccion or not company.dia_vencimiento_detraccion:
			return fecha_base
		primer_dia_mes_sig = fecha_base.replace(day=1) + relativedelta(months=1)
		# Cap al último día del mes (ej: si día=31 y siguiente mes es febrero → 28/29)
		ultimo_dia_mes = (primer_dia_mes_sig + relativedelta(months=1) - relativedelta(days=1)).day
		dia = min(company.dia_vencimiento_detraccion, ultimo_dia_mes)
		return primer_dia_mes_sig.replace(day=dia)

	@api.depends('invoice_date', 'tiene_detraccion', 'company_id')
	def _compute_fecha_vencimiento_detraccion(self):
		for move in self:
			if not move.tiene_detraccion or not move.invoice_date:
				move.fecha_vencimiento_detraccion = False
				continue
			move.fecha_vencimiento_detraccion = move._calcular_fecha_detraccion(move.invoice_date)

	@api.depends('origin_payment_id.glosa')
	def _compute_glosa_move(self):
		"""
		Bug 1 fix: propaga la glosa del pago al asiento contable sin usar write()
		dentro de un compute (antipatrón que causaba recursión).
		Solo sobreescribe cuando el asiento tiene un pago origen con glosa.
		Facturas y asientos manuales conservan su valor al no tener origin_payment_id.
		"""
		for move in self:
			if move.origin_payment_id and move.origin_payment_id.glosa:
				move.glosa = move.origin_payment_id.glosa
			# Sin origin_payment_id: Odoo conserva el valor almacenado (readonly=False)

	def obtener_cuotas_pago(self):
		"""Cuotas del cronograma para el bloque FormaPago del XML (obs. 3319).

		Esta es la versión que EJECUTA la suite: `solse_pe_accountant`
		carga después de `solse_pe_cpe` y pisa a la del emisor, así que la
		lógica definitiva vive aquí (y el emisor mantiene una equivalente
		para instalaciones sin este módulo).

		Historia del bug que motivó la reescritura: la versión anterior
		restaba la detracción a la PRIMERA línea del cronograma y ADEMÁS
		saltaba la línea del split comparando su importe — con el split
		activo (1212 neto + 12123 detracción) el descuento se aplicaba dos
		veces, la suma de cuotas quedaba en neto − detracción y SUNAT
		observaba 3319 en toda factura con detracción al crédito.

		Reglas:
		  * la línea del split de detracción/retención NO es cuota: se
			excluye por cuenta configurada en la compañía o, si la
			configuración falta (pasa más de lo que debería), por importe
			exacto — solo cuando hay más de una línea, porque con una sola
			esa línea es el total;
		  * la resta legacy sobre la primera cuota corre ÚNICAMENTE cuando
			no se excluyó nada (facturas sin split);
		  * cuotas en cero o negativas se descartan;
		  * el último céntimo se ajusta contra el neto pendiente para que
			la suma cierre exacta.
		"""
		invoice = self
		company = invoice.company_id
		en_base = invoice.currency_id.id == company.currency_id.id
		monto_det = (invoice.monto_detraccion if en_base
					 else invoice.monto_detraccion_base)
		monto_ret = (invoice.monto_retencion if en_base
					 else invoice.monto_retencion_base)
		neto = (invoice.monto_neto_pagar if en_base
				else invoice.monto_neto_pagar_base)
		redondear = invoice.currency_id.round

		cuentas_excluidas = {
			cuenta.id for cuenta in (
				getattr(company, 'cuenta_detracciones', False),
				getattr(company, 'cuenta_detracciones_compra', False),
				getattr(company, 'cuenta_retenciones', False),
				getattr(company, 'cuenta_retenciones_venta', False),
			) if cuenta
		}

		lineas = invoice.line_ids.filtered(
			lambda l: l.account_id.account_type
			in ('asset_receivable', 'liability_payable'))
		varias = len(lineas) > 1

		cuotas = []
		excluidas = 0
		for rec_line in lineas:
			amount = redondear(rec_line.amount_currency)
			es_split = rec_line.account_id.id in cuentas_excluidas
			if not es_split and varias:
				# Configuración ausente: la línea del split se reconoce
				# por su importe exacto. Nunca con línea única, que ahí
				# el importe es el total.
				es_split = bool(
					(monto_det and redondear(monto_det) == amount)
					or (monto_ret and redondear(monto_ret) == amount))
			if es_split:
				excluidas += 1
				continue
			cuotas.append({
				'amount': amount,
				'currency_name': rec_line.move_id.currency_id.name,
				'date_maturity': rec_line.date_maturity,
			})

		if not excluidas and cuotas and (monto_det or monto_ret):
			cuotas[0]['amount'] = redondear(
				cuotas[0]['amount'] - monto_det - monto_ret)
		cuotas = [c for c in cuotas if c['amount'] > 0]

		if cuotas:
			desvio = redondear(
				neto - sum(c['amount'] for c in cuotas))
			if desvio and abs(desvio) <= 0.05:
				cuotas[-1]['amount'] = redondear(
					cuotas[-1]['amount'] + desvio)
		return cuotas

	def _onchange_fecha_apertura(self):
		if self.es_x_apertura and self.fecha_apertura:
			self.date = self.fecha_apertura or fields.Date.context_today(self)
		else:
			self.date = self.invoice_date or fields.Date.context_today(self)

	def _post(self, soft=True):
		res = super(AccountMove, self)._post(soft=soft)
		return res

	@api.depends('invoice_date', 'currency_id')
	def _compute_tipo_cambio_sistema(self):
		for reg in self:
			if reg.currency_id and reg.currency_id.name == 'USD':
				moneda_dolar = reg.currency_id
			else:
				tipo = 'venta'
				if reg.move_type in ['out_invoice', 'out_refund']:
					tipo = 'venta'
				if reg.move_type in ['in_invoice', 'in_refund']:
					tipo = 'compra'
				moneda_dolar = self.env["res.currency"].search([("name", "=", "USD"), ("rate_type", "=", tipo)], limit=1)

			if not moneda_dolar:
				moneda_dolar = self.env["res.currency"].search([("name", "=", "USD")], limit=1)

			tipo_cambio = 1.0
			if reg.invoice_date:
				tipo_cambio = moneda_dolar._convert(1, reg.company_id.currency_id, reg.company_id, reg.invoice_date, round=False)
			reg.tipo_cambio_dolar_sistema = tipo_cambio

	# obtener_totales_linea_detraccion ELIMINADO (v19.0.0.7):
	# Era código zombie. La única referencia estaba en account_payment_term.py
	# (también eliminado), dentro de un _compute_terms_pe que nunca se invoca.
	# La lógica real de la línea SPOT vive en _compute_needed_terms.

	@api.depends(
		'invoice_payment_term_id', 'journal_id', 'invoice_date', 'currency_id',
		'amount_total_in_currency_signed', 'amount_total_signed', 'invoice_date_due',
		'monto_detraccion', 'monto_retencion',
	)
	def _compute_needed_terms(self):
		AccountTax = self.env['account.tax']
		# bin_size=False: necesario en draft para que los campos binary no estén
		# recortados a su tamaño (impacta _get_rounded_base_and_tax_lines).
		for invoice in self.with_context(bin_size=False):
			# Distingue registros nuevos/onchange (NewId) vs registros persistidos.
			# En NewId los campos amount_tax/amount_untaxed pueden no reflejar
			# todavía los cambios pendientes; hay que recalcular desde base_lines.
			is_draft = invoice.id != invoice._origin.id

			cuenta_det_id = invoice.company_id.cuenta_detracciones.id
			cuenta_det_compra_id = invoice.company_id.cuenta_detracciones_compra.id
			cuenta_ret_id = invoice.company_id.cuenta_retenciones_venta.id
			cuenta_ret_compra_id = invoice.company_id.cuenta_retenciones.id

			if invoice.move_type == 'in_invoice':
				cuenta_det_id = cuenta_det_compra_id
				cuenta_ret_id = cuenta_ret_compra_id

			invoice.needed_terms = {}
			invoice.needed_terms_dirty = True
			sign = 1 if invoice.is_inbound(include_receipts=True) else -1

			if invoice.is_invoice(True) and invoice.invoice_line_ids:
				if invoice.invoice_payment_term_id:
					if is_draft:
						# Replica el comportamiento del nativo Odoo 19
						# (account_move.py:1388-1402): recalcula desde
						# base_lines + _prepare_tax_lines para tener montos
						# coherentes con los onchange en curso.
						tax_amount_currency = 0.0
						tax_amount = tax_amount_currency
						untaxed_amount_currency = 0.0
						untaxed_amount = untaxed_amount_currency
						sign = invoice.direction_sign
						base_lines, _tax_lines = invoice._get_rounded_base_and_tax_lines(round_from_tax_lines=False)
						AccountTax._add_accounting_data_in_base_lines_tax_details(
							base_lines, invoice.company_id,
							include_caba_tags=invoice.always_tax_exigible,
						)
						tax_results = AccountTax._prepare_tax_lines(base_lines, invoice.company_id)
						for _base_line, to_update in tax_results['base_lines_to_update']:
							untaxed_amount_currency += sign * to_update['amount_currency']
							untaxed_amount += sign * to_update['balance']
						for tax_line_vals in tax_results['tax_lines_to_add']:
							tax_amount_currency += sign * tax_line_vals['amount_currency']
							tax_amount += sign * tax_line_vals['balance']
					else:
						tax_amount_currency = invoice.amount_tax * sign
						tax_amount = invoice.amount_tax_signed
						untaxed_amount_currency = invoice.amount_untaxed * sign
						untaxed_amount = invoice.amount_untaxed_signed

					monto_detraccion_base = invoice.monto_detraccion_base * sign
					monto_detraccion = invoice.monto_detraccion * sign

					if invoice.tiene_detraccion:
						untaxed_amount_currency = untaxed_amount_currency - monto_detraccion_base
						untaxed_amount = untaxed_amount - monto_detraccion

					# En Odoo 19 _compute_terms recibe cash_rounding
					invoice_payment_terms = invoice.invoice_payment_term_id._compute_terms(
						date_ref=invoice.invoice_date or invoice.date or fields.Date.context_today(invoice),
						currency=invoice.currency_id,
						tax_amount_currency=tax_amount_currency,
						tax_amount=tax_amount,
						untaxed_amount_currency=untaxed_amount_currency,
						untaxed_amount=untaxed_amount,
						company=invoice.company_id,
						sign=sign,
						cash_rounding=invoice.invoice_cash_rounding_id,
					)

					for term in invoice_payment_terms['line_ids']:
						# En Odoo 19 la clave ya no incluye discount_amount_currency ni account_id
						key = frozendict({
							'move_id': invoice.id,
							'date_maturity': fields.Date.to_date(term.get('date')),
							'discount_date': invoice_payment_terms.get('discount_date'),
						})
						values = {
							'balance': term['company_amount'],
							'amount_currency': term['foreign_amount'],
							'discount_date': invoice_payment_terms.get('discount_date'),
							'discount_balance': invoice_payment_terms.get('discount_balance') or 0.0,
							'discount_amount_currency': invoice_payment_terms.get('discount_amount_currency') or 0.0,
						}
						if key not in invoice.needed_terms:
							invoice.needed_terms[key] = values
						else:
							invoice.needed_terms[key]['balance'] += values['balance']
							invoice.needed_terms[key]['amount_currency'] += values['amount_currency']

					if invoice.tiene_detraccion:
						if invoice.move_type == 'out_invoice' and not cuenta_det_id:
							raise UserError("No se ha configurado una cuenta de detracción para ventas")
						if invoice.move_type == 'in_invoice' and not cuenta_det_compra_id:
							raise UserError("No se ha configurado una cuenta de detracción para compras")

						fecha_base = invoice.invoice_date or invoice.date or fields.Date.today()
						# Calcular fecha de vencimiento de detracción según config de empresa.
						# Si usar_fecha_vencimiento_detraccion está activo, usa el día N del mes
						# siguiente; si no, usa la fecha base de la factura.
						fecha_ini = invoice._calcular_fecha_detraccion(fecha_base)
						# Bug 2+4 fix: account_id en el key evita colisión con cuotas de igual fecha.
						key_detraccion = frozendict({
							'move_id': invoice.id,
							'date_maturity': fecha_ini,
							'discount_date': False,
							'account_id': cuenta_det_id,
						})
						values_det = {
							'balance': monto_detraccion,
							'amount_currency': monto_detraccion_base,
							'discount_date': False,
							'discount_balance': 0.0,
							'discount_amount_currency': 0.0,
						}
						if key_detraccion not in invoice.needed_terms:
							invoice.needed_terms[key_detraccion] = values_det
						else:
							invoice.needed_terms[key_detraccion]['balance'] = monto_detraccion
							invoice.needed_terms[key_detraccion]['amount_currency'] = monto_detraccion_base

				else:
					# Sin término de pago
					untaxed_amount_currency = invoice.amount_total_in_currency_signed
					untaxed_amount = invoice.amount_total_signed

					monto_detraccion_base = invoice.monto_detraccion_base * sign
					monto_detraccion = invoice.monto_detraccion * sign
					monto_retencion_base = invoice.monto_retencion_base * sign
					monto_retencion = invoice.monto_retencion * sign

					if invoice.tiene_detraccion:
						untaxed_amount_currency = untaxed_amount_currency - monto_detraccion_base
						untaxed_amount = untaxed_amount - monto_detraccion

					if invoice.tiene_retencion:
						untaxed_amount_currency = untaxed_amount_currency - monto_retencion_base
						untaxed_amount = untaxed_amount - monto_retencion

					if invoice.tiene_detraccion or invoice.tiene_retencion:
						# Línea del monto neto a pagar (lo que recibe el partner por la
						# receivable/payable, ya descontados det y ret).
						invoice.needed_terms[frozendict({
							'move_id': invoice.id,
							'date_maturity': fields.Date.to_date(invoice.invoice_date_due),
							'discount_date': False,
						})] = {
							'balance': untaxed_amount,
							'amount_currency': untaxed_amount_currency,
							'discount_date': False,
							'discount_balance': 0.0,
							'discount_amount_currency': 0.0,
						}

					if invoice.tiene_detraccion:
						if invoice.move_type == 'out_invoice' and not cuenta_det_id:
							raise UserError("No se ha configurado una cuenta de detracción para ventas")
						if invoice.move_type == 'in_invoice' and not cuenta_det_compra_id:
							raise UserError("No se ha configurado una cuenta de detracción para compras")

						fecha_base = invoice.invoice_date or invoice.date or fields.Date.today()
						fecha_ini = invoice._calcular_fecha_detraccion(fecha_base)

						# Línea de detracción - Bug 2+4 fix: account_id en el key evita colisión
						# con la línea de neto cuando invoice_date == invoice_date_due (contado)
						key_detraccion = frozendict({
							'move_id': invoice.id,
							'date_maturity': fecha_ini,
							'discount_date': False,
							'account_id': cuenta_det_id,
						})
						values_det = {
							'balance': monto_detraccion,
							'amount_currency': monto_detraccion_base,
							'discount_date': False,
							'discount_balance': 0.0,
							'discount_amount_currency': 0.0,
						}
						if key_detraccion in invoice.needed_terms:
							invoice.needed_terms[key_detraccion]['balance'] = monto_detraccion
							invoice.needed_terms[key_detraccion]['amount_currency'] = monto_detraccion_base
						else:
							invoice.needed_terms[key_detraccion] = values_det

					if invoice.tiene_retencion:
						if invoice.move_type == 'out_invoice' and not cuenta_ret_id:
							raise UserError("No se ha configurado una cuenta de retenciones para ventas")
						if invoice.move_type == 'in_invoice' and not cuenta_ret_id:
							raise UserError("No se ha configurado una cuenta de retenciones para compras")

						key_retencion = frozendict({
							'move_id': invoice.id,
							'date_maturity': invoice.invoice_date or invoice.date or fields.Date.today(),
							'discount_date': False,
							'account_id': cuenta_ret_id,
						})
						values_ret = {
							'balance': monto_retencion,
							'amount_currency': monto_retencion_base,
							'discount_date': False,
							'discount_balance': 0.0,
							'discount_amount_currency': 0.0,
						}
						if key_retencion in invoice.needed_terms:
							invoice.needed_terms[key_retencion]['balance'] = monto_retencion
							invoice.needed_terms[key_retencion]['amount_currency'] = monto_retencion_base
						else:
							invoice.needed_terms[key_retencion] = values_ret

					# Fallback: sin detracción y sin retención → una sola línea con el total.
					if not invoice.tiene_detraccion and not invoice.tiene_retencion:
						invoice.needed_terms[frozendict({
							'move_id': invoice.id,
							'date_maturity': fields.Date.to_date(invoice.invoice_date_due),
							'discount_date': False,
						})] = {
							'balance': invoice.amount_total_signed,
							'amount_currency': invoice.amount_total_in_currency_signed,
							'discount_date': False,
							'discount_balance': 0.0,
							'discount_amount_currency': 0.0,
						}
