from datetime import datetime, timedelta
from openerp import SUPERUSER_ID
from openerp import api, fields, models, _
from openerp.exceptions import UserError
from openerp.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT
from openerp.addons.edi_tools.models.exceptions import EdiValidationError
import openerp.addons.decimal_precision as dp
import logging
import json
_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model
    def edi_import_orders_handig_validator(self, ids):
        _logger.debug("Validating handig order")

        # Read the EDI Document
        edi_db = self.env['edi.tools.edi.document.incoming']
        document = edi_db.browse(ids)
        document.ensure_one()

        try:
            data = json.loads(document.content)
            if not data:
                raise EdiValidationError('EDI Document is empty.')
        except Exception:
            raise EdiValidationError('Content is not valid JSON.')

        if not 'number' in data:
            raise EdiValidationError('Could not find field: number.')

        if self.env['sale.order'].search([('client_order_ref','=',data["number"])]):
            raise EdiValidationError('Sale order exists with the same number.')

        unknown_eans = []
        for line in data['line_items']:
	    product = self.env['product.product'].search([('barcode', '=', line['product']['sku'])], limit=1)
            if not product:
              unknown_eans.append(line['product']['sku'])
            
        if unknown_eans:
            raise EdiValidationError('Product(s) with ean %s unknown.' % ', '.join(unknown_eans)) 

        # If we get all the way to here, the document is valid
        return True

    @api.model
    def receive_edi_import_orders_handig(self, document_id):
        document = self.env['edi.tools.edi.document.incoming'].browse(document_id)
        document.ensure_one()
        return self.edi_import_orders_handig(document)

    @api.model
    def edi_import_orders_handig(self, document):
        data = json.loads(document.content)
        name = self.create_sale_order_handig(data)
        if not name:
            raise except_orm(_('No sales order created!'), _('Something went wrong while creating the sales order.'))
        edi_db = self.env['edi.tools.edi.document.incoming']
	edi_db.message_post(body=_("Sale order <em>%s</em> <b>created</b>.") % (name))
        return True

    @api.model
    def _build_party_header_handig(self, param, data):
	partner_db = self.env['res.partner']
        _logger.debug("partnerdb set") 
        customer_address = data['billing_address']
        _logger.debug("var customer_address set")
        shipping_address = data['shipping_address']
        _logger.debug("var shipping_address set")
        invoice_address = data['billing_address']
        _logger.debug("var invoice_address set")
           
        if data['user'] is None:
           _logger.debug("No User Created, fetching email from root: %s", data['email'])
           billing_partner, shipping_partner = self.resolve_customer_info(data['billing_address'], data['shipping_address'], data['email'],param)
	else:
           _logger.debug("User Created, fetchin email from user: %s", data['user']['email'])
           billing_partner, shipping_partner = self.resolve_customer_info(data['billing_address'], data['shipping_address'], data['user']['email'],param)
        
	_logger.debug("param after customer resolve: %s",param)
        _logger.debug("billing_partner after customer resolve: %s",billing_partner)

	param['partner_id'] = billing_partner.id
	param['partner_invoice_id'] = billing_partner.id
	param['partner_shipping_id'] = shipping_partner.id

	_logger.debug("All partners found in param: %s", param)

        return param

    @api.model
    def create_sale_order_handig(self, data):
	param = {}

	_logger.debug("Building Party Header")
        param = self._build_party_header_handig(param, data)
	_logger.debug("Building Sale Order with data :%d", data)
        param = self.create_sale_order(param, data)

        # Actually create the sale order
        _logger.debug("Creating Sales Order with params: %s", param)
	sid = self.env['sale.order'].create(param)
        so = self.env['sale.order'].browse(sid.id)
	return so.name

    @api.model
    def create_sale_order(self, param, data):
	# Prepare the call to create a sale order
        param['origin'] = data['number']
        param['picking_policy'] = 'one'
        param['client_order_ref'] = data['number']
        param['fiscal_position'] = 1
        param['pricelist_id'] = 1
        param['payment_term_id'] = 5

	# TO DO : Get Fiscal position from partner : self.env['res.partner'].browse(param['partner_id']).property_account_position_id
	#fiscal_pos = self.env['account.fiscal.position'].browse(param['fiscal_position']) or False

        # Create the line items
        pricelist_db = self.env['product.pricelist']
        param['order_line'] = []
        for line in data['line_items']:
	    product = self.env['product.product'].search([('barcode', '=', line['product']['sku'])], limit=1)
            line_params = (0, False, {
                'name' 			: product.name,
                'product_id'            : product.id,
                'product_uom'           : product.uom_id.id,
                'product_uos_qty'       : line['quantity'],
                'product_uom_qty'       : line['quantity'],
                'price_unit'            : line['price'],
                'type'                  : 'make_to_stock',
                'tax_id'                : [(6, 0, [3])],
            })
            param['order_line'].append(line_params)
        
        if data['promotion_total'] != "0":
            product = self.env['product.product'].search([('id', '=', 12302)], limit=1)
	    line_promotion_params = (0, False, {
	    	'name'			: data['promotion_code'],
     		'product_id'            : 12302,
		'product_uom'           : product.uom_id.id,
		'product_uos_qty'       : 1,
                'product_uom_qty'       : 1,
                'price_unit'            : (float(-1)*(float(data['promotion_total']))),
                'type'                  : 'make_to_stock',
                'tax_id'                : [(6, 0, [3])],
	    })
	    param['order_line'].append(line_promotion_params)
	
        product = self.env['product.product'].search([('id', '=', 5)], limit=1)
	line_shipping_params = (0, False, {
		'name'			: product.name,
     		'product_id'            : product.id,
		'product_uom'           : product.uom_id.id,
		'product_uos_qty'       : 1,
                'product_uom_qty'       : 1,
                'price_unit'            : data['shipping_total'],
                'type'                  : 'make_to_stock',
                'tax_id'                : [(6, 0, [3])],
	})
	param['order_line'].append(line_shipping_params)
        
        
	return param

    @api.model
    def resolve_customer_info(self, billing_address, shipping_address, email, param):
        partner_db = self.env['res.partner']
        country_db = self.env['res.country']
        _logger.debug("Resolving Customer with email %s", email)
        # Check if this partner already exists
        billing_partner = partner_db.search([('email', '=', email)], limit=1)
        if billing_partner:
            _logger.debug("BP Found : %s", billing_partner)
            # Check if the shipment address exists
            country_id = self.env['res.country'].search([('code', '=', shipping_address['country'])]).id
            _logger.debug("country_id %s", country_id)
	    shipping_partner = False
            partners = partner_db.search([('parent_id', '=', billing_partner.id)])
	    _logger.debug("partners %s", partners)
            _logger.debug("shipping_address: %s", shipping_address)
            for partner in partners:
                if self.partner_exists(partner, param, country_id, shipping_address):
                    shipping_partner = partner
		    _logger.debug("shipping_partner %s", shipping_partner)

            if shipping_partner:
		_logger.debug("SP Found")
                return billing_partner, shipping_partner
            
            
        # If the billing address doesn't exist yet, create it
        if not billing_partner:
            _logger.debug("No Billing Partner Found, Searching Country")
            country_id = country_db.search([('code', '=', billing_address['country'])])
            vals = {
                'active'     : True,
                'customer'   : True,
                'is_company' : False, # to be upgraded : if VAT > True
                'city'       : billing_address['city'],
                'zip'        : billing_address['zipcode'],
                'country_id' : country_id[0].id,
                'email'      : email,
                'phone'      : billing_address['telephone'],
                'name'       : billing_address['firstname'] + ' ' + billing_address['lastname']
            }
            if billing_address['house_number_alt'] is None:
                    _logger.debug("No house number alt, not filling data")
                    vals['street'] = billing_address['street'] + ' ' + billing_address['house_number']
	    else:
                    _logger.debug("House number alt found, filling data")
                    vals['street'] = billing_address['street'] + ' ' + billing_address['house_number'] + ' ' + billing_address['house_number_alt']
            _logger.debug("Creating partner with vals: %s", vals)
            billing_partner = partner_db.create(vals)

        # If the shipping address doesn't exist yet, create it
	_logger.debug("Creating Shipping Partner")
        country_id = country_db.search([('code', '=', shipping_address['country'])])
        vals = {
                'active'     : True,
                'customer'   : True,
                'is_company' : False,
                'parent_id'  : billing_partner.id,
                'type'	     : 'delivery',
                'city'       : shipping_address['city'],
                'zip'        : shipping_address['zipcode'],
                'country_id' : country_id[0].id,
                'email'      : email,
                'phone'      : shipping_address['telephone'],
                'name'       : shipping_address['firstname'] + ' ' + shipping_address['lastname']
        }

        if shipping_address['house_number_alt'] is None:
                _logger.debug("No house number alt, not filling data")
                vals['street'] = shipping_address['street'] + ' ' + shipping_address['house_number']
        else:
                _logger.debug("House number alt found, filling data")
                vals['street'] = shipping_address['street'] + ' ' + shipping_address['house_number'] + ' ' + shipping_address['house_number_alt']
        _logger.debug("Creating partner with vals: %s", vals)

        shipping_partner = partner_db.create(vals)
        return billing_partner, shipping_partner

    @api.model
    def partner_exists(self, partner, params, country_id, shipping_address):
        return partner.name == shipping_address['firstname'] + ' ' + shipping_address['lastname'] and \
               partner.city == shipping_address['city'] and \
               partner.zip == shipping_address['zipcode'] and \
               partner.street == shipping_address['street'] + ' ' + shipping_address['house_number'] and \
               partner.country_id.id == country_id
