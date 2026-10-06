# -*- coding: utf-8 -*-

import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

# ERR-3355: alfanumerico de 10 a 15 caracteres, solo mayusculas y numeros,
# no se permite solamente ceros.
PATRON_TUCE = re.compile(r'^[A-Z0-9]{10,15}$')


class FleetVehicle(models.Model):
	_inherit = 'fleet.vehicle'

	pe_tuce = fields.Char(
		string="TUCE / Certificado de habilitación vehicular",
		copy=False,
		help="Tarjeta Única de Circulación Electrónica, Constancia de "
			 "Inscripción Vehicular o Certificado de Habilitación Vehicular.\n"
			 "SUNAT lo exige en la GRE - Remitente cuando la modalidad de "
			 "traslado es 01-Público y se activa el 'Indicador de registro de "
			 "vehículos y conductores del transportista' (OBS-4399).\n"
			 "Formato: 10 a 15 caracteres, solo letras mayúsculas y números "
			 "(ERR-3355)."
	)

	@api.constrains('pe_tuce')
	def _check_pe_tuce(self):
		"""ERR-3355: valida el formato de la TUCE antes de llegar a SUNAT."""
		for vehiculo in self:
			valor = (vehiculo.pe_tuce or '').strip()
			if not valor:
				continue
			if not PATRON_TUCE.match(valor):
				raise ValidationError(_(
					"El número de TUCE / Certificado de habilitación del "
					"vehículo '%s' no cumple el formato SUNAT (ERR-3355): "
					"de 10 a 15 caracteres, solo letras mayúsculas y números."
				) % (vehiculo.license_plate or vehiculo.display_name or ''))
			if not valor.strip('0'):
				raise ValidationError(_(
					"El número de TUCE / Certificado de habilitación del "
					"vehículo '%s' no puede estar compuesto solo por ceros "
					"(ERR-3355)."
				) % (vehiculo.license_plate or vehiculo.display_name or ''))
