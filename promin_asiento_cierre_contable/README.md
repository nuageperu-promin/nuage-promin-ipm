# promin_asiento_cierre_contable

Cierre del ejercicio y apertura del siguiente (prototipo, pendiente de validación del contador de PROMIN).

Menú: Contabilidad > Asientos > Cierre y apertura contable. Un registro por compañía y año; al generar crea y publica:

1. Cierre de resultados (31/12): cancela las cuentas de gestión (6, 7) y lleva la utilidad o pérdida a la cuenta configurada.
2. Cierre de balance (31/12): cancela las demás cuentas, con detalle por tercero y moneda en cuentas por cobrar/pagar.
3. Apertura (01/01 del año siguiente): repite los saldos del cierre de balance.

Los asientos se marcan con `es_x_cierre` / `es_x_apertura` (Solse) y se vinculan al registro de cierre (`nuage_cierre_id`). "Revertir" elimina los tres asientos.

Pendiente de definir con PROMIN: traslado del resultado a la cuenta 59, diario y numeración, separación por clases.
