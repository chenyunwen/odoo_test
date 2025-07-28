from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import base64

PREFIX = "ELOM"
OFFSET = 10000

class LineChatStatus(models.Model):
    _name = 'line.chat.status'
    _description = _('客服人員名單') 
    partner_id = fields.Many2one(
        'res.partner',
        string=_('客服人員'),
        domain=lambda self: self._get_internal_user_partners(),
        required=True,
        copy=False,
        index=True
    )

    group_role = fields.Char(
        string='所屬群組',
        compute='_compute_group',
        readonly=True,
        store=False
    )

    referral_code = fields.Char(string='推薦代碼', compute='_generate_referral_code', readonly=True, store=True)

    # serving_count = fields.Integer(string=_('服務中人數'), default=0, readonly=True, compute='_get_serving_count', store=True)

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
    def _generate_referral_code(self) -> str:
        for record in self:
            partner_id = record.partner_id.id
            value = int(partner_id) + OFFSET
            base36 = record.base36_encode(value)
            record.referral_code = f"{PREFIX}-{base36.upper()}"

    @staticmethod
    def base36_encode(number: int) -> str:
        """將數字轉為 base36 編碼"""
        alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
        base36 = ""
        while number:
            number, i = divmod(number, 36)
            base36 = alphabet[i] + base36
        return base36 or "0"
        
    # @api.depends('partner_id')
    # def _get_serving_count(self):
    #     all_chats = self.env['line.chat'].search([])
    #     for record in self:
    #         count = 0
    #         for chat in all_chats:
    #             if record.partner_id in chat.channel.sudo().channel_partner_ids:
    #                 count += 1
    #         record.serving_count = count

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
    
    # def unlink(self):
    #     for record in self:
    #         user = self.env['res.users'].search([('partner_id', '=', record.partner_id.id)], limit=1)
    #         group = self.env.ref('line_chat.line_chat_agent_group')
    #         if user and group:
    #             user.groups_id = [(3, group.id)]

    #     return super().unlink()

    
    @api.depends('partner_id')
    def _compute_group(self):
        group_manager = self.env.ref('line_chat.line_chat_manager_group')
        group_agent = self.env.ref('line_chat.line_chat_agent_group')

        for record in self:
            user = self.env['res.users'].search([('partner_id', '=', record.partner_id.id)], limit=1)
            if group_manager and group_manager in user.groups_id:
                record.group_role = '管理員'
            elif group_agent and group_agent in user.groups_id:
                record.group_role = '業務'
            else:
                user.sudo().write({'groups_id': [(4, group_agent.id)]})
                record.group_role = '業務'