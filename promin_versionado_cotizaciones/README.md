# promin_versionado_cotizaciones

Versionado de cotizaciones (Ventas). Cronograma PROMIN: «Versionado de cotizaciones».

- Botón **Nueva versión** en cotizaciones en borrador o enviadas, con motivo opcional.
- La cotización original conserva su número (S00123); las revisiones suman sufijo: S00123-V2, S00123-V3…
- La versión nueva es una copia editable y es la única vigente. La anterior queda cancelada y marcada «Versión anterior» (solo consulta), con enlace a la vigente.
- Botón inteligente **Versiones** con toda la cadena; filtros «Solo versiones vigentes» y «Versiones anteriores».
- Una versión anterior no se puede confirmar ni volver a cotización. Un pedido ya confirmado no se versiona.

Decisión de diseño: solo el botón genera versiones (editar no crea versión).
Pendiente de validar con PROMIN: si las versiones anteriores deben ocultarse por defecto en la lista de cotizaciones.
