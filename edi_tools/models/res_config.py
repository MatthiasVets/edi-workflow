from openerp.osv import osv
from odoo import fields

class edi_tools_config_settings(osv.osv_memory):
    _name = 'edi.tools.config.settings'
    _inherit = 'res.config.settings'

    default_edi_root_directory = fields.Char(size=256, default_model='edi.tools.config.settings')

    _defaults = {
        'default_edi_root_directory': 'EDI',
    }
