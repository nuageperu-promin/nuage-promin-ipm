/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { formatDateTime } from "@web/core/l10n/dates";
const { DateTime } = luxon;

import { PosOrder } from "@point_of_sale/app/models/pos_order";

patch(PosOrder.prototype, {
	setup(vals) {
		super.setup(vals);
		this.invoice_journal_id = vals.invoice_journal_id || false;
		this.custom_journal_id = vals.custom_journal_id || false;
		this.number = vals.number || false;
		this.number_ref = vals.number_ref || false;
		this.l10n_latam_document_type_id = vals.l10n_latam_document_type_id || this.l10n_latam_document_type_id || 0;
		this.invoice_payment_term_id = vals.invoice_payment_term_id || this.invoice_payment_term_id || 0;
		this.invoice_sequence_number = vals.invoice_sequence_number || 0;
		this.date_invoice = vals.date_invoice || false;
		this.pe_invoice_date = vals.pe_invoice_date || false;
	},
	
	// GETTER: QR code SUNAT - se genera dinámicamente
	get sunat_qr_code() {
		if (!this.es_cpe() || !this.number) {
			return false;
		}
		
		try {
			var qr_string = this.get_cpe_qr();
			var qrcodesingle = new window.QRCode(false, {
				width: 128, 
				height: 128, 
				correctLevel: window.QRCode.CorrectLevel.Q
			});
			qrcodesingle.makeCode(qr_string);
			let qrdibujo = qrcodesingle.getDrawing();
			return qrdibujo._canvas_base64;
		} catch(error) {
			console.error("Error generando QR SUNAT:", error);
			return false;
		}
	},
	
	check_pe_journal() {
		var client = this.getPartner();
		var doc_type = client ? client.doc_type : false;
		var l10n_latam_document_type_id = this.get_doc_type_sale();

		var journal_type = this.get_cpe_type();
		if(!journal_type){
			return [false, 'Seleccione un diario valido'];
		}
		if(journal_type == '01' && doc_type != '6') {
			return [false, 'El tipo de documento del cliente no es valido para facturas'];
		} else if(journal_type == '03' && doc_type == '6') {
			return [false, 'El tipo de documento del cliente no es valido para boletas'];
		}
		return  [true, 'OK'];
	},

	get_cpe_type() {
		var tipo_doc_venta = this.get_doc_type_sale();
		if (!tipo_doc_venta){
			return false;
		}
		var doc_type_sale = this.get_doc_type_sale_id(tipo_doc_venta);
		return doc_type_sale ? doc_type_sale.code : false;
	},

	es_cpe() {
		let tipo_doc_venta = this.get_cpe_type()
		if(tipo_doc_venta) {
			return true;
		}
		return false;
	},

	es_un_cpe() {
		var tipo_doc_venta = this.get_doc_type_sale();
		if (!tipo_doc_venta){
			return false;
		}
		var doc_type_sale = this.get_doc_type_sale_id(tipo_doc_venta);
		return doc_type_sale ? doc_type_sale.is_cpe : false;
	},

	get_cpe_qr(){
		var res = []
		res.push(this.company.vat || '');
		res.push(this.get_cpe_type() || ' ');
		res.push(this.get_number() || ' ');
		// ✅ CORREGIDO: Usar propiedades en vez de métodos inexistentes
		res.push((this.priceIncl - this.priceExcl) || 0.0);  // Total impuestos
		res.push(this.priceIncl || 0.0);  // Total con impuestos
		res.push(formatDateTime(DateTime.now(), {format: "YYYY-MM-DD"}));
		res.push(this.get_doc_type() || '-');
		res.push(this.get_doc_number() || '-');
		var qr_string = res.join('|');
		return qr_string;
	},
	
	get_l10n_latam_document_type() {
		return this.l10n_latam_document_type_id;
	},
	
	set_l10n_latam_document_type(l10n_latam_document_type) {
		this.assertEditable();
		this.update({l10n_latam_document_type_id: l10n_latam_document_type});
	},
	
	get_doc_type_sale() {
		return this.l10n_latam_document_type_id;
	},
	
	get_doc_type_sale_id(journal_id) {
		if(!this.config) {
			return false;
		}
		let doc_types = this.config.documento_venta_ids;
		if (!doc_types instanceof Array) {
			doc_types = [doc_types];
		}
		let id_doc = journal_id
		if (typeof id_doc == 'object') {
			id_doc = journal_id.id
		}
		for (var i = 0, len = doc_types.length; i < len; i++) {
			if(doc_types[i].id == id_doc) {
				return doc_types[i];
			}
		}
		return false;
	},

	set_invoice_payment_term(invoice_payment_term_id) {
		this.assertEditable();
		this.invoice_payment_term_id = invoice_payment_term_id;
	},

	get_invoice_payment_term() {
		return this.invoice_payment_term_id;
	},

	get_payment_term() {
		var plazos_pago = this.get_invoice_payment_term();
		if (!plazos_pago){
			return false;
		}
		var nombre_plazo_pago = this.pos.get_invoice_payment_term(plazos_pago);
		return nombre_plazo_pago ? nombre_plazo_pago.name : false;
	},

	set_number(number) {
		this.assertEditable();
		this.number = number;
	},

	get_number() {
		return this.number || "";
	},

	get_number_ref() {
		return this.number_ref || "";
	},

	get_doc_type() {
		var client = this.getPartner();
		if(!client) {
			return false
		}
		var doc_type = client ? client.doc_type : "";
		if(client.parent_id) {
			doc_type = client.cod_doc_rel
		}
		return doc_type;
	},

	get_doc_number() {
		var client = this.getPartner();
		var doc_number = client ? client.doc_number : "";
		if(!doc_number) {
			doc_number = client ? client.vat : "";
		}
		if(!client) {
			return "";
		}
		if(client.parent_id) {
			doc_number = client.numero_temp || ""
		}
		return doc_number;
	},

	get_amount_text() {
		// ✅ CORREGIDO: Usar propiedad en vez de método inexistente
		let monto = Math.abs(this.priceIncl || 0)
		return window.numeroALetras(monto, {
		  plural: this.currency.plural_name,
		  singular: this.currency.singular_name,
		  centPlural: this.currency.show_fraction ? this.currency.fraction_name: "",
		  centSingular: this.currency.show_fraction ? this.currency.fraction_name: ""
		})
	},
});