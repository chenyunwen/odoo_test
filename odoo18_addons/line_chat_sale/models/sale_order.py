from odoo import fields, models, api, _

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    line_chat = fields.Many2one('line.chat', string='Line 聊天室', compute="_find_line_chat_channel", readonly=True)
    line_channel = fields.Many2one('discuss.channel', string='聊天室', compute="_find_line_chat_channel", readonly=True)

    @api.depends('partner_id')
    def _find_line_chat_channel(self):
        for property in self:
            line_chat = self.env['line.chat'].search([('partner_id', '=', property.partner_id.id)], limit=1)
            if(line_chat): 
                property.line_chat = line_chat
                property.line_channel = line_chat.channel
            else: 
                property.line_chat = False
                property.line_channel = False

    def action_quotation_send_line(self):
        self.ensure_one()
        # line_chat = self.env['line.chat'].search([('partner_id', '=', self.partner_id.id)], limit=1)
        if(self.line_chat): 
            message = f"訂單 #{self.name}\n \
            報價日期:{self.date_order}\n\
            金額（未稅+稅金=總計）:{self.amount_untaxed} + {self.amount_tax} = {self.amount_total}"

            # 將傳送此訂單的帳號加入聊天室
            if self.line_chat and self.line_chat.channel:
                channel = self.line_chat.channel.sudo()
                if self.env.user.partner_id not in channel.channel_partner_ids:
                    channel.add_members([self.env.user.partner_id.id])
            self.line_chat._post_odoo_text_message(self.line_chat.channel, f"已建立報價:\n {message}", self.env.user.partner_id)
            self.state = 'sent'

        # report = self.env.ref('sale.action_report_saleorder')
        # pdf_content, _ = report._render_qweb_pdf(self.id)
        
        # print(report)

        return  {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("已傳送"),
                'type': 'success',
                'message': _("已成功透過 LINE 發送訂單資訊"),
                'sticky': False,
            },
        }
    
    def open_confirm_wizard(self):
        return {
            'name': '確認發送報價單？',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.confirm.send.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_message': '你確定要發送這張報價單嗎？',
                'active_id': self.id,
            }
        }