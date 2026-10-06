# -*- coding: utf-8 -*-

from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError
import logging
_logging = logging.getLogger(__name__)

class L10nLatamDocumentType(models.Model):
	_inherit = 'l10n_latam.document.type'

	inc_ple_compras = fields.Boolean("Incluir en PLE de Compras")
	inc_ple_ventas = fields.Boolean("Incluir en PLE de Ventas")

	