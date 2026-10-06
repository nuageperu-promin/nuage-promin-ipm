# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class Partner(models.Model):
	_inherit = 'res.partner'

	pe_driver_license = fields.Char("Licencia de conducir")
	doc_name = fields.Char(string="Tipo doc.",related="l10n_latam_identification_type_id.name")
	pe_mtc_number = fields.Char(
		string="Número de Registro MTC",
		help="Número de Registro otorgado por el Ministerio de Transportes y "
			 "Comunicaciones al transportista. Se envía en "
			 "cac:CarrierParty/cac:PartyLegalEntity/cbc:CompanyID de la "
			 "GRE - Remitente para modalidad 01-Público (OBS-4391).\n"
			 "Formato: hasta 20 caracteres, solo letras mayúsculas y números."
	)
