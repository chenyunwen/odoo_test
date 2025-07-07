import os
from odoo import http, _
from odoo.http import request
import base64
import hmac
import hashlib
import time
from .. import constants

class SecureMediaController(http.Controller):

    @http.route(f'{constants.DEFAULTS["image_path"]}/<int:attachment_id>.<string:ext>', type='http', auth='public', methods=['GET'], csrf=False)
    def secure_image(self, attachment_id, signature=None, expires=None, **kw):
        attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
        if not attachment.exists():
            return request.not_found(description=_("找不到指定的圖片附件"))

        image_data = base64.b64decode(attachment.datas or '')
        ext = os.path.splitext(attachment.name or '')[1] or '.jpg'
        filename = f'image{ext}'

        return request.make_response(image_data, headers=[
            ('Content-Type', attachment.mimetype),
            ('Content-Disposition', f'inline; filename="{filename}"')
        ])
    
    @http.route(f'{constants.DEFAULTS["audio_path"]}/<int:attachment_id>.<string:ext>', type='http', auth='public', methods=['GET'], csrf=False)
    def secure_audio(self, attachment_id, signature=None, expires=None, **kw):
        attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
        if not attachment.exists():
            return request.not_found(description=_("找不到指定的音訊附件"))

        image_data = base64.b64decode(attachment.datas or '')
        ext = os.path.splitext(attachment.name or '')[1] or '.mp3'
        filename = f'audio{ext}'

        return request.make_response(image_data, headers=[
            ('Content-Type', attachment.mimetype),
            ('Content-Disposition', f'inline; filename="{filename}"')
        ])
