# Copyright (c) 2023, Dinesh Panchal and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

class PurchaseOrder(Document):
    def on_cancel(self):
        """
        Handle cancellation of Purchase Order - break circular dependency with Stock Order
        """
        # Check if this is a forced cancellation (ignore links flag set)
        # or if it's being cancelled from a Stock Order
        if (hasattr(self.flags, 'ignore_links') and self.flags.ignore_links) or \
           (hasattr(self.flags, 'from_stock_order') and self.flags.from_stock_order):
            return
            
        # Check if there are any linked Stock Orders
        if self.stock_order:
            stock_order_doc = frappe.get_doc("Stock Order", self.stock_order)
            
            # Only if it's submitted
            if stock_order_doc.docstatus == 1:
                frappe.throw(
                    _("This Purchase Order is linked to Stock Order {0}. Please cancel the Stock Order first.")
                    .format(self.stock_order)
                )


@frappe.whitelist()
def cancel_purchase_order_and_linked_docs(purchase_order):
    """
    Utility function to cancel a Purchase Order and its linked documents
    """
    try:
        doc = frappe.get_doc("Purchase Order", purchase_order)
        
        # Check if linked to a Stock Order
        if doc.stock_order:
            stock_order = frappe.get_doc("Stock Order", doc.stock_order)
            
            # If the Stock Order is submitted, cancel it first
            if stock_order.docstatus == 1:
                stock_order.flags.ignore_links = True
                stock_order.flags.from_purchase_order = True
                stock_order.cancel()
                frappe.db.commit()
        
        # Now cancel the Purchase Order
        doc.flags.ignore_links = True
        doc.cancel()
        frappe.db.commit()
        
        return {"success": True}
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Error cancelling Purchase Order {purchase_order}: {str(e)}")
        return {"success": False, "error": str(e)}