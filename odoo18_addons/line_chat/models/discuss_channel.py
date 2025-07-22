from odoo import exceptions, models, api

class Channel(models.Model):
    _inherit = 'discuss.channel'

    def add_members(self, partner_ids):
        try:
            res = super().add_members(partner_ids)
        except Exception as e:
            raise exceptions.ValidationError("Failed to add members: %s", e)

        for channel in self:
            related_line_chats =  self.env['line.chat'].search([('channel', '=', channel.id)])
            if related_line_chats:
                for pid in partner_ids:
                    status = self.env['line.chat.status'].search([('partner_id', '=', pid)], limit=1)
                    if not status:
                        # status.serving_count += 1
                        # customer_group = self.env.ref('line_chat.line_chat_customer_group')
                        # status.partner_id.sudo().write({'groups_id': [(4, customer_group.id)]})
                        self.env['line.chat.status'].create({
                            'partner_id': pid,
                        })
        return res
