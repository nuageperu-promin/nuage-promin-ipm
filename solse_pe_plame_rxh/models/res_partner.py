# -*- coding: utf-8 -*-

from odoo import _, api, fields, models

from .catalogos_plame import (
	TABLA_3_TIPO_DOCUMENTO,
	TABLA_25_CONVENIO,
	normalizar_texto,
	quitar_tildes,
)

# Partículas que forman parte del apellido y no deben tratarse como
# palabras independientes al separar un nombre completo.
PARTICULAS_APELLIDO = (
	'DE', 'DEL', 'DE LA', 'DE LOS', 'DE LAS', 'LA', 'LAS', 'LOS',
	'VDA', 'VDA.', 'SAN', 'SANTA', 'MC', 'VAN', 'VON', 'DA', 'DI',
)


class ResPartner(models.Model):
	_inherit = 'res.partner'

	plame_apellido_paterno = fields.Char(
		string='Apellido paterno',
		size=40,
		help="Campo 3 del archivo .ps4 del PDT PLAME.",
	)
	plame_apellido_materno = fields.Char(
		string='Apellido materno',
		size=40,
		help="Campo 4 del archivo .ps4 del PDT PLAME.",
	)
	plame_nombres = fields.Char(
		string='Nombres',
		size=40,
		help="Campo 5 del archivo .ps4 del PDT PLAME.",
	)
	plame_domiciliado = fields.Boolean(
		string='Domiciliado (LIR)',
		default=True,
		help="Condición de domiciliado según la Ley del Impuesto a la Renta. "
		     "Corresponde al campo 6 del archivo .ps4.",
	)
	plame_tipo_documento = fields.Selection(
		selection=TABLA_3_TIPO_DOCUMENTO,
		string='Tipo de documento PLAME',
		compute='_calcular_tipo_documento_plame',
		store=True,
		readonly=False,
		help="Tabla 3 del Anexo 2 de la Planilla Electrónica. Los prestadores "
		     "domiciliados se informan con RUC (06).",
	)
	plame_convenio_dt = fields.Selection(
		selection=TABLA_25_CONVENIO,
		string='Convenio doble tributación',
		default='0',
		help="Tabla 25 del Anexo 2. Solo aplica a prestadores no "
		     "domiciliados; en el resto de casos se informa 0 (Ninguno).",
	)
	plame_suspension_ids = fields.One2many(
		'plame.suspension.cuarta',
		'partner_id',
		string='Constancias de suspensión 4ta',
	)
	plame_datos_completos = fields.Boolean(
		string='Datos PLAME completos',
		compute='_calcular_datos_completos_plame',
		store=True,
		help="Indica si el prestador tiene todos los datos que exige el "
		     "archivo .ps4.",
	)

	@api.depends('vat', 'plame_domiciliado')
	def _calcular_tipo_documento_plame(self):
		for registro in self:
			# Un valor definido a mano no se sobrescribe, pero igual debe
			# reasignarse: un compute almacenado tiene que dejar el campo
			# escrito en cada iteración.
			valor = registro.plame_tipo_documento
			if not valor:
				numero = (registro.vat or '').strip()
				if registro.plame_domiciliado and len(numero) == 11 and numero.isdigit():
					valor = '06'
				else:
					valor = False
			registro.plame_tipo_documento = valor

	@api.depends(
		'plame_apellido_paterno', 'plame_apellido_materno', 'plame_nombres',
		'plame_tipo_documento', 'vat',
	)
	def _calcular_datos_completos_plame(self):
		for registro in self:
			registro.plame_datos_completos = bool(
				registro.vat
				and registro.plame_tipo_documento
				and registro.plame_apellido_paterno
				and registro.plame_nombres
			)

	def separar_nombre_completo(self):
		"""Intenta poblar apellidos y nombres a partir del campo `name`.

		Es una heurística de apoyo para la carga inicial: asume el orden
		peruano APELLIDO_PATERNO APELLIDO_MATERNO NOMBRES y respeta las
		partículas compuestas. Los valores deben revisarse a mano antes de
		usarse en una declaración.
		"""
		for registro in self:
			if not registro.name:
				continue
			palabras = normalizar_texto(registro.name).split(' ')
			palabras = [palabra for palabra in palabras if palabra]
			if len(palabras) < 2:
				continue

			apellidos = []
			indice = 0
			while indice < len(palabras) and len(apellidos) < 2:
				palabra = palabras[indice]
				if palabra in PARTICULAS_APELLIDO and indice + 1 < len(palabras):
					compuesto = [palabra]
					indice += 1
					while (indice < len(palabras)
					       and palabras[indice] in PARTICULAS_APELLIDO
					       and indice + 1 < len(palabras)):
						compuesto.append(palabras[indice])
						indice += 1
					compuesto.append(palabras[indice])
					apellidos.append(' '.join(compuesto))
				else:
					apellidos.append(palabra)
				indice += 1

			nombres = ' '.join(palabras[indice:])
			registro.plame_apellido_paterno = apellidos[0] if apellidos else False
			registro.plame_apellido_materno = apellidos[1] if len(apellidos) > 1 else False
			registro.plame_nombres = nombres or False
		return True

	def tiene_suspension_vigente(self, fecha):
		"""Indica si el prestador tiene constancia de suspensión en la fecha."""
		self.ensure_one()
		return self.plame_suspension_ids.esta_vigente_en(fecha)

	def obtener_documento_plame(self):
		"""Devuelve (tipo_documento, numero) listos para el archivo."""
		self.ensure_one()
		numero = quitar_tildes(self.vat or '').strip().upper()
		return self.plame_tipo_documento or '', numero

	def action_separar_nombre_completo(self):
		"""Acción de la vista: separa el nombre y avisa que hay que revisar."""
		self.separar_nombre_completo()
		return {
			'type': 'ir.actions.client',
			'tag': 'display_notification',
			'params': {
				'type': 'warning',
				'title': _("Nombres separados automáticamente"),
				'message': _("La separación es una estimación a partir del "
				             "nombre completo. Revise los tres campos antes "
				             "de generar una declaración."),
				'sticky': False,
			},
		}
