# -*- coding: utf-8 -*-
# Copyright (c) 2026 FM SYSTEMS SOLUTIONS E.I.R.L. (sistemas@solse.pe)
# Licencia: Other proprietary. Prohibida la redistribucion total o parcial.
"""B-4/M-51: el servidor de guías (GRE) debe ser de la propia compañía.
El aviso de mezcla beta/producción vive en solse_pe_cpe."""

from odoo import api, models, _
from odoo.exceptions import ValidationError


class ResCompanyCredencialesGuias(models.Model):
	_inherit = 'res.company'

	@api.constrains('pe_cpe_eguide_server_id')
	def _check_servidor_guias_de_la_compania(self):
		for compania in self:
			servidor = compania.pe_cpe_eguide_server_id
			if servidor and servidor.company_id and \
					servidor.company_id != compania:
				raise ValidationError(_(
					'El servidor de guías «%s» pertenece a la '
					'compañía «%s» y no puede asignarse a «%s».',
					servidor.display_name,
					servidor.company_id.display_name,
					compania.display_name))
