import frappe
from frappe.utils import logger, getdate
from frappe import _

logger.set_log_level("DEBUG")
logger = frappe.logger("Sranco_logs", allow_site=True, file_count=1)

def on_submit(doc, method):
    item_price_update(doc, method)
    sales_order_on_submit(doc, method)
    update_customer_item_code(doc, method)
    update_stock_order(doc, method)
    # NEW: Update Standard Buying Item Prices after everything else is done
    update_standard_buying_item_prices(doc, method)

# --- before_save HOOK (Corrected) ---
def before_save(doc, method):
    if doc.docstatus == 0:  # Only apply on new or draft
        for item in doc.items:
            if item.custom_gi_date:
                # --- Temporarily bypass validation on delivery_date ---
                try:
                    frappe.db.set_value("DocField", {"parent": "Sales Order Item", "fieldname": "delivery_date"}, "ignore_user_permissions", 1)
                    frappe.db.commit()
                    item.delivery_date = item.custom_gi_date
                    item.schedule_date = item.custom_gi_date # Also set schedule date at item level.
                finally:
                    frappe.db.set_value("DocField", {"parent": "Sales Order Item", "fieldname": "delivery_date"}, "ignore_user_permissions", 0)
                    frappe.db.commit()
                # --- End temporary bypass ---
# -------------------------------

def item_price_update(doc, method):
    """
    Updates or creates Item Price records for Standard Selling price list.
    FIXED: Properly updates both custom_customer_item_code and custom_customer_code fields.
    """
    for item in doc.items:
        logger.info(f"Processing Item {item.item_code} with rate {item.rate} and customer {doc.customer}")
        
        # Check if Item Price exists for this item-customer combination
        item_price = frappe.db.exists('Item Price', {
            'item_code': item.item_code, 
            'price_list': 'Standard Selling', 
            'customer': doc.customer
        })
        logger.info(f"Standard Selling Item Price {item_price} exists: {bool(item_price)}")

        if item_price:
            # Update existing Item Price
            logger.info(f"Updating existing Standard Selling Item Price {item_price}")
            existing_item_price = frappe.get_doc('Item Price', item_price)
            
            # Update rate if different
            if round(existing_item_price.price_list_rate, 2) != round(item.rate, 2):
                existing_item_price.price_list_rate = item.rate
            
            # Update customer information - ENSURE THIS IS ALWAYS SET
            existing_item_price.customer = doc.customer
            existing_item_price.custom_customer_name = doc.customer_name
            
            # FIXED: Always update BOTH customer item code fields from sales order item
            if hasattr(item, 'custom_customer_item_code'):
                customer_item_code = item.custom_customer_item_code or "N/A"
                existing_item_price.custom_customer_item_code = customer_item_code
                # FIXED: Also update the custom_customer_code field (Small Text field)
                existing_item_price.custom_customer_code = customer_item_code
                logger.info(f"Updated customer item codes to: {customer_item_code}")
            
            # Update commission fields
            commission_fields = [
                'custom_snc_commission_type', 'custom_snc_commission_',
                'custom_has_representative_commission', 'custom_representative',
                'custom_rep_commission_type', 'custom_rep_commission_'
            ]
            for field in commission_fields:
                if hasattr(item, field):
                    setattr(existing_item_price, field, getattr(item, field))
            
            # FIXED: Always use per-quantity amounts for commission
            if hasattr(item, 'custom_snc_commission_amount_per_qty'):
                existing_item_price.custom_snc_commission_amount = item.custom_snc_commission_amount_per_qty
                existing_item_price.custom_snc_commission_lumpsum = item.custom_snc_commission_amount_per_qty
                logger.info(f"Set SNC commission amount to per-qty value: {item.custom_snc_commission_amount_per_qty}")
            
            if hasattr(item, 'custom_rep_commission_amount_per_qty'):
                existing_item_price.custom_rep_commission_amount = item.custom_rep_commission_amount_per_qty
                logger.info(f"Set Rep commission amount to per-qty value: {item.custom_rep_commission_amount_per_qty}")

            existing_item_price.save()
            logger.info(f"Successfully updated Standard Selling Item Price {existing_item_price.item_code}")
            frappe.msgprint(f"Updated Standard Selling Item Price {existing_item_price.item_code} with customer code and rate {item.rate}")
            
        else:
            # Create new Item Price
            logger.info(f"Creating new Standard Selling Item Price for {item.item_code}")
            new_item_price = frappe.new_doc('Item Price')
            new_item_price.price_list = 'Standard Selling'
            new_item_price.item_code = item.item_code
            new_item_price.customer = doc.customer
            new_item_price.custom_customer_name = doc.customer_name
            new_item_price.uom = item.uom
            new_item_price.price_list_rate = item.rate
            
            # FIXED: Always set BOTH customer item code fields
            if hasattr(item, 'custom_customer_item_code'):
                customer_item_code = item.custom_customer_item_code or "N/A"
                new_item_price.custom_customer_item_code = customer_item_code
                # FIXED: Also set the custom_customer_code field (Small Text field)
                new_item_price.custom_customer_code = customer_item_code
                logger.info(f"Set customer item codes to: {customer_item_code}")
            
            # Set commission fields
            commission_fields = [
                'custom_snc_commission_type', 'custom_snc_commission_',
                'custom_has_representative_commission', 'custom_representative',
                'custom_rep_commission_type', 'custom_rep_commission_'
            ]
            for field in commission_fields:
                if hasattr(item, field):
                    setattr(new_item_price, field, getattr(item, field))
            
            # FIXED: Always use per-quantity amounts for commission
            if hasattr(item, 'custom_snc_commission_amount_per_qty'):
                new_item_price.custom_snc_commission_amount = item.custom_snc_commission_amount_per_qty
                new_item_price.custom_snc_commission_lumpsum = item.custom_snc_commission_amount_per_qty
                logger.info(f"Set SNC commission amount to per-qty value: {item.custom_snc_commission_amount_per_qty}")
            
            if hasattr(item, 'custom_rep_commission_amount_per_qty'):
                new_item_price.custom_rep_commission_amount = item.custom_rep_commission_amount_per_qty
                logger.info(f"Set Rep commission amount to per-qty value: {item.custom_rep_commission_amount_per_qty}")
                
            new_item_price.insert()
            logger.info(f"Successfully created new Standard Selling Item Price {new_item_price.item_code}")
            frappe.msgprint(f"Created new Standard Selling Item Price {new_item_price.item_code} with customer code and rate {item.rate}")

# NEW FUNCTION: Update Standard Buying Item Prices with customer info
def update_standard_buying_item_prices(doc, method):
    """
    Find and update any Standard Buying Item Price records created during this process
    to include customer information and commission data.
    FIXED: Properly updates both custom_customer_item_code and custom_customer_code fields.
    """
    for item in doc.items:
        # Look for Standard Buying Item Price records for this item without customer
        buying_item_prices = frappe.get_all('Item Price', 
            filters={
                'item_code': item.item_code,
                'price_list': 'Standard Buying',
                'customer': ['in', [None, '']]
            },
            fields=['name']
        )
        
        for price_record in buying_item_prices:
            logger.info(f"Updating Standard Buying Item Price {price_record.name} with customer and commission info")
            
            # Update the Standard Buying Item Price with customer information
            buying_item_price = frappe.get_doc('Item Price', price_record.name)
            buying_item_price.customer = doc.customer
            buying_item_price.custom_customer_name = doc.customer_name
            
            # FIXED: Always set BOTH customer item code fields
            if hasattr(item, 'custom_customer_item_code'):
                customer_item_code = item.custom_customer_item_code or "N/A"
                buying_item_price.custom_customer_item_code = customer_item_code
                # FIXED: Also set the custom_customer_code field (Small Text field)
                buying_item_price.custom_customer_code = customer_item_code
                logger.info(f"Set customer item codes in Standard Buying price to: {customer_item_code}")
            
            # Copy commission information to Standard Buying Item Price
            commission_fields = [
                'custom_snc_commission_type', 'custom_snc_commission_',
                'custom_has_representative_commission', 'custom_representative',
                'custom_rep_commission_type', 'custom_rep_commission_'
            ]
            
            for field in commission_fields:
                if hasattr(item, field):
                    setattr(buying_item_price, field, getattr(item, field))
            
            # FIXED: Always use per-quantity amounts for Standard Buying Item Price
            if hasattr(item, 'custom_snc_commission_amount_per_qty'):
                buying_item_price.custom_snc_commission_lumpsum = item.custom_snc_commission_amount_per_qty
                buying_item_price.custom_snc_commission_amount = item.custom_snc_commission_amount_per_qty
                logger.info(f"Set SNC commission in Standard Buying price to per-qty value: {item.custom_snc_commission_amount_per_qty}")
            
            if hasattr(item, 'custom_rep_commission_amount_per_qty'):
                buying_item_price.custom_rep_commission_amount = item.custom_rep_commission_amount_per_qty
                logger.info(f"Set Rep commission in Standard Buying price to per-qty value: {item.custom_rep_commission_amount_per_qty}")
            
            buying_item_price.save()
            
            frappe.msgprint(f"Updated Standard Buying Item Price {buying_item_price.item_code} with customer code and commission info", alert=True)
            logger.info(f"Updated Standard Buying Item Price {price_record.name} - added customer {doc.customer} and customer code data")

def sales_order_on_submit(doc, method):
    # Check if Sales Order items are available
    if not doc.items:
        return

    # Check if any item in Sales Order does not have an associated Purchase Order
    has_item_without_po = any(not item.purchase_order for item in doc.items)
    if not has_item_without_po:
        # All items have a Purchase Order, so skip the PO creation
        frappe.msgprint(_("All items have a Purchase Order, so skipping PO creation"))
        return

    # Create a new Purchase Order
    po = frappe.new_doc("Purchase Order")

    # Copy the relevant fields from Sales Order to Purchase Order
    po.customer = doc.customer
    po.delivery_date = doc.delivery_date  # Use SO delivery date
    po.custom_order_confirmation = doc.custom_order_confirmation
    po.schedule_date = doc.delivery_date    # Use SO delivery_date
    po.supplier = "TYROLIT INDIA SUPERABRASIVE TOOLS PVT. LTD."  # HARDCODED - Option 2
    po.transaction_date = doc.transaction_date # Set PO transaction date

    # Loop through Sales Order items and append to Purchase Order
    for item in doc.items:
        if not item.purchase_order:
            po_item = po.append('items', {})
            po.custom_order_confirmation = item.custom_order_confirmation  # Copy order confirmation
            po_item.item_code = item.item_code
            po_item.item_name = item.item_name
            po_item.description = item.description
            po_item.qty = item.qty
            po_item.uom = item.uom
            po_item.rate = item.rate
            po_item.custom_tn_number = item.custom_tn_number
            po_item.custom_customer_item_code = item.custom_customer_item_code
            po_item.sales_order = doc.name  # Linking Sales Order to Purchase Order items

            # --- TEMPORARILY DISABLE VALIDATION on *Purchase Order Item* ---
            try:
                frappe.db.set_value("DocField", {"parent": "Purchase Order Item", "fieldname": "schedule_date"}, "ignore_user_permissions", 1)
                frappe.db.commit()
                po_item.schedule_date =  item.delivery_date  # Use item.delivery_date
                po_item.expected_delivery_date =  item.delivery_date

            finally:
                frappe.db.set_value("DocField", {"parent": "Purchase Order Item", "fieldname": "schedule_date"}, "ignore_user_permissions", 0)
                frappe.db.commit()
            # --- END TEMPORARILY DISABLE VALIDATION ---

    # Save and submit the Purchase Order
    po.flags.ignore_permissions = True  # Very Important
    try:
        po.insert()
        po.save()
        for item in doc.items:
            if not item.purchase_order:
                item.purchase_order = po.name
        po.submit()
        logger.info(f"Stock Order Items {doc.items}")
        logger.info(f"Purchase Order {po.name} created successfully!")
        frappe.msgprint(_("Purchase Order {0} created successfully!").format(po.name))

    except Exception as e:
        frappe.db.rollback()  # Rollback if any error during save/submit
        frappe.msgprint(f"Error creating Purchase Order: {e}")
        logger.error(f"Error creating Purchase Order: {e}")  # Log the full error
        raise  # Re-raise to stop the Sales Order submission

def update_stock_order(doc, method):
    # Update Stock Order items with sales quantities
    for item in doc.items:
        logger.info(f"Sales Order Stock Order Items {item.custom_stock_order}")
        if item.custom_stock_order:
            logger.info(f"Sales Order Stock Order Items {item.custom_stock_order}")
            stock_order_items = frappe.get_all(
                "Stock Order Items",
                filters={"parent": item.custom_stock_order, "item_code": item.item_code},
                fields=["name", "sales_qty"],
            )
            logger.info(f"Sales Order Stock Order Items {stock_order_items}")
            for stock_order_item in stock_order_items:
                stock_order = frappe.get_doc("Stock Order Items", stock_order_item.name)
                stock_order.sales_qty += item.qty
                logger.info(f"Updated Stock Order {stock_order.name} with sales quantity {item.qty}")
                stock_order.save()
                frappe.msgprint(f"Updated Stock Order {stock_order.name} with sales quantity {item.qty}", alert=True)

def update_customer_item_code(doc, method):
    """
    Updates Item master with customer-specific item codes.
    IMPROVED: Better error handling and ensures all items are processed.
    """
    # Iterate through each item in the sales order
    for item in doc.items:
        try:
            item_code = item.item_code
            # Get the value, defaulting to "N/A" if it's None or empty
            custom_customer_item_code = item.custom_customer_item_code or "N/A"
            
            logger.info(f"Processing customer item code for {item_code}: {custom_customer_item_code}")

            # Fetch the corresponding Item document
            item_doc = frappe.get_doc("Item", item_code)

            # Track if a matching customer item is found
            found = False

            # Check if the customer exists in the item's customer_items
            for customer_item in item_doc.customer_items:
                if customer_item.customer_name == doc.customer:
                    # If found, update the ref_code
                    customer_item.ref_code = custom_customer_item_code
                    found = True
                    logger.info(f"Updated existing customer item entry for {doc.customer}")
                    break

            if not found:
                # If not found, add a new customer item entry
                item_doc.append("customer_items", {
                    "customer_name": doc.customer,
                    "ref_code": custom_customer_item_code # Using "N/A" default
                })
                logger.info(f"Added new customer item entry for {doc.customer}")

            # Save the Item document
            item_doc.save()
            logger.info(f"Successfully updated customer item code for {item_code}")
            frappe.msgprint(_("Updated customer item code for {0}").format(item_code), alert=True)

        except frappe.DoesNotExistError:
            error_msg = f"Item {item_code} not found."
            frappe.msgprint(_(error_msg), alert=True)
            logger.error(error_msg)
            # Continue processing other items instead of stopping
            continue
        except Exception as e:
            error_msg = f"Error updating customer item code for {item_code}: {str(e)}"
            frappe.msgprint(_(error_msg), alert=True)
            logger.error(error_msg)
            # Continue processing other items instead of stopping
            continue

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def custom_item_query(doctype, txt, searchfield, start, page_len, filters):

    # logger.info(f"txt: {txt}, searchfield: {searchfield}, start: {start}, page_len: {page_len}, filters: {filters}")
    customer_filter = ""
    if filters.get('customer'):
        customer_filter = "AND ip.customer = %(customer)s"

    return frappe.db.sql(f"""
        SELECT it.item_code, it.item_name, it.custom_tn_number, icd.ref_code
        FROM `tabItem` it
        LEFT JOIN `tabItem Price` ip ON it.item_code = ip.item_code
        LEFT JOIN `tabItem Customer Detail` icd ON it.item_code = icd.parent
        WHERE it.docstatus = 0
            {customer_filter}
            AND ((it.{searchfield} LIKE %(txt)s) OR (icd.ref_code LIKE %(txt)s) OR (it.item_name LIKE %(txt)s) OR (it.item_code LIKE %(txt)s) OR (it.custom_tn_number LIKE %(txt)s) OR (it.custom_tn_number LIKE %(_txt)s))
        ORDER BY it.creation ASC, it.name ASC
        LIMIT %(start)s, %(page_len)s
    """, {
        'customer': filters.get('customer'),
        'txt': "%{}%".format(txt),
        '_txt': txt.replace("%", ""),
        'start': start,
        'page_len': page_len
    })

@frappe.whitelist()
def get_purchase_order_from_items(order_confirmation):
    result = frappe.db.sql("""
        SELECT soi.purchase_order
        FROM `tabSales Order` so
        JOIN `tabSales Order Item` soi ON so.name = soi.parent
        WHERE soi.custom_order_confirmation = %s
        LIMIT 1
    """, (order_confirmation,), as_dict=1)

    return result[0].purchase_order if result else None

@frappe.whitelist()
def get_sales_order_from_items(order_confirmation):
    logger.info(f"Order Confirmation {order_confirmation}")
    result = frappe.db.sql("""
        SELECT so.name, so.customer
        FROM `tabSales Order` so
        JOIN `tabSales Order Item` soi ON so.name = soi.parent
        WHERE soi.custom_order_confirmation = %s
        LIMIT 1
    """, (order_confirmation,), as_dict=1)
    logger.info(f"Sales Order from items {result}")

    return {"sales_order": result[0].name, "customer": result[0].customer} if result else None