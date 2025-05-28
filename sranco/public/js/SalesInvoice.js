frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {
        calc_total_rep_commission(frm);
        calc_total_snc_commission(frm);
    },
    onload: function (frm) {
        calc_total_rep_commission(frm);
        calc_total_snc_commission(frm);
    },
});

frappe.ui.form.on("Sales Invoice Item", {
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
    // Add handlers for percentage changes
    custom_rep_commission_percent: function (frm, cdt, cdn) {
        update_rep_commission(frm, cdt, cdn);
        calc_total_rep_commission(frm);
    },
    custom_snc_commission_percent: function (frm, cdt, cdn) {
        update_snc_commission(frm, cdt, cdn);
        calc_total_snc_commission(frm);
    },
    // Add handlers for amount per qty changes
    custom_rep_commission_amount_per_qty: function (frm, cdt, cdn) {
        update_rep_commission(frm, cdt, cdn);
        calc_total_rep_commission(frm);
    },
    custom_snc_commission_amount_per_qty: function (frm, cdt, cdn) {
        update_snc_commission(frm, cdt, cdn);
        calc_total_snc_commission(frm);
    }
});

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
        var commission_per_qty = (row.custom_rep_commission_percent * row.rate) / 100;
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
        var commission_per_qty = (row.custom_snc_commission_percent * row.rate) / 100;
        row.custom_snc_commission_amount_per_qty = commission_per_qty;
        
        // Then calculate total commission for all qty
        row.custom_snc_commission_amount = commission_per_qty * row.qty;
    } else if (row.custom_snc_commission_type == "Amount") {
        // If it's a fixed amount per qty, just multiply
        row.custom_snc_commission_amount = (row.custom_snc_commission_amount_per_qty || 0) * row.qty;
    }
    frm.refresh_field("items");
}