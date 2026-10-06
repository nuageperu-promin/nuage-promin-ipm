# -*- coding: utf-8 -*-

# Pago masivo a bancos: TXT de abono de haberes y CTS.
# Formatos portados del módulo SOLSE v17 (hr_massive_payment):
#   - BCP Telecrédito (haberes y CTS): cabecera '1' + detalle '2A'/'2B',
#     con dígito de control por suma de cuentas.
#   - Interbank (haberes y CTS): cabecera 0104/0106 + detalle '02'.
# Simplificaciones v1 (documentadas): moneda PEN, documento DNI (01),
# abonos a cuenta del mismo banco o CCI interbancario. Scotiabank y
# Banco de la Nación llegan en la siguiente entrega (BN espera layout
# del cliente; Scotiabank requiere validar la plantilla de 2 archivos).

import base64
from datetime import date, datetime

from odoo import _, fields, models
from odoo.exceptions import ValidationError

MESES = [(str(m), n) for m, n in enumerate(
	['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
	 'Agosto', 'Setiembre', 'Octubre', 'Noviembre', 'Diciembre'], start=1)]

# Códigos de banco (l10n_pe / SBS): BCP=02, Interbank=03
CODIGO_BCP = '02'
CODIGO_INTERBANK = '03'


def _rellenar(texto, longitud, alineacion='izq'):
	texto = (texto or '')[:longitud]
	return texto.rjust(longitud) if alineacion == 'der' else texto.ljust(longitud)


def _monto_bcp(valor, digitos=14):
	"""Entero con ceros a la izquierda + '.' + 2 decimales (formato v17)."""
	entero = int(valor)
	decimal = ('%.2f' % (valor - entero))[1:]
	return str(entero).zfill(digitos) + decimal


def _monto_ibk(valor):
	"""Interbank: 15 posiciones = 13 dígitos enteros + 2 decimales,
	sin punto (equivale al struct_zero_number(16)[3:] del v17)."""
	return str(int(round(valor * 100))).zfill(15)


def _monto_scotia(valor, enteros=11, decimales=9):
	"""Scotiabank haberes: '0.' + enteros con ceros + '.' + decimales
	rellenados con ceros a la derecha (formato v17)."""
	entero = str(int(valor)).zfill(enteros)
	dec = ('%.2f' % (valor - int(valor)))[2:].ljust(decimales, '0')
	return '0.' + entero + '.' + dec


def _monto_scotia_cts(valor):
	"""Scotiabank CTS: 13 posiciones enteras + 2 decimales sin punto."""
	return str(int(round(valor * 100))).zfill(15)


def _cuenta_limpia(cuenta, tipo):
	cuenta = (cuenta or '').replace(' ', '').replace('-', '')
	try:
		return int(cuenta[10:]) if tipo == 'B' else int(cuenta[3:])
	except Exception:
		return 0


class SolsePayrollBancosWizard(models.TransientModel):
	_name = 'solse.payroll.bancos.wizard'
	_description = 'Pago masivo a bancos (PE)'

	mes = fields.Selection(selection=MESES, string='Mes', required=True,
						   default=lambda self: str(fields.Date.today().month))
	anio = fields.Integer(string='Año', required=True,
						  default=lambda self: fields.Date.today().year)
	tipo = fields.Selection([('sueldo', 'Haberes (sueldo)'), ('cts', 'CTS')],
							string='Tipo de pago', required=True, default='sueldo')
	banco = fields.Selection([('bcp', 'BCP - Telecrédito'),
							  ('interbank', 'Interbank'),
							  ('scotiabank', 'Scotiabank')],
							 string='Banco de cargo', required=True, default='bcp')
	cuenta_cargo = fields.Char(
		string='Cuenta de cargo de la empresa', required=True,
		help='Número de la cuenta de la compañía en el banco elegido, '
			 'desde la que se debitan los abonos.')
	fecha_pago = fields.Date(string='Fecha de pago', required=True,
							 default=fields.Date.today)
	incluir_gratificaciones = fields.Boolean(
		string='Incluir gratificaciones del mes', default=False,
		help='Suma al abono de haberes las boletas de gratificación '
			 'validadas del periodo (julio/diciembre).')
	archivo = fields.Binary(string='Archivo TXT', readonly=True)
	archivo_nombre = fields.Char()
	resumen = fields.Text(readonly=True)

	# ------------------------------------------------------------------
	def _netos_por_empleado(self):
		"""{employee: neto} de las boletas validadas del periodo según tipo."""
		self.ensure_one()
		ref = self.env.ref
		if self.tipo == 'cts':
			estructuras = [ref('solse_pe_payroll.hr_payroll_structure_cts').id]
		else:
			estructuras = [
				ref('solse_pe_payroll.hr_payroll_structure_mensual_empleados').id,
				ref('solse_pe_payroll.hr_payroll_structure_semanal_obreros').id,
			]
			if self.incluir_gratificaciones:
				estructuras.append(ref(
					'solse_pe_payroll.hr_payroll_structure_gratificaciones').id)
		boletas = self.env['hr.payslip'].search([
			('state', 'in', ('validated', 'paid')),
			('struct_id', 'in', estructuras),
			('date_start_dt', '=', date(self.anio, int(self.mes), 1)),
			('company_id', '=', self.env.company.id),
		])
		netos = {}
		for boleta_id in boletas:
			neto = sum(boleta_id.line_ids.filtered(
				lambda l: l.code == 'NET').mapped('total'))
			if neto > 0.005:
				netos[boleta_id.employee_id] = netos.get(
					boleta_id.employee_id, 0.0) + neto
		return netos

	def _cuenta_empleado(self, empleado_id):
		"""Cuenta según uso (sueldo/cts). Devuelve (registro, codigo_banco)."""
		uso = 'cts' if self.tipo == 'cts' else 'sueldo'
		cuenta_id = self.env['res.partner.bank'].search([
			('partner_id', '=', empleado_id.work_contact_id.id),
			('uso_cuenta', '=', uso),
		], limit=1)
		codigo = cuenta_id.bank_id.bic or ''
		# l10n_pe_bank_code si el banco lo trae; fallback por nombre
		if hasattr(cuenta_id.bank_id, 'l10n_pe_bank_code'):
			codigo = cuenta_id.bank_id.l10n_pe_bank_code or codigo
		if not codigo and cuenta_id.bank_id:
			nombre = (cuenta_id.bank_id.name or '').lower()
			if 'crédito' in nombre or 'bcp' in nombre:
				codigo = CODIGO_BCP
			elif 'interbank' in nombre:
				codigo = CODIGO_INTERBANK
			elif 'scotia' in nombre:
				codigo = CODIGO_SCOTIABANK
		return cuenta_id, codigo

	# ------------------------------------------------------------------
	def action_generar(self):
		self.ensure_one()
		netos = self._netos_por_empleado()
		if not netos:
			raise ValidationError(_('No hay boletas validadas del periodo '
									'para el tipo de pago elegido.'))
		sin_cuenta = []
		if self.banco == 'bcp':
			contenido, total, abonados = self._generar_bcp(netos, sin_cuenta)
			extension = 'txt'
		else:
			contenido, total, abonados = self._generar_interbank(netos, sin_cuenta)
			extension = 'txt'
		if sin_cuenta:
			raise ValidationError(_(
				'Trabajadores sin cuenta de %s registrada:\n%s') % (
				dict(self._fields['tipo'].selection)[self.tipo],
				'\n'.join('  - ' + n for n in sin_cuenta)))
		self.archivo = base64.b64encode(contenido.encode('latin-1', 'replace'))
		self.archivo_nombre = 'ABONO_%s_%s_%s%02d.%s' % (
			self.banco.upper(), self.tipo.upper(), self.anio,
			int(self.mes), extension)
		self.resumen = _('Abonados: %s trabajadores | Total: S/ %.2f') % (
			abonados, total)
		return {
			'type': 'ir.actions.act_window', 'res_model': self._name,
			'res_id': self.id, 'view_mode': 'form', 'target': 'new',
			'name': _('Pago masivo a bancos'),
		}

	# ------------------------------------------------------------------
	def _generar_bcp(self, netos, sin_cuenta):
		detalles = []
		cuentas_control = []
		total = 0.0
		for empleado_id in sorted(netos, key=lambda e: e.name):
			neto = netos[empleado_id]
			cuenta_id, codigo = self._cuenta_empleado(empleado_id)
			if not cuenta_id:
				sin_cuenta.append(empleado_id.name)
				continue
			if self.tipo == 'cts' and codigo != CODIGO_BCP:
				# La CTS solo se abona a cuentas CTS del propio BCP
				continue
			if codigo == CODIGO_BCP:
				tipo_reg, numero, mismo = '2A', cuenta_id.acc_number, 'S'
			else:
				tipo_reg, numero, mismo = '2B', cuenta_id.cci, 'N'
			if not numero:
				sin_cuenta.append(empleado_id.name)
				continue
			doc = _rellenar(empleado_id.identification_id, 15)
			nombre = _rellenar(empleado_id.name, 75)
			ref_benef = _rellenar('Referencia Beneficiario %s'
								  % empleado_id.identification_id, 40)
			ref_emp = _rellenar('Ref Emp %s' % empleado_id.identification_id, 20)
			monto = _monto_bcp(neto)
			if self.tipo == 'sueldo':
				linea = (tipo_reg + _rellenar(numero, 20) + '1' + doc + nombre
						 + ref_benef + ref_emp + '0' + '001' + monto + mismo)
				cuentas_control.append(_cuenta_limpia(numero, tipo_reg[1:]))
			else:
				linea = (tipo_reg[0] + _rellenar(numero, 20) + '1' + doc
						 + nombre + ref_benef + ref_emp + '0' + '001' + monto
						 + '0' + '001' + monto)
				cuentas_control.append(_cuenta_limpia(numero, 'A'))
			detalles.append(linea)
			total += neto
		# Cabecera
		control = str(sum(cuentas_control)
					  + _cuenta_limpia(self.cuenta_cargo, 'A')).zfill(15)
		fecha = self.fecha_pago.strftime('%Y%m%d')
		cargo = _rellenar(self.cuenta_cargo.replace('-', ''), 20)
		if self.tipo == 'sueldo':
			cabecera = ('1' + str(len(detalles)).zfill(6) + fecha + 'X' + 'C'
						+ '0' + '001' + cargo + _monto_bcp(total)
						+ _rellenar('HABERES', 40) + control)
		else:
			ruc = _rellenar(''.join(c for c in (self.env.company.vat or '')
									if c.isdigit()), 12)
			cabecera = ('1' + str(len(detalles)).zfill(6) + fecha + 'C' + '0'
						+ '001' + cargo + '6' + ruc + _monto_bcp(total)
						+ _rellenar('Referencia CTS', 40) + control)
		return '\r\n'.join([cabecera] + detalles) + '\r\n', total, len(detalles)

	def _generar_interbank(self, netos, sin_cuenta):
		detalles = []
		total = 0.0
		for empleado_id in sorted(netos, key=lambda e: e.name):
			neto = netos[empleado_id]
			cuenta_id, codigo = self._cuenta_empleado(empleado_id)
			if not cuenta_id:
				sin_cuenta.append(empleado_id.name)
				continue
			if codigo == CODIGO_INTERBANK:
				numero, medio, oficina = cuenta_id.acc_number, '09', '002'
			else:
				numero, medio, oficina = cuenta_id.cci, '99', '   '
			if not numero:
				sin_cuenta.append(empleado_id.name)
				continue
			doc_largo = _rellenar(('01%s' % empleado_id.identification_id
								   ).zfill(10), 49)
			nombres = (_rellenar(empleado_id.lastname or '', 20)
					   + _rellenar(getattr(empleado_id, 'secondname', '') or '', 20)
					   + _rellenar(empleado_id.firstname or empleado_id.name, 20))
			linea = ('02' + doc_largo + '01' + _monto_ibk(neto) + ' '
					 + medio + oficina + '01' + _rellenar(numero, 23) + 'P'
					 + '01' + _rellenar(empleado_id.identification_id, 15)
					 + nombres + ('0' * 15 if self.tipo == 'sueldo'
								  else '01' + _monto_ibk(neto)))
			detalles.append(linea)
			total += neto
		proceso = '0104' if self.tipo == 'sueldo' else '0106'
		cabecera = (_rellenar(proceso, 40)
					+ self.fecha_pago.strftime('%Y%m%d')
					+ _rellenar(datetime.now().strftime('%H%M%S'), 15)
					+ str(len(detalles)).zfill(6)
					+ _monto_ibk(total) + '0' * 15 + 'MC001')
		return '\r\n'.join([cabecera] + detalles) + '\r\n', total, len(detalles)

	# ------------------------------------------------------------------
	def _generar_scotiabank(self, netos):
		"""Formatos Scotiabank del v17.
		HABERES (sin cabecera): moneda(13) + 20esp + nombre(30) + '1' +
		8esp + monto '0.'+9ent+'.'+9dec + relleno fijo + cuenta(30) +
		'5' + 14esp + tipo_doc(2) + doc(12) + 38esp [+ CCI(20) si es
		abono interbancario].
		CTS: cabecera '0NO'+10esp+moneda(92 PEN)+total(15 sin punto)+
		11 ceros; detalle '1'+moneda+cuenta(10)+moneda+neto(15 sin
		punto)+20esp+moneda+retiro(15 ceros, TRE no gestionado en v1).
		Moneda: soles (v1)."""
		detalles = []
		omitidos = []
		total = 0.0
		for empleado_id, neto in sorted(netos.items(), key=lambda x: x[0].name):
			cuenta_id, codigo = self._cuenta_empleado(empleado_id)
			if not cuenta_id or not cuenta_id.acc_number:
				omitidos.append(empleado_id.name)
				continue
			numero = cuenta_id.acc_number.replace(' ', '').replace('-', '')
			es_scotia = codigo == CODIGO_SCOTIABANK
			cci = (cuenta_id.cci or '').replace(' ', '').replace('-', '')
			if not es_scotia and not cci:
				omitidos.append(empleado_id.name + ' (sin CCI)')
				continue
			total += neto
			if self.tipo == 'cts':
				detalles.append(
					'1' + '92' + _rellenar(numero, 10, 'izq') + '92'
					+ _monto_scotia_cts(neto) + ' ' * 20 + '92'
					+ '0' * 15)
			else:
				nombre = '%s %s' % (empleado_id.name or '', '')
				linea = (
					'20'.zfill(13) + ' ' * 20
					+ _rellenar(nombre.strip(), 30, 'izq') + '1' + ' ' * 8
					+ _monto_scotia(neto)
					+ '.000000000.000000000.000000000.000000000.00'
					+ _rellenar(numero if es_scotia else '', 30, 'izq')
					+ '5' + ' ' * 14 + '01'
					+ _rellenar(empleado_id.identification_id or '', 12, 'izq')
					+ ' ' * 38)
				if not es_scotia:
					linea += _rellenar(cci, 20, 'izq')
				detalles.append(linea)
		lineas = []
		if self.tipo == 'cts':
			lineas.append('0NO' + ' ' * 10 + '92'
						  + _monto_scotia_cts(total) + '0' * 11)
		lineas.extend(detalles)
		return '\r\n'.join(lineas) + '\r\n', len(detalles), omitidos
