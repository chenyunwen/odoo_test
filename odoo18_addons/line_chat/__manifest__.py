{
    'name': 'Line Chat',
    'version': '1.0',
    'category': 'Tutorials',
    'summary': 'Summary!',
    'depends': ['base', 'mail', 'sale'],
    'data': [
      'security/ir.model.access.csv',
      'views/line_chat_views.xml',
      'views/line_chat_status_views.xml',
      'views/line_image_set_views.xml',
      'views/sale_order_views.xml',
      'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': True,
    'post_init_hook': 'create_default_channel',
}