# models/hr_attendance.py
from odoo import _, models, fields

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    photo = fields.Binary(string=_('Check-in Photo'))
    photo_filename = fields.Char(string=_('Photo Filename'))
