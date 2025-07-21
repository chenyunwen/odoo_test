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
                    if status:
                        status.serving_count += 1
        return res
