import frappe
from frappe.utils import logger
from frappe import _

logger.set_log_level("DEBUG")
logger = frappe.logger("Sranco_logs", allow_site=True, file_count=1)

def on_submit(doc, method):
    item_price_update(doc, method)
    sales_order_on_submit(doc, method)
    update_customer_item_code(doc, method)
    update_stock_order(doc, method)

def item_price_update(doc, method):
    for item in doc.items:
        logger.info(f"Item {item.item_code} with rate {item.rate} and customer {doc.customer}")
        item_price = frappe.db.exists('Item Price', {'item_code': item.item_code, 'price_list': 'Standard Selling', 'customer': doc.customer})
        logger.info(f"Item Price {item_price} exists")

        if item_price:
            logger.info(f"Item Price in if condition {item_price} exists")
            existing_item_price = frappe.get_doc('Item Price', item_price)
            if round(existing_item_price.price_list_rate, 2) != round(item.rate, 2):
                existing_item_price.price_list_rate = item.rate
                # Use setattr for cleaner updates
                for field in ['custom_snc_commission_type', 'custom_snc_commission_',
                              'custom_snc_commission_amount', 'custom_snc_commission_lumpsum',
                              'custom_has_representative_commission', 'custom_representative',
                              'custom_rep_commission_type', 'custom_rep_commission_',
                              'custom_rep_commission_amount']:
                    if hasattr(item, field):  # Check if the field exists on the item
                        setattr(existing_item_price, field, getattr(item, field))
                if not item.custom_snc_commission_:
                    existing_item_price.custom_snc_commission_amount = item.custom_snc_commission_amount_per_qty
                    existing_item_price.custom_snc_commission_lumpsum = item.custom_snc_commission_amount_per_qty
                if not item.custom_rep_commission_:
                    existing_item_price.custom_rep_commission_amount = item.custom_rep_commission_amount_per_qty

                logger.info(f"Updating Item Price {existing_item_price.item_code} with rate {item.rate}")
                frappe.msgprint(f"Updated Item Price {existing_item_price.item_code} with rate {item.rate}")
                existing_item_price.save()
        else:
            logger.info(f"Item Price in else condition {item_price} exists")
            new_item_price = frappe.new_doc('Item Price')
            new_item_price.price_list = 'Standard Selling'
            new_item_price.item_code = item.item_code
            new_item_price.customer = doc.customer
            new_item_price.custom_customer_name = doc.customer_name
            new_item_price.uom = item.uom
            new_item_price.price_list_rate = item.rate
            # Use setattr here as well
            for field in ['custom_snc_commission_type', 'custom_snc_commission_',
                          'custom_snc_commission_amount', 'custom_snc_commission_lumpsum',
                          'custom_has_representative_commission', 'custom_representative',
                          'custom_rep_commission_type', 'custom_rep_commission_',
                          'custom_rep_commission_amount']:
                if hasattr(item, field):
                    setattr(new_item_price, field, getattr(item, field))
            if not item.custom_snc_commission_:
                new_item_price.custom_snc_commission_amount = item.custom_snc_commission_amount_per_qty
                new_item_price.custom_snc_commission_lumpsum = item.custom_snc_commission_amount_per_qty
            if not item.custom_rep_commission_:
                new_item_price.custom_rep_commission_amount = item.custom_rep_commission_amount_per_qty
            logger.info(f"Creating new Item Price {new_item_price.item_code} with rate {item.rate}")
            new_item_price.insert()
            frappe.msgprint(f"Created new Item Price {new_item_price.item_code} with rate {item.rate}")

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
    po.delivery_date = doc.delivery_date  # Use SO delivery date as PO delivery date
    po.custom_order_confirmation = doc.custom_order_confirmation
    po.schedule_date = doc.delivery_date    # Use SO delivery_date for PO schedule date
    # po.supplier = "Default"  # REMOVE

    # Loop through Sales Order items and append to Purchase Order
    for item in doc.items:
        if not item.purchase_order:
            # --- Get Supplier from Item (Option A) ---
            item_doc = frappe.get_doc("Item", item.item_code)
            supplier = item_doc.custom_preferred_supplier  # Replace 'custom_preferred_supplier'
            if not supplier:
                frappe.throw(_("Please set a preferred supplier for item {0}").format(item.item_code))
            # --- End Get Supplier ---
            po_item = po.append('items', {})
            po.custom_order_confirmation = item.custom_order_confirmation #copy the order confirmation
            po_item.item_code = item.item_code
            po_item.item_name = item.item_name
            po_item.description = item.description
            po_item.qty = item.qty
            po_item.uom = item.uom
            po_item.rate = item.rate
            po_item.custom_tn_number = item.custom_tn_number
            po_item.custom_customer_item_code = item.custom_customer_item_code
            po_item.sales_order = doc.name  # Linking Sales Order to Purchase Order items

            # --- TEMPORARILY DISABLE VALIDATION ---
            try:
                frappe.db.set_value("DocField", {"parent": "Sales Order Item", "fieldname": "schedule_date"}, "ignore_user_permissions", 1)
                frappe.db.commit()
                po_item.schedule_date = item.custom_gi_date or doc.delivery_date  # Use custom_gi_date if available, otherwise SO delivery_date
                po_item.expected_delivery_date = item.custom_gi_date or doc.delivery_date

            finally:
                frappe.db.set_value("DocField", {"parent": "Sales Order Item", "fieldname": "schedule_date"}, "ignore_user_permissions", 0)
                frappe.db.commit()
            # --- END TEMPORARILY DISABLE VALIDATION ---
    po.supplier = supplier # set supplier
    # Save and submit the Purchase Order
    po.flags.ignore_permissions = True # Very Important
    try:
        po.insert()
        po.save()
        for item in doc.items:
            if not item.purchase_order:
                item.purchase_order = po.name
        po.submit() # You might want to remove the automatic submit, see notes below.
        logger.info(f"Stock Order Items {doc.items}")
        logger.info(f"Purchase Order {po.name} created successfully!")
        frappe.msgprint(_("Purchase Order {0} created successfully!").format(po.name))

    except Exception as e:
        frappe.db.rollback()  # Rollback if any error during save/submit
        frappe.msgprint(f"Error creating Purchase Order: {e}")
        logger.error(f"Error creating Purchase Order: {e}")  # Log the full error
        raise  # Re-raise to stop the Sales Order submission


    # --- NO CHANGES NEEDED BELOW HERE for the date issue ---

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
    # Iterate through each item in the sales order
    try:
        for item in doc.items:
            item_code = item.item_code
            custom_customer_item_code = item.custom_customer_item_code

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
                    break

            if not found:
                # If not found, add a new customer item entry
                item_doc.append("customer_items", {
                    "customer_name": doc.customer,
                    "ref_code": custom_customer_item_code
                })

            # Save the Item document
            item_doc.save()
            frappe.msgprint(_("Updated customer item code for {0}").format(item_code), alert=True)

    except frappe.DoesNotExistError:
        frappe.msgprint(_("Item {0} not found.").format(item_code), alert=True)
        logger.error(f"Item {item_code} not found.")
        raise  # Re-raise to stop processing
    except Exception as e:
        frappe.msgprint(_("Error updating customer item code: {0}").format(str(e)), alert=True)
        logger.error(f"Error updating customer item code: {str(e)}")
        raise

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