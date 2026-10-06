/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { onMounted, useState } from "@odoo/owl";  // ✅ AGREGAR useState
import { ConnectionLostError, RPCError, rpc } from "@web/core/network/rpc";
import { serializeDateTime } from "@web/core/l10n/dates";
import { useService } from "@web/core/utils/hooks";
import { handleRPCError } from "@point_of_sale/app/utils/error_handlers";

var ejecutando = false;

patch(PaymentScreen.prototype, {
	setup() {
		super.setup(...arguments);
		this.orm = useService("orm");
		this.notification = useService("notification");
		
		// ✅ NUEVO: Estado reactivo para tipo de documento seleccionado
		this.docState = useState({
			selectedDocType: null
		});
			
		// Establecer valor por defecto si no existe
		if (!this.pos.company.sunat_amount) {
			this.pos.company.sunat_amount = 700;
			console.warn("SUNAT amount no configurado, usando valor por defecto: 700");
		}
		
		onMounted(() => {
			this.inicioPago();
			if (this.is_check_default_tipo_doc()) {
				this.apply_default_tipo_doc();
				// ✅ NUEVO: Sincronizar estado inicial
				const order = this.currentOrder;
				if (order.l10n_latam_document_type_id) {
					this.docState.selectedDocType = order.l10n_latam_document_type_id;
				}
			}
		});
	},
	
	is_check_default_tipo_doc() {
		var journal_id = this.pos.config.doc_venta_defecto;
		if (journal_id) {
			return true;
		}
	},
	
	apply_default_tipo_doc() {
		// Si la orden es una nota de crédito (refund), no aplicamos el tipo
		// de documento por defecto porque ese default está pensado para venta
		// (factura/boleta). En refund se deja en blanco para que el usuario
		// seleccione manualmente la NC desde la pantalla.
		if (this.currentOrder.isRefund) {
			return;
		}
		var doc_venta_defecto = this.pos.config.doc_venta_defecto;
		if (doc_venta_defecto) {
			this.currentOrder.set_l10n_latam_document_type(doc_venta_defecto);
			this.currentOrder.setToInvoice(true);
		}
	},
	
	click_tipo_doc(journal_id) {
		console.log("=== CLICK TIPO DOC ===");
		console.log("journal_id recibido:", journal_id);
		const order = this.currentOrder;
		console.log("Order l10n_latam_document_type_id antes:", order.l10n_latam_document_type_id);
		
		order.setToInvoice(true);

		if (order.l10n_latam_document_type_id !== journal_id) {
			console.log("Actualizando tipo documento a:", journal_id);
			order.set_l10n_latam_document_type(journal_id);
			// ✅ ACTUALIZAR estado reactivo
			this.docState.selectedDocType = journal_id;
		} else {
			console.log("Removiendo tipo documento");
			order.set_l10n_latam_document_type(false);
			order.setToInvoice(false);
			// ✅ ACTUALIZAR estado reactivo
			this.docState.selectedDocType = null;
		}
		
		console.log("Order l10n_latam_document_type_id después:", order.l10n_latam_document_type_id);
		console.log("Estado reactivo:", this.docState.selectedDocType);
		console.log("==================");
	},
	
	async validate_journal_invoice() {
		console.log("=== VALIDATE_JOURNAL_INVOICE INICIADO ===");
		var self = this;
		var order = this.currentOrder;
		var client = order.getPartner();
		
		console.log("Cliente:", client ? client.name : "SIN CLIENTE");
		console.log("Monto orden:", order.priceIncl);
		console.log("Tipo CPE:", order.get_cpe_type());
		console.log("SUNAT amount límite:", this.pos.company.sunat_amount);

		if(!client){
			if(order.es_cpe() && this.pos.config.cliente_varios) {
				order.setPartner(this.pos.models['res.partner'].get(this.pos.config.cliente_varios[0]));
			}
			client = order.getPartner();
		}

		if(!client){
			if(order.es_cpe()) {
				// Lógica adicional
			}
			self.dialog.add(AlertDialog,{
				'title': _t('Error en cliente'),
				'body':  _t('El cliente es necesario'),
			});
			return true;
		}

		var doc_type = order.get_doc_type();
		var doc_number = order.get_doc_number();
		let val_diario = order.check_pe_journal(doc_type, doc_number);
		
		if(!val_diario[0]){
			self.dialog.add(AlertDialog,{
				'title': _t('Error en el diario'),
				'body':  val_diario[1],
			});
			return true;
		}
		
		var res = false;
		var is_validate = this.pos.validate_pe_doc(doc_type, doc_number);
		var cpe_type = order.get_cpe_type();

		let lineas = order.lines;
		for(let linea of lineas) {
			if(linea.price == 0) {
				self.dialog.add(AlertDialog, {
					title: 'Aviso',
					body: 'El monto de las lineas no puede ser 0 para un comprobante electronico',
				});
				res = true;
			}
			if(linea.quantity == 0) {
				self.dialog.add(AlertDialog, {
					title: 'Aviso',
					body: 'La cantidad no puede ser 0 para un comprobante electronico',
				});
				res = true;
			}
		}

		let monto_total = order.priceIncl;
		
		if (self.pos.company.sunat_amount < monto_total && !doc_type && !doc_number){
			await self.dialog.add(AlertDialog,{
				'title': _t('An anonymous order cannot be invoiced'),
				'body': _t('Debe seleccionar un cliente con RUC o DNI válido antes de poder facturar su pedido.'),
			});
			res = true;
		}

		if (['1', '6'].indexOf(doc_type)!=-1 && !is_validate){
			await self.dialog.add(AlertDialog,{
				title: _t('Please select the Customer'),
				body: _t('Debe seleccionar un cliente con RUC o DNI válido antes de poder facturar su pedido.'),
			});
			res = true;
		}

		if (cpe_type=='01' && doc_type!='6') {
			await self.dialog.add(AlertDialog,{
				'title': _t('Please select the Customer'),
				'body': _t('Debe seleccionar un cliente con RUC antes de poder facturar su pedido.'),
			});
			res = true;
		}
		
		if (cpe_type=='03' && doc_type=='6') {
			await self.dialog.add(AlertDialog,{
				'title': _t('Please select the Customer'),
				'body': _t('Debe seleccionar un cliente con DNI antes de poder facturar su pedido.'),
			});
			res = true;
		}
		
		console.log("=== EVALUANDO VALIDACIÓN DE MONTO SUNAT ===");
		console.log("cpe_type:", cpe_type, "- tipo:", typeof cpe_type);
		console.log("doc_type:", doc_type, "- tipo:", typeof doc_type);
		console.log("doc_number:", doc_number);
		console.log("monto_total:", monto_total, "- tipo:", typeof monto_total);
		console.log("sunat_amount:", self.pos.company.sunat_amount, "- tipo:", typeof self.pos.company.sunat_amount);
		console.log("Condición 1 (cpe_type=='03'):", cpe_type=='03');
		console.log("Condición 2 (doc_type != '1'):", doc_type != '1');
		console.log("Condición 3 (sunat_amount < monto_total):", self.pos.company.sunat_amount < monto_total);
		console.log("Resultado final:", (cpe_type=='03' && doc_type != '1' && self.pos.company.sunat_amount < monto_total));
		
		if (cpe_type=='03' && doc_type != '1' && self.pos.company.sunat_amount < monto_total) {
			console.log(">>> ENTRANDO A VALIDACIÓN - DEBE MOSTRAR ALERTA <<<");
			self.dialog.add(AlertDialog,{
				'title': 'Aviso',
				'body':  'Para montos iguales o mayores a '+self.pos.company.sunat_amount+' Son obligatorios el Tipo de Doc. y Numero',
			});
			res = true;
		} else {
			console.log(">>> NO ENTRA A VALIDACIÓN <<<");
		}

		order.pe_invoice_date = serializeDateTime(luxon.DateTime.now());
		return res;
	},
	
	mostrarTiposDocumentos(newOrder){
		var self = this;
	},
	
	click_sale_journals(doc_type_sale_id) {
		var order = this.currentOrder;
		order.setToInvoice(true);
		this.render();
	},
	
	async validateOrder(isForceValidate) {
		if(ejecutando) {
			return;
		}
		ejecutando = true;
		
		const order = this.currentOrder;
		
		// Validaciones personalizadas ANTES de la validación estándar
		var tipo_doc_venta = order.get_cpe_type();
		let monto_orden = order.priceIncl;
		
		let lineas = order.lines;
		for(let linea of lineas) {
			if(linea.price == 0) {
				this.dialog.add(AlertDialog, {
					title: 'Aviso',
					body: 'El monto de las lineas no puede ser 0 para un comprobante electronico',
				});
				ejecutando = false;
				return;
			}
			if(linea.quantity == 0) {
				this.dialog.add(AlertDialog, {
					title: 'Aviso',
					body: 'La cantidad no puede ser 0 para un comprobante electronico',
				});
				ejecutando = false;
				return;
			}
		}

		if(!tipo_doc_venta){
			// Caso refund sin tipo de doc seleccionado: NO debemos aplicar el
			// doc_venta_defecto (que es factura/boleta). Forzamos al usuario a
			// elegir explícitamente la NC. Esto cubre el caso devolución
			// compensada con recarga de billetera (monto_orden = 0 pero isRefund).
			if(order.isRefund) {
				this.dialog.add(AlertDialog, {
					title: 'Aviso',
					body: 'Defina el tipo de documento (Nota de Crédito) para el comprobante',
				});
				ejecutando = false;
				return;
			}
			if(monto_orden >= 0) {
				if(this.pos.config.doc_venta_defecto) {
					this.click_sale_journals(this.pos.config.doc_venta_defecto[0]);
				} else {
					this.dialog.add(AlertDialog, {
						title: 'Aviso',
						body: 'Defina un tipo de documento para el comprobante',
					});
					ejecutando = false;
					return;
				}
			} else {
				this.dialog.add(AlertDialog, {
					title: 'Aviso',
					body: 'Defina un tipo de documento para el comprobante',
				});
				ejecutando = false;
				return;
			}
		}

		var client = order.getPartner();
		if(!client){
			if(order.es_cpe() && this.pos.config.cliente_varios) {
				order.setPartner(this.pos.models['res.partner'].get(this.pos.config.cliente_varios[0]));
			}
		}
		
		// Validación CPE específica
		if(order.es_cpe()) {
			if (await this.validate_journal_invoice()) {
				ejecutando = false;
				return;
			}
		}
		
		// Llamar a la validación estándar de Odoo 19
		try {
			await super.validateOrder(isForceValidate);
			// Si llegamos aquí, la validación fue exitosa
			// Ahora ejecutar lógica post-validación de CPE
			if(order.es_cpe() && order.isToInvoice()) {
				await this._postValidationCPE();
			}
		} finally {
			ejecutando = false;
		}
	},

	async _postValidationCPE() {
		const order = this.currentOrder;
		
		this.notification.add(
			'Generando comprobante electrónico, por favor espere...',
			{ type: 'info', sticky: true }
		);
		
		try {
			if(order.id && order.account_move) {
				console.log("Generando XML CPE para orden:", order.id);
				
				let data = await rpc(
					'/web/dataset/call_kw/pos.order/generar_enviar_xml_cpe',
					{
						model: 'pos.order',
						method: 'generar_enviar_xml_cpe',
						args: [{"pos_order_id": [order.id]}],
						kwargs: {}
					},
					{ silent: true }
				);
				
				console.log("Respuesta recibida:", data);
				
				if(data && data.length > 0) {
					order.number = data[0]['serie'];
					if('serie_referencia' in data[0]) {
						order.number_ref = data[0]['serie_referencia'];
					}
					console.log("Serie asignada:", order.number);
					
					this.notification.add(
						'Comprobante generado exitosamente',
						{ type: 'success' }
					);
				} else {
					await this.dialog.add(AlertDialog, {
						title: 'Aviso',
						body: 'No se pudo recuperar la serie, por favor reimprima el comprobante',
					});
				}
			}
		} catch(error) {
			console.error("Error en post-validación CPE:", error);
			
			this.notification.add(
				'Error al generar CPE. Verifique el comprobante en el backend.',
				{ type: 'danger' }
			);
			
			await this.dialog.add(AlertDialog, {
				title: 'Error CPE',
				body: `Error al generar CPE: ${error.message || 'Error desconocido'}. Verifique el comprobante en el backend.`,
			});
		}
	},
	
	validar_plazo_pago() {
		return true;
	},
	
	ejecutarDatosGraficos(paymentMethod) {
		// Lógica opcional
	},
	
	addNewPaymentLine(paymentMethod) {
		for(let linea of this.paymentLines) {
			if(linea.payment_method && linea.payment_method.type == 'pay_later') {
				return;
			}
		}

		const result = this.currentOrder.addPaymentline(paymentMethod);
		let estado = false;
		
		if (result) {
			this.numberBuffer.reset();
			estado = true;
		} else {
			this.dialog.add(AlertDialog, {
				title: _t("Error"),
				body: _t("There is already an electronic payment in progress."),
			});
			estado = false;
		}
		
		this.ejecutarDatosGraficos(paymentMethod);
		this.validar_monto_pago();
		return estado;
	},

	inicioPago() {
		ejecutando = false;
	},

	_updateSelectedPaymentline() {
		var res = super._updateSelectedPaymentline();
		this.validar_monto_pago();
		return res;
	},

	deletePaymentLine(event) {
		var res = super.deletePaymentLine(event);
		this.validar_monto_pago();
		return res;
	},

	validar_monto_pago() {
		// Validación opcional
	},
	
	tiene_pago_con_banco() {
		for(let linea of this.paymentLines) {
			if(linea.payment_method.type == 'bank') {
				return true;
			}
		}
		return false;
	},
});