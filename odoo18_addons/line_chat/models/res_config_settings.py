from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    
    print('ResConfigSettings(models.TransientModel)!!!!!!!!!!!!!!!!!!!!!!!!!')
    _inherit = 'res.config.settings'

    line_sign_secret = fields.Char(string="LINE Sign Secret", config_parameter="line_chat.line_sign_secret")

    line_access_token = fields.Char(string="Channel Access Token", config_parameter="line_chat.line_access_token")
    line_secret = fields.Char(string="Channel secret", config_parameter="line_chat.line_secret")

    base_url = fields.Char(string="LINE Callback 網址", config_parameter="line_chat.base_url")
    image_path = fields.Char(string="圖片路徑", config_parameter="line_chat.image_path")
    audio_path = fields.Char(string="音訊路徑", config_parameter="line_chat.audio_path")

# api_key = self.env['ir.config_parameter'].sudo().get_param('line_chat.line_api_key')
# enabled = self.env['ir.config_parameter'].sudo().get_param('line_chat.enable_feature')

# for Boolean:
# enabled = self.env['ir.config_parameter'].sudo().get_param('line_chat.enable_feature') == 'True'
