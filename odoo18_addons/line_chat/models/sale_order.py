from odoo import fields, models, api, _

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    print("_inherit = 'sale.order'")
    line_chat = fields.Many2one('line.chat', string='Line 聊天室', compute="_find_line_chat_channel", readonly=True)
    line_channel = fields.Many2one('discuss.channel', string='聊天室', compute="_find_line_chat_channel", readonly=True)

    @api.depends('partner_id')
    def _find_line_chat_channel(self):
        for property in self:
            line_chat = self.env['line.chat'].search([('partner_id', '=', property.partner_id.id)], limit=1)
            if(line_chat): 
                print('find')
                property.line_chat = line_chat
                property.line_channel = line_chat.channel
            else: 
                print('no')
                property.line_chat = False
                property.line_channel = False

    def action_quotation_send_line(self):
        line_chat = self.env['line.chat'].search([('partner_id', '=', self.partner_id.id)], limit=1)
        if(line_chat): 
            message = _("訂單 #%s\n報價日期: %s\n金額（未稅+稅金=總計）: %s + %s = %s") % (
                self.name,
                self.date_order,
                self.amount_untaxed,
                self.amount_tax,
                self.amount_total,
            )
            line_chat._post_odoo_text_message(
                line_chat.channel,
                _("已建立報價:\n%s") % message,
                line_chat.agent_partner_id
            )
        return True
