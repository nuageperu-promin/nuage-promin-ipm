# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..hooks import _detectar_taxes_por_concepto, _aplicar_configuracion_afectaciones


class ConfigurarAfectacionWizard(models.TransientModel):
	_name = "solse.pe.afectacion.compra.wizard"
	_description = "Asistente para configurar afectaciones de compra"

	company_id = fields.Many2one(
		'res.company',
		string="Compañía",
		required=True,
		default=lambda self: self.env.company,
	)

	# IGV diferenciado por destino. Si en el plan contable solo hay un IGV
	# genérico, los tres campos apuntarán al mismo (resuelto en default_get).
	tax_igv_dg_id = fields.Many2one(
		'account.tax',
		string="IGV — Destinada a Gravadas",
		domain="[('type_tax_use', '=', 'purchase'), ('company_id', '=', company_id)]",
		help="IGV 18% para compras destinadas exclusivamente a operaciones gravadas. "
			 "Sus montos se distribuyen a las columnas 15 (BI) y 16 (IGV) del SIRE 8.4.",
	)
	tax_igv_dgng_id = fields.Many2one(
		'account.tax',
		string="IGV — Destinada a Gravadas y No Gravadas (mixta/prorrata)",
		domain="[('type_tax_use', '=', 'purchase'), ('company_id', '=', company_id)]",
		help="IGV 18% para compras de uso mixto (con prorrata). "
			 "Sus montos se distribuyen a las columnas 17 (BI) y 18 (IGV) del SIRE 8.4. "
			 "Si tu plan no diferencia este caso, deja el mismo IGV de DG.",
	)
	tax_igv_dng_id = fields.Many2one(
		'account.tax',
		string="IGV — Destinada a No Gravadas (sin crédito fiscal)",
		domain="[('type_tax_use', '=', 'purchase'), ('company_id', '=', company_id)]",
		help="IGV 18% para compras destinadas exclusivamente a operaciones no gravadas. "
			 "Sus montos se distribuyen a las columnas 19 (BI) y 20 (IGV) del SIRE 8.4. "
			 "Si tu plan no diferencia este caso, deja el mismo IGV de DG.",
	)
	tax_icbper_id = fields.Many2one(
		'account.tax',
		string="ICBPER (Bolsas plásticas)",
		domain="[('type_tax_use', '=', 'purchase'), ('company_id', '=', company_id)]",
	)
	tax_isc_id = fields.Many2one(
		'account.tax',
		string="ISC (Impuesto Selectivo al Consumo)",
		domain="[('type_tax_use', '=', 'purchase'), ('company_id', '=', company_id)]",
	)
	tax_exonerado_id = fields.Many2one(
		'account.tax',
		string="Exonerado (0%)",
		domain="[('type_tax_use', '=', 'purchase'), ('company_id', '=', company_id)]",
	)
	tax_inafecto_id = fields.Many2one(
		'account.tax',
		string="Inafecto (0%)",
		domain="[('type_tax_use', '=', 'purchase'), ('company_id', '=', company_id)]",
	)
	reemplazar = fields.Boolean(
		string="Reemplazar configuración existente",
		default=False,
		help="Si está marcado, las afectaciones que ya tienen impuestos configurados "
			 "serán reemplazadas. Por defecto, sólo se completan las afectaciones vacías.",
	)
	resumen_deteccion = fields.Html(
		string="Detección automática",
		compute="_compute_resumen_deteccion",
	)

	@api.model
	def default_get(self, fields_list):
		"""Pre-llena los Many2one con la detección automática diferenciada."""
		valores = super().default_get(fields_list)
		compania = self.env['res.company'].browse(valores.get('company_id')) or self.env.company
		taxes = _detectar_taxes_por_concepto(self.env, compania)
		mapeo = {
			'tax_igv_dg_id':     'igv_dg',
			'tax_igv_dgng_id':   'igv_dgng',
			'tax_igv_dng_id':    'igv_dng',
			'tax_icbper_id':     'icbper',
			'tax_isc_id':        'isc',
			'tax_exonerado_id':  'exonerado',
			'tax_inafecto_id':   'inafecto',
		}
		for campo, concepto in mapeo.items():
			if campo in fields_list and not valores.get(campo):
				detectado = taxes.get(concepto)
				if detectado:
					valores[campo] = detectado[:1].id
		return valores

	@api.depends('company_id')
	def _compute_resumen_deteccion(self):
		for wizard in self:
			compania = wizard.company_id or self.env.company
			taxes = _detectar_taxes_por_concepto(self.env, compania)
			etiquetas = [
				('igv_dg',    'IGV — Destinada a Gravadas'),
				('igv_dgng',  'IGV — Destinada a Gravadas y No Gravadas'),
				('igv_dng',   'IGV — Destinada a No Gravadas'),
				('icbper',    'ICBPER'),
				('isc',       'ISC'),
				('exonerado', 'Exonerado (0%)'),
				('inafecto',  'Inafecto (0%)'),
			]
			filas = []
			for concepto, etiqueta in etiquetas:
				detectados = taxes.get(concepto)
				if detectados:
					nombres = ', '.join(detectados.mapped('name'))
					filas.append(
						f"<tr><td><b>{etiqueta}</b></td>"
						f"<td><i>{nombres}</i></td></tr>"
					)
				else:
					filas.append(
						f"<tr><td><b>{etiqueta}</b></td>"
						f"<td><span style='color:#a00;'>No detectado</span></td></tr>"
					)
			html = (
				"<p>Resultado de la detección automática para la compañía "
				f"<b>{compania.name}</b>:</p>"
				"<table class='table table-sm'>"
				"<thead><tr><th>Concepto</th><th>Impuesto detectado</th></tr></thead>"
				"<tbody>" + "".join(filas) + "</tbody></table>"
				"<p class='text-muted'><small>"
				"<b>Patrones de clasificación de IGV:</b> "
				"se busca '<code>G NG</code>', '<code>GNG</code>', '<code>mixt</code>' o "
				"'<code>prorrat</code>' en el nombre para clasificar como DGNG. "
				"Se busca '<code>NG</code>', '<code>no grav</code>' o '<code>sin créd</code>' "
				"para clasificar como DNG. El resto se considera DG. "
				"Si en tu plan solo hay un IGV genérico, los tres campos quedarán "
				"con el mismo impuesto (es válido)."
				"</small></p>"
			)
			wizard.resumen_deteccion = html

	def action_aplicar(self):
		self.ensure_one()
		if not any([
			self.tax_igv_dg_id, self.tax_igv_dgng_id, self.tax_igv_dng_id,
			self.tax_icbper_id, self.tax_isc_id,
			self.tax_exonerado_id, self.tax_inafecto_id,
		]):
			raise UserError(_("Debes seleccionar al menos un impuesto antes de aplicar."))

		taxes_por_concepto = {
			'igv_dg':    self.tax_igv_dg_id,
			'igv_dgng':  self.tax_igv_dgng_id,
			'igv_dng':   self.tax_igv_dng_id,
			'icbper':    self.tax_icbper_id,
			'isc':       self.tax_isc_id,
			'exonerado': self.tax_exonerado_id,
			'inafecto':  self.tax_inafecto_id,
		}
		configuradas, omitidas = _aplicar_configuracion_afectaciones(
			self.env, self.company_id, taxes_por_concepto, reemplazar=self.reemplazar,
		)

		mensaje_partes = []
		if configuradas:
			mensaje_partes.append(
				_("Afectaciones configuradas: %s") %
				", ".join(configuradas.mapped('name'))
			)
		if omitidas:
			mensaje_partes.append(
				_("Afectaciones omitidas (ya tenían impuestos): %s") %
				", ".join(omitidas.mapped('name'))
			)
		if not mensaje_partes:
			mensaje_partes.append(_("No se realizaron cambios."))

		return {
			'type': 'ir.actions.client',
			'tag': 'display_notification',
			'params': {
				'title': _("Configuración de afectaciones"),
				'message': "\n".join(mensaje_partes),
				'sticky': False,
				'type': 'success' if configuradas else 'warning',
				'next': {'type': 'ir.actions.act_window_close'},
			},
		}
