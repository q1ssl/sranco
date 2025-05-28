frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {
        calc_total_rep_commission(frm);
        calc_total_snc_commission(frm);
    },
    onload: function (frm) {
        calc_total_rep_commission(frm);
        calc_total_snc_commission(frm);
    },
    customer: function(frm) {
        // When customer changes, update all items' customer item codes
        if(frm.doc.customer) {
            frm.doc.items.forEach(function(item) {
                if(item.item_code) {
                    fetch_customer_item_code(frm, item.item_code, frm.doc.customer, item.idx - 1);
                }
            });
        }
    }
});

frappe.ui.form.on("Sales Invoice Item", {
    item_code: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if(row.item_code && frm.doc.customer) {
            // When item code changes, fetch the customer's item code
            fetch_customer_item_code(frm, row.item_code, frm.doc.customer, row.idx - 1);
        }
    },
    qty: function (frm, cdt, cdn) {
        calc_total_rep_commission(frm);
        calc_total_snc_commission(frm);
        update_rep_commission(frm, cdt, cdn);
        update_snc_commission(frm, cdt, cdn);
    },
    rate: function (frm, cdt, cdn) {
        update_rep_commission(frm, cdt, cdn);
        update_snc_commission(frm, cdt, cdn);
        calc_total_rep_commission(frm);
        calc_total_snc_commission(frm);
    },
    custom_rep_commission_type: function (frm, cdt, cdn) {
        update_rep_commission(frm, cdt, cdn);
        calc_total_rep_commission(frm);
    },
    custom_snc_commission_type: function (frm, cdt, cdn) {
        update_snc_commission(frm, cdt, cdn);
        calc_total_snc_commission(frm);
    },
    custom_rep_commission_: function (frm, cdt, cdn) {
        update_rep_commission(frm, cdt, cdn);
        calc_total_rep_commission(frm);
    },
    custom_snc_commission_: function (frm, cdt, cdn) {
        update_snc_commission(frm, cdt, cdn);
        calc_total_snc_commission(frm);
    },
    custom_rep_commission_amount_per_qty: function (frm, cdt, cdn) {
        update_rep_commission(frm, cdt, cdn);
        calc_total_rep_commission(frm);
    },
    custom_snc_commission_amount_per_qty: function (frm, cdt, cdn) {
        update_snc_commission(frm, cdt, cdn);
        calc_total_snc_commission(frm);
    }
});

// Function to fetch customer-specific item code
function fetch_customer_item_code(frm, item_code, customer, row_idx) {
    frappe.call({
        method: "sranco.sales_invoice.get_customer_item_code",
        args: {
            item_code: item_code,
            customer: customer
        },
        callback: function(r) {
            if(r.message) {
                // Update the custom_customer_item_code field in the specific row
                frappe.model.set_value(
                    "Sales Invoice Item", 
                    frm.doc.items[row_idx].name, 
                    "custom_customer_item_code", 
                    r.message
                );
                frm.refresh_field("items");
            }
        }
    });
}

function calc_total_rep_commission(frm) {
    // calculate total representative commission and set it to custom_total_representative_commission field
    var total_rep_commission = 0;
    frm.doc.items.forEach(function (item) {
        total_rep_commission += item.custom_rep_commission_amount || 0;
    });
    frm.set_value(
        "custom_total_representative_commission",
        total_rep_commission
    );
    frm.refresh_field("custom_total_representative_commission");
}

function calc_total_snc_commission(frm) {
    // calculate total snc commission and set it to custom_total_snc_commission field
    var total_snc_commission = 0;
    frm.doc.items.forEach(function (item) {
        total_snc_commission += item.custom_snc_commission_amount || 0;
    });
    frm.set_value("custom_total_snc_commission", total_snc_commission);
    frm.refresh_field("custom_total_snc_commission");
}

function update_rep_commission(frm, cdt, cdn) {
    var row = locals[cdt][cdn];
    if (row.custom_rep_commission_type == "Percent") {
        // Calculate commission per qty first
        var commission_per_qty = (row.custom_rep_commission_ * row.rate) / 100;
        row.custom_rep_commission_amount_per_qty = commission_per_qty;
        
        // Then calculate total commission
        row.custom_rep_commission_amount = commission_per_qty * row.qty;
    } else if (row.custom_rep_commission_type == "Amount") {
        row.custom_rep_commission_amount = (row.custom_rep_commission_amount_per_qty || 0) * row.qty;
    }
    frm.refresh_field("items");
}

function update_snc_commission(frm, cdt, cdn) {
    var row = locals[cdt][cdn];
    if (row.custom_snc_commission_type == "Percent") {
        // Calculate commission per qty first (for a single item)
        var commission_per_qty = (row.custom_snc_commission_ * row.rate) / 100;
        row.custom_snc_commission_amount_per_qty = commission_per_qty;
        
        // Then calculate total commission for all qty
        row.custom_snc_commission_amount = commission_per_qty * row.qty;
    } else if (row.custom_snc_commission_type == "Amount") {
        // If it's a fixed amount per qty, just multiply
        row.custom_snc_commission_amount = (row.custom_snc_commission_amount_per_qty || 0) * row.qty;
    }
    frm.refresh_field("items");
}