import os
from odoo import http
from odoo.http import request
import base64
import hmac
import hashlib
import time

class SecureMediaController(http.Controller):

    SIGN_SECRET = os.environ.get('LINE_SIGN_SECRET')
    IMAGE_PATH = os.environ.get('IMAGE_PATH')
    AUDIO_PATH = os.environ.get('AUDIO_PATH')

    @http.route(f'{IMAGE_PATH}/<int:attachment_id>.<string:ext>', type='http', auth='public', methods=['GET'], csrf=False)
    def secure_image(self, attachment_id, signature=None, expires=None, **kw):

        # if not signature or not expires:
        # if not signature:
        #     return request.not_found()

        # try:
        #     expires = int(expires)
        # except ValueError:
        #     return request.not_found()

        # if time.time() > expires:
        #     return request.not_found()

        # data = f"{attachment_id}:{expires}".encode('utf-8')
        # data = f"{attachment_id}".encode('utf-8')
        # expected_signature = hmac.new(self.SIGN_SECRET.encode(), data, hashlib.sha256).hexdigest()

        # if not hmac.compare_digest(expected_signature, signature):
        #     return request.not_found()

        attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
        if not attachment.exists():
            return request.not_found()

        image_data = base64.b64decode(attachment.datas or '')
        ext = os.path.splitext(attachment.name or '')[1] or '.jpg'
        filename = f'image{ext}'

        return request.make_response(image_data, headers=[
            ('Content-Type', attachment.mimetype),
            ('Content-Disposition', f'inline; filename="{filename}"')
            # ('Content-Disposition', f'attachment; filename="{filename}"')
        ])
    
    @http.route(f'{AUDIO_PATH}/<int:attachment_id>.<string:ext>', type='http', auth='public', methods=['GET'], csrf=False)
    def secure_audio(self, attachment_id, signature=None, expires=None, **kw):

        attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
        if not attachment.exists():
            return request.not_found()

        image_data = base64.b64decode(attachment.datas or '')
        ext = os.path.splitext(attachment.name or '')[1] or '.mp3'
        filename = f'audio{ext}'

        return request.make_response(image_data, headers=[
            ('Content-Type', attachment.mimetype),
            ('Content-Disposition', f'inline; filename="{filename}"')
            # ('Content-Disposition', f'attachment; filename="{filename}"')
        ])