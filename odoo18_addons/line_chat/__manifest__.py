{
    'name': 'Line Chat',
    'version': '1.0',
    'category': 'Sales/Line',
    'summary': '將 Odoo 中的客服訊息與 LINE 官方帳號串接，並支援圖片與音訊回覆。',
    'depends': ['base', 'mail'], # ,'sale'
    'data': [
      'security/groups.xml',
      'security/ir.model.access.csv',
      'views/line_chat_views.xml',
      'views/line_chat_status_views.xml',
      'views/line_chat_tag_views.xml',
      'views/line_image_set_views.xml',
      'views/res_config_settings_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    # 'post_init_hook': 'create_default_channel',
}