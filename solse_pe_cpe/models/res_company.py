# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class Company(models.Model):
	_inherit = "res.company"

	validacion_estricta_cpe = fields.Boolean(
		string='Validación estricta de comprobantes',
		default=True,
		help='Revisa el comprobante ANTES de generar el XML y avisa de lo '
			 'que SUNAT rechazaría, diciendo qué campo corregir y dónde.\n\n'
			 'Cubre la coherencia entre el tipo de afectación y el tipo de '
			 'operación, los datos de la detracción, la identificación del '
			 'receptor, la referencia de las notas, el tipo de cambio, el '
			 'cuadre de las líneas con el total, las operaciones gratuitas, '
			 'el receptor no domiciliado, la unidad de medida y la serie.\n\n'
			 'Sin esta opción, esos errores se descubren cuando SUNAT '
			 'devuelve el rechazo: el correlativo ya se consumió y hay que '
			 'emitir una nota o volver a enviar.\n\n'
			 'En instalaciones nuevas viene activada. Al actualizar una base '
			 'existente nace desactivada, para que se pueda revisar el '
			 'histórico antes de exigir el cumplimiento.')

	pe_validar_plazo_envio = fields.Boolean(
		string='Validar plazo de envío de 3 días',
		default=True,
		help='R.S. 003-2023/SUNAT: las facturas y sus notas se envían '
			 'hasta 3 días calendario contados desde el día siguiente a '
			 'la emisión; después, el envío individual responde 2108 '
			 '(«comprobante enviado fuera de plazo»), que oculta '
			 'cualquier otro error del XML y consume reintentos. Con '
			 'esta opción activa, la validación estricta detiene la '
			 'emisión de un comprobante ya vencido y explica las '
			 'salidas. Apagar solo en compañías que cargan históricos a '
			 'propósito (el laboratorio de demostración lo hace solo).')

	pe_nc_anticipo_bloquea = fields.Boolean(
		string='La NC sobre factura con anticipos bloquea la emisión',
		default=False,
		help='Una nota de crédito sobre una factura que dedujo anticipos '
			 'cae en un hueco de la normativa: SUNAT exige declarar el '
			 'importe bruto (reglas 2062 y 3280) y a la vez prohíbe que '
			 'la nota supere el total del documento modificado (regla '
			 '3286), que quedó en cero por el anticipo. No existe un XML '
			 'que cumpla las tres.\n\n'
			 'Desactivado (por defecto): el sistema ADVIERTE en el '
			 'chatter del comprobante y deja emitir con el importe bruto.\n'
			 'Activado: la emisión se BLOQUEA y el mensaje explica las '
			 'dos salidas — la nota sobre las facturas de anticipo (la '
			 'vía limpia) o el motivo 10 «Otros conceptos» (exento de la '
			 '3286).\n\n'
			 'Requiere la validación estricta de comprobantes activa.')

	pe_is_sync = fields.Boolean("Es sincrono", default=True)
	pe_certificate_id = fields.Many2one(comodel_name="cpe.certificate", string="Certificado", domain="[('state','=','done')]")
	pe_cpe_server_id = fields.Many2one(comodel_name="cpe.server", string="Servidor", domain="[('state','=','done')]")
	enviar_email = fields.Boolean('Envio correo automatico', help="Si esta activo cada vez que se confirme un comprobante se enviara el pdf al cliente")

	# ------------------------------------------------------------------
	# L-6 · Las secuencias de comprobantes electrónicos son POR COMPAÑÍA
	#
	# Decisión de Gabriel (2026-09-22): en esta suite **no hay secuencias
	# globales** para nada que tenga que ver con comprobantes electrónicos
	# ni con asientos contables. Cada empresa lleva su correlativo.
	#
	# El problema que corrige: una `ir.sequence` cargada desde `data/` sin
	# `company_id` NO queda global — el campo toma por defecto la compañía
	# que instala—, así que `next_by_code` desde una segunda empresa no la
	# encuentra y el proceso falla. Es la trampa 22 de
	# `migrar-modulo-v17-a-v19.md`, y le costó una corrida al módulo de
	# liquidación de compra.
	#
	# Aditivo a propósito: los registros de `data/` se quedan donde están
	# —son la secuencia de la compañía que instaló— y esto crea las que
	# falten. Ningún correlativo en marcha se toca.
	# ------------------------------------------------------------------
	def pe_asegurar_secuencia(self, codigo, nombre, **valores):
		"""Devuelve la `ir.sequence` de `codigo` para esta compañía,
		creándola si no existe. Nunca devuelve la de otra empresa.

		L-6b (corrida 2 de MULTIEMPRESA, 2026-09-23): crear sin formato
		no basta — la secuencia de guías rendía «1» y la numeración
		cortaba en la regex `T###-N`; RA/RC rendían un entero pelado
		cuando el archivo exige `RC-AAAAMMDD-N`. Cada módulo pasa ahora
		su `prefix`/`padding` (los del `data/`), y si la secuencia de la
		compañía YA existe pero le falta el prefijo, se le pone: el
		correlativo NO se toca (`number_next` intacto — son números que
		pudieron viajar a SUNAT), solo el vestido.
		"""
		self.ensure_one()
		Secuencia = self.env['ir.sequence'].sudo()
		existente = Secuencia.search([
			('code', '=', codigo), ('company_id', '=', self.id)], limit=1)
		if existente:
			reparar = {}
			if valores.get('prefix') and not existente.prefix:
				reparar['prefix'] = valores['prefix']
				if valores.get('padding') and not existente.padding:
					reparar['padding'] = valores['padding']
			if reparar:
				existente.write(reparar)
				_logger.info(
					'CPE: la secuencia «%s» de «%s» no tenía formato; se '
					'le puso prefijo «%s» sin tocar su correlativo.',
					codigo, self.display_name, reparar['prefix'])
			return existente
		# Una secuencia del mismo código SIN compañía sería global, y en
		# esta suite eso no se admite: se le asigna esta empresa en vez de
		# crear una segunda que competiría con ella.
		huerfana = Secuencia.search([
			('code', '=', codigo), ('company_id', '=', False)], limit=1)
		if huerfana:
			huerfana.company_id = self.id
			_logger.warning(
				'CPE: la secuencia «%s» no tenía compañía y se ha asignado a '
				'«%s». Revisar si otra empresa la estaba usando.',
				codigo, self.display_name)
			return huerfana
		datos = {'name': '%s - %s' % (nombre, self.name),
				 'code': codigo, 'company_id': self.id,
				 'implementation': 'no_gap', 'padding': 0}
		datos.update(valores)
		return Secuencia.create(datos)

	@api.model
	def pe_asegurar_secuencias_cpe_todas(self):
		"""Todas las compañías. Es la que invoca el `<function>` del data.

		Separada de la de registro a propósito: un `<function>` sin
		argumentos exige `@api.model`, y mezclar los dos usos en un mismo
		método es la trampa 17.
		"""
		self.env['res.company'].sudo().search([]).pe_asegurar_secuencias_cpe()

	def pe_asegurar_secuencias_cpe(self):
		"""Las secuencias que necesita el CPE en cada compañía peruana.

		Con el formato del `data/` (L-6b): el nombre del archivo del
		resumen es RUC-RA/RC-AAAAMMDD-N (Manual del programador), y ese
		AAAAMMDD sale del prefijo con `ir_sequence_date`."""
		for compania in self._pe_companias_con_cpe():
			compania.pe_asegurar_secuencia(
				'pe.sunat.cpe.ra', 'Resumen de Anulaciones RA',
				prefix='RA-%(year)s%(month)s%(day)s-', padding=5)
			compania.pe_asegurar_secuencia(
				'pe.sunat.cpe.rc', 'Resumen de Boletas RC',
				prefix='RC-%(year)s%(month)s%(day)s-', padding=5)

	def _pe_companias_con_cpe(self):
		"""Las compañías sobre las que tiene sentido crear secuencias de
		comprobantes: las peruanas, o todas si no se puede saber."""
		companias = self or self.env['res.company'].sudo().search([])
		pe_id = self.env.ref('base.pe', raise_if_not_found=False)
		if not pe_id:
			return companias
		peruanas = companias.filtered(lambda c: c.country_id == pe_id)
		return peruanas or companias

	@api.model_create_multi
	def create(self, vals_list):
		"""Una empresa nueva nace con sus secuencias, no con las de otra."""
		companias = super().create(vals_list)
		try:
			companias.pe_asegurar_secuencias_cpe()
		except Exception as error:				# noqa: BLE001
			_logger.warning('CPE: no se pudieron crear las secuencias de la '
							'compañía nueva: %s', error)
		return companias


	

class Partner(models.Model):
	_inherit = "res.partner"

	@staticmethod
	def validate_ruc(vat):
		return True
		factor = '5432765432'
		sum = 0
		dig_check = False
		if len(vat) != 11:
			return False
		try:
			int(vat)
		except ValueError:
			return False
		for f in range(0, 10):
			sum += int(factor[f]) * int(vat[f])
		subtraction = 11 - (sum % 11)
		if subtraction == 10:
			dig_check = 0
		elif subtraction == 11:
			dig_check = 1
		else:
			dig_check = subtraction
		if not int(vat[10]) == dig_check:
			return False
		return True
