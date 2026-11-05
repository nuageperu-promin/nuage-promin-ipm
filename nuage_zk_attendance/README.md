# nuage_zk_attendance — Relojes ZKTeco (ADMS) → Asistencias de Odoo 19

Recibe las marcaciones que envían los relojes ZKTeco por el protocolo ADMS
(push) y las convierte en entradas/salidas de **Asistencias** (`hr.attendance`).
No necesita IP fija ni abrir puertos en la red del cliente: el reloj llama a Odoo.

Desarrollado por Nuage Perú S.A.C. para Proveedores Mineros S.A.C.
Versión 19.0.1.0.0 (primera versión, pendiente de validar con los relojes reales).

## Relojes de PROMIN
| Equipo | Serie | Firmware | Push |
|---|---|---|---|
| MB20-VL/ID | C08E224460189 | ZMM510-NF-Ver1.0.19 | 2.0.33S |
| SenseFace M2F-LR | UFS2254801685 | ZAM70-NF28HA-Ver3.1.15 | 3.0.4S |

Hoy ambos apuntan a un servidor `18.209.x.x:8538`. **Cambiarlo los desconecta de
ese servidor**: confirmar con PROMIN quién lo administra antes de configurar.

## Puesta en marcha
1. Instalar el módulo (depende de `hr_attendance` y `mail`). Solo en `develop`
   de Odoo.sh primero.
2. **Asistencias → Configuración → Relojes marcadores → Nuevo**: nombre, número
   de serie (tal como figura en *Información del Equipo*), zona horaria
   (America/Lima) y **Confirmar**. Al confirmar, "Procesar marcaciones desde"
   toma la fecha actual para no importar el historial del reloj (editable).
3. En cada **empleado** (pestaña Configuración de RR. HH.) completar **ID en reloj**
   con el mismo ID que tiene en el equipo (exacto: "0012" ≠ "12").
4. En el reloj: *Menú → Comunicación → Servidor en la nube* (Conf. Srvr. de Nube):
   modo **ADMS**, activar **Nombre de dominio**, dirección = dominio de la base
   (sin `https://`), puerto **443**, activar **HTTPS** si el equipo lo ofrece y
   reiniciar. La pestaña *Configurar el reloj* del dispositivo muestra los valores.
5. Probar con un solo reloj y un empleado. Activar **Modo diagnóstico** si algo no
   llega (Configuración → Peticiones del reloj, requiere modo desarrollador).

## Cómo funciona
- Rutas públicas `/iclock/cdata`, `/iclock/getrequest`, `/iclock/devicecmd`,
  `/iclock/registry`, `/iclock/push`, `/iclock/ping`. Solo responden a números de
  serie registrados y **confirmados** (otro → HTTP 403, sin datos).
- Cada marcación se guarda cruda en *Asistencias → Reporting → Marcaciones del
  reloj* y se procesa al instante; un proceso programado (5 min) reintenta las
  pendientes. Reenvíos del reloj no duplican (índice único dispositivo+ID+hora).
- Estados: Pendiente, Procesada, Sin empleado (se reprocesa sola al asignar el
  ID), Duplicada, Ignorada (anterior a la fecha de inicio), **Revisar** y Error.
  La acción **Reprocesar** está en la lista y el formulario.
- Reglas (por reloj): alternar entrada/salida (o respetar el estado del reloj),
  ventana de duplicados (60 s), turno máximo (16 h) y cierre automático opcional
  de turnos olvidados. Un turno abierto más de lo permitido queda en *Revisar*:
  nunca se inventa una salida salvo que se active el cierre automático.
- Aviso en el chatter del reloj si no reporta en 15 min (parámetro
  `nuage_zk_attendance.offline_minutes`).
- Las asistencias se crean con modo `technical` y el reloj como ubicación.
  Los módulos de nómina (p. ej. `solse_pe_payroll_asistencia_ee`) leen
  `hr.attendance.check_in`/`check_out` en UTC y lo convierten a hora local.

## Por validar con los relojes reales (fase 0)
- Formato exacto de Push 2.0.33S (MB20) y 3.0.4S (SenseFace): el módulo atiende
  ambas familias de rutas, pero las respuestas están basadas en la referencia
  habitual del protocolo.
- Que el MB20 (firmware 2021) negocie HTTPS con Odoo.sh.
- Si el reloj envía `Content-Type: application/x-www-form-urlencoded`, Odoo
  podría consumir el cuerpo antes del controlador (el diagnóstico lo mostraría).
- Multi-base: Odoo.sh resuelve la base por dominio; con varias bases en un mismo
  dominio hay que fijar `db_filter`.

## Fuera de alcance (v1)
Enviar usuarios/huellas al reloj, inscripción remota, comandos al equipo,
conexión directa por IP:4370 (PyZK). No se guardan plantillas biométricas.

## Pruebas
- Lógica pura: `python3 tests/test_protocol.py` (sin Odoo).
- Odoo: `odoo-bin -d <db> -u nuage_zk_attendance --test-enable --test-tags /nuage_zk_attendance`


## Traer el historial guardado en el reloj (v19.0.1.1.0)

El reloj conserva en su memoria las marcaciones. Además del tiempo real, desde el
formulario del reloj (**Traer historial**) se pueden recuperar las de un periodo
**desde – hasta** (máximo 92 días por vez):

- **Pedirlo al reloj (por red):** Odoo le envía `DATA QUERY ATTLOG StartTime=… EndTime=…`
  en su próxima consulta (≈30–60 s) y el reloj reenvía las marcaciones del rango. Depende del
  firmware (Push 3.x); si no lo admite, responde un código negativo y queda anotado en el
  chatter y en la pestaña "Historial pedido".
- **Importar archivo attlog.dat:** descargado del reloj con una memoria USB
  (Menú → Gestión de datos → Descargar → Datos de asistencia). Sirve en cualquier modelo.

Ambas opciones: adelantan la fecha "Procesar marcaciones desde" para no ignorar el periodo,
no duplican las marcaciones que Odoo ya tiene y procesan en orden cronológico. Las tandas
grandes procesan las 300 más antiguas al recibirlas; el resto queda **pendiente** y se
procesa con el botón **Procesar pendientes** (o con la tarea programada cada 5 min).
