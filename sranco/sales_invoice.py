import frappe
from frappe.utils import logger

logger.set_log_level("DEBUG")
logger = frappe.logger("sranco_logs", allow_site=True, file_count=1)

@frappe.whitelist()
def get_customer_item_code(item_code, customer):
    """
    Fetch the customer-specific item code (ref_code) from Item Customer Detail
    """
    try:
        logger.info(f"Fetching customer item code for item: {item_code}, customer: {customer}")
        
        # Get the full customer name from the customer ID
        customer_name = frappe.db.get_value('Customer', customer, 'customer_name')
        
        # Query to find the ref_code for the specific item and customer name
        customer_items = frappe.db.sql("""
            SELECT ref_code
            FROM `tabItem Customer Detail`
            WHERE parent = %s AND customer_name = %s
        """, (item_code, customer_name), as_dict=1)
        
        if customer_items and customer_items[0].get('ref_code'):
            ref_code = customer_items[0].get('ref_code')
            logger.info(f"Found ref_code: {ref_code} for customer: {customer_name}")
            return ref_code
        
        logger.info(f"No ref_code found for item: {item_code}, customer: {customer_name}")
        return None
            
    except Exception as e:
        logger.error(f"Error in get_customer_item_code: {e}")
        frappe.log_error(f"Error in get_customer_item_code: {e}", "Sranco_logs")
        return None

@frappe.whitelist()
def get_rep_sales_invoice_list(representative, from_date, to_date):
    try:
        # Fetching sales invoices based on the representative and date range
        logger.info(f"Fetching sales invoices based on the representative and date range {representative} {from_date} {to_date}")
        invoices = frappe.db.sql("""
            SELECT si.name AS sales_invoice, si.posting_date AS invoice_date, si.customer, si.custom_total_representative_commission AS commission_amount, si.custom_invoice_no_t as invoice_no_t
            FROM `tabSales Invoice` si
            JOIN `tabSales Invoice Item` si_item ON si.name = si_item.parent
            WHERE si_item.custom_representative = %(representative)s
            AND si.custom_representative_commission_statement_generated = 0
            AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
            AND si.docstatus = 1
            GROUP BY si.name
            ORDER BY si.posting_date DESC
            """, {'representative': representative, 'from_date': from_date, 'to_date': to_date}, as_dict=1)
        return invoices
    except Exception as e:
        logger.error(f"Error in get_rep_sales_invoice_list: {e}")
        frappe.log_error(f"Error in get_rep_sales_invoice_list: {e}", "Sranco_logs")
        return []

@frappe.whitelist()
def get_snc_sales_invoice_list(from_date, to_date):
    try:
        # Fetching sales invoices based on date range for SNC commission
        logger.info(f"Fetching sales invoices for SNC commission in date range {from_date} {to_date}")
        invoices = frappe.db.sql("""
            SELECT si.name AS sales_invoice, si.posting_date AS invoice_date, si.customer, si.custom_total_snc_commission AS commission_amount, si.custom_invoice_no_t as invoice_no_t
            FROM `tabSales Invoice` si
            WHERE si.posting_date BETWEEN %(from_date)s AND %(to_date)s
            AND si.docstatus = 1
            AND si.custom_snc_commission_statement_generated = 0
            AND si.custom_total_snc_commission > 0
            ORDER BY si.posting_date DESC
            """, {'from_date': from_date, 'to_date': to_date}, as_dict=1)
        return invoices
    except Exception as e:
        logger.error(f"Error in get_snc_sales_invoice_list: {e}")
        frappe.log_error(f"Error in get_snc_sales_invoice_list: {e}", "Sranco_logs")
        return []

@frappe.whitelist()
def update_commission_calculations(sales_invoice):
    """
    Manually recalculate all commission values for a sales invoice
    """
    try:
        invoice = frappe.get_doc("Sales Invoice", sales_invoice)
        total_rep_commission = 0
        total_snc_commission = 0
        
        for item in invoice.items:
            # Update representative commission
            if item.custom_rep_commission_type == "Percent":
                commission_per_qty = (item.custom_rep_commission_ * item.rate) / 100
                item.custom_rep_commission_amount_per_qty = commission_per_qty
                item.custom_rep_commission_amount = commission_per_qty * item.qty
            elif item.custom_rep_commission_type == "Amount":
                item.custom_rep_commission_amount = (item.custom_rep_commission_amount_per_qty or 0) * item.qty
            
            # Update SNC commission
            if item.custom_snc_commission_type == "Percent":
                commission_per_qty = (item.custom_snc_commission_ * item.rate) / 100
                item.custom_snc_commission_amount_per_qty = commission_per_qty
                item.custom_snc_commission_amount = commission_per_qty * item.qty
            elif item.custom_snc_commission_type == "Amount":
                item.custom_snc_commission_amount = (item.custom_snc_commission_amount_per_qty or 0) * item.qty
            
            # Sum up commissions
            total_rep_commission += item.custom_rep_commission_amount or 0
            total_snc_commission += item.custom_snc_commission_amount or 0
        
        # Update totals on the invoice
        invoice.custom_total_representative_commission = total_rep_commission
        invoice.custom_total_snc_commission = total_snc_commission
        
        # Save the invoice
        invoice.save()
        
        return {
            "success": True,
            "message": "Commission calculations updated successfully",
            "total_rep_commission": total_rep_commission,
            "total_snc_commission": total_snc_commission
        }
    except Exception as e:
        logger.error(f"Error in update_commission_calculations: {e}")
        frappe.log_error(f"Error in update_commission_calculations: {e}", "Sranco_logs")
        return {
            "success": False,
            "message": f"Error updating commission calculations: {str(e)}"
        }

# Add a server hook to update customer item codes whenever an item is saved
def update_customer_item_codes_hook(doc, method=None):
    """
    Hook to update customer item codes in all open Sales Invoices when an Item is saved
    This ensures that customer item codes are always up-to-date
    """
    try:
        # Find all open (draft) sales invoices
        open_invoices = frappe.get_all("Sales Invoice", 
            filters={"docstatus": 0},
            fields=["name", "customer"]
        )
        
        for invoice in open_invoices:
            # Get all invoice items that use this item
            invoice_items = frappe.get_all("Sales Invoice Item",
                filters={"parent": invoice.name, "item_code": doc.name},
                fields=["name", "idx"]
            )
            
            # Get the customer name
            customer_name = frappe.db.get_value('Customer', invoice.customer, 'customer_name')
            
            if not customer_name:
                continue
                
            # Find the matching customer item
            ref_code = None
            for customer_item in doc.customer_items:
                if customer_item.customer_name == customer_name:
                    ref_code = customer_item.ref_code
                    break
            
            # Update the custom_customer_item_code in all matching Sales Invoice Items
            if ref_code:
                for item in invoice_items:
                    frappe.db.set_value("Sales Invoice Item", item.name, "custom_customer_item_code", ref_code)
                    
        logger.info(f"Updated customer item codes for item {doc.name}")
    except Exception as e:
        logger.error(f"Error in update_customer_item_codes_hook: {e}")
        frappe.log_error(f"Error in update_customer_item_codes_hook: {e}", "Sranco_logs")