# -*- coding: utf-8 -*-

import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


# Catálogo 61 SUNAT - tipos de documento que requieren consignar
# el emisor (RUC). Cumple con ERR-3380, ERR-3382 y ERR-3614 (01/06/2026).
TIPOS_DOCUMENTO_CON_EMISOR_RUC = ('01', '03', '04', '09', '12', '48', '92')

# Patrones de validación cliente-side (subset de ERR-3441).
# La validación completa la hace SUNAT; aquí bloqueamos casos obvios.
PATRONES_NUMERO_DOCUMENTO = {
	'01': r'^[F][A-Z0-9]{3}-\d{1,8}$|^E001-\d{1,8}$|^\d{1,4}-\d{1,8}$',
	'03': r'^[B][A-Z0-9]{3}-\d{1,8}$|^EB01-\d{1,8}$|^\d{1,4}-\d{1,8}$',
	'04': r'^[L][A-Z0-9]{3}-\d{1,8}$|^E001-\d{1,8}$|^\d{1,4}-\d{1,8}$',
	'09': r'^[T][A-Z0-9]{3}-\d{1,8}$|^EG07-\d{1,8}$|^EG02-\d{1,8}$',
	'48': r'^\d{1,4}-\d{1,7}$',
	'49': r'^\d{1,15}$',
	'80': r'^\d{1,15}$',
	'92': r'^\d{1,50}$',
}


class PeStockDocumentoRelacionado(models.Model):
	_name = 'pe.stock.documento.relacionado'
	_description = 'Documento Relacionado a Guía Electrónica de Remisión'
	_order = 'sequence, id'

	picking_id = fields.Many2one(
		comodel_name='stock.picking',
		string='Guía',
		required=True,
		ondelete='cascade',
		index=True,
	)
	sequence = fields.Integer(string='Secuencia', default=10)

	codigo_documento = fields.Selection(
		selection='_get_codigo_documento',
		string='Tipo de documento',
		required=True,
		help="Catálogo 61 SUNAT - Tipo de documento relacionado a la guía."
	)
	numero_documento = fields.Char(
		string='Número de documento',
		required=True,
		size=100,
	)

	emisor_id = fields.Many2one(
		comodel_name='res.partner',
		string='Emisor del documento',
		help="RUC del emisor del documento relacionado. Obligatorio para los "
			 "tipos 01, 03, 04, 09, 12, 48 y 92 según ERR-3380/3382/3614.",
		domain="[('doc_type', '=', '6')]",
	)
	emisor_requerido = fields.Boolean(
		compute='_compute_emisor_requerido',
		help="Verdadero cuando el tipo de documento exige RUC del emisor.",
	)

	@api.model
	def _get_codigo_documento(self):
		# Catálogo 61 SUNAT - cargado por hooks.py al instalar el módulo.
		return self.env['pe.datas'].get_selection('PE.CPE.CATALOG61')

	@api.depends('codigo_documento')
	def _compute_emisor_requerido(self):
		for registro in self:
			registro.emisor_requerido = (
				registro.codigo_documento in TIPOS_DOCUMENTO_CON_EMISOR_RUC
			)

	@api.constrains('codigo_documento', 'emisor_id')
	def _validar_emisor_requerido(self):
		# Cumple ERR-3380 / ERR-3382 / ERR-3614 (SUNAT 01/06/2026)
		for registro in self:
			if registro.codigo_documento not in TIPOS_DOCUMENTO_CON_EMISOR_RUC:
				continue
			if not registro.emisor_id:
				raise ValidationError(_(
					"El emisor (RUC) es obligatorio para documentos "
					"relacionados de tipo %s."
				) % registro.codigo_documento)
			if registro.emisor_id.doc_type != '6':
				raise ValidationError(_(
					"El emisor del documento relacionado tipo %s debe tener "
					"RUC (tipo de documento 6)."
				) % registro.codigo_documento)
			if not registro.emisor_id.doc_number:
				raise ValidationError(_(
					"El emisor %s no tiene número de RUC registrado."
				) % registro.emisor_id.name)

	@api.constrains('codigo_documento', 'numero_documento')
	def _validar_formato_numero(self):
		# Validación cliente-side parcial de ERR-3441.
		for registro in self:
			patron = PATRONES_NUMERO_DOCUMENTO.get(registro.codigo_documento)
			if not patron or not registro.numero_documento:
				continue
			if not re.match(patron, registro.numero_documento.strip()):
				raise ValidationError(_(
					"El número de documento '%s' no cumple con el formato "
					"esperado para el tipo %s."
				) % (registro.numero_documento, registro.codigo_documento))
