import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { _t } from "@web/core/l10n/translation";

patch(PosStore.prototype, {
	async setup(env, deps) {
		await super.setup(env, deps);
		this.doc_types = [];
		this.invoice_payment_term_ids = [];
		this.l10n_latam_document_type_ids = [];
		this.doc_type_sale_by_id = {};
		this.invoice_payment_term_by_id = {};
		this.partner_states = [
			{'code': 'ACTIVO', 'name':'ACTIVO'},
			{'code': 'BAJA DE OFICIO', 'name':'BAJA DE OFICIO'},
			{'code': 'BAJA PROVISIONAL', 'name':'BAJA PROVISIONAL'},
			{'code': 'SUSPENSION TEMPORAL', 'name':'SUSPENSION TEMPORAL'},
			{'code': 'INHABILITADO-VENT.UN', 'name':'INHABILITADO-VENT.UN'},
			{'code': 'BAJA MULT.INSCR. Y O', 'name':'BAJA MULT.INSCR. Y O'},
			{'code': 'PENDIENTE DE INI. DE', 'name':'PENDIENTE DE INI. DE'},
			{'code': 'OTROS OBLIGADOS', 'name':'OTROS OBLIGADOS'},
			{'code': 'NUM. INTERNO IDENTIF', 'name':'NUM. INTERNO IDENTIF'},
			{'code': 'ANUL.PROVI.-ACTO ILI', 'name':'ANUL.PROVI.-ACTO ILI'},
			{'code': 'ANULACION - ACTO ILI', 'name':'ANULACION - ACTO ILI'},
			{'code': 'BAJA PROV. POR OFICI', 'name':'BAJA PROV. POR OFICI'},
			{'code': 'ANULACION - ERROR SU', 'name':'ANULACION - ERROR SU'},
		];
		this.partner_conditions = [
			{'code': 'HABIDO', 'name':'HABIDO'},
			{'code': 'NO HALLADO', 'name':'NO HALLADO'},
			{'code': 'NO HABIDO', 'name':'NO HABIDO'},
			{'code': 'PENDIENTE', 'name':'PENDIENTE'},
			{'code': 'NO HALLADO SE MUDO D', 'name':'NO HALLADO SE MUDO D'},
			{'code': 'NO HALLADO NO EXISTE', 'name':'NO HALLADO NO EXISTE'},
			{'code': 'NO HALLADO FALLECIO', 'name':'NO HALLADO FALLECIO'},
			{'code': 'NO HALLADO OTROS MOT', 'name':'NO HALLADO OTROS MOT'},
			{'code': 'NO APLICABLE', 'name':'NO APLICABLE'},
			{'code': 'NO HALLADO NRO.PUERT', 'name':'NO HALLADO NRO.PUERT'},
			{'code': 'NO HALLADO CERRADO', 'name':'NO HALLADO CERRADO'},
			{'code': 'POR VERIFICAR', 'name':'POR VERIFICAR'},
			{'code': 'NO HALLADO DESTINATA', 'name':'NO HALLADO DESTINATA'},
			{'code': 'NO HALLADO RECHAZADO', 'name':'NO HALLADO RECHAZADO'},
			{'code': '-', 'name':'NO HABIDO'},
		];
	},
	
	async processServerData() {
		await super.processServerData(...arguments);
		
		// Acceder a los datos mediante this.data.models
		const identifications = this.data.models['l10n_latam.identification.type']?.getAll() || [];
		this.doc_code_by_id = {};
		
		identifications.forEach((doc) => {
			this.doc_code_by_id[doc.id] = doc.l10n_pe_vat_code;
		});
		this.doc_types = identifications;

		const plazos_pago = this.data.models['account.payment.term']?.getAll() || [];
		this.invoice_payment_term_ids = plazos_pago;

		const documentos_venta = this.data.models['l10n_latam.document.type']?.getAll() || [];
		this.l10n_latam_document_type_ids = documentos_venta;

		this.provincias = this.data.models["res.city"]?.getAll() || [];
		this.distritos = this.data.models["l10n_pe.res.city.district"]?.getAll() || [];
	},
	
	get_doc_type_sale_id(journal_id) {
		let doc_types = this.l10n_latam_document_type_ids;
		if (!Array.isArray(doc_types)) {
			doc_types = [doc_types];
		}
		for (var i = 0, len = doc_types.length; i < len; i++) {
			this.doc_type_sale_by_id[doc_types[i].id] = doc_types[i];
		}
		return this.doc_type_sale_by_id[journal_id];
	},
	
	get_invoice_payment_term(item_id) {
		let plazos_pago = this.invoice_payment_term_ids;
		if (!Array.isArray(plazos_pago)) {
			plazos_pago = [plazos_pago];
		}
		for (var i = 0, len = plazos_pago.length; i < len; i++) {
			this.invoice_payment_term_by_id[plazos_pago[i].id] = plazos_pago[i];
		}
		return this.invoice_payment_term_by_id[item_id];
	},
	
	validate_pe_doc(doc_type, doc_number) {
		if (!doc_type || !doc_number){
			return false;
		}
		if (doc_number.length==8 && doc_type=='1') {
			return true;
		}
		else if (doc_number.length==11 && doc_type=='6') {
			var vat = doc_number;
			var factor = '5432765432';
			var sum = 0;
			var dig_check = false;
			if (vat.length != 11){
				return false;
			}
			try{
				parseInt(vat);
			}
			catch(err){
				return false; 
			}
			
			for (var i = 0; i < factor.length; i++) {
				sum += parseInt(factor[i]) * parseInt(vat[i]);
			} 

			var subtraction = 11 - (sum % 11);
			if (subtraction == 10){
				dig_check = 0;
			}
			else if (subtraction == 11){
				dig_check = 1;
			}
			else{
				dig_check = subtraction;
			}
			
			if (parseInt(vat[10]) != dig_check){
				return false;
			}
			return true;
		}
		else if (doc_number.length>=3 && ['0', '4', '7', 'A'].indexOf(doc_type)!=-1) {
			return true;
		}
		else if (doc_type.length>=2) {
			return true;
		}
		else {
			return false;
		}
	},
	
	getReceiptHeaderData(order) {
		let texto = this.get_cashier()?.name;
		try {
			texto = order.getCashierName() || this.get_cashier()?.name;
		} catch (error) {
			// Silenciar error
		}
		return {
			company: this.company,
			cashier: _t("Served by %s", texto),
			header: this.config.receipt_header,
		};
	},

	/*
	 * =====================================================================
	 * Override pos_loyalty.postProcessLoyalty.
	 *
	 * Tras la sincronización de la orden, hace un search_read estándar a
	 * `loyalty.card` para obtener las gift_cards / ewallets creadas en esta
	 * orden y las guarda en `order.solse_gift_cards` (propiedad propia).
	 *
	 * Decidimos NO modificar `order.new_coupon_info` (campo nativo de
	 * pos_loyalty) porque mutarlo después del flujo del super genera
	 * conflictos con el render de Owl (VToggler.mount errors). En su lugar
	 * almacenamos las cards en una propiedad propia y las renderizamos en
	 * nuestro propio XML del receipt, sin tocar el template nativo.
	 *
	 * Usamos searchRead (método ORM estándar, siempre disponible) en lugar
	 * de un endpoint custom — así no depende de que Python recargue la
	 * clase en memoria al hacer update de módulo.
	 * =====================================================================
	 */
	async postProcessLoyalty(order) {
		const superMethod = super.postProcessLoyalty;
		if (superMethod) {
			await superMethod.call(this, order);
		}

		// Inicializar la propiedad por si no existe
		if (!order) return;
		order.solse_gift_cards = order.solse_gift_cards || [];

		// Si la orden no tiene id real (no se sincronizó), no hay nada que pedir
		if (!order.id || order.id < 0) {
			return;
		}

		// Si pos_loyalty no está disponible en el cache, no hay programas que mirar
		if (!this.models["loyalty.card"]) {
			return;
		}

		try {
			const cards = await this.data.searchRead(
				"loyalty.card",
				[
					["source_pos_order_id", "=", order.id],
					["program_id.program_type", "in", ["gift_card", "ewallet"]],
				],
				["code", "program_id", "expiration_date", "points"]
			);
			if (!cards || !cards.length) {
				return;
			}

			// Reemplazar (no acumular) — esta orden tiene exactamente estas cards
			order.solse_gift_cards = cards
				.filter((c) => c.code)
				.map((c) => ({
					code: c.code,
					program_name: Array.isArray(c.program_id) ? c.program_id[1] : "",
					expiration_date: c.expiration_date || false,
					points: c.points || 0,
				}));

			console.info(
				"[solse_pe_cpe_pos] gift cards guardadas en order.solse_gift_cards:",
				order.solse_gift_cards.map((a) => a.code)
			);
		} catch (error) {
			console.warn(
				"[solse_pe_cpe_pos] No se pudo obtener gift cards de la orden:",
				error
			);
		}
	},
});