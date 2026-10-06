# -*- coding: utf-8 -*-

from base64 import b64encode

from odoo import api, fields, models

from .eguide_transport import get_document_transport

import logging

_logging = logging.getLogger(__name__)


class CPESunatEguideTransport(models.Model):
	"""Guía de Remisión Electrónica Transportista (tipo 31).

	Herencia de prototipo sobre `solse.cpe.eguide`: tabla propia, pero
	reutiliza todos los campos y toda la mecánica de firma, envío, consulta
	de ticket y lectura del CDR del módulo base. Solo se redefine lo que
	cambia entre la 09 y la 31.
	"""
	_name = 'solse.cpe.eguide.transport'
	_inherit = 'solse.cpe.eguide'
	_description = 'Guia Electronica Transportista'
	_order = 'name, date'

	# Los One2many heredados apuntan a los inversos de la GRR (pe_guide_id,
	# pe_voided_id); sin redefinirlos el registry no levanta.
	voided_ids = fields.One2many(
		comodel_name="stock.picking",
		inverse_name="pe_voided_transport_id",
		string="Guía transportista cancelada",
	)
	picking_ids = fields.One2many(
		comodel_name="stock.picking",
		inverse_name="pe_guide_transport_id",
		string="Guía transportista",
	)

	# ------------------------------------------------------------------
	# Puntos de divergencia con la GRR
	# ------------------------------------------------------------------
	def obtener_servidor(self):
		"""Servidor de la GRT, con fallback al de guías de remisión
		(mismo endpoint GRE de SUNAT para la 09 y la 31)."""
		self.ensure_one()
		empresa = self.obtener_empresa()
		return empresa.pe_cpe_eguide_transport_server_id \
			or empresa.pe_cpe_eguide_server_id

	def get_document_name(self):
		"""Nombre del archivo: RUC-31-SERIE-CORRELATIVO."""
		self.ensure_one()
		empresa = self.obtener_empresa()
		ruc = empresa.partner_id.doc_number
		if self.type == "sync":
			numero = self.picking_ids[0].pe_guide_number
		else:
			numero = self.name
		return "%s-31-%s" % (ruc, numero)

	def _prepare_eguide(self):
		"""Genera el XML con el constructor de la GRT (tipo 31)."""
		if not self.xml_document and self.type != "low":
			file_name = self.get_document_name()
			xml_document = get_document_transport(self)
			self.xml_document = xml_document
			self.datas = b64encode(xml_document)
			self.datas_fname = file_name + ".xml"

	def send_eguide(self):
		"""Igual al base salvo la secuencia de la comunicación de baja,
		que es la de la compañía del documento."""
		self.ensure_one()
		if self.name == "/" and self.type == "low":
			self.name = self.env['ir.sequence'].with_company(
				self.company_id).next_by_code('pe.eguide.transport.cancel')
		return super(CPESunatEguideTransport, self).send_eguide()
