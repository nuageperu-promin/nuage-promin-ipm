# -*- coding: utf-8 -*-
{
    'name': 'Asistencias - Relojes ZKTeco (ADMS)',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'summary': 'Recibe las marcaciones de relojes ZKTeco por ADMS (push) y '
               'las convierte en asistencias de Odoo',
    'description': """
Integración de relojes marcadores ZKTeco con Asistencias (hr_attendance).

El reloj envía sus marcaciones a Odoo (protocolo ADMS / Push); no se requiere
IP fija ni abrir puertos en la red del cliente. Cada marcación se guarda
primero cruda y luego se convierte en entrada o salida de Asistencias, sin
duplicados.

Alcance versión 1: recepción de marcaciones, dispositivos por número de
serie, ID del reloj por empleado, bitácora con reproceso, aviso de reloj sin
conexión y modo diagnóstico. No envía usuarios ni huellas al reloj.
    """,
    'author': 'Nuage Peru S.A.C.',
    'maintainer': 'Nuage Peru S.A.C.',
    'license': 'LGPL-3',
    'depends': ['hr_attendance', 'mail'],
    'data': [
        'security/zk_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/zk_device_views.xml',
        'views/zk_attendance_log_views.xml',
        'views/zk_request_log_views.xml',
        'views/hr_employee_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
