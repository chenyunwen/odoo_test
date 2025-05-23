import os
from odoo import models, api
# from linebot import LineBotApi

from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
)

class MailMessage(models.Model):
    _inherit = 'mail.message'
    @api.model_create_multi
    def create(self, vals_list):
        messages = super(MailMessage, self).create(vals_list)
        print('vals_list')
        print(vals_list)

        channel_id = [vals.get('res_id') for vals in vals_list if vals.get('model') == 'discuss.channel'][0]
        partner_id = [vals.get('author_id') for vals in vals_list if vals.get('model') == 'discuss.channel'][0]
        line_chat = self.env['line.chat'].search([('channel', '=', channel_id)], limit=1)
        partner = self.env['line.chat.status'].search([('partner_id', '=', partner_id)], limit=1)

        if(line_chat and partner):
            access_token = os.environ.get('LINE_ACCESS_TOKEN')
            configuration = Configuration(access_token=access_token)
            line_bot_api = MessagingApi(ApiClient(configuration))
            # line_bot_api = LineBotApi(access_token)

            for message in messages:
                # body = message.body or ''
                if(message.attachment_ids):
                    print(message.attachment_ids)
                    # attachments = message.attachment_ids.filtered(lambda a: a.mimetype and a.mimetype.startswith('image/'))
                    i = 0
                    for attachment in message.attachment_ids:
                        if(attachment.mimetype):
                            print('iiiiiii: ',i)
                            i = i+1
                            if(attachment.mimetype.startswith('image/')):
                                print(f"找到圖片附件：{attachment.name}")
                                # image_url = '/web/content/ir.attachment/%d/datas' % attachment.id
                                # base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                                # image_url = f"{base_url}/web/content/ir.attachment/{attachment.id}/datas"
                                
                                # print('image_url')
                                # print(image_url) 

                                line_chat._send_line_image_message(line_bot_api, attachment)
                                # line_bot_api.push_message(
                                #     user_id,  # 收訊人的 LINE userId
                                #     ImageSendMessage(
                                #         original_content_url=full_url,  # 原圖 URL
                                #         preview_image_url=full_url       # 預覽圖 URL (可用同一張)
                                #     )
                                # )
                            elif(attachment.mimetype.startswith('audio/')):
                                print(f"找到音訊附件：{attachment.name}")

                message_data = {
                    'subject': message.subject or '',
                    'body': message.body or '',
                    'author': message.author_id.name or '',
                    'date': str(message.date),
                    'attachment_ids': message.attachment_ids
                }

                print(line_chat._html_to_text_with_newlines(message_data['body']))
                # $$$
                # line_chat._send_line_text_message(line_bot_api, line_chat._html_to_text_with_newlines(message_data['body']))
                
        return messages
