from odoo import fields, models

class LineChatTag(models.Model):
    _name = "line.chat.tag"
    _description = "Tags for customers"
    _order = "name"

    name = fields.Char(required=True)
    color = fields.Integer()

    _sql_constraints = [
        ('unique_tag_name', 'UNIQUE(name)', 'Property tag name must be unique.')
    ]