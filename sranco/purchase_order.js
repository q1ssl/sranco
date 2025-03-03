// Copyright (c) 2023, Dinesh Panchal and contributors
// For license information, please see license.txt

frappe.ui.form.on('Purchase Order', {
    before_cancel: function(frm) {
        // Check if this PO is linked to a Stock Order
        if (frm.doc.stock_order) {
            // Call frappe.client.get to check if the Stock Order is still valid
            frappe.call({
                method: "frappe.client.get",
                args: {
                    doctype: "Stock Order",
                    name: frm.doc.stock_order
                },
                callback: function(r) {
                    if (r.message && r.message.docstatus === 1) { // 1 = Submitted
                        frappe.confirm(
                            __("This Purchase Order is linked to Stock Order {0}. The Stock Order will also be cancelled. Continue?", [frm.doc.stock_order]),
                            function() {
                                // User confirmed, use our utility function
                                frappe.call({
                                    method: "sranco.purchase_order.cancel_purchase_order_and_linked_docs",
                                    args: {
                                        purchase_order: frm.doc.name
                                    },
                                    callback: function(r) {
                                        if (r.message && r.message.success) {
                                            frappe.msgprint(__("Purchase Order and linked documents cancelled successfully."));
                                            frm.refresh();
                                        } else {
                                            frappe.msgprint(__("Failed to cancel linked documents. Error: {0}", 
                                                [r.message ? r.message.error : "Unknown error"]));
                                        }
                                    }
                                });
                            },
                            function() {
                                // User declined, do nothing
                                frappe.validated = false;
                            }
                        );
                        
                        // Prevent the standard cancellation process
                        frappe.validated = false;
                    }
                }
            });
        }
    }
});