from odoo import fields, models


class LineImageSet(models.Model):
    _name = 'line.image.set'

    image_set_id = fields.Char(string='id', readonly=True, copy=False)
    message_id = fields.Many2one('mail.message', string='Message ID', readonly=True, copy=False)