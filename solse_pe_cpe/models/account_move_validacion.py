# -*- coding: utf-8 -*-

"""Validaciones preventivas del comprobante electronico.

Proposito
---------
Que el usuario NO tenga que esperar el rechazo de SUNAT para enterarse de
que un dato estaba mal. Un rechazo llega minutos u horas despues, con un
codigo numerico y sin decir que campo corregir; para entonces el
comprobante ya consumio correlativo y hay que emitir una nota o volver a
enviar.

Cada validacion de aqui:

  * se dispara **antes** de generar el XML;
  * dice **que** esta mal, **por que** SUNAT lo rechazaria y **donde** se
    corrige;
  * cita el codigo de rechazo, para que quien haya visto el error de SUNAT
    reconozca la relacion.

Alcance
-------
Se aplican solo a los comprobantes que emitimos nosotros (ventas) y solo si
la compania tiene activada la validacion estricta. En una base que se
actualiza, el campo nace desactivado: activar diez validaciones nuevas de
golpe sobre datos historicos impediria postear facturas que hoy pasan, y
eso hay que decidirlo, no imponerlo.
"""

import logging
import re
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


# Tipo de afectacion (catalogo 7) -> familia. SUNAT cruza esto con el tipo
# de operacion del catalogo 51 y con la existencia de valor referencial.
AFECTACION_GRAVADA = ('10', '11', '12', '13', '14', '15', '16', '17')
AFECTACION_EXONERADA = ('20', '21')
AFECTACION_INAFECTA = ('30', '31', '32', '33', '34', '35', '36', '37')
AFECTACION_EXPORTACION = ('40',)
# Las gratuitas exigen valor referencial y no suman al total del documento.
# CC-PRODUCTIVO (rama casos-cpe, 2026-09-25): el 17 es «Gravado – IVAP»
# (Catálogo 07), operación ONEROSA; estaba listado como gratuita y toda
# venta con IVAP moría en _val_gratuitas (medido FAC-36).
AFECTACION_GRATUITA = ('11', '12', '13', '14', '15', '16',
					   '21', '31', '32', '33', '34', '35', '36', '37')

TOLERANCIA = 0.01


class AccountMove(models.Model):
	_inherit = 'account.move'

	# ------------------------------------------------------------ entrada

	def validar_antes_de_emitir(self):
		"""Ejecuta las validaciones preventivas sobre el comprobante.

		Se detiene en la primera que falla: un usuario corrige de a un
		problema por vez, y una lista de diez errores a la vez es menos util
		que uno bien explicado.
		"""
		for move in self:
			if move.move_type not in ('out_invoice', 'out_refund'):
				continue
			if not move.company_id.validacion_estricta_cpe:
				continue
			move._val_plazo_de_envio()
			move._val_afectacion_vs_operacion()
			move._val_detraccion_completa()
			move._val_documento_receptor()
			move._val_nota_referencia()
			move._val_moneda_tipo_cambio()
			move._val_suma_de_lineas()
			move._val_gratuitas()
			move._val_receptor_exterior()
			move._val_unidad_de_medida()
			move._val_serie_vs_tipo_documento()
			move._val_nc_sobre_factura_con_anticipos()
		return True

	# --------------------------------------------------- 1 · coherencia

	def _val_afectacion_vs_operacion(self):
		"""Afectación de la línea contra tipo de operación del comprobante.

		Rechazos 2033 y 2034. Hoy solo se comprueba la exportación; una
		venta exonerada dentro de una operación gravada, o al revés, pasa el
		posteo y la rechaza SUNAT.
		"""
		self.ensure_one()
		operacion = self.pe_sunat_transaction51 or ''
		es_exportacion = operacion[:2] == '02'

		for linea in self.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
			codigo = linea.pe_affectation_code or ''
			if not codigo:
				raise UserError(_(
					'La línea «%(linea)s» no tiene tipo de afectación del '
					'IGV.\n\nSUNAT lo exige en todas las líneas (catálogo 7) '
					'y rechaza el comprobante con el código 2032.\n\n'
					'Se corrige en la línea de la factura, campo «Tipo de '
					'afectación».',
					linea=linea.name or linea.product_id.display_name))

			if codigo in AFECTACION_EXPORTACION and not es_exportacion:
				raise UserError(_(
					'La línea «%(linea)s» está marcada como exportación, pero '
					'el comprobante es de tipo de operación «%(op)s».\n\n'
					'SUNAT rechaza esta combinación con el código 2033.\n\n'
					'Se corrige de una de estas dos formas: cambiar el tipo '
					'de afectación de la línea, o poner el tipo de operación '
					'en «0200 Exportación de bienes» o «0201 Exportación de '
					'servicios», en la pestaña «Otra información».',
					linea=linea.name, op=operacion or '(sin definir)'))

			if es_exportacion and codigo not in AFECTACION_EXPORTACION:
				raise UserError(_(
					'El comprobante es una exportación (tipo de operación '
					'%(op)s) pero la línea «%(linea)s» tiene afectación '
					'«%(cod)s».\n\nEn una exportación todas las líneas deben '
					'estar afectas como exportación (código 40). SUNAT la '
					'rechaza con el código 2034.\n\n'
					'Se corrige en la línea, campo «Tipo de afectación».',
					op=operacion, linea=linea.name, cod=codigo))

	# --------------------------------------------------- 2 · detracción

	def _val_detraccion_completa(self):
		"""Detracción: todos sus datos, y el monto MAYOR QUE CERO.

		La regla de SUNAT sobre `/Invoice/cac:PaymentTerms/cbc:Amount` es
		«decimal **positivo mayor a cero** de 12 enteros y hasta 2
		decimales», y su incumplimiento devuelve el error 3037 con el texto
		«el dato ingresado en monto de detraccion no cumple con el formato
		establecido».

		El mensaje habla del formato y la causa habitual es el valor: si el
		porcentaje del catálogo 54 está en cero, el monto sale cero y el
		comprobante se rechaza. Diagnosticar eso desde el lado del cliente es
		casi imposible, porque nada en el mensaje apunta al porcentaje.
		"""
		self.ensure_one()
		if not self.tiene_detraccion:
			return

		if not self.detraccion_id:
			raise UserError(_(
				'El comprobante está sujeto a detracción pero no tiene código '
				'del anexo 3.\n\nSe define en el producto, campo «Aplicar '
				'detracción». SUNAT rechaza el comprobante con el código '
				'3035.'))

		if not self.porc_detraccion:
			raise UserError(_(
				'El código de detracción «%(cod)s» tiene porcentaje CERO en el '
				'catálogo 54, así que el monto a depositar sale cero y SUNAT '
				'rechaza el comprobante con el código 3037 —cuyo texto habla '
				'del formato, no del valor—.\n\n'
				'Se corrige en Configuración / Catálogos SUNAT / Catálogo 54, '
				'poniendo el porcentaje vigente del anexo 3. Para «demás '
				'servicios gravados con el IGV» (037) es 12%%; para transporte '
				'de carga (027), 4%%.',
				cod=self.detraccion_id))

		if not self.monto_detraccion or self.monto_detraccion <= 0:
			raise UserError(_(
				'El monto de la detracción es %(monto)s y SUNAT exige un valor '
				'mayor que cero (error 3037).\n\nRevisar el porcentaje del '
				'código «%(cod)s» y el importe del comprobante.',
				monto=self.monto_detraccion, cod=self.detraccion_id))

		if not self.nro_cuenta_detraccion:
			raise UserError(_(
				'El proveedor no tiene número de cuenta del Banco de la '
				'Nación.\n\nEs obligatorio en el comprobante con detracción. '
				'Se registra en la ficha del contacto.'))

		if self.move_type in ('out_invoice', 'out_refund') and \
				not self.company_id.cuenta_detracciones:
			raise UserError(_(
				'No está configurada la cuenta contable de detracciones de '
				'venta.\n\nSe define en Ajustes / Configuración Peruana.'))

		# La moneda del monto de detraccion debe ser PEN (error 3208).
		moneda = getattr(self, 'moneda_base', False)
		if moneda and moneda.name != 'PEN':
			raise UserError(_(
				'El monto de la detracción está expresado en %(mon)s y SUNAT '
				'exige que sea en soles (error 3208).',
				mon=moneda.name))

		operacion = self.pe_sunat_transaction51 or ''
		if operacion[:2] != '10':
			raise UserError(_(
				'El comprobante tiene detracción pero su tipo de operación es '
				'«%(op)s».\n\nEn una operación sujeta al SPOT el tipo debe ser '
				'«1001 Operación sujeta a detracción» —o «1002» si son '
				'recursos hidrobiológicos—. SUNAT la rechaza con el código '
				'4333.\n\nSe corrige en la pestaña «Otra información», campo '
				'«Tipo de transacción de SUNAT».',
				op=operacion or '(sin definir)'))

	# ----------------------------------------------- 3 · doc. del receptor

	def _val_documento_receptor(self):
		"""Documento del receptor según el tipo de comprobante.

		Rechazo 2800. En boletas por importes iguales o mayores al umbral
		vigente el receptor tiene que estar identificado, y el DNI tiene que
		tener ocho dígitos: uno de siete pasa el posteo y lo rechaza SUNAT.
		"""
		self.ensure_one()
		codigo = self.pe_invoice_code or ''
		if codigo not in ('03',):
			return

		umbral = self.company_id.sunat_amount or 700.0
		if self.amount_total < umbral:
			return

		tipo = self.partner_id.doc_type or ''
		numero = (self.partner_id.doc_number or self.partner_id.vat or '').strip()
		if not tipo or tipo in ('0', '-') or not numero:
			raise UserError(_(
				'La boleta supera S/ %(umbral)s y el cliente «%(cliente)s» no '
				'tiene tipo y número de documento.\n\nSUNAT exige '
				'identificar al receptor a partir de ese importe y rechaza el '
				'comprobante con el código 2800.\n\n'
				'Se corrige en la ficha del cliente, campos «Tipo de '
				'documento» y «Número de documento».',
				umbral=umbral, cliente=self.partner_id.display_name))

		if tipo == '1' and not re.fullmatch(r'\d{8}', numero):
			raise UserError(_(
				'El DNI de «%(cliente)s» es «%(numero)s» y un DNI tiene '
				'exactamente ocho dígitos.\n\nSUNAT valida la longitud y '
				'rechaza el comprobante.\n\nSe corrige en la ficha del '
				'cliente.',
				cliente=self.partner_id.display_name, numero=numero))

	# ---------------------------------------------- 4 · notas de crédito

	def _val_nota_referencia(self):
		"""Nota de crédito o débito: documento de referencia.

		Rechazos 3206 y 2116. Una nota sin referencia, o que apunta a un
		comprobante anulado, se rechaza.
		"""
		self.ensure_one()
		codigo = self.pe_invoice_code or ''
		if codigo not in ('07', '08'):
			return

		origen = self.reversed_entry_id or self.debit_origin_id
		if not origen:
			raise UserError(_(
				'La nota %(tipo)s no indica a qué comprobante afecta.\n\n'
				'SUNAT exige el documento de referencia y rechaza la nota con '
				'el código 3206.\n\nSe corrige emitiendo la nota desde el '
				'comprobante original, con el botón «Nota de crédito» o '
				'«Nota de débito».',
				tipo=_('de crédito') if codigo == '07' else _('de débito')))

		if origen.state == 'cancel':
			raise UserError(_(
				'La nota afecta al comprobante %(doc)s, que está '
				'anulado.\n\nNo se puede emitir una nota sobre un comprobante '
				'anulado: SUNAT la rechaza con el código 2116.',
				doc=origen.name))

		if codigo == '07' and not self.pe_credit_note_code:
			raise UserError(_(
				'La nota de crédito no tiene motivo.\n\nSUNAT exige el código '
				'del catálogo 9 —anulación, descuento, devolución, corrección '
				'del valor— y rechaza la nota sin él.\n\nSe corrige en la '
				'pestaña «Otra información», campo «Tipo de nota de '
				'crédito».'))

	# ------------------------------------------------------- 5 · moneda

	def _val_moneda_tipo_cambio(self):
		"""Moneda extranjera con tipo de cambio de la fecha.

		Rechazo 2029. Sin tipo de cambio del día, el importe en soles del
		comprobante no coincide con lo que calcula SUNAT.
		"""
		self.ensure_one()
		if self.currency_id == self.company_id.currency_id:
			return
		fecha = self.invoice_date or self.date
		tasa = self.env['res.currency.rate'].sudo().search([
			('currency_id', '=', self.currency_id.id),
			('company_id', 'in', (self.company_id.id, False)),
			('name', '<=', fecha),
		], order='name desc', limit=1)
		if not tasa:
			raise UserError(_(
				'El comprobante está en %(moneda)s y no hay tipo de cambio '
				'registrado al %(fecha)s ni antes.\n\nSUNAT compara el '
				'importe en soles con el tipo de cambio publicado y rechaza '
				'el comprobante con el código 2029.\n\n'
				'Se corrige en Contabilidad / Configuración / Monedas, o '
				'ejecutando la actualización automática del tipo de cambio.',
				moneda=self.currency_id.name, fecha=fecha))

	# --------------------------------------------------- 6 · el redondeo

	def _val_suma_de_lineas(self):
		"""La suma de las líneas contra el total del comprobante.

		Rechazos 3271 y 3272, los más difíciles de diagnosticar: aparecen
		por diferencias de céntimos entre el importe que calcula el sistema
		y el que recalcula SUNAT línea por línea.
		"""
		self.ensure_one()
		lineas = self.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
		if not lineas:
			raise UserError(_(
				'El comprobante no tiene ninguna línea de producto o '
				'servicio.'))

		suma = sum(linea.price_subtotal for linea in lineas)
		if abs(suma - self.amount_untaxed) > TOLERANCIA:
			raise UserError(_(
				'La suma de las líneas es %(suma)s y el subtotal del '
				'comprobante es %(total)s: difieren en %(dif)s.\n\nSUNAT '
				'recalcula línea por línea y rechaza la diferencia con los '
				'códigos 3271 o 3272.\n\nSuele deberse a un descuento global '
				'o a un redondeo manual sobre el total.',
				suma=round(suma, 2), total=round(self.amount_untaxed, 2),
				dif=round(suma - self.amount_untaxed, 2)))

	# ------------------------------------------------- 7 · las gratuitas

	def _val_gratuitas(self):
		"""Operaciones gratuitas: valor referencial obligatorio.

		Rechazo 2010. Una línea gratuita con precio cero y sin valor
		referencial no permite a SUNAT calcular el IGV que corresponde.
		"""
		self.ensure_one()
		for linea in self.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
			codigo = linea.pe_affectation_code or ''
			if codigo not in AFECTACION_GRATUITA:
				continue
			# CC-PRODUCTIVO (rama casos-cpe, 2026-09-24, H-CC-12): el campo
			# pe_referential_price no existe en ningún módulo de la suite, así
			# que esta validación bloqueaba TODA gratuita. El XML (cpe_xml.py:
			# 1010/1263) toma como valor referencial el precio unitario de la
			# línea con descuento 100 %: se acepta ese mismo criterio aquí.
			referencial = getattr(linea, 'pe_referential_price', 0.0) or 0.0
			if referencial <= 0 and int(linea.discount or 0) == 100:
				referencial = linea.price_unit or 0.0
			if referencial <= 0:
				raise UserError(_(
					'La línea «%(linea)s» es una entrega gratuita '
					'(afectación %(cod)s) y no tiene valor '
					'referencial.\n\nSUNAT exige el valor de mercado para '
					'calcular el IGV de las gratuitas y rechaza el '
					'comprobante con el código 2010.\n\n'
					'Se corrige en la línea, campo «Precio referencial».',
					linea=linea.name, cod=codigo))

	# -------------------------------------------- 8 · receptor del exterior

	def _val_receptor_exterior(self):
		"""Receptor no domiciliado en una exportación.

		El Anexo 1 de SUNAT exige RUC en las facturas «salvo en las
		operaciones del inciso a) del numeral 17.2 del artículo 17 de la
		RS 097-2012», que son las de exportación. En ellas el receptor lleva
		el código «0» del catálogo 06 (DOC.TRIB.NO.DOM.SIN.RUC), carné de
		extranjería (4) o pasaporte (7).
		"""
		self.ensure_one()
		operacion = self.pe_sunat_transaction51 or ''
		if operacion[:2] != '02':
			return

		if self.partner_id.country_id.code == 'PE':
			raise UserError(_(
				'El comprobante es una exportación pero el cliente '
				'«%(cliente)s» tiene país Perú.\n\nUna exportación se emite a '
				'un no domiciliado. Se corrige en la ficha del cliente, campo '
				'«País», o cambiando el tipo de operación.',
				cliente=self.partner_id.display_name))

		tipo = self.partner_id.doc_type or ''
		if tipo not in ('0', '4', '7', 'A', 'B', 'C', 'D', 'E', '-'):
			raise UserError(_(
				'El cliente «%(cliente)s» de la exportación tiene tipo de '
				'documento «%(tipo)s».\n\nEn una exportación el receptor debe '
				'identificarse con «0 - DOC.TRIB.NO.DOM.SIN.RUC», carné de '
				'extranjería (4) o pasaporte (7), según el catálogo 06 de '
				'SUNAT.\n\nSe corrige en la ficha del cliente, campo «Tipo de '
				'documento».',
				cliente=self.partner_id.display_name, tipo=tipo))

	# ------------------------------------------- 9 · unidad de medida

	def _val_unidad_de_medida(self):
		"""Unidad de medida del catálogo 3 en cada línea.

		Rechazo 2015. Sin unidad SUNAT no puede validar la cantidad.
		"""
		self.ensure_one()
		# M-9. Esto leía `producto.sunat_code`, y `sunat_code` NO vive en el
		# producto: está en `uom.uom` (solse_pe_edi/models/product.py:35-37).
		# O sea que la guarda `'sunat_code' not in producto._fields` era
		# SIEMPRE cierta y —con `return`, no `continue`— abortaba la
		# validación entera en la primera línea. La validación nunca se
		# ejecutó: el rechazo 2015 llegaba de SUNAT en vez de avisarse antes
		# de enviar.
		Unidad = self.env['uom.uom']
		if 'sunat_code' not in Unidad._fields:
			return
		for linea in self.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
			producto = linea.product_id
			if not producto:
				continue
			unidad = linea.product_uom_id or producto.uom_id
			if not unidad.sunat_code:
				raise UserError(_(
					'La unidad de medida «%(unidad)s», del producto '
					'«%(producto)s», no tiene código de SUNAT.\n\nEs '
					'obligatorio en cada línea (catálogo 3) y su ausencia se '
					'rechaza con el código 2015. Para servicios corresponde '
					'«ZZ - Unidad de servicio».\n\n'
					'Se corrige en la unidad de medida, no en el producto: '
					'Inventario › Configuración › Unidades de medida.',
					unidad=unidad.display_name,
					producto=producto.display_name))

	# ------------------------------------------ 10 · serie vs tipo de doc.

	def _val_serie_vs_tipo_documento(self):
		"""La serie del comprobante contra la del tipo de documento.

		Rechazo 2016. Una factura numerada con serie B —o una boleta con
		serie F— pasa el posteo y la rechaza SUNAT.
		"""
		self.ensure_one()
		numero = self.l10n_latam_document_number or ''
		if '-' not in numero:
			return
		serie = numero.split('-', 1)[0].strip().upper()
		codigo = self.pe_invoice_code or ''

		esperada = {'01': 'F', '03': 'B'}.get(codigo)
		if esperada and serie[:1] != esperada:
			raise UserError(_(
				'El comprobante es %(doc)s y su serie es «%(serie)s».\n\nLas '
				'series de %(doc)s empiezan con «%(esperada)s». SUNAT rechaza '
				'la combinación con el código 2016.\n\nSe corrige en el tipo '
				'de documento, campo «Prefijo».',
				doc=_('una factura') if codigo == '01' else _('una boleta'),
				serie=serie, esperada=esperada))

		tipo = self.l10n_latam_document_type_id
		if tipo.usar_prefijo_personalizado and tipo.prefijo:
			if serie != tipo.prefijo.strip().upper():
				raise UserError(_(
					'El tipo de documento «%(tipo)s» tiene configurada la '
					'serie «%(prefijo)s» pero el comprobante salió con la '
					'serie «%(serie)s».\n\nSuele ocurrir cuando se cambia el '
					'prefijo después de haber emitido: la secuencia sigue con '
					'la serie anterior.\n\nSe corrige en el tipo de documento '
					'o en su secuencia.',
					tipo=tipo.display_name, prefijo=tipo.prefijo, serie=serie))

	# --------------------------------------- 11 · NC sobre anticipos

	def _val_nc_sobre_factura_con_anticipos(self):
		"""NC que afecta una factura que dedujo anticipos.

		Es el escenario donde tres reglas de SUNAT son incompatibles
		entre si (decision-nc-con-anticipos.md de la biblia):

		  * 2062 exige PayableAmount positivo y distinto de cero;
		  * 3280 exige la suma SIN restar anticipos (el concepto ni
		    existe en la hoja de NC);
		  * 3286 prohibe que la NC supere el total del documento que
		    modifica — y ese total quedo en ~0 porque el anticipo lo
		    cubrio.

		El XML sale con el importe BRUTO (cumple 2062/3280, incumple
		3286). El motivo 10 «Otros conceptos» esta exento de 3286, y la
		via tributariamente limpia es emitir la NC sobre las facturas
		DE anticipo, no sobre la final.

		Por decision registrada (2026-09-13): el aviso ADVIERTE por
		defecto —nota en el chatter, no bloquea— y cada compania puede
		volverlo bloqueante con «La NC sobre factura con anticipos
		bloquea la emisión».
		"""
		self.ensure_one()
		if (self.pe_invoice_code or '') != '07':
			return
		if self.pe_credit_note_code == '10':
			return
		origen = self.reversed_entry_id
		if not origen:
			return

		def _es_deduccion(ln):
			if ln.display_type != 'product' or ln.price_subtotal >= 0:
				return False
			if 'is_downpayment' in ln._fields and ln.is_downpayment:
				return True
			texto = '%s %s' % (ln.name or '', ln.product_id.name or '')
			return bool(re.search(r'anticip|deducc', texto, re.IGNORECASE))

		if not origen.invoice_line_ids.filtered(_es_deduccion):
			return

		mensaje = _(
			'La nota de crédito afecta a %(doc)s, que dedujo anticipos.\n\n'
			'En este escenario las reglas de SUNAT son incompatibles entre '
			'sí: la nota debe declarar el importe BRUTO (reglas 2062 y '
			'3280), pero ese bruto supera el total del documento que '
			'modifica (regla 3286). El XML saldrá con el bruto; SUNAT '
			'puede observar la nota por la 3286.\n\n'
			'Las salidas:\n'
			'· La vía limpia: emitir la(s) nota(s) sobre las facturas DE '
			'anticipo, no sobre la factura final. Cada nota cabe en su '
			'documento y el motivo declarado es el real.\n'
			'· La excepción: motivo «10 — Otros conceptos», exento de la '
			'regla 3286 — a cambio, el motivo no describe la operación y '
			'habrá que explicarlo en una fiscalización.',
			doc=origen.name)

		if self.company_id.pe_nc_anticipo_bloquea:
			raise UserError(mensaje + _(
				'\n\nLa compañía tiene activado el bloqueo de este caso '
				'(Ajustes de la compañía → «La NC sobre factura con '
				'anticipos bloquea la emisión»).'))
		self.message_post(body=mensaje.replace('\n', '<br/>'))
		_logger.warning(
			'NC %s sobre factura con anticipos %s (motivo %s): se emite '
			'con importe bruto, 3286 puede observarla',
			self.name or self.id, origen.name, self.pe_credit_note_code)

	# --------------------------------------------------- 12 · plazo de envío
	def _val_plazo_de_envio(self):
		"""CPE-04/MEJ-48 · El plazo de envío de 3 días (R.S. 003-2023).

		Las facturas y sus notas se envían a SUNAT hasta 3 días
		calendario contados desde el día siguiente a la emisión; pasado
		el plazo el envío individual responde 2108 («comprobante fue
		enviado fuera de plazo»), que además ENMASCARA cualquier otro
		error del XML y quema reintentos del ciclo — por eso esta
		validación corre PRIMERA en la cadena. Las boletas y sus notas
		quedan fuera: viajan por resumen diario, con otro régimen.

		`pe_validar_plazo_envio` (compañía) la apaga: el laboratorio
		siembra ejercicios pasados completos —beta no aplica el 2108—
		y una migración de históricos tampoco debe tropezar aquí.
		"""
		self.ensure_one()
		if not self.company_id.pe_validar_plazo_envio:
			return
		codigo = self.l10n_latam_document_type_id.code
		if codigo not in ('01', '07', '08'):
			return
		# Serie B: boleta o nota sobre boleta → resumen diario, sin 2108.
		serie = (self.name or '').split('-')[0]
		if serie[:1].upper() == 'B':
			return
		fecha = self.invoice_date or fields.Date.context_today(self)
		limite = fecha + timedelta(days=3)
		hoy = fields.Date.context_today(self)
		if hoy <= limite:
			return
		raise UserError(_(
			'%(doc)s: la fecha de emisión es %(fecha)s y el plazo de envío '
			'a SUNAT venció el %(limite)s (3 días calendario desde el día '
			'siguiente a la emisión, R.S. 003-2023/SUNAT). El envío '
			'individual respondería 2108 «comprobante enviado fuera de '
			'plazo», que además oculta cualquier otro error del XML y '
			'consume reintentos.\n\n'
			'Salidas: emitir el comprobante con fecha vigente (si el '
			'período contable lo permite), o revisar con el contador el '
			'tratamiento del documento vencido. Si esta compañía carga '
			'históricos a propósito, la validación se apaga en su ficha '
			'(«Validar plazo de envío de 3 días»).',
			doc=self.name or self.ref or 'Comprobante',
			fecha=fecha, limite=limite))
