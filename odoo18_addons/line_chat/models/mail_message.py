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

        channel_id = next((vals.get('res_id') for vals in vals_list if vals.get('model') == 'discuss.channel'), None)
        partner_id = next((vals.get('author_id') for vals in vals_list if vals.get('model') == 'discuss.channel'), None)
        
        if(channel_id and partner_id):
            line_chat = self.env['line.chat'].search([('channel', '=', channel_id)], limit=1)
            partner = self.env['line.chat.status'].search([('partner_id', '=', partner_id)], limit=1)

            if(line_chat and partner):
                access_token = os.environ.get('LINE_ACCESS_TOKEN')
                configuration = Configuration(access_token=access_token)
                line_bot_api = MessagingApi(ApiClient(configuration))

                image_set = []
                audio_set = []
                for message in messages:
                    if(message.attachment_ids):
                        print(message.attachment_ids)
                        # attachments = message.attachment_ids.filtered(lambda a: a.mimetype and a.mimetype.startswith('image/'))
                        for attachment in message.attachment_ids:
                            if(attachment.mimetype):
                                if(attachment.mimetype.startswith('image/')):
                                    print(f"找到圖片附件：{attachment.name}")
                                    image_set.append(attachment)

                                elif(attachment.mimetype.startswith('audio/')):
                                    print(f"找到音訊附件：{attachment.name}")
                                    audio_set.append(attachment)

                                    
                    message_data = {
                        'subject': message.subject or '',
                        'body': message.body or '',
                        'author': message.author_id.name or '',
                        'date': str(message.date),
                        'attachment_ids': message.attachment_ids
                    }

                    print(line_chat._html_to_text_with_newlines(message_data['body']))
                    
                    ''' $$$
                    if(message_data['body']):
                        line_chat._send_line_text_message(line_bot_api, line_chat._html_to_text_with_newlines(message_data['body']))
                    '''

                ''' $$$
                if(image_set):
                    line_chat._send_line_image_message(line_bot_api, image_set)
                
                '''
                
                '''$$$
                if(audio_set):
                    line_chat._send_line_audio_message(line_bot_api, audio_set)
                '''
                

        return messages
