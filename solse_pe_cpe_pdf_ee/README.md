# solse_pe_cpe_pdf_ee — formatos PDF de comprobantes

Añade formatos de impresión para los CPE (factura, boleta, notas) y un
ticket. El formato se elige **por diario**: campo `formato_defecto`
(«Formato») del `account.journal`, vista `views/journal_view.xml`. No es un
ajuste de compañía.

| `formato_defecto` | Plantilla | Acción de reporte | Archivo |
|---|---|---|---|
| `formato_n1` (defecto) | la factura nativa (`account.report_invoice`, con lo que le añada `solse_pe_cpe_pdf` si está instalado) | — | — |
| `formato_n2` | `report_invoice_with_payments` | `report_cpe_sunat_plantilla_2` | `report/report_invoice_p2.xml` |
| `formato_n3` | `report_invoice_with_payments_m3` | `report_cpe_sunat_plantilla_3` | `report/report_invoice_p3.xml` |
| `formato_n4` | `report_invoice_with_payments_m4` | `report_cpe_sunat_plantilla_4` | `report/report_invoice_p4.xml` |
| `formato_n5` | `report_invoice_with_payments_m5` | `report_cpe_sunat_plantilla_5` | `report/report_invoice_p5.xml` |
| `formato_n6` | `report_invoice_with_payments_m6` | `report_cpe_sunat_plantilla_6` | `report/report_invoice_p6.xml` |

Aparte, el **ticket** (`cpe_print_ticket`, acción `report_invoice_ticket`,
`report/report_ticket_n1.xml`) con su propio paperformat.

El PDF que se adjunta al enviar el comprobante por correo sale del formato
del diario (`models/account_move.py`, rama de adjuntos); sin formato o con
`formato_n1`, del reporte nativo.

> Historial: este Readme decía «4 nuevos formatos» cuando el código ya
> definía seis (M-30); en el ZIP de 19.0.0.3 llegó vacío. Reescrito en
> 19.0.0.4 (L8.2) contra `models/account_move.py:27-28` y los `report/`.
