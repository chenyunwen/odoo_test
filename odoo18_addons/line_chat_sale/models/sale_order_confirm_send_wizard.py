import base64
from odoo import _, models, fields

class SaleOrderConfirmSendWizard(models.TransientModel):
    _name = 'sale.order.confirm.send.wizard'
    _description = '確認是否發送報價單'

    message = fields.Char(default='你確定要發送這張報價單嗎？')

    def confirm_action(self):
        active_id = self.env.context.get('active_id')
        order = self.env['sale.order'].browse(active_id)
        order.action_quotation_send_line() 
        return {
            'type': 'ir.actions.act_multi',
            'actions': [{
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _("已傳送"),
                        'type': 'success',
                        'message': _("已成功透過 LINE 發送訂單資訊"),
                        'sticky': False,
                    },
                },
                {'type': 'ir.actions.act_window_close'},
            ],
        }
