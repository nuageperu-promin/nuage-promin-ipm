# Changelog — nuage-promin-ipm

Registro de versiones y actualizaciones recibidas o desarrolladas para cada módulo.
Formato por entrada: fecha, módulo(s), motivo, acción.

---

## 2026-11-23 — promin_portal_empleado (19.0.1.0.0)
- Nuevo: Portal del Empleado (1.ª entrega). Mis datos (DNI, derechohabientes, estudios, experiencia, CUL) con aprobación de RRHH; Mis documentos (contratos publicados por RRHH y boletas PDF con registro de lectura); accesos al portal desde Empleados.

## Cómo agregar una entrada nueva

Cuando se reciba una corrección de un módulo de terceros, o se complete una
versión de un desarrollo propio:

## AAAA-MM-DD — <nombre técnico del módulo>

- **Motivo:** <qué se corrigió, mejoró o desarrolló>
- **Acción:** <qué se hizo: código actualizado, "Actualizar" ejecutado en Aplicaciones, etc.>

---

## 2026-11-26 — promin_portal_empleado (19.0.1.0.1)

- **Motivo:** las páginas del trabajador (`/my/empleado/datos`, `/my/empleado/documentos`) devolvían «Internal Server Error» en el staging de PROMIN. Reproducido en NUAGETEST: las rutas no declaraban `website=True` y el diseño del portal fallaba al armar el selector de idioma (`TypeError: object of type 'NoneType' has no len()`).
- **Acción:** se agregó `website=True` a las 9 rutas del controlador `controllers/portal.py`. Sin cambios de datos ni de vistas: basta actualizar el módulo (Aplicaciones > Portal PROMIN > Actualizar) y reiniciar. Verificado en NUAGETEST: `/my`, `/my/empleado/datos` y `/my/empleado/documentos` responden 200 con un usuario de portal.

---

## 2026-11-25 — nuage_pe_rate_fill y nuage_pe_rate_origen (19.0.1.0.0)

- **Motivo:** Alex Moreno (PROMIN) pidió pasar a PROMIN los módulos de tipo de cambio ya usados por Nuage: consultar el T.C. SUNAT de fechas sin registro y fijar el T.C. de las notas de crédito/débito según su comprobante de origen.
- **Acción:** `nuage_pe_rate_fill` (nuevo, depende de `account` y `solse_pe_rate_api`): en comprobantes en USD consulta en línea el T.C. de la fecha al cambiar fecha/moneda y al confirmar; si es fin de semana o no hay dato usa el último día hábil anterior (hasta 7 días) sin crear filas falsas, recalcula borradores cuando entra una tasa nueva y el botón «Actualizar T.C.» rellena los días hábiles faltantes de los últimos 30 días. `nuage_pe_rate_origen` (nuevo, depende de `account`, `solse_pe_accountant` y `solse_pe_rate_api`): en NC/ND en borrador (ventas y compras) toma del comprobante de origen la fecha del T.C., el T.C. mostrado, el T.C. interno (PLE/SIRE) y la tasa del asiento; no modifica notas confirmadas. Instalar ambos desde Aplicaciones (Actualizar lista de aplicaciones).

---

## 2026-11-25 — nuage_vendor_evaluation (19.0.1.0.1)

- **Motivo:** en la reunión se acordó instalar el módulo de Evaluación de Proveedores (Nuage Peru) para calificar a los proveedores con criterios ponderados, con el cumplimiento de entregas calculado desde las recepciones de compras.
- **Acción:** módulo nuevo (sobre `purchase`, `purchase_stock` y `mail`): evaluaciones por proveedor y periodo con criterios configurables, cálculo automático de entregas a tiempo, estados borrador/confirmada (solo el responsable de compras puede reabrir una confirmada; los campos quedan bloqueados al confirmar), calificación en la ficha del proveedor y reportes. Incluye pruebas automáticas (11, sin fallos). Instalar desde Aplicaciones (Actualizar lista de aplicaciones → Evaluación de Proveedores → Instalar); ver `nuage_vendor_evaluation/INSTALAR.md`.

---

## 2026-11-24 — promin_bloqueo_credito (19.0.1.2.0)

- **Motivo:** el área de ventas observó que, al exceder el cliente su línea de crédito, el bloqueo debe aplicarse sobre la generación de la orden de venta: el sistema debe permitir crear e imprimir la cotización, pero no convertirla en orden de venta.
- **Acción:** con el check activo y el cliente en su límite, la cotización ya se puede crear, editar, imprimir y enviar; solo se bloquea **Confirmar** (se oculta el botón, aparece un aviso rojo y la confirmación por otra vía se rechaza con mensaje). El check de ventas pasa a llamarse «Bloquear Orden de Venta». Compras no cambia. Actualizar el módulo desde Aplicaciones.

---

## 2026-11-24 — promin_cotizacion_formato (19.0.1.0.3)

- **Motivo:** ventas pidió un campo editable de texto «Lugar de entrega» en la cotización, que se imprima en el reporte.
- **Acción:** el campo «Lugar de entrega» (ya existente e impreso en «Condiciones de venta» de la Cotización PROMIN) se muestra ahora en el bloque **Entrega** de la cotización, debajo de «Estado de la entrega». El módulo depende además de `sale_stock`. Actualizar el módulo desde Aplicaciones.

---

## 2026-11-23 — promin_rrhh_encuestas (19.0.1.0.0)

- **Motivo:** RRHH de PROMIN envió los modelos de encuesta de clima laboral y evaluación de desempeño (90°) y pidió gestionarlos por formularios con resultados cuantitativos y cualitativos.
- **Acción:** módulo nuevo sobre `survey`. Carga la encuesta de clima (anónima, con segmentos) y la de desempeño (jefe a subordinado, por invitación); asistente para generar las evaluaciones por jefe y enviarles el enlace; resultados por empleado/área/competencia y por pregunta/segmento. Requiere instalar antes el módulo estándar Encuestas.

---

## 2026-11-22 — promin_cotizacion_lista_materiales (19.0.1.2.0) y promin_cotizacion_formato (19.0.1.0.2)

- **Motivo:** PROMIN pidió elegir, al confeccionar la lista de materiales (BoM), qué componentes se imprimen en la cotización; y la cotización «Cotización PROMIN» separaba en páginas distintas la cabecera y el detalle cuando la lista de materiales era larga.
- **Acción:** `promin_cotizacion_lista_materiales`: nuevo check «Imp. Cot» en cada componente de la BoM (por defecto desactivado); la cotización imprime solo los componentes con el check activo. `promin_cotizacion_formato`: la lista de materiales se imprime fila por fila dentro de la tabla de ítems, de modo que continúa en la página siguiente en vez de saltar completa y dejar la primera página casi vacía. Actualizar ambos módulos desde Aplicaciones y marcar «Imp. Cot» en las BoM que corresponda.

---

## 2026-11-22 — promin_ejecutivo_tecnico (19.0.1.0.0)

- **Motivo:** PROMIN pidió registrar un «Ejecutivo Técnico» por cotización/orden de venta, además del Vendedor, y verlo en las listas.
- **Acción:** módulo nuevo (depende de `sale`). Agrega el campo Ejecutivo Técnico (usuario interno) debajo del Vendedor en Otra información, como columna en las listas de cotizaciones y órdenes de venta, y en búsqueda/agrupación. Instalar desde Aplicaciones.

---

## 2026-11-22 — promin_bloqueo_credito (19.0.1.1.0)

- **Motivo:** PROMIN pidió un límite de crédito también para compras: no colocar órdenes de compra a un proveedor por encima del límite establecido, con la misma lógica de aviso y bloqueo que ya existe en ventas.
- **Acción:** el módulo ahora depende también de `purchase`. En el contacto: «Límite de crédito» pasa a llamarse «Límite de Crédito Ventas» y se agregan «Límite de Crédito Compras» (casilla + monto, como en ventas) y el check «Bloquear Cotización/Orden de Compra»; el check de ventas se renombra «Bloquear Cotización/Orden de Venta». En la cotización/orden de compra aparece un aviso amarillo cuando deuda pendiente al proveedor + órdenes confirmadas sin facturar + la orden actual superan el límite; con el check activo el aviso es rojo, no se puede grabar y se ocultan Enviar, Confirmar y Aprobar (cancelar sigue permitido). Actualizar el módulo desde Aplicaciones.

---

## 2026-11-17 — promin_bloqueo_credito (19.0.1.0.0)

- **Motivo:** PROMIN pidió que, cuando un cliente llegó a su límite de crédito, no se pueda grabar ni continuar su cotización/orden de venta (hoy Odoo solo muestra un aviso).
- **Acción:** módulo nuevo (depende de `sale` y `account`). Agrega en el contacto, bajo «Límites de crédito», el check «Bloquear generación de Cotización/Orden de Venta». Con el check activo y el límite alcanzado, la cotización no se puede grabar, se ocultan Enviar y Confirmar y se rechaza confirmar o enviar por otra vía; cancelar sigue permitido. Instalar desde Aplicaciones.

---

## 2026-11-17 — promin_cotizacion_formato (19.0.1.0.1) y promin_cotizacion_lista_materiales (19.0.1.1.0)

- **Motivo:** Proveedores Mineros entregó su modelo de cotización y Alex Moreno pidió que la lista de materiales impresa use la versión elegida en la línea del ítem.
- **Acción:** `promin_cotizacion_formato` (nuevo) agrega el reporte «Cotización PROMIN» en el menú Imprimir de la cotización, con el formato del modelo: encabezado con logo e ISO, datos del cliente y del vendedor, tabla de ítems, plazos de entrega por ítem, totales, condiciones de venta, bloque IMPORTANTE y datos bancarios (BCP, BBVA, Scotiabank) tomados de las cuentas de la compañía. Agrega en la cotización los textos editables Lugar de entrega, Tolerancia, Términos de venta e IMPORTANTE. `promin_cotizacion_lista_materiales` 1.1.0: la lista de materiales impresa usa la versión elegida en la línea (`bom_id`) y muestra su referencia; si no hay una elegida, usa la BoM por defecto. Instalar `promin_cotizacion_formato` y actualizar `promin_cotizacion_lista_materiales` desde Aplicaciones; registrar las cuentas bancarias de la compañía.

---

## 2026-11-13 — promin_cotizacion_lista_materiales (19.0.1.0.0)

- **Motivo:** el equipo de Ventas de PROMIN necesita, en algunas cotizaciones de tableros, imprimir debajo de cada producto su lista de materiales (BoM).
- **Acción:** módulo nuevo (depende de `sale` y `mrp`). Agrega en la cotización el check «Se imprime Lista de Materiales». Si está activo, el PDF estándar imprime bajo cada producto con BoM sus componentes de primer nivel (código, descripción, cantidad multiplicada por lo cotizado y unidad), sin precios. Con el check apagado el PDF no cambia. Instalar desde Aplicaciones.

---

## 2026-11-13 — solse_pe_vat (19.0.1.4), solse_pe_edi (19.0.1.5), solse_pe_cpe_guias_transp (19.0.1.0.5), solse_pe_sire_ventas (19.0.0.14), solse_pe_sire_compra (19.0.2.7), solse_pe_accountant (19.0.1.5) y solse_pe_cpe_pos (19.0.1.13)

- **Motivo:** al actualizar el submódulo en Staging, Odoo 19 mostraba avisos (WARNING) en el log: dos campos de `res.partner` con la misma etiqueta «Estado», un campo traducible y almacenado (`account.move.line.nombre_producto`) que no se calcula bien en todos los idiomas, y dos campos «Transbordo programado» repetidos entre módulos de guías, campos con etiqueta repetida en SIRE («Periodo» y «Nombre de archivo zip»), alertas de accesibilidad en el asistente de diagnóstico de la Tabla 34 y cuatro asistentes de POS sin reglas de acceso.
- **Acción:** `solse_pe_vat`: la etiqueta de `state_sunat` pasa a «Estado SUNAT». `solse_pe_edi`: `nombre_producto` deja de almacenarse (solo se usa en una línea comentada de un reporte; la columna existente no se borra). `solse_pe_cpe_guias_transp`: la etiqueta de `pe_grt_transbordo_programado` pasa a «Transbordo programado (GRT)». `solse_pe_sire_ventas` y `solse_pe_sire_compra`: `periodo_id` pasa a «Reporte de periodo» y `datas_zip_fname_02` a «Nombre de archivo zip (8.5)». `solse_pe_accountant`: las alertas del asistente de diagnóstico Tabla 34 llevan `role="status"`. `solse_pe_cpe_pos`: se agregan reglas de acceso (usuarios internos) para los asistentes `sale.advance.pos.order`, `pos.return.picking`, `pos.return.picking.line` y `pe.pos.recover.wizard`. No cambia datos ni funcionalidad. Actualizar los siete módulos desde Aplicaciones.

---

## 2026-11-13 — promin_control_obligaciones_financieras (19.0.1.0.1)

- **Motivo:** PROMIN pidió el control de obligaciones financieras (pagarés y otros) con alertas de vencimiento, vinculado al registro contable (Anexo B, 14.1). Alicia Quispe entregó el listado de pagarés, los cronogramas del BBVA y del BCP, el tratamiento contable y los ejemplos de asientos.
- **Acción:** módulo nuevo (depende de `account` y `mail`). Registra pagarés, cartas fianza, leasing, descuento de facturas y otras obligaciones, con cronograma de cuotas que se carga pegando el texto del banco (formatos simple, BBVA y BCP), líneas de crédito con utilizado y disponible, y alertas diarias por actividad. Reportes: calendario de vencimientos, saldo por banco, intereses y comisiones por mes y parte corriente / no corriente. Genera los asientos de desembolso, pago de cuota (pasivo, interés, comisión e ITF contra banco) y ajuste mensual por diferencia de cambio por documento, sin devengo de intereses. Roles: Tesorería, Jefe de Finanzas (aprueba), Contabilidad y Consulta. Validado en NUAGETEST con el pagaré BCP en soles y el BBVA en dólares: los asientos coinciden con los ejemplos de PROMIN. Tras instalar desde Aplicaciones, configurar en la compañía (pestaña «Obligaciones financieras») el diario y las cuentas de intereses, comisiones, ITF y diferencia de cambio.

---

## 2026-11-11 — promin_bimoneda_antiguedad (19.0.1.0.1) y promin_tableros_gerencia (19.0.0.3.0)

- **Motivo:** PROMIN pidió que «Cuenta por cobrar vencida» y «Cuenta por pagar vencida» se puedan ver en soles o en dólares, igual que los demás reportes bimoneda. También pidió llegar al nivel de documento en los tableros.
- **Acción:** `promin_bimoneda_antiguedad` (módulo nuevo; depende de `account_reports` y `promin_bimoneda_pen_usd`) crea las variantes «(USD)» y «(SOL)» de ambos reportes; el saldo vencido en dólares se calcula al tipo de cambio del movimiento y el símbolo es US$. `promin_tableros_gerencia` 0.3.0 agrega agrupación por pedido, comprobante u orden de compra, por producto, y un botón para abrir el documento desde la lista. Instalar el primero desde Aplicaciones y actualizar el segundo.

---

## 2026-11-08 — promin_tableros_gerencia (19.0.0.2.0, prototipo)

- **Motivo:** PROMIN pidió tableros gerenciales en dólares (Anexo B, 14.4): pedidos, pedidos vs facturación, pendientes por atender, rentabilidad y control de compras.
- **Acción:** módulo nuevo (depende de `sale`, `sales_team`, `account`, `purchase` y `sale_margin`), con menú «Tableros PROMIN» y 9 tableros sobre tres vistas SQL (pedidos, facturación y compras) convertidas a USD al tipo de cambio de la fecha. Agrega al cliente los campos «Empresa relacionada» y «Sector (tableros)», y al pedido de venta el «Integrador» (interno o externo). Prototipo para validar criterios en la reunión con PROMIN; faltan mercado, marca, foto mensual de pendientes y rentabilidad por lote. Instalar desde Aplicaciones.

---

## 2026-11-06 — promin_libros_impresos (19.0.1.0.2)

- **Motivo:** PROMIN pidió el Libro Diario (5.1) y el Libro Mayor (6.1) impresos en PDF, con el formato clásico de sus modelos.
- **Acción:** módulo nuevo (depende de `account` y `solse_pe_accountant`). Se usa desde Contabilidad → Reportes → «Libros contables impresos»: período, folio inicial y cuentas opcionales. No reemplaza a los libros electrónicos PLE; usa el mismo libro, CUO y correlativo para que ambos coincidan. Instalar desde Aplicaciones.

---

## 2026-11-06 — solse_pe_payroll_renta5 (19.0.1.0.0)

- **Motivo:** mostrar paso a paso cómo se calculó la retención de renta de 5ta categoría de cada recibo (regla R5TA_001 de `solse_pe_payroll`), para revisión del contador y del trabajador.
- **Acción:** módulo nuevo (depende de `solse_pe_payroll`); no modifica la regla ni el cálculo de la nómina. Agrega la pestaña «Renta de 5ta» en el recibo, la lista «Detalle de Renta de 5ta» y un PDF. Instalar desde Aplicaciones y recalcular las hojas para generar el detalle.

---

## 2026-11-04 — promin_versionado_cotizaciones (19.0.1.0.0)

- **Motivo:** desarrollo del cronograma «Versionado de cotizaciones»: cada revisión conserva el número con sufijo (S00123, S00123-V2…), solo la última versión sigue activa y las anteriores quedan como referencia navegable.
- **Acción:** módulo nuevo (depende de `sale`). Botón manual «Nueva versión» con motivo opcional; la versión anterior se cancela y queda bloqueada para confirmar o volver a cotización. Instalar desde Aplicaciones.

---

## 2026-11-03 — nuage_pe_retencion (19.0.2.0.0)

- **Motivo:** PROMIN solicita que el Comprobante de Retención viaje a la OSE Nubefact igual que las facturas: generación del XML UBL 2.0 (Retention-1), firma, envío (sendBill), lectura del CDR, estados en el comprobante y envío automático al emitir (más reintento por cron cada 15 min).
- **Acción:** Desarrollo nuevo; depende de `solse_pe_cpe`. Activar "Enviar retenciones a la OSE" en la empresa. Las retenciones anteriores quedan como "No enviado". Actualizar el módulo desde Aplicaciones.

---

## 2026-11-03 — python_deps/pysimplesoap (versión 1.16.2.post1)

- **Motivo:** tras el cambio de HTTPS, Staging seguía mostrando el mismo error (`fixer() missing 3 required positional arguments`). Como la copia corregida declaraba la misma versión (1.16.2) que la ya instalada, `pip` la daba por satisfecha y no la reinstalaba.
- **Acción:** la copia pasa a declarar la versión `1.16.2.post1`, de modo que `pip` la reinstale al actualizar. Sin otros cambios de código.

---

## 2026-11-03 — python_deps/pysimplesoap (conexión HTTPS)

- **Motivo:** en Staging, el envío a la OSE llegaba a abrir la conexión pero fallaba con `fixer() missing 3 required positional arguments: 'key_file', 'cert_file', and 'check_hostname'`. PySimpleSOAP 1.16.2 compara versiones de httplib2 como texto (`"0.20.4" <= "0.7.7"` es verdadero) y aplica un parche de httplib2 de 2012 que reemplaza `http.client.HTTPSConnection.__init__` y rompe todo HTTPS.
- **Acción:** en `python_deps/pysimplesoap/pysimplesoap/transport.py` las versiones se comparan numéricamente (tercer cambio mínimo sobre 1.16.2). Sin cambios en Solse. Probado con una llamada HTTPS real a un servidor TLS local. Requiere actualizar el submódulo y reconstruir en Staging.

---

## 2026-11-03 — python_deps (renombre de carpeta)

- **Motivo:** la carpeta `vendor/` en la raíz del repo hacía fallar la compilación de estilos de Odoo (`@import "vendor/rfs"` de Bootstrap se resolvía contra ella: "File to import not found or unreadable: .../nuage-promin-ipm/vendor/rfs", bundle `web.assets_web`), dejando la interfaz sin estilos.
- **Acción:** se renombra a `python_deps/` (sin otro cambio de contenido) y se ajusta `requirements.txt`. Requiere actualizar el submódulo y reconstruir dependencias en Staging.

---

## 2026-11-03 — requirements.txt (pysimplesoap, corrección)

- **Motivo:** el cambio del 2026-11-02 (`PySimpleSOAP==1.16.2` de PyPI) no se pudo instalar en Staging (Odoo.sh, Python 3.12): "Could not install dependencies (see pip.log)". El `setup.py` de esa versión importa el paquete y este usa `inspect.getargspec`, eliminado en Python 3.11.
- **Acción:** se incluye en `python_deps/pysimplesoap/` una copia de PySimpleSOAP 1.16.2 con dos cambios mínimos (`transport.py`: `getargspec` -> `getfullargspec`; `setup.py` sin importar el paquete) y `requirements.txt` la instala desde este mismo repositorio. Comportamiento idéntico a 1.16.2. No se modifica código de Solse. Requiere reconstruir/reinstalar dependencias en Staging.

---

## 2026-11-02 — requirements.txt (pysimplesoap)

- **Motivo:** en Staging, el envío de comprobantes a la OSE fallaba en todos los casos con `unsupported operand type(s) for +: 'NoneType' and 'str'`. El traceback apuntaba a `pysimplesoap/client.py:243` (`soap_action = self.action + method`), que es la versión del fork `nuageperu-promin/pysimplesoap@master` que pedía este archivo. Solse (`solse_pe_cpe`) espera el comportamiento de la versión pública 1.16.2 (cabecera SOAPAction solo si `action` no es None), que es la que corre en los servidores de pruebas donde el envío funciona.
- **Acción:** se reemplaza el fork por `PySimpleSOAP==1.16.2`. No se modifica código de Solse ni el fork. Requiere reconstruir/reinstalar dependencias en Staging.

---

## 2026-10-28 — Paquete: estados financieros en bimoneda + cierre y apertura contable

- **promin_bimoneda_pen_usd 19.0.1.2.2** (actualización): agrega el Balance de Comprobación en dos variantes, «(SOL)» y «(USD)». El saldo USD de cada apunte se guarda con 6 decimales y sin redondeo por línea, para que la balanza en dólares cuadre en 0.00. Al actualizar, un script de migración recalcula el USD de los apuntes existentes (puede tardar en bases grandes: actualizar fuera de horario).
- **promin_bimoneda_flujo 19.0.1.0.1** (nuevo): Estado de Flujos de Efectivo en dos variantes «(SOL)» y «(USD)». En USD, la línea de diferencia se rotula «Diferencia por tipo de cambio» (efecto de convertir con el tipo de cambio de la factura y del pago). Instalar después de la bimoneda.
- **promin_estado_patrimonio 19.0.1.0.1** (nuevo): Estado de Cambios en el Patrimonio en soles y dólares (columnas del PCGE: capital, acciones de inversión, capital adicional, resultados no realizados, excedente de revaluación, reservas, resultados acumulados). Excluye los asientos generados por el cierre y apertura. Depende de la bimoneda y del cierre y apertura.
- **promin_asiento_cierre_contable 19.0.1.0.1** (nuevo, prototipo): genera, por compañía y año, el cierre de resultados, el cierre de balance y la apertura del ejercicio siguiente (detalle por tercero y moneda en cuentas por cobrar/pagar). Menú: Contabilidad > Asientos > Cierre y apertura contable. Pendiente de validación del contador de PROMIN: traslado del resultado a la cuenta 59, diario y numeración.
- **Limpieza de warnings (reportados por PROMIN en el build de Odoo.sh)**, sin cambios de lógica: `solse_pe_cpe` separa el cálculo del campo no almacenado `origin_doc_id` del de `origin_doc_code`/`origin_doc_number` (warnings de `compute_sudo` y `store` inconsistentes); se diferencian las etiquetas duplicadas de campos en `solse_pe_accountant` (`parent_move_type`), `solse_pe_purchase` y `solse_pe_sire_compra` (`tipo_afectacion_compra`); `promin_asiento_cierre_contable` usa `models.Constraint` en lugar de `_sql_constraints`. Queda pendiente el warning de `nombre_producto` (campo relacionado, almacenado y traducible en `solse_pe_edi`), que requiere migrar la columna y probar facturas.
- **nuage_pe_oc 19.0.1.1.2**: solo cambia el título de la pestaña en la compañía («Órdenes Compra»).
- **nuage_pe_factura_pdf 19.0.1.1.2**: título de la pestaña («Facturas») y dos ajustes al formato de factura pedidos por PROMIN: «Guía de Remisión - Remitente» imprime solo el número de la guía de remisión (vacío si no existe, ya no el número de entrega de almacén) y «Orden de Compra» imprime el campo «Referencia del cliente» de la factura (en blanco en notas de crédito y débito).
- **Acción:** actualizar el submódulo al commit indicado en el correo, y en este orden: actualizar `nuage_pe_oc` y `nuage_pe_factura_pdf`; actualizar `promin_bimoneda_pen_usd`; instalar `promin_asiento_cierre_contable`, `promin_bimoneda_flujo` y por último `promin_estado_patrimonio`. Requiere tipos de cambio PEN/USD cargados.

---

## 2026-10-28 — promin_bimoneda_pen_usd (nuevo, 19.0.1.1.1, prototipo)

- **Motivo:** desarrollo "Bimoneda (PEN/USD)": estados financieros valorizados en soles y dólares.
- **Acción:** módulo nuevo. Agrega el campo almacenado `nuage_balance_usd` en los apuntes (conversión con el tipo de cambio de la tabla de Odoo) y habilita las columnas PEN y USD en el Balance General (PE) y el Estado de Resultados (PE), en pantalla, PDF y XLSX. Al instalar, Odoo calcula el campo para todos los apuntes existentes: instalar fuera de horario. Requiere cotizaciones PEN/USD cargadas en `res.currency`. Alcance actual: solo conversión; pendientes la moneda de transacción original con diferencia de cambio, la valuación de Inventario, balanza de comprobación, estado de cambios en el patrimonio y flujo de efectivo.

---

## 2026-10-28 — solse_pe_* (mantenimiento: warnings del build)

- **Motivo:** el build del staging salía en naranja por warnings del log: falta de `author` en los manifests y el import obsoleto `odoo.osv`.
- **Acción:** se agrega `'author': 'Nuage Peru SAC'` en los 23 manifests de `solse_pe_*` y se elimina el import sin uso `from odoo.osv import expression` en `solse_pe_cpe/models/account_tax.py` y `solse_pe_edi/models/res_partner.py`. Sin cambios de lógica ni de versión: no requiere actualizar módulos. Quedan pendientes los warnings de `origin_doc_*` (compute_sudo/store) y `nombre_producto`, que requieren pruebas de notas de crédito/débito.

---

## 2026-10-28 — nuage_pe_retencion (nuevo, 19.0.1.1.3)

- **Motivo:** PROMIN, como agente de retención, retendrá el IGV al pagar a proveedores. Se toma como modelo el comprobante RT08-00002911 (factura en dólares).
- **Acción:** módulo nuevo. La retención se decide al registrar el pago (suma de facturas del mismo proveedor; umbral de S/ 700 en soles; tasa 3%) y reemplaza, por compañía, la retención que Solse calcula al validar la factura de compra. Soporta facturas en USD: tipo de cambio de la tabla de Odoo a la fecha de pago, retención registrada en soles. Genera el comprobante de retención con serie y correlativo propios (estado borrador/emitido/cancelado) y su PDF con el formato de PROMIN, más el reporte "Retenciones por proveedor". Instalar (depende de `solse_pe_edi` y `solse_pe_accountant`). Después, en Ajustes > Compañías > pestaña "Retenciones": activar "Retener IGV al pagar", tasa, umbral, serie y correlativo inicial (confirmar con PROMIN: RT08 desde 2912 u otra serie) y la cuenta de IGV retenido por pagar (confirmar con el contador). No envía el comprobante a SUNAT: la emisión electrónica por Nubefact/Bizlinks queda para una segunda etapa. Probado en promindemo con facturas en soles y en dólares.

---

## 2026-10-28 — nuage_pe_guia_pdf (corrección, 19.0.1.0.2)

- **Motivo:** Odoo.sh rechazó el módulo ("manifest has an invalid syntax"): el `__manifest__.py` se subió vacío en el commit anterior.
- **Acción:** manifest restaurado. Actualizar el submódulo y luego instalar `nuage_pe_guia_pdf`. `nuage_pe_oc` no cambia.

---

## 2026-10-27 — nuage_pe_oc (19.0.1.1.1) y nuage_pe_guia_pdf (nuevo, 19.0.1.0.2)

- **Motivo:** observaciones de PROMIN tras la demostración. (1) El "Tipo de OC" pasa a 7 tipos con numeración propia: PMA Activo, PMC Consumibles, PMI Importación, PML Local, PMS Stock, PMT Tableros, SRV Servicios. (2) El PDF se separa en dos formatos independientes del tipo: "Orden de Compra Local (PROMIN)" y "Orden de Compra Importación (PROMIN)". (3) Columna, filtros y agrupación por Tipo de OC en la lista y búsqueda. (4) Nuevo módulo con el formato PDF de la guía de remisión remitente (transporte privado y público).
- **Acción:** `nuage_pe_oc` incluye migración: las OC con tipo "local" pasan a PMS y las de "importación" a PMI, conservando secuencias y contadores. Las secuencias nuevas (PMA, PMC, PML, PMT, SRV) empiezan en 1: ajustar el número inicial con PROMIN en Ajustes > Técnico > Secuencias. Para `nuage_pe_oc` usar **Actualizar** y para `nuage_pe_guia_pdf` **Instalar** (depende de `solse_pe_cpe_guias`). Probado en promindemo.

---

## 2026-10-23 — nuage_pe_oc y nuage_pe_factura_pdf (nuevos, 19.0.1.0.0 y 19.0.1.1.0)

- **Motivo:** formatos PDF de PROMIN enviados por Alicia Quispe: orden de compra local (PMS) e importación (PMI), factura electrónica y notas de crédito/débito.
- **Acción:** módulos nuevos en rama `feature/oc-factura-pdf`, probados en promindemo (factura y notas confirmadas; OC revisadas contra los PDF originales). Instalar primero en *develop*. `nuage_pe_oc` agrega el campo "Tipo de OC" y las secuencias PMS/PMI (ajustar el número inicial con PROMIN); ambos módulos añaden una pestaña en la compañía con los textos fijos editables. Dependen de `purchase` y de `solse_pe_cpe_pdf_ee`.

---

## 2026-11-04 — nuage_zk_attendance (19.0.1.1.0)

- **Motivo:** PROMIN necesita datos de prueba: los relojes guardan marcaciones en su memoria y se pidió poder traerlas por rango de fechas, además del tiempo real.
- **Acción:** botón "Traer historial" en el reloj (pedido por red con `DATA QUERY ATTLOG` o importación de `attlog.dat`), comandos al reloj (`getrequest`/`devicecmd`), botón "Procesar pendientes", procesamiento por tandas. 20 pruebas automáticas pasan. Pendiente: validar el comando con el SenseFace y el MB20 reales.

---

## 2026-10-22 — nuage_zk_attendance

- **Motivo:** probado en promindemo (handshake, entrada/salida, duplicado). El formulario mostraba puerto 80 y sin HTTPS porque `web.base.url` queda en http detrás del proxy.
- **Acción:** la pestaña "Configurar el reloj" ahora indica HTTPS/443 para cualquier servidor no local.

---

## 2026-10-21 — nuage_zk_attendance (nuevo, 19.0.1.0.0)

- **Motivo:** integrar los 2 relojes ZKTeco de PROMIN (MB20-VL/ID y SenseFace
  M2F-LR, ADMS) con Asistencias de Odoo 19 en Odoo.sh.
- **Acción:** módulo nuevo en rama `feature/zk-attendance` (no está en `main`).
  Instalar primero en el entorno *develop*; ver `nuage_zk_attendance/README.md`.
  Antes de apuntar los relojes a Odoo, confirmar con PROMIN quién administra el
  servidor actual (18.209.x.x:8538).
