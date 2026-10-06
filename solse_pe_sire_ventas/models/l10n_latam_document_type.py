# -*- coding: utf-8 -*-

from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError
import logging
_logging = logging.getLogger(__name__)

class L10nLatamDocumentType(models.Model):
	_inherit = 'l10n_latam.document.type'

	inc_sire_compras = fields.Boolean("Incluir en Sire de Compras")
	inc_sire_ventas = fields.Boolean("Incluir en Sire de Ventas")

	