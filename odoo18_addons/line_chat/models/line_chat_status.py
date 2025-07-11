from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LineChatStatus(models.Model):
    _name = 'line.chat.status'
    _description = _('客服人員狀態') 
    partner_id = fields.Many2one(
        'res.partner',
        string=_('客服人員'),
        domain=lambda self: self._get_internal_user_partners(),
        required=True,
        copy=False,
        index=True
    )

    serving_count = fields.Integer(string=_('服務中人數'), default=0, readonly=True, compute='_get_serving_count', store=True)

    _sql_constraints = [
        ('partner_id_unique', 'unique(partner_id)', _('客服人員不可重複！'))
    ]

    @api.model
    def _get_internal_user_partners(self):
        internal_group = self.env.ref('base.group_user')
        internal_users = self.env['res.users'].search([
            ('groups_id', 'in', internal_group.id)
        ])
        partner_ids = internal_users.mapped('partner_id').ids
        return [('id', 'in', partner_ids)]

    @api.depends('partner_id')
    def _get_serving_count(self):
        all_chats = self.env['line.chat'].search([])
        for record in self:
            count = 0
            for chat in all_chats:
                if record.partner_id in chat.channel.sudo().channel_partner_ids:
                    count += 1
            record.serving_count = count

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        agent_group = self.env.ref('line_chat.line_chat_agent_group')
        for record in records:
            user = self.env['res.users'].search([('partner_id', '=', record.partner_id.id)], limit=1)
            if user:
                if agent_group not in user.groups_id:
                    user.sudo().write({'groups_id': [(4, agent_group.id)]})

        return records