# models/hr_attendance.py
from odoo import _, api, models, fields

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    check_in = fields.Datetime(string="Check In", default=fields.Datetime.now, required=True, tracking=True,readonly=True)
    check_out = fields.Datetime(string="Check Out", tracking=True, readonly=True)
    photo = fields.Binary(string=_('Check-in Photo'),required=True)
    photo_filename = fields.Char(string=_('Photo Filename'))

    def create(self, vals):
        if vals.get('photo'):
            vals['check_in'] = fields.Datetime.now()
            vals['check_out'] = fields.Datetime.now()
        return super().create(vals)
    
    def write(self, vals):
        if vals.get('photo'):
            vals['check_in'] = fields.Datetime.now()
            vals['check_out'] = fields.Datetime.now()
        return super().write(vals)
        