# -*- coding: utf-8 -*-
# Copyright (c) 2026 NUAGE PERU SAC
import base64
import datetime
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.solse_pe_ple_pro.models.ple_report import fill_name_data
from . import ple_03_format as fmt
from .ple_01_format import a_centimos

_logging = logging.getLogger(__name__)

# Sub-libro de la Tabla 34 al que pertenecen los rubros del estado de situación.
SUBLIBRO_ESF = '3_1'

# Rubro donde se informa el resultado que aún no pasó por el asiento de cierre,
# por sector (Tabla 34): en el sector 01 es «Resultados Acumulados».
RUBRO_RESULTADO_POR_SECTOR = {'01': '1D0707'}

CABECERAS_31 = [
    'Periodo',
    'Código del catálogo (Tabla 22)',
    'Código del rubro del estado financiero (Tabla 34)',
    'Saldo del rubro contable',
    'Indica el estado de la operación',
]


def _soles(centimos):
    return fmt.formatear_saldo(centimos)


class PLEReport03(models.Model):
    _name = 'ple.report.03'
    _description = 'PLE 03 - Estructura del Libro de Inventarios y Balances'
    _inherit = 'ple.report.templ'

    year = fields.Integer(required=True)
    # El balance anual es al 31 de diciembre (oportunidad 01): mes y día fijos.
    month = fields.Selection(selection_add=[], default='12')
    day = fields.Integer(default=31)

    rubro_resultado_id = fields.Many2one(
        comodel_name='pe.datas',
        string='Rubro del resultado no cerrado',
        domain=[('table_code', '=', 'PE.TABLA34'), ('description', '=', SUBLIBRO_ESF)],
        compute='_compute_rubro_resultado', store=True, readonly=False,
        help='Rubro del estado de situación donde se informa el resultado de '
             'las cuentas de ingresos y gastos que todavía no pasaron por el '
             'asiento de cierre. Si el cierre ya está registrado, no se usa.')

    resultado_no_cerrado = fields.Float(
        string='Resultado sin cerrar', digits=(16, 2), readonly=True,
        help='Ganancia (+) o pérdida (-) acumulada en cuentas de ingresos y '
             'gastos a la fecha del balance.')
    total_activo = fields.Float(string='Total activo', digits=(16, 2), readonly=True)
    total_pasivo_patrimonio = fields.Float(
        string='Total pasivo y patrimonio', digits=(16, 2), readonly=True)
    diferencia_balance = fields.Float(string='Diferencia', digits=(16, 2), readonly=True)

    archivo_ids = fields.One2many(
        comodel_name='ple.report.03.archivo', inverse_name='report_id',
        string='Archivos generados', readonly=True)

    # ------------------------------------------------------------------
    # Valores por defecto y nombre de archivo
    # ------------------------------------------------------------------

    @api.depends('company_id')
    def _compute_rubro_resultado(self):
        for reporte in self:
            sector = reporte.company_id.sector_contable or '01'
            codigo = RUBRO_RESULTADO_POR_SECTOR.get(sector)
            reporte.rubro_resultado_id = self.env['pe.datas'].search([
                ('table_code', '=', 'PE.TABLA34'),
                ('un_ece_code', '=', sector),
                ('description', '=', SUBLIBRO_ESF),
                ('code', '=', codigo),
            ], limit=1) if codigo else False

    def get_default_filename(self, ple_id='030100', tiene_datos=False):
        # LE + RUC + AAAA + MM + DD + LLLLLL + CC + O I M G (hoja «Reglas de
        # nombres de libros»): el libro 3 lleva la fecha completa del balance
        # (1231) y el código de oportunidad 01 (al 31 de diciembre).
        name = super().get_default_filename()
        name_dict = {
            'month': '12',
            'day': '31',
            'ple_id': ple_id,
            'report_03': fmt.OPORTUNIDAD_CIERRE_ANUAL,
        }
        if not tiene_datos:
            name_dict['contenido'] = '0'
        fill_name_data(name_dict)
        return name % name_dict

    # ------------------------------------------------------------------
    # Lectura de saldos y validaciones
    # ------------------------------------------------------------------

    @staticmethod
    def _rubro_valido(rubro, sector):
        """El rubro es del estado de situación (3.1) y del sector de la empresa."""
        return bool(rubro) \
            and (rubro.description or '').strip() == SUBLIBRO_ESF \
            and (rubro.un_ece_code or '').strip() == sector

    def _rubro_3_1(self, cuenta, sector):
        """Código del rubro del 3.1 de una cuenta, o '' si no tiene uno válido.

        El asistente «Asignar Rubros EEFF (Tabla 34)» deja el rubro de las
        cuentas de patrimonio (50x-59x) en `pe_t34_patrimonio` —con códigos
        1D07xx, que SON del 3.1— y no en `pe_t34_esf`. Por eso se toma el
        primero que sea válido entre los tres campos (el legado incluido).
        """
        for rubro in (cuenta.pe_t34_esf, cuenta.pe_tabla34_id, cuenta.pe_t34_patrimonio):
            if self._rubro_valido(rubro, sector):
                return rubro.code
        return ''

    def _cuentas_del_balance(self, fecha, sector):
        """Una entrada por cuenta con movimientos hasta la fecha del balance.

        Una sola consulta agrupada: la suma de apuntes publicados de cada cuenta
        es la misma fuente de las cifras del Balance de comprobación nativo.
        """
        dominio = [
            ('company_id', '=', self.company_id.id),
            ('parent_state', '=', 'posted'),
            ('date', '<=', fecha),
            ('account_id', '!=', False),
        ]
        grupos = self.env['account.move.line'].sudo()._read_group(
            dominio, groupby=['account_id'], aggregates=['debit:sum', 'credit:sum'])
        cuentas = []
        for cuenta, debe, haber in grupos:
            tipo = cuenta.account_type
            cuentas.append({
                'codigo': cuenta.code or '',
                'nombre': cuenta.name or '',
                'naturaleza': fmt.naturaleza_por_tipo(tipo),
                'resultado': fmt.es_cuenta_de_resultado(tipo),
                'debe': a_centimos(debe),
                'haber': a_centimos(haber),
                'rubro': self._rubro_3_1(cuenta, sector),
            })
        cuentas.sort(key=lambda c: c['codigo'])
        return cuentas

    def _validar_rubros_asignados(self, cuentas, fecha, sector):
        """Falla antes de generar si una cuenta con saldo no tiene rubro válido.

        Omitirla en silencio dejaría el estado sin cuadrar, y el archivo pasaría
        el validador del PLE declarando un balance incompleto.
        """
        sin_rubro = [c for c in cuentas
                     if c['naturaleza'] and not c['rubro'] and c['debe'] != c['haber']]
        if not sin_rubro:
            return
        detalle = '\n'.join(
            '  • %s %s — saldo %s' % (c['codigo'], c['nombre'], _soles(c['debe'] - c['haber']))
            for c in sin_rubro[:25])
        mas = ('\n  ... y %d cuentas más' % (len(sin_rubro) - 25)) if len(sin_rubro) > 25 else ''
        raise UserError(_(
            "No se puede generar el estado de situación financiera (3.1): hay %(n)s "
            "cuenta(s) con saldo al %(fecha)s sin un rubro válido de la Tabla 34 "
            "para el 3.1 (sector %(sector)s).\n\n%(detalle)s%(mas)s\n\n"
            "Asigne el rubro en la cuenta o ejecute el asistente «Asignar Rubros "
            "EEFF (Tabla 34)» desde el plan de cuentas."
        ) % {'n': len(sin_rubro), 'fecha': fecha.strftime('%d/%m/%Y'),
             'sector': sector, 'detalle': detalle, 'mas': mas})

    # ------------------------------------------------------------------
    # Generación
    # ------------------------------------------------------------------

    def generate_report(self):
        # Los campos company-dependent de Odoo 19 (`account.account.code`) se
        # leen según la compañía ACTIVA: todo el método va anclado a la del libro.
        self = self.with_company(self.company_id)
        res = super().generate_report()
        self.ensure_one()

        fecha = datetime.date(self.year, 12, 31)
        sector = (self.company_id.sector_contable or '01').strip()
        cuentas = self._cuentas_del_balance(fecha, sector)
        self._validar_rubros_asignados(cuentas, fecha, sector)

        saldos = fmt.consolidar_rubros(cuentas)

        # Resultado de ingresos/gastos que el asiento de cierre aún no trasladó
        # al patrimonio: sin él el estado no cuadra.
        resultado = fmt.resultado_no_cerrado([c for c in cuentas if c['resultado']])
        if resultado:
            rubro = self.rubro_resultado_id
            if not self._rubro_valido(rubro, sector):
                raise UserError(_(
                    "Hay un resultado sin cerrar de S/ %(monto)s en las cuentas de "
                    "ingresos y gastos al %(fecha)s. Registre el asiento de cierre "
                    "del ejercicio o elija el «Rubro del resultado no cerrado» "
                    "(un rubro del 3.1 del sector %(sector)s) para informarlo en el "
                    "patrimonio."
                ) % {'monto': _soles(resultado), 'fecha': fecha.strftime('%d/%m/%Y'),
                     'sector': sector})
            saldos[rubro.code] = saldos.get(rubro.code, 0) + resultado

        activo, pasivo_patrimonio = fmt.totales_situacion(cuentas, resultado)
        diferencia = activo - pasivo_patrimonio
        if abs(diferencia) > 1:   # tolerancia de un céntimo
            raise UserError(_(
                "El estado de situación no cuadra al %(fecha)s: activo S/ %(activo)s, "
                "pasivo y patrimonio S/ %(pp)s (diferencia S/ %(dif)s).\n\n"
                "Revise que las cuentas tengan el tipo correcto (activo, pasivo, "
                "patrimonio, ingreso o gasto) y que no haya asientos descuadrados."
            ) % {'fecha': fecha.strftime('%d/%m/%Y'), 'activo': _soles(activo),
                 'pp': _soles(pasivo_patrimonio), 'dif': _soles(diferencia)})

        filas = fmt.filas_31(fmt.periodo_balance(self.year), sector, saldos)
        archivos = []
        if filas:
            archivos.append((0, 0, self._valores_archivo(
                '3.1', '030100', filas, CABECERAS_31)))

        self.write({
            'archivo_ids': [(5, 0, 0)] + archivos,
            'resultado_no_cerrado': resultado / 100.0,
            'total_activo': activo / 100.0,
            'total_pasivo_patrimonio': pasivo_patrimonio / 100.0,
            'diferencia_balance': diferencia / 100.0,
            'date_generated': str(fields.Datetime.now()),
        })
        return res

    def _valores_archivo(self, estructura, ple_id, filas, cabeceras):
        """Valores del registro ple.report.03.archivo de una estructura."""
        nombre = self.get_default_filename(ple_id=ple_id, tiene_datos=True)
        texto = '\r\n'.join(filas + [''])
        xlsx = self._generate_xlsx_base64_bytes(texto, nombre[2:], headers=cabeceras)
        return {
            'estructura': estructura,
            'ple_id': ple_id,
            'txt': texto,
            'txt_binary': base64.b64encode(self._codificar_txt(texto)),
            'txt_filename': nombre + '.txt',
            'xls_binary': xlsx.encode(),
            'xls_filename': nombre + '.xlsx',
        }


class PLEReport03Archivo(models.Model):
    """Un archivo (TXT + Excel) de una estructura del Libro 3.

    El libro 3 tiene más de veinte estructuras: en lugar de dos o tres campos
    binarios por cada una en el libro, cada estructura generada es un registro
    de esta tabla.
    """
    _name = 'ple.report.03.archivo'
    _description = 'PLE 03 - Archivo generado de una estructura'
    _order = 'ple_id'

    report_id = fields.Many2one(
        'ple.report.03', string='Libro', required=True, ondelete='cascade')
    estructura = fields.Char(string='Estructura', readonly=True)
    ple_id = fields.Char(string='Código del libro', readonly=True)
    txt = fields.Text(string='Contenido del TXT', readonly=True)
    txt_binary = fields.Binary(string='TXT', readonly=True)
    txt_filename = fields.Char(string='Nombre del TXT')
    xls_binary = fields.Binary(string='Excel', readonly=True)
    xls_filename = fields.Char(string='Nombre del Excel')
