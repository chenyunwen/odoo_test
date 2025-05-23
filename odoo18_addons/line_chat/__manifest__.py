{
    'name': 'Line Chat',
    'version': '1.0',
    'category': 'Tutorials',
    'summary': 'Summary!',
    'depends': ['base', 'mail'],
    'data': [
      'security/ir.model.access.csv',
      'views/line_chat_views.xml',
      'views/line_chat_status_views.xml',
      'views/line_image_set_views.xml',
    ],
    'installable': True,
    'application': True,
    'post_init_hook': 'create_default_channel',
}