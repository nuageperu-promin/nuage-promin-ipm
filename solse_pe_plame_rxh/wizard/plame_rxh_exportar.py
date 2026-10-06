# -*- coding: utf-8 -*-

import base64
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.catalogos_plame import (
	FIN_DE_LINEA,
	TABLA_23_TIPO_COMPROBANTE,
	UMBRAL_RETENCION_CUARTA,
	armar_linea,
	formato_fecha,
	formato_monto,
	normalizar_texto,
)

MESES = [
	('01', 'Enero'), ('02', 'Febrero'), ('03', 'Marzo'), ('04', 'Abril'),
	('05', 'Mayo'), ('06', 'Junio'), ('07', 'Julio'), ('08', 'Agosto'),
	('09', 'Setiembre'), ('10', 'Octubre'), ('11', 'Noviembre'),
	('12', 'Diciembre'),
]

# Longitudes máximas de la Estructura 20.
LONGITUD_SERIE = 4
LONGITUD_NUMERO = 8
LONGITUD_DOCUMENTO = 15


class PlameRxhExportar(models.TransientModel):
	_name = 'plame.rxh.exportar'
	_description = 'Exportar recibos por honorarios al PDT PLAME'

	company_id = fields.Many2one(
		'res.company',
		string='Compañía',
		required=True,
		default=lambda self: self.env.company,
	)
	ejercicio = fields.Char(
		string='Ejercicio',
		required=True,
		size=4,
		default=lambda self: str(fields.Date.context_today(self).year),
	)
	mes = fields.Selection(
		selection=MESES,
		string='Mes',
		required=True,
		default=lambda self: '%02d' % fields.Date.context_today(self).month,
	)
	fecha_inicio = fields.Date(
		string='Desde',
		compute='_calcular_rango_periodo',
	)
	fecha_fin = fields.Date(
		string='Hasta',
		compute='_calcular_rango_periodo',
	)

	estado = fields.Selection(
		selection=[('config', 'Configuración'), ('listo', 'Archivos generados')],
		string='Estado',
		default='config',
	)
	hay_errores = fields.Boolean(string='Hay errores', default=False)
	resumen = fields.Text(string='Validaciones', readonly=True)

	linea_ids = fields.One2many(
		'plame.rxh.exportar.linea',
		'exportar_id',
		string='Comprobantes del periodo',
		readonly=True,
	)
	cantidad_prestadores = fields.Integer(string='Prestadores', readonly=True)
	cantidad_comprobantes = fields.Integer(string='Comprobantes', readonly=True)
	total_declarado = fields.Monetary(
		string='Total declarado',
		currency_field='currency_id',
		readonly=True,
	)
	currency_id = fields.Many2one(
		'res.currency',
		related='company_id.currency_id',
		readonly=True,
	)

	archivo_ps4 = fields.Binary(string='Archivo .ps4', readonly=True, attachment=False)
	nombre_ps4 = fields.Char(string='Nombre .ps4', readonly=True)
	archivo_4ta = fields.Binary(string='Archivo .4ta', readonly=True, attachment=False)
	nombre_4ta = fields.Char(string='Nombre .4ta', readonly=True)

	# ── Periodo ────────────────────────────────────────────────────────

	@api.depends('ejercicio', 'mes')
	def _calcular_rango_periodo(self):
		for asistente in self:
			try:
				anio = int(asistente.ejercicio)
				mes = int(asistente.mes)
				inicio = date(anio, mes, 1)
			except (TypeError, ValueError):
				asistente.fecha_inicio = False
				asistente.fecha_fin = False
				continue
			asistente.fecha_inicio = inicio
			asistente.fecha_fin = inicio + relativedelta(months=1, days=-1)

	# ── Recopilación ───────────────────────────────────────────────────

	def _buscar_comprobantes_candidatos(self):
		"""Comprobantes de honorarios que pudieron cancelarse en el periodo."""
		self.ensure_one()
		return self.env['account.move'].search([
			('company_id', '=', self.company_id.id),
			('state', '=', 'posted'),
			('move_type', 'in', ('in_invoice', 'in_refund')),
			('es_recibo_honorarios', '=', True),
			('invoice_date', '<=', self.fecha_fin),
			# Sin filtro por `payment_state`: desde Odoo 18 un pago cuyo
			# método no tiene cuenta *outstanding* no genera asiento ni
			# concilia (`account/models/account_payment.py:997`), y el
			# `payment_state` ALMACENADO del comprobante puede quedarse en
			# «not_paid» aunque el pago exista —depende de
			# `amount_residual` y `reconciled_payment_ids.state`—. Con ese
			# filtro, esos recibos no entraban al PLAME. El importe y la
			# fecha de pago los decide después `obtener_pagos_plame`, que
			# es la fuente de verdad del criterio de percepción.
		], order='partner_id, invoice_date, id')

	def _recopilar_datos_periodo(self):
		"""Arma la lista de diccionarios con un registro por comprobante."""
		self.ensure_one()
		datos = []
		for documento in self._buscar_comprobantes_candidatos():
			if documento.move_type == 'in_refund':
				registro = self._preparar_nota_credito(documento)
			else:
				registro = self._preparar_recibo(documento)
			if registro:
				datos.append(registro)
		return datos

	def _preparar_recibo(self, documento):
		"""Prepara el registro de un recibo por honorarios pagado en el mes."""
		importe_pagado, fecha_pago = documento.obtener_pagos_plame(
			self.fecha_inicio, self.fecha_fin
		)
		moneda = documento.currency_id
		if not fecha_pago or moneda.is_zero(importe_pagado):
			return False

		bruto_documento = documento.obtener_monto_bruto_plame()
		total_documento = abs(documento.amount_total)
		# Si el pago del periodo no cancela el total, se declara la parte
		# proporcional del importe bruto. Con pago total se usa el bruto
		# exacto para evitar arrastrar diferencias de redondeo.
		if total_documento and moneda.compare_amounts(importe_pagado, total_documento) != 0:
			bruto_periodo = bruto_documento * (importe_pagado / total_documento)
		else:
			bruto_periodo = bruto_documento

		return self._armar_registro(documento, bruto_periodo, fecha_pago)

	def _preparar_nota_credito(self, documento):
		"""Prepara el registro de una nota de crédito de honorarios.

		Criterio contable acordado: la nota de crédito se declara con la
		fecha de pago del recibo que la origina y con el importe en
		positivo, porque el PDT aplica la disminución por sí mismo.
		"""
		fecha_pago = documento.obtener_fecha_pago_origen_plame()
		if not fecha_pago:
			# Sin recibo origen identificable se usa su propia conciliación.
			_importe, fecha_pago = documento.obtener_pagos_plame(
				self.fecha_inicio, self.fecha_fin
			)
		if not fecha_pago:
			return False
		# Una nota de crédito emitida DESPUÉS del pago del recibo que
		# corrige —lo normal cuando se anula parte de algo ya pagado—
		# quedaba con fecha de pago anterior a su emisión, y el PDT
		# rechaza ese caso (lo detecta `_validar_datos`). Se declara
		# entonces con su propia fecha de emisión, que es cuando la
		# disminución existe. Criterio adoptado el 2026-09-20 sobre el
		# original de la v17; anotado como C-3 para el contador.
		if documento.invoice_date and fecha_pago < documento.invoice_date:
			fecha_pago = documento.invoice_date
		if fecha_pago < self.fecha_inicio or fecha_pago > self.fecha_fin:
			return False
		return self._armar_registro(
			documento, documento.obtener_monto_bruto_plame(), fecha_pago
		)

	def _armar_registro(self, documento, bruto_moneda, fecha_pago):
		"""Convierte el comprobante en el diccionario que alimenta el archivo."""
		prestador = documento.partner_id.commercial_partner_id
		serie, numero = documento.obtener_serie_numero_plame()
		tipo_documento, numero_documento = prestador.obtener_documento_plame()
		monto_soles = documento.convertir_a_soles_plame(bruto_moneda, fecha_pago)

		return {
			'documento': documento,
			'prestador': prestador,
			'tipo_documento': tipo_documento,
			'numero_documento': numero_documento,
			'tipo_comprobante': documento.obtener_tipo_comprobante_plame(),
			'serie': serie,
			'numero': numero,
			'monto': monto_soles,
			'monto_moneda': bruto_moneda,
			'fecha_emision': documento.invoice_date,
			'fecha_pago': fecha_pago,
			'retencion': documento.tiene_retencion_cuarta(),
		}

	# ── Validación ─────────────────────────────────────────────────────

	def _validar_datos(self, datos):
		"""Devuelve (errores, advertencias) como listas de texto."""
		self.ensure_one()
		errores = []
		advertencias = []
		compania = self.company_id

		if not compania.vat:
			errores.append(_("La compañía %s no tiene RUC configurado.") % compania.name)

		prestadores_revisados = set()
		for registro in datos:
			documento = registro['documento']
			prestador = registro['prestador']
			etiqueta = documento.name or documento.ref or str(documento.id)

			if prestador.id not in prestadores_revisados:
				prestadores_revisados.add(prestador.id)
				errores += self._validar_prestador(prestador)

			if not registro['serie'] or not registro['numero']:
				errores.append(_(
					"%s: no se pudo determinar la serie y el número. Se esperaba "
					"un formato tipo E001-75 en el número de documento o en la "
					"referencia."
				) % etiqueta)
			else:
				if len(registro['serie']) > LONGITUD_SERIE:
					errores.append(_("%s: la serie %s supera %s caracteres.") % (
						etiqueta, registro['serie'], LONGITUD_SERIE))
				if len(registro['numero']) > LONGITUD_NUMERO:
					errores.append(_("%s: el número %s supera %s caracteres.") % (
						etiqueta, registro['numero'], LONGITUD_NUMERO))

			if not registro['fecha_emision']:
				errores.append(_("%s: no tiene fecha de emisión.") % etiqueta)
			elif registro['fecha_pago'] < registro['fecha_emision']:
				errores.append(_(
					"%s: la fecha de pago (%s) es anterior a la de emisión (%s). "
					"El PDT rechaza este caso."
				) % (etiqueta, formato_fecha(registro['fecha_pago']),
				     formato_fecha(registro['fecha_emision'])))

			if registro['monto'] <= 0:
				errores.append(_("%s: el monto a declarar es cero o negativo.") % etiqueta)

			if documento.currency_id != compania.currency_id:
				if not self._existe_tipo_cambio(documento.currency_id, registro['fecha_pago']):
					errores.append(_(
						"%s: no hay tipo de cambio compra registrado para %s al %s."
					) % (etiqueta, documento.currency_id.name,
					     formato_fecha(registro['fecha_pago'])))

			advertencias += self._validar_retencion(registro, etiqueta)

			if (compania.plame_dias_tolerancia_emision
			        and registro['fecha_emision']
			        and (registro['fecha_pago'] - registro['fecha_emision']).days
			            > compania.plame_dias_tolerancia_emision):
				advertencias.append(_(
					"%s: se emitió el %s y se paga el %s, más de %s días después."
				) % (etiqueta, formato_fecha(registro['fecha_emision']),
				     formato_fecha(registro['fecha_pago']),
				     compania.plame_dias_tolerancia_emision))

		return errores, advertencias

	def _validar_prestador(self, prestador):
		"""Comprueba que el prestador tenga lo que exige el archivo .ps4."""
		errores = []
		if not prestador.vat:
			errores.append(_("%s: no tiene número de documento registrado.") % prestador.name)
		elif len(prestador.vat.strip()) > LONGITUD_DOCUMENTO:
			errores.append(_("%s: el número de documento supera %s caracteres.") % (
				prestador.name, LONGITUD_DOCUMENTO))
		elif prestador.plame_tipo_documento == '06' and len(prestador.vat.strip()) > 11:
			errores.append(_("%s: el RUC no puede tener más de 11 dígitos.") % prestador.name)

		if not prestador.plame_tipo_documento:
			errores.append(_(
				"%s: falta el tipo de documento PLAME (Tabla 3) en la ficha "
				"del prestador."
			) % prestador.name)
		if not prestador.plame_apellido_paterno:
			errores.append(_("%s: falta el apellido paterno.") % prestador.name)
		if not prestador.plame_nombres:
			errores.append(_("%s: faltan los nombres.") % prestador.name)
		return errores

	def _validar_retencion(self, registro, etiqueta):
		"""Avisa cuando corresponde retener y no se está reteniendo."""
		if registro['tipo_comprobante'] != 'R' or registro['retencion']:
			return []
		if registro['monto'] <= UMBRAL_RETENCION_CUARTA:
			return []
		if registro['prestador'].tiene_suspension_vigente(registro['fecha_pago']):
			return []
		return [_(
			"%s: supera S/ %s, no tiene retención registrada y el prestador no "
			"tiene constancia de suspensión vigente al %s. Verifique antes de "
			"declarar."
		) % (etiqueta, formato_monto(UMBRAL_RETENCION_CUARTA),
		     formato_fecha(registro['fecha_pago']))]

	def _existe_tipo_cambio(self, moneda, fecha):
		"""Comprueba que exista una tasa registrada aplicable a la fecha."""
		self.ensure_one()
		Moneda = self.env['res.currency']
		moneda_compra = Moneda.search([
			('name', '=', moneda.name),
			('rate_type', '=', 'compra'),
		], limit=1)
		moneda_aplicable = moneda_compra or moneda
		return bool(self.env['res.currency.rate'].search_count([
			('currency_id', '=', moneda_aplicable.id),
			('name', '<=', fecha),
			('company_id', 'in', (False, self.company_id.id)),
		]))

	# ── Generación de los archivos ─────────────────────────────────────

	def _generar_contenido_ps4(self, datos):
		"""Arma el archivo maestro de prestadores (Estructura 7)."""
		prestadores = {}
		for registro in datos:
			prestadores.setdefault(registro['numero_documento'], registro)

		lineas = []
		for numero_documento in sorted(prestadores):
			registro = prestadores[numero_documento]
			prestador = registro['prestador']
			lineas.append(armar_linea([
				registro['tipo_documento'],
				numero_documento,
				normalizar_texto(prestador.plame_apellido_paterno, 40),
				normalizar_texto(prestador.plame_apellido_materno, 40),
				normalizar_texto(prestador.plame_nombres, 40),
				'1' if prestador.plame_domiciliado else '0',
				prestador.plame_convenio_dt or '0',
			]))
		return FIN_DE_LINEA.join(lineas) + FIN_DE_LINEA if lineas else ''

	def _generar_contenido_4ta(self, datos):
		"""Arma el archivo de detalle de comprobantes (Estructura 20)."""
		regimen = self.company_id.plame_regimen_pensionario or ''
		ordenados = sorted(
			datos,
			key=lambda registro: (
				registro['numero_documento'],
				registro['serie'] or '',
				int(registro['numero']) if (registro['numero'] or '').isdigit() else 0,
			),
		)
		lineas = []
		for registro in ordenados:
			lineas.append(armar_linea([
				registro['tipo_documento'],
				registro['numero_documento'],
				registro['tipo_comprobante'],
				registro['serie'],
				registro['numero'],
				formato_monto(registro['monto']),
				formato_fecha(registro['fecha_emision']),
				formato_fecha(registro['fecha_pago']),
				'1' if registro['retencion'] else '0',
				regimen,
				'',
			]))
		return FIN_DE_LINEA.join(lineas) + FIN_DE_LINEA if lineas else ''

	def _nombre_archivo(self, extension):
		"""Devuelve ffffaaaamm<RUC>.<extension>."""
		self.ensure_one()
		ruc = (self.company_id.vat or '').strip()
		return '0601%s%s%s.%s' % (self.ejercicio, self.mes, ruc, extension)

	def _codificar(self, contenido):
		"""Codifica el contenido tal como lo espera el PDT (ASCII)."""
		return base64.b64encode(contenido.encode('ascii', 'replace'))

	# ── Acciones ───────────────────────────────────────────────────────

	def _volver_al_asistente(self):
		self.ensure_one()
		return {
			'type': 'ir.actions.act_window',
			'name': _("Exportar recibos por honorarios al PLAME"),
			'res_model': self._name,
			'res_id': self.id,
			'view_mode': 'form',
			'target': 'new',
		}

	def action_revisar(self):
		"""Recopila y valida sin generar los archivos."""
		self.ensure_one()
		self._procesar(generar=False)
		return self._volver_al_asistente()

	def action_generar(self):
		"""Valida y, si no hay errores, genera ambos archivos."""
		self.ensure_one()
		self._procesar(generar=True)
		return self._volver_al_asistente()

	def _procesar(self, generar):
		self.ensure_one()
		if not self.fecha_inicio:
			raise UserError(_("El ejercicio indicado no es un año válido."))

		self.linea_ids.unlink()
		datos = self._recopilar_datos_periodo()
		if not datos:
			self.write({
				'estado': 'config',
				'hay_errores': False,
				'resumen': _(
					"No se encontraron recibos por honorarios pagados entre el "
					"%s y el %s."
				) % (formato_fecha(self.fecha_inicio), formato_fecha(self.fecha_fin)),
				'linea_ids': False,
				'cantidad_prestadores': 0,
				'cantidad_comprobantes': 0,
				'total_declarado': 0.0,
				'archivo_ps4': False,
				'archivo_4ta': False,
			})
			return

		errores, advertencias = self._validar_datos(datos)
		valores = {
			'linea_ids': [(0, 0, self._preparar_linea_vista(registro)) for registro in datos],
			'cantidad_prestadores': len({registro['numero_documento'] for registro in datos}),
			'cantidad_comprobantes': len(datos),
			'total_declarado': sum(registro['monto'] for registro in datos),
			'hay_errores': bool(errores),
			'resumen': self._formatear_resumen(errores, advertencias),
		}

		if errores or not generar:
			valores.update({
				'estado': 'config',
				'archivo_ps4': False,
				'archivo_4ta': False,
				'nombre_ps4': False,
				'nombre_4ta': False,
			})
		else:
			valores.update({
				'estado': 'listo',
				'archivo_ps4': self._codificar(self._generar_contenido_ps4(datos)),
				'nombre_ps4': self._nombre_archivo('ps4'),
				'archivo_4ta': self._codificar(self._generar_contenido_4ta(datos)),
				'nombre_4ta': self._nombre_archivo('4ta'),
			})
		self.write(valores)

	def _preparar_linea_vista(self, registro):
		return {
			'move_id': registro['documento'].id,
			'partner_id': registro['prestador'].id,
			'numero_documento': registro['numero_documento'],
			'tipo_comprobante': registro['tipo_comprobante'],
			'serie': registro['serie'] or '',
			'numero': registro['numero'] or '',
			'monto': registro['monto'],
			'fecha_emision': registro['fecha_emision'],
			'fecha_pago': registro['fecha_pago'],
			'retencion': registro['retencion'],
		}

	def _formatear_resumen(self, errores, advertencias):
		bloques = []
		if errores:
			bloques.append(_("ERRORES (%s) — impiden generar los archivos:") % len(errores))
			bloques += ['  • %s' % texto for texto in errores]
		if advertencias:
			if bloques:
				bloques.append('')
			bloques.append(_("ADVERTENCIAS (%s) — revise antes de declarar:") % len(advertencias))
			bloques += ['  • %s' % texto for texto in advertencias]
		if not bloques:
			bloques.append(_("Sin observaciones. Los datos del periodo están completos."))
		return '\n'.join(bloques)


class PlameRxhExportarLinea(models.TransientModel):
	_name = 'plame.rxh.exportar.linea'
	_description = 'Detalle de comprobantes a exportar al PLAME'
	_order = 'numero_documento, serie, numero'

	exportar_id = fields.Many2one(
		'plame.rxh.exportar',
		string='Exportación',
		required=True,
		ondelete='cascade',
	)
	move_id = fields.Many2one('account.move', string='Comprobante', readonly=True)
	partner_id = fields.Many2one('res.partner', string='Prestador', readonly=True)
	numero_documento = fields.Char(string='N° documento', readonly=True)
	tipo_comprobante = fields.Selection(
		selection=TABLA_23_TIPO_COMPROBANTE,
		string='Tipo',
		readonly=True,
	)
	serie = fields.Char(string='Serie', readonly=True)
	numero = fields.Char(string='Número', readonly=True)
	monto = fields.Float(string='Monto S/', digits=(16, 2), readonly=True)
	fecha_emision = fields.Date(string='Emisión', readonly=True)
	fecha_pago = fields.Date(string='Pago', readonly=True)
	retencion = fields.Boolean(string='Retención 4ta', readonly=True)
