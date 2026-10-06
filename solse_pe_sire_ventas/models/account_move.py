# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
_logging = logging.getLogger(__name__)

class AccountMove(models.Model) :
	_inherit = 'account.move'

	pago_detraccion = fields.Many2one('account.payment', 'Pago de Detracción/Retención')

	serie_venta = fields.Char("Serie Venta", compute="_compute_serie_venta", store=True)
	correlativo_venta = fields.Char("Correlativo Venta", compute="_compute_serie_venta", store=True)

	@api.depends('l10n_latam_document_number')
	def _compute_serie_venta(self):
		for reg in self:
			if not reg.l10n_latam_document_number:
				reg.serie_venta = ""
				reg.correlativo_venta = ""
				continue
			datos = reg.l10n_latam_document_number.split("-")
			if len(datos) != 2:
				reg.serie_venta = ""
				reg.correlativo_venta = ""
				continue

			reg.serie_venta = datos[0]
			reg.correlativo_venta = datos[1]

	"""def obtener_total_base_afecto(self):
		suma = 0
		for linea in self.invoice_line_ids:
			if linea.pe_affectation_code in ('10', '11', '12', '13', '14', '15', '16'):
				suma = suma + abs(linea.balance)
		return suma

	def obtener_total_base_inafecto(self):
		suma = 0
		for linea in self.invoice_line_ids:
			if linea.pe_affectation_code not in ('10', '11', '12', '13', '14', '15', '16'):
				suma = suma + abs(linea.balance)
		return suma"""

	# ------------------------------------------- RVIE-03b · doc modificado
	# El equivalente en ventas de lo que RCE-05 resolvio en compras: las NC
	# digitadas sueltas, sin la factura original en Odoo, dejaban las
	# columnas 29-32 del Reemplazo RVIE vacias y ademas caian siempre en
	# «mismo periodo» (observacion 5 del contador).
	#
	# UN SOLO CAMPO NUEVO, no cuatro. La primera version anadia tambien
	# tipo, serie y numero — y duplicaba lo que el usuario YA teclea en
	# `origin_doc_code` y `origin_doc_number` de solse_pe_cpe, que existen
	# desde antes, persisten (store + readonly=False) y son justo los que
	# hay que rellenar para que SUNAT acepte la nota. Obligar a teclear lo
	# mismo dos veces en la misma pantalla era el arreglo, no el problema.
	#
	# La fecha si es nueva: el XML del CPE no la necesita y el RVIE si.
	rvie_origen_fecha = fields.Date(
		string='RVIE · Fecha doc. modificado',
		help='Solo para notas de crédito cuya factura original NO está '
			 'registrada en Odoo: fecha de emisión del comprobante que la '
			 'nota modifica (campo 29 del Reemplazo RVIE).\n\n'
			 'Decide además si la nota se declara contra el mismo periodo '
			 'del comprobante que modifica (importe en negativo en la base '
			 'gravada y el IGV) o contra un periodo anterior (importe en '
			 'negativo en las columnas de descuento).\n\n'
			 'El tipo, la serie y el número salen de «Código de documento '
			 'de origen» y «Número de documento de origen». Si la nota está '
			 'enlazada a su factura en Odoo, todo esto se ignora.')

	def _rvie_fecha_doc_modificado(self):
		"""Fecha de emisión del comprobante modificado.

		Prioridad: el enlace real de Odoo primero, el campo manual
		después. Devuelve None si no hay ninguno de los dos.
		"""
		self.ensure_one()
		origen = self.reversed_entry_id if self.pe_invoice_code == '07' \
			else self.debit_origin_id
		if origen and origen.invoice_date:
			return origen.invoice_date
		return self.rvie_origen_fecha or None

	def _rvie_es_periodo_anterior(self):
		"""¿La nota modifica un comprobante de un periodo anterior?

		Regla RVIE-02: si la nota y el comprobante que modifica están en
		el mismo (año, mes), el importe va en negativo a la base gravada
		y al IGV (campos 15 y 17). Si el comprobante es de un periodo
		anterior, va en negativo a las columnas de descuento (16 y 18).

		Sin fecha de origen —ni enlace ni campo manual— se devuelve False,
		que es el comportamiento anterior: mismo periodo. No se adivina.
		"""
		self.ensure_one()
		fecha_nota = self.invoice_date
		fecha_origen = self._rvie_fecha_doc_modificado()
		if not fecha_nota or not fecha_origen:
			return False
		return (fecha_origen.year, fecha_origen.month) < \
			(fecha_nota.year, fecha_nota.month)

	def obtener_montos_libro_ventas(self):
		move = self
		valor_nro_13 = 0 # Valor facturado de la exportación
		valor_nro_14 = 0 # Base imponible de la operación gravada (4)
		valor_nro_15 = 0 # Descuento de la Base Imponible
		valor_nro_16 = 0 # Impuesto General a las Ventas y/o Impuesto de Promoción Municipal
		valor_nro_17 = 0 # Descuento del Impuesto General a las Ventas y/o Impuesto de Promoción Municipal
		valor_nro_18 = 0 # Importe total de la operación exonerada
		valor_nro_19 = 0 # Importe total de la operación inafecta 
		valor_nro_20 = 0 # Impuesto Selectivo al Consumo, de ser el caso.
		valor_nro_21 = 0 # Base imponible de la operación gravada con el Impuesto a las Ventas del Arroz Pilado
		valor_nro_22 = 0 # Impuesto a las Ventas del Arroz Pilado 
		valor_nro_23 = 0 # Impuesto al Consumo de las Bolsas de Plástico.
		valor_nro_24 = 0 # Otros conceptos, tributos y cargos que no forman parte de la base imponible
		valor_nro_25 = 0 # Importe total del comprobante de pago

		total_exonerado = 0
		total_inafecto = 0
		total_icbper = 0
		total_exportacion = 0

		estado_comprobante = '1'
		if move.state in ["annul", "cancel"]:
			estado_comprobante = '2'

		for line in self.invoice_line_ids:
			# `abs(balance)` y no `credit`: en las notas de crédito las
			# líneas van al DEBE (credit = 0) y los montos exonerados /
			# inafectos / de exportación caían enteros a la base gravada.
			# `balance` además ya está en soles, coherente con los
			# `*_signed` de abajo.
			monto_linea = abs(line.balance)
			for impuesto in line.tax_ids:
				if impuesto.l10n_pe_edi_tax_code in ['9997'] and len(line.tax_ids) == 1:
					total_exonerado += monto_linea

				if impuesto.l10n_pe_edi_tax_code in ['9998'] and len(line.tax_ids) == 1:
					total_inafecto += monto_linea

				if impuesto.l10n_pe_edi_tax_code in ['9995'] and len(line.tax_ids) == 1:
					total_exportacion += monto_linea

				if impuesto.l10n_pe_edi_tax_code in ['7152']:
					total_icbper += impuesto.amount

		# RVIE-02: un monto va al valor facturado de exportación (15) O a
		# la base gravada + IGV (16/18) — NUNCA a ambos. Sin la resta, la
		# exportación se declaraba doble (columna propia Y dentro de la
		# gravada, con un IGV que no cuadraba con esa base).
		base_imponible = abs(move.amount_untaxed_signed) - total_exonerado \
			- total_inafecto - total_exportacion
		impuesto_general = abs(move.amount_tax_signed) - total_icbper
		importe_total = abs(move.amount_total_signed)


		valor_nro_13 = total_exportacion
		valor_nro_14 = base_imponible
		valor_nro_16 = impuesto_general
		valor_nro_18 = total_exonerado
		valor_nro_19 = total_inafecto
		valor_nro_23 = total_icbper
		valor_nro_25 = importe_total

		if move.pe_invoice_code in ['07']:
			valor_nro_13 = (valor_nro_13 * -1.00)
			valor_nro_14 = (valor_nro_14 * -1.00)
			valor_nro_16 = (valor_nro_16 * -1.00)
			valor_nro_18 = (valor_nro_18 * -1.00)
			valor_nro_19 = (valor_nro_19 * -1.00)
			valor_nro_23 = (valor_nro_23 * -1.00)
			valor_nro_25 = (valor_nro_25 * -1.00)

			# RVIE-02, segunda mitad: si la NC modifica un comprobante de
			# un periodo ANTERIOR, el importe no descuenta la base
			# gravada del mes — va a las columnas de descuento. Hasta
			# 19.0.0.11 valor_nro_15 y valor_nro_17 se inicializaban a 0
			# y no se tocaban nunca, asi que toda nota caia en «mismo
			# periodo» aunque modificara un comprobante de meses atras.
			# La exportacion (13) no tiene columna de descuento y se
			# queda donde esta.
			if move._rvie_es_periodo_anterior():
				valor_nro_15 = valor_nro_14   # campo 16 · Dscto BI
				valor_nro_17 = valor_nro_16   # campo 18 · Dscto IGV
				valor_nro_14 = 0              # campo 15 · BI Gravada
				valor_nro_16 = 0              # campo 17 · IGV / IPM

		if estado_comprobante == '2':
			valor_nro_13 = 0
			valor_nro_14 = 0
			valor_nro_15 = 0
			valor_nro_16 = 0
			valor_nro_17 = 0
			valor_nro_18 = 0
			valor_nro_19 = 0
			valor_nro_23 = 0
			valor_nro_25 = 0

		json = {
			"nro_13": valor_nro_13,
			"nro_14": valor_nro_14,
			"nro_15": valor_nro_15,
			"nro_16": valor_nro_16,
			"nro_17": valor_nro_17,
			"nro_18": valor_nro_18,
			"nro_19": valor_nro_19,
			"nro_20": valor_nro_20,
			"nro_21": valor_nro_21,
			"nro_22": valor_nro_22,
			"nro_23": valor_nro_23,
			"nro_24": valor_nro_24,
			"nro_25": valor_nro_25,
		}
		return json

	
	def obtener_valor_campo_14(self, tipo_cambio):
		suma = 0
		for linea in self.invoice_line_ids:
			if linea.tipo_afectacion_compra.nro_col_importe_afectacion == 14:
				monto = abs(linea.price_subtotal)
				monto = monto * tipo_cambio
				suma = suma + monto

		respuesta = ""
		if suma > 0:
			respuesta = format(suma, '.2f')
		else:
			respuesta = ""

		return respuesta

	def obtener_valor_campo_15(self, tipo_cambio):
		suma = 0
		for linea in self.invoice_line_ids:
			impuesto_afect_ids = []
			impuesto = linea.tax_ids[0]
			for item in linea.tipo_afectacion_compra.impuesto_afect_ids:
				if impuesto.id == item.impuesto_id.id and item.nro_col_importe_impuesto == 15:
					monto = abs(linea.price_total - linea.price_subtotal)
					monto = monto * tipo_cambio
					suma = suma + monto

		respuesta = ""
		if suma > 0:
			respuesta = format(suma, '.2f')
		else:
			respuesta = ""
			
		return respuesta

	def obtener_valor_campo_16(self, tipo_cambio):
		suma = 0
		for linea in self.invoice_line_ids:
			if linea.tipo_afectacion_compra.nro_col_importe_afectacion == 16:
				monto = abs(linea.price_subtotal)
				monto = monto * tipo_cambio
				suma = suma + monto

		respuesta = ""
		if suma > 0:
			respuesta = format(suma, '.2f')
		else:
			respuesta = ""

		return respuesta

	def obtener_valor_campo_17(self, tipo_cambio):
		suma = 0
		for linea in self.invoice_line_ids:
			impuesto_afect_ids = []
			impuesto = linea.tax_ids[0]
			for item in linea.tipo_afectacion_compra.impuesto_afect_ids:
				if impuesto.id == item.impuesto_id.id and item.nro_col_importe_impuesto == 17:
					monto = abs(linea.price_total - linea.price_subtotal)
					monto = monto * tipo_cambio
					suma = suma + monto

		respuesta = ""
		if suma > 0:
			respuesta = format(suma, '.2f')
		else:
			respuesta = ""
			
		return respuesta

	def obtener_valor_campo_18(self, tipo_cambio):
		suma = 0
		for linea in self.invoice_line_ids:
			if linea.tipo_afectacion_compra.nro_col_importe_afectacion == 18:
				monto = abs(linea.price_subtotal)
				monto = monto * tipo_cambio
				suma = suma + monto

		respuesta = ""
		if suma > 0:
			respuesta = format(suma, '.2f')
		else:
			respuesta = ""

		return respuesta

	def obtener_valor_campo_19(self, tipo_cambio):
		suma = 0
		for linea in self.invoice_line_ids:
			impuesto_afect_ids = []
			impuesto = linea.tax_ids[0]
			for item in linea.tipo_afectacion_compra.impuesto_afect_ids:
				if impuesto.id == item.impuesto_id.id and item.nro_col_importe_impuesto == 19:
					monto = abs(linea.price_total - linea.price_subtotal)
					monto = monto * tipo_cambio
					suma = suma + monto

		respuesta = ""
		if suma > 0:
			respuesta = format(suma, '.2f')
		else:
			respuesta = ""
			
		return respuesta

	def obtener_valor_campo_20(self, tipo_cambio):
		suma = 0
		for linea in self.invoice_line_ids:
			if linea.tipo_afectacion_compra.nro_col_importe_afectacion == 20:
				monto = abs(linea.price_subtotal)
				monto = monto * tipo_cambio
				suma = suma + monto

		respuesta = ""
		if suma > 0:
			respuesta = format(suma, '.2f')
		else:
			respuesta = ""

		return respuesta

	def obtener_valor_campo_21(self, tipo_cambio):
		suma = 0
		for linea in self.invoice_line_ids:
			impuesto_afect_ids = []
			impuesto = linea.tax_ids[0]
			for item in linea.tipo_afectacion_compra.impuesto_afect_ids:
				if impuesto.id == item.impuesto_id.id and item.nro_col_importe_impuesto == 21:
					monto = abs(linea.price_total - linea.price_subtotal)
					monto = monto * tipo_cambio
					suma = suma + monto

		respuesta = ""
		if suma > 0:
			respuesta = format(suma, '.2f')
		else:
			respuesta = ""
			
		return respuesta

	def obtener_valor_campo_22(self, tipo_cambio):
		suma = 0
		for linea in self.invoice_line_ids:
			impuesto_afect_ids = []
			impuesto = linea.tax_ids[0]
			for item in linea.tipo_afectacion_compra.impuesto_afect_ids:
				if impuesto.id == item.impuesto_id.id and item.nro_col_importe_impuesto == 22:
					monto = abs(linea.price_total - linea.price_subtotal)
					monto = monto * tipo_cambio
					suma = suma + monto

		respuesta = ""
		if suma > 0:
			respuesta = format(suma, '.2f')
		else:
			respuesta = ""
			
		return respuesta

	def obtener_valor_campo_23(self, tipo_cambio):
		suma = 0
		for linea in self.invoice_line_ids:
			if linea.tipo_afectacion_compra.nro_col_importe_afectacion == 23:
				monto = abs(linea.price_subtotal)
				monto = monto * tipo_cambio
				suma = suma + monto

		respuesta = ""
		if suma > 0:
			respuesta = format(suma, '.2f')
		else:
			respuesta = ""

		return respuesta

	def obtener_valor_campo_24(self, tipo_cambio):
		suma = 0
		for linea in self.invoice_line_ids:
			suma = suma + abs(linea.balance)

		respuesta = ""
		if suma > 0:
			respuesta = format(suma, '.2f')
		else:
			respuesta = ""
			
		return respuesta


class AccountMoveLine(models.Model):
	_inherit = 'account.move.line'

	glosa = fields.Char("Glosa", related="move_id.glosa", store=True)
