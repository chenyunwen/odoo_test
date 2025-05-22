from odoo import api, fields, models, exceptions, tools

class LineChatStatus(models.Model):
    _name = 'line.chat.status'
    _description = '客服人員狀態'

    # name = fields.Char(readonly=True, copy=False)
    partner_id = fields.Many2one(
        'res.partner', string='客服人員',
        domain=lambda self: self._get_internal_user_partners(),
        required=True,
        copy=False,
        index=True
    )

    serving_count = fields.Integer(string='服務中人數', default=0, readonly=True)

    _sql_constraints = [
        ('partner_id_unique', 'unique(partner_id)', '客服人員 partner_id 不可重複！')
    ]
    
    @api.model
    def _get_internal_user_partners(self):
        internal_group = self.env.ref('base.group_user')
        internal_users = self.env['res.users'].search([
            ('groups_id', 'in', internal_group.id)
        ])
        partner_ids = internal_users.mapped('partner_id').ids
        return [('id', 'in', partner_ids)]