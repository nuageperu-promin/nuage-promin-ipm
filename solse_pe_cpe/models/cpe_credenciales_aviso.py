# -*- coding: utf-8 -*-
# Copyright (c) 2026 FM SYSTEMS SOLUTIONS E.I.R.L. (sistemas@solse.pe)
# Licencia: Other proprietary. Prohibida la redistribucion total o parcial.
"""Lote B-4 / M-51 — credenciales SUNAT cruzadas.

Cuatro juegos de credenciales por compañía en dos modelos:
`pe_cpe_server_id` (CPE, SOAP), `pe_cpe_server_otros_id`
(retención/percepción, SOAP), `pe_cpe_eguide_server_id` (GRE,
REST+OAuth2) y `solse.sunat.api` (SIRE). Cruzarlas produce errores de
autenticación que se diagnostican como problemas de certificado.

Dos comprobaciones distintas porque los dos cruces son distintos:
- Servidor de OTRA compañía asignado en `res.company` → SIEMPRE es un
  error: constrains que bloquea (aquí el juego CPE; retención y guías
  ponen el suyo en su propio módulo).
- Mezcla beta/producción entre los juegos de una misma compañía →
  puede ser legítima en un onboarding (CPE ya en producción, GRE aún
  en beta): AVISO visible en el formulario de la compañía, sin
  bloquear. El entorno se detecta por la URL ('beta' en el host).
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CpeServerEntorno(models.Model):
	_inherit = 'cpe.server'

	def entorno_sunat(self):
		"""'beta' o 'producción' según la URL del servidor."""
		self.ensure_one()
		return 'beta' if 'beta' in (self.url or '').lower() \
			else 'producción'


class ResCompanyCredencialesSunat(models.Model):
	_inherit = 'res.company'

	pe_aviso_credenciales = fields.Text(
		'Aviso de credenciales SUNAT',
		compute='_compute_pe_aviso_credenciales')

	@api.constrains('pe_cpe_server_id')
	def _check_servidor_cpe_de_la_compania(self):
		for compania in self:
			servidor = compania.pe_cpe_server_id
			if servidor and servidor.company_id and \
					servidor.company_id != compania:
				raise ValidationError(_(
					'El servidor CPE «%s» pertenece a la compañía '
					'«%s» y no puede asignarse a «%s». Cada compañía '
					'usa sus propias credenciales SUNAT.',
					servidor.display_name,
					servidor.company_id.display_name,
					compania.display_name))

	def _juegos_credenciales(self):
		"""(etiqueta, servidor) de los juegos con URL configurados en
		esta compañía. Retención y guías pueden no estar instalados:
		sus campos se leen solo si existen. `solse.sunat.api` no lleva
		URL, así que no participa del detector de entorno."""
		self.ensure_one()
		juegos = [('CPE', self.pe_cpe_server_id)]
		if 'pe_cpe_server_otros_id' in self._fields:
			juegos.append(('Retención/Percepción',
						   self.pe_cpe_server_otros_id))
		if 'pe_cpe_eguide_server_id' in self._fields:
			juegos.append(('Guías (GRE)',
						   self.pe_cpe_eguide_server_id))
		return [(etiqueta, servidor) for etiqueta, servidor in juegos
				if servidor]

	def _compute_pe_aviso_credenciales(self):
		for compania in self:
			avisos = []
			juegos = compania._juegos_credenciales()
			ajenos = [
				(etiqueta, servidor) for etiqueta, servidor in juegos
				if servidor.company_id and
				servidor.company_id != compania]
			for etiqueta, servidor in ajenos:
				avisos.append(_(
					'• El juego %s usa el servidor «%s», que es de la '
					'compañía «%s».') % (
					etiqueta, servidor.display_name,
					servidor.company_id.display_name))
			entornos = {(etiqueta, servidor.entorno_sunat())
						for etiqueta, servidor in juegos}
			if len({e for _et, e in entornos}) > 1:
				detalle = ', '.join(
					'%s en %s' % (etiqueta, entorno)
					for etiqueta, entorno in sorted(entornos))
				avisos.append(_(
					'• Los juegos de credenciales mezclan entornos '
					'(%s). Si no es un despliegue en curso, revise las '
					'URL: el cruce produce errores de autenticación '
					'que parecen problemas de certificado.') % detalle)
			compania.pe_aviso_credenciales = '\n'.join(avisos)
