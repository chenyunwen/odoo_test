{
    'name': 'Line Chat Sale',
    'version': '1.0',
    'category': 'Sales/Line',
    'summary': 'Line Chat 之擴充模組，可在銷售頁面將訂單資訊透過 LINE 傳送給已具 LINE 聯繫方式的客戶。',
    'depends': ['base', 'mail', 'line_chat', 'sale_management', 'sale'],
    'data': [
      'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
}