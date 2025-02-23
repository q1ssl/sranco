#stock_order_dashboard.py

from frappe import _

def get_data():
    return {
        'fieldname': 'purchase_order',  # The field on Stock Order that links to Purchase Order
        'transactions': [
            {
                'label': _('Related Documents'),  # You can customize this label
                'items': ['Purchase Order']      # The DocType we're linking to
            }
        ],
        # 'internal_links': {  #  *Not* needed in this case
        #     'Purchase Order': 'custom_stock_order'
        # },
        'non_standard_fieldnames': {
            'Purchase Order': 'custom_stock_order'
        }
    }