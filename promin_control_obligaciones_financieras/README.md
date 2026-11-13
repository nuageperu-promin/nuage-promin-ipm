# promin_control_obligaciones_financieras

**Desarrollo:** Control de obligaciones financieras (pagarés y otros) — Anexo B, 14.1
**Versión:** 19.0.1.0.0 (primera entrega para validar en Staging)

## Qué hace
- Registra pagarés, cartas fianza, leasing, descuento de facturas y otras obligaciones, con banco,
  N° de operación, moneda, monto, TEA, desembolso, vencimiento, línea de crédito y facturas financiadas.
- **Cronograma de cuotas** (capital, interés, comisión, ITF/portes). Se carga pegando el texto del banco
  (formatos Simple, BBVA y BCP) y se puede calcular el interés con la TEA: saldo × ((1+TEA)^(días/360) − 1).
- **Líneas de crédito** con utilizado y disponible, incluidas las líneas múltiples (tope compartido).
- **Flujo con roles:** Tesorería registra, el Jefe de Finanzas aprueba, Contabilidad registra desembolso y pagos, Consulta.
- **Alertas:** acción programada diaria; crea una actividad para el responsable cuando faltan N días (por compañía).
- **Reportes:** calendario de vencimientos (lista, calendario, tabla y gráfico), saldo por banco,
  intereses y comisiones por mes, parte corriente / no corriente (primeras 12 cuotas por vencer = corriente).
- **Asientos:** desembolso (banco / pasivo), pago de cuota (pasivo + interés + comisión + ITF / banco) y
  ajuste mensual por diferencia de cambio por documento. Sin devengo de intereses: se reconocen al pagar la cuota.

## Configuración (una vez)
Ajustes de la compañía → pestaña **Obligaciones financieras**: diario de asientos, cuentas de intereses,
comisiones, ITF/portes, ganancia y pérdida por diferencia de cambio, y días de anticipación de la alerta.
En cada obligación: diario del banco y cuenta del pasivo (se sugiere 4544001/4544002 para pagarés).

## Diferencia de cambio
El menú Operaciones → Ajuste por diferencia de cambio reexpresa cada obligación en moneda extranjera al tipo de
cambio de la fecha de cierre y registra la diferencia por documento. Al cancelarse la obligación el ajuste lleva
el pasivo a cero. Verificado contra el ejemplo de PROMIN (BBVA USD 50,000): coincide al centavo.
