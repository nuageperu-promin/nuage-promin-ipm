# -*- coding: utf-8 -*-
"""Puente entre la nómina ENTERPRISE y el PLAME de 4ta categoría.

Gemelo de `solse_pe_plame_4ta` (Community), NEE hito 4 (2026-09-21).
Este módulo NO genera el archivo: añade al ZIP del asistente PLAME de la
nómina los DOS ficheros que produce `solse_pe_plame_rxh`, que es donde
vive el generador y su normativa.

Lo que el puente usa del asistente de `solse_pe_payroll` está verificado
en `solse_pe_payroll/wizard/plame.py`: `_name = 'solse.payroll.plame.wizard'`
(:40), `mes` (:43), `anio` (:45), `archivo` (:47), `resumen` (:49) y
`action_generar` (:78). Son los mismos que en Community; la única línea
propia de la edición es el `inherit_id` de la vista.

Por qué dos archivos (PL4-01, heredado del análisis en Community). El Anexo 3 de la Planilla Electrónica (R.M.
121-2011-TR, mod. R.S. 028-2018/SUNAT) define dos archivos distintos:

	`.ps4`	estructura 7  — maestro de prestadores
	`.4ta`	estructura 20 — detalle de comprobantes

y en el PDT se importa primero el `.ps4` y después el `.4ta`.

Con el puente hay UNA sola implementación, la del RxH, verificada contra
archivos reales aceptados por el PDT y cubierta por el caso PLAME-RXH del
laboratorio. Quien solo declara 4ta instala `solse_pe_plame_rxh` y usa su
asistente; quien además lleva nómina instala este módulo y los archivos
salen dentro del mismo ZIP.

Los errores de validación NO rompen la generación de la nómina: se
informan en el resumen del asistente y el ZIP sale sin los archivos de
4ta, porque una planilla a medio declarar es peor que una sin el anexo.
"""

import base64
import io
import zipfile

from odoo import _, fields, models


class SolsePayrollPlameWizard(models.TransientModel):
	_inherit = 'solse.payroll.plame.wizard'

	incluir_4ta = fields.Boolean(
		string='Incluir 4ta categoría (.ps4 y .4ta)', default=True,
		help='Agrega al ZIP los dos archivos de Prestadores de Servicios '
			 'de 4ta categoría: el maestro de prestadores (.ps4, estructura '
			 '7) y el detalle de comprobantes (.4ta, estructura 20), con los '
			 'Recibos por Honorarios pagados en el periodo. Los genera '
			 'solse_pe_plame_rxh, el mismo módulo que usan las empresas sin '
			 'nómina.')

	def _exportador_rxh(self):
		"""El asistente del RxH posicionado en el periodo de la nómina."""
		self.ensure_one()
		return self.env['plame.rxh.exportar'].create({
			'company_id': self.env.company.id,
			'ejercicio': str(self.anio),
			'mes': '%02d' % int(self.mes),
		})

	def action_generar(self):
		accion = super().action_generar()
		if not self.incluir_4ta or not self.archivo:
			return accion

		exportador = self._exportador_rxh()
		datos = exportador._recopilar_datos_periodo()
		if not datos:
			self.resumen = (self.resumen or '') + _(
				'\n4ta categoría: no hay recibos por honorarios pagados en '
				'el periodo.')
			return accion

		errores, advertencias = exportador._validar_datos(datos)
		if errores:
			# La nómina se entrega igual; el anexo de 4ta, no.
			self.resumen = (self.resumen or '') + _(
				'\n4ta categoría: NO se agregaron los archivos por '
				'%(cantidad)s error(es):\n  • %(detalle)s',
				cantidad=len(errores), detalle='\n  • '.join(errores))
			return accion

		contenidos = {
			exportador._nombre_archivo('ps4'):
				exportador._generar_contenido_ps4(datos),
			exportador._nombre_archivo('4ta'):
				exportador._generar_contenido_4ta(datos),
		}
		buffer = io.BytesIO(base64.b64decode(self.archivo))
		with zipfile.ZipFile(buffer, 'a', zipfile.ZIP_DEFLATED) as zf:
			for nombre, contenido in contenidos.items():
				# `_codificar` devuelve base64 (es lo que guarda el campo
				# binario del asistente del RxH); aquí hacen falta bytes.
				zf.writestr(nombre, base64.b64decode(
					exportador._codificar(contenido)))
		self.archivo = base64.b64encode(buffer.getvalue())

		retenciones = sum(1 for registro in datos if registro['retencion'])
		self.resumen = (self.resumen or '') + _(
			'\n4ta categoría: %(prestadores)s prestador(es) en el .ps4 y '
			'%(comprobantes)s comprobante(s) en el .4ta '
			'(%(retenciones)s con retención).%(avisos)s',
			prestadores=len({registro['numero_documento']
							 for registro in datos}),
			comprobantes=len(datos), retenciones=retenciones,
			avisos=(_('\n  Advertencias:\n  • %s')
					% '\n  • '.join(advertencias)) if advertencias else '')
		return accion
