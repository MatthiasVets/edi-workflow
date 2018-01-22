{
    'name': 'edi_routes_orders_handig',
    'summary': 'Handig ORDERS communication using the EDI framework',
    'description' : """
Handig ORDERS communication using the EDI framework
====================================================

This module implements routes for the following implementations.

    * handig.nl JSON

    """,
    'version': '1.0',
    'category': 'EDI Tools',
    'author': 'Clubit BVBA',
    'website': 'http://www.clubit.be',
    'depends': [
        'edi_tools',
        'sale',
    ],
    'data': [
        'data/config.xml',
    ],
    'installable': True,
    'auto_install': False,
}
