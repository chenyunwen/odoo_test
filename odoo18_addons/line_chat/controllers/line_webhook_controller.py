# controllers/main.py

from odoo import http, _
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class LineWebhookController(http.Controller):

    @http.route('/line/webhook', type='json', auth='public', methods=['POST'], csrf=False)
    def line_webhook(self, **kwargs):
        try:
            body = request.httprequest.get_data(as_text=True)
            # line_data = request.get_json_data()
            signature = request.httprequest.headers['X-Line-Signature']

            if not signature:
                # return {"error": "Missing signature"}, 403
                return {"error": _("Missing signature")}, 403

            request.env['line.chat'].sudo().handle_webhook_getMsg(body, signature)
            return {"status": "ok"}

        except Exception as e:
            _logger.error(_("Webhook 處理失敗: %s") % e, exc_info=True)
            return {
                "status": "error",
                "message": _("Webhook 處理失敗: %s") % str(e)
            }
