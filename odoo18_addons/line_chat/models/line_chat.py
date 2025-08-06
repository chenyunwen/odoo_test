import base64
import contextlib
import io
import os
import json
import re
import wave

# import requests
import httpx
import datetime
import tempfile
import time
# import hmac
# import hashlib
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
import requests
# from mutagen.wave import WAVE

# from dotenv import load_dotenv

from odoo import api, fields, models, exceptions, tools, _
from odoo.tools.config import config
# from datetime import date
# from dateutil.relativedelta import relativedelta
from odoo.fields import Command
# from flask import Flask, request
from bs4 import BeautifulSoup
from markupsafe import Markup

from urllib.parse import urlencode


# 載入 LINE Message API 相關函式庫
# from linebot import LineBotApi, WebhookHandler
# from linebot.exceptions import InvalidSignatureError
# from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageSendMessage

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError

from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
    ImageMessage,
    AudioMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

from .. import constants



class LineChat(models.Model):
    _name = 'line.chat'

    name = fields.Char(string='客戶 LINE 名稱', readonly=True, copy=False)
    line_user_id = fields.Char(string='Line ID', readonly=True, copy=False)
    line_picture_url = fields.Char(string="LINE 頭貼網址", readonly=True)
    partner_id = fields.Many2one(
        'res.partner', string='聯絡人名稱', index=True, readonly=True, copy=False, 
    )
    # agent_partner_id = fields.Many2one(
    #     'res.partner', string='客服人員', index=True, readonly=True, copy=False, 
    # )
    agent_partner_ids = fields.Many2many(
        'res.partner', string='客服人員', index=True, copy=False, readonly=True,  
        compute="_get_agent_partner",
    )
    channel = fields.Many2one('discuss.channel', string='聊天室', readonly=True)
    tag_ids = fields.Many2many('line.chat.tag', string="Tags")

    @api.depends("channel.channel_partner_ids")
    def _get_agent_partner(self):
        for property in self:
            # property.agent_partner_id_2 = property.channel.channel_partner_ids
            property.agent_partner_ids = property.channel.sudo().channel_partner_ids.filtered(
                lambda p: p.id != property.partner_id.id
            )
            if not property.agent_partner_ids:
                admin = self.env.ref('base.user_admin')
                self.channel.add_members([admin.partner_id.id])
                property.channel.channel_partner_ids += admin.partner_id

    # --------------------------------------------------------------------------
    
    @api.model
    def handle_webhook_getMsg(self, body, signature):
        """處理從 controller 傳來的 LINE 資料並回覆訊息"""

        json_data = json.loads(body) 

        config = self.env['ir.config_parameter'].sudo()

        access_token = config.get_param(constants.LINE_CONFIG_KEYS["access_token"])
        secret = config.get_param(constants.LINE_CONFIG_KEYS["secret"])

        configuration = Configuration(access_token=access_token)
        handler = WebhookHandler(secret)
        self._validate_signature(handler, body, signature)
        line_bot_api = MessagingApi(ApiClient(configuration))

        for event in json_data['events']:
            try:
                message_type = event['message']['type']
                reply_token = event['replyToken']
                line_user_id = event['source']['userId']
                profile = line_bot_api.get_profile(line_user_id)
                line_name = profile.display_name
                line_image_url = profile.picture_url

                timestamp = event['timestamp'] / 1000
                dt = datetime.datetime.fromtimestamp(timestamp)
                filename = dt.strftime('%Y%m%d_%H%M%S')  # '20250520_025052'

                existing_user = self.env['line.chat'].search([('line_user_id', '=', line_user_id)], limit=1)
                if not existing_user:
                    print("new user")
                    existing_user = self._create_new_line_chat_user(line_name, line_user_id, line_image_url)
                    if message_type == 'text' and event['message']['text'].lower().startswith('推薦碼：'):
                        code = event['message']['text'].split('：')[-1].strip()
                        ref_user = self.env['line.chat.status'].search([('referral_code', '=', code)], limit=1)
                        if ref_user and ref_user.partner_id not in existing_user.channel.channel_partner_ids:
                            existing_user.channel.add_members([ref_user.partner_id.id])

                curr_partner_id = existing_user.partner_id
                curr_agent_partner_ids = existing_user.agent_partner_ids
                curr_channel = existing_user.channel
                self._update_user_line_image_url(existing_user, line_image_url)
                    
            except Exception as e:
                raise exceptions.ValidationError(_("創建資料時錯誤: %s") % e)

            if curr_channel:
                if message_type == 'text':
                    text = event['message']['text'] if message_type == 'text' else None
                    reply = _("已收到您說：\n%s\n請稍等客服回應") % text
                    
                    self._post_odoo_text_message(curr_channel, text, curr_partner_id)
                    # self._reply_line_message(line_bot_api, reply_token, reply)
                    # self._post_odoo_text_message(curr_channel, reply, curr_agent_partner_ids[0])

                    #   $$$
                    # self._send_line_text_message(line_bot_api, reply)
                    # self._post_odoo_text_message(curr_channel, reply, curr_agent_partner_id)

                elif message_type == 'image':
                    message_id = event['message']['id']
                    message_content, content_type = self._download_line_media_file_with_retry(message_id, access_token)
                    
                    image_set = event['message'].get('imageSet')
                    if image_set:
                        image_set_id = event['message']['imageSet']['id']
                        index = event['message']['imageSet']['index']
                        total = event['message']['imageSet']['total']
                        self._post_odoo_image_set_message(curr_channel, message_content, content_type, filename, image_set_id, total == index, curr_partner_id)
                    else:
                        self._post_odoo_image_message(curr_channel, message_content, content_type, filename, curr_partner_id)
                
                elif message_type == 'audio':
                    message_id = event['message']['id']
                    message_content, content_type = self._download_line_media_file_with_retry(message_id, access_token)
                    self._post_odoo_audio_message(curr_channel, message_content, content_type, filename, curr_partner_id)

                elif message_type == 'sticker':
                    headers = {"Authorization": f"Bearer {access_token}"}
                    stickerId = event['message']['stickerId']
                    self._post_odoo_sticker_message(headers, stickerId, curr_channel, filename, curr_partner_id)
                    
                else:
                    text = _("非文字訊息")
                    reply = _("暫時無法解析 %s 類別的訊息") % message_type
                    self._post_odoo_text_message(curr_channel, text, curr_partner_id)
                    self._reply_line_message(line_bot_api, reply_token, reply)
                    self._post_odoo_text_message(curr_channel, reply, curr_agent_partner_ids[0])
            # else:
            #     print("尚未建立聊天室。")



    # 
    def _validate_signature(self, handler, body, signature):
        try:
            handler.handle(body, signature)
        except Exception as e:
            raise exceptions.ValidationError(_("LINE 簽章驗證失敗: %s") % e)
    

    def _download_line_media_file_with_retry(self, message_id, access_token, retries=3, delay=2):
        url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        with httpx.Client() as client:
            for attempt in range(retries):
                response = client.get(url, headers=headers)
                if response.status_code == 200:
                    return response.content, response.headers.get('content-type', '')
                elif response.status_code == 202:
                    print(f"Content not ready, retry {attempt + 1}/{retries} after {delay} seconds")
                    time.sleep(delay)
                else:
                    raise Exception(f"Failed to get message content: {response.status_code}")
            raise Exception("Exceeded max retries to get message content")
        
    
    def _create_new_line_chat_user(self, line_name, line_user_id, picture_url):
        image_data = False

        if picture_url:
            try:
                response = requests.get(picture_url)
                if response.status_code == 200:
                    image_data = base64.b64encode(response.content)
            except Exception as e:
                raise exceptions.ValidationError(f"無法下載 LINE 頭像：{e}")
        fake_partner = self.env['res.partner'].create({'name': f"Guest-{line_name}", 'image_1920': image_data,})
        # customer_group = self.env.ref('line_chat.line_chat_customer_group')
        # fake_partner.sudo().write({'groups_id': [(4, customer_group.id)]})

        # least_busy_agent = self.env['line.chat.status'].search([], order='serving_count ASC', limit=1)
        # if least_busy_agent and least_busy_agent.partner_id:
        #     members_to_add = [Command.link(least_busy_agent.partner_id.id)]
        # else:
        

        least_busy_agent = self.env.ref('base.user_admin')
        existing_status = self.env['line.chat.status'].search([('partner_id', '=', least_busy_agent.partner_id.id)], limit=1)
        if not existing_status:
            self.env['line.chat.status'].create({
                'partner_id': least_busy_agent.partner_id.id,
            })
        members_to_add = [Command.link(least_busy_agent.partner_id.id)]
        
        # least_busy_agent.serving_count += 1
        members_to_add.append(Command.link(fake_partner.id))

        # channel = self.env['discuss.channel'].create({
        #     'name': line_name,
        #     'channel_type': 'chat',
        #     'channel_partner_ids': members_to_add
        # })
        
        # -----
        # channel = self.env['discuss.channel'].create({
        #     'name': 'Private Channel',
        #     'channel_type': 'group',
        #     'channel_partner_ids': [(6, 0, self.partner_employee.id)]
        # })
        channel = self.env['discuss.channel'].create({
            'name': f"Guest-{line_name}（LINE）",
            'channel_type': 'group',
            'channel_partner_ids': members_to_add,
            'image_128': image_data
        })
        # channel = self.env['discuss.channel'].create_group(partners_to=members_to_add)
        # ------

        return self.env['line.chat'].create({
            'name': line_name,
            'line_user_id': line_user_id,
            'line_picture_url': picture_url,
            'partner_id': fake_partner.id,
            'channel': channel.id,
            'agent_partner_ids':  [(4, least_busy_agent.partner_id.id)]
        })
    
    def _update_user_line_image_url(self, existing_user, picture_url):
        if existing_user.line_picture_url != picture_url:
            response = requests.get(picture_url)
            if response.status_code == 200:
                existing_user.partner_id.image_1920 = base64.b64encode(response.content)
                existing_user.channel.image_128 = base64.b64encode(response.content)
                existing_user.line_picture_url = picture_url

    def _reply_line_message(self, line_bot_api, reply_token, text):
        try:
            messages = [
                TextMessage(text=f"r : {text}"),
                TextMessage(text="r請稍等客服回應")
            ]
            reply_request = ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages
            )
            line_bot_api.reply_message(reply_request)

        except Exception as e:
            raise exceptions.ValidationError(_("即時回覆 LINE 訊息時錯誤: %s") % e)


    def _send_line_text_message(self, line_bot_api, text):
        try:
            messages = [
                TextMessage(text=text)
            ]

            push_request = PushMessageRequest(
                to=self.line_user_id,
                messages=messages
            )

            line_bot_api.push_message(push_request)
            # line_bot_api.push_message(self.line_user_id, TextSendMessage(text))
            
        except Exception as e:
            raise exceptions.ValidationError(_("回覆 LINE 訊息時錯誤: %s") % e)
    
    def _send_line_image_message(self, line_bot_api, attachments, expire_seconds=300):
        config = self.env['ir.config_parameter'].sudo()
        # secret = config.get_param('line_chat.line_sign_secret')

        try:
            BASE_URL = config.get_param('line_chat.base_url')
            IMAGE_PATH = constants.DEFAULTS["image_path"]

            messages = []
            for attachment in attachments:
                # expires = int(time.time()) + expire_seconds
                # data = f"{attachment.id}:{expires}".encode('utf-8')
                # data = f"{attachment.id}".encode('utf-8')
                # signature = hmac.new(secret.encode(), data, hashlib.sha256).hexdigest()

                
                ext = os.path.splitext(attachment.name or '')[1] or '.jpg'
                # params = urlencode({'signature': signature, 'expires': expires})
                # params = urlencode({'signature': signature})
                url = f"{BASE_URL}{IMAGE_PATH}/{attachment.id}{ext}" # ?{params}"
                print(f"IMAGE URL: {url}")
                # line_bot_api.push_message(
                #     self.line_user_id,  
                #     ImageSendMessage(
                #         original_content_url=url,
                #         preview_image_url=url,
                #     )
                # )
                messages.append(
                    ImageMessage(
                        original_content_url=url,
                        preview_image_url=url
                    )
                )

            push_request = PushMessageRequest(
                to=self.line_user_id,
                messages=messages
            )

            line_bot_api.push_message(push_request)
        except Exception as e:
            raise exceptions.ValidationError(_("LINE 傳送圖片失敗：%s") % e)
        
    def get_audio_duration_ms(self, attachment):
        try:
            # 將 binary 轉成音訊物件
            audio_data = base64.b64decode(attachment.datas)
            
            # 建立暫時檔案讀取（因 mutagen 只吃檔案路徑）
            suffix = os.path.splitext(attachment.name or '')[1] or '.m4a'
            tmp_path = None
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name

            if suffix in ['.mp3', '.m4a', '.mp4', '.aac']:
                try:
                    if suffix in ['.mp3']:
                        audio = MP3(tmp_path)
                    elif suffix in ['.m4a', '.mp4', '.aac']:
                        audio = MP4(tmp_path)
                    
                    if audio and audio.info.length:
                        duration_ms = int(audio.info.length * 1000)
                        return duration_ms
                except Exception as e:
                    raise ValueError(_("無法讀取音訊： %s") % e)

            elif suffix in ['.wav']:
                try:
                    with contextlib.closing(wave.open(io.BytesIO(audio_data), 'rb')) as wf:
                        frames = wf.getnframes()
                        rate = wf.getframerate()
                        duration = frames / float(rate)
                        duration_ms = int(duration * 1000)
                        return duration_ms
                except Exception as e:
                    raise exceptions.ValidationError(_("無法讀取wav音訊： %s") % e)
            else:
                raise exceptions.ValidationError(_("不支援的音訊格式： %s") % suffix)
        except Exception as e:
            raise exceptions.ValidationError(_("無法取得語音長度：%s") % e)

    def _send_line_audio_message(self, line_bot_api, attachments, expire_seconds=300):
        
        config = self.env['ir.config_parameter'].sudo()
        # secret = config.get_param('line_chat.line_sign_secret')

        try:
            BASE_URL = config.get_param('line_chat.base_url')
            AUDIO_PATH = constants.DEFAULTS["audio_path"]

            messages = []
            for attachment in attachments:
                # expires = int(time.time()) + expire_seconds
                # data = f"{attachment.id}:{expires}".encode('utf-8')
                # data = f"{attachment.id}".encode('utf-8')
                # signature = hmac.new(secret.encode(), data, hashlib.sha256).hexdigest()
                
                ext = os.path.splitext(attachment.name or '')[1] or '.m4a'
                url = f"{BASE_URL}{AUDIO_PATH}/{attachment.id}{ext}"
                print(f"Audio URL: {url}")

                duration_ms = self.get_audio_duration_ms(attachment)

                messages.append(
                    AudioMessage(
                        original_content_url=url,
                        duration=duration_ms
                    )
                )

            push_request = PushMessageRequest(
                to=self.line_user_id,
                messages=messages
            )

            line_bot_api.push_message(push_request)

        except Exception as e:
            raise exceptions.ValidationError(_("LINE 傳送語音失敗： %s") % e)

    def _post_odoo_sticker_message(self, headers, stickerId, channel, filename, partner_id, retries=3, delay=2):
        with httpx.Client() as client:
            for attempt in range(retries):
                response = client.get(f'https://stickershop.line-scdn.net/stickershop/v1/sticker/{stickerId}/android/sticker.png', headers=headers)
                if response.status_code == 200:
                    message_content, content_type = response.content, response.headers.get('content-type', '')
                    attachment = self.env['ir.attachment'].create({
                        'name': f'{filename}.jpg',
                        'datas': base64.b64encode(message_content).decode('utf-8'),
                        'res_model': 'discuss.channel',
                        'res_id': channel.id,
                        'mimetype': content_type,
                    })
                    msg = channel.message_post(
                        body='(sticker)',
                        message_type='comment',
                        subtype_xmlid='mail.mt_comment',
                        author_id=partner_id.id
                    )
                    msg.write({'attachment_ids': [(4, attachment.id)]})
                    return
                elif response.status_code == 202:
                    print(f"Content not ready, retry {attempt + 1}/{retries} after {delay} seconds")
                    time.sleep(delay)
                else:
                    raise Exception(f"Failed to get message content: {response.status_code}")
            raise Exception("Exceeded max retries to get message content")

    def _post_odoo_text_message(self, channel, text, partner_id):
        try:
            
            html_text = self._text_to_html_with_linebreaks_and_links(text)
            # print(html_text)

            msg = channel.message_post(
                body=html_text,
                # subject= subject if subject else None,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                author_id=partner_id.id
            )
            # print("訊息 ID：", msg.id)
            # print("發送者 ID：", partner_id.id)

        except Exception as e:
            raise exceptions.ValidationError(_("發送訊息時錯誤： %s") % e)
        
    def _post_odoo_image_message(self, channel, image_bytes, content_type, filename, partner_id):
        attachment = self.env['ir.attachment'].create({
            'name': f'{filename}.jpg',
            'datas': base64.b64encode(image_bytes).decode('utf-8'),  # Odoo 附件要 base64 字串
            'res_model': 'discuss.channel',
            'res_id': channel.id,  # 討論頻道ID
            'mimetype': content_type,
        })
        msg = channel.message_post(
            body='(image)',
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            author_id=partner_id.id
        )
        msg.write({'attachment_ids': [(4, attachment.id)]})

        # msg = self.env['mail.message'].create({
        #     'body': '',
        #     'message_type': 'comment',
        #     'subtype_id': self.env.ref('mail.mt_comment').id,
        #     'model': 'discuss.channel',
        #     'res_id': channel.id,
        #     'attachment_ids': [(4, attachment.id)],
        #     'author_id': partner_id.id
        # })

    def _post_odoo_image_set_message(self, channel, image_bytes, content_type, filename, image_set_id, is_last_one, partner_id):
        attachment = self.env['ir.attachment'].create({
            'name': f'{filename}.jpg',
            'datas': base64.b64encode(image_bytes).decode('utf-8'),
            'res_model': 'discuss.channel',
            'res_id': channel.id,
            'mimetype': content_type,
        })

        existing_image_set = self.env['line.image.set'].search([('image_set_id', '=', image_set_id)], limit=1)
        if not existing_image_set:
            msg = channel.message_post(
                body='(images)',
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                author_id=partner_id.id
            )
            msg.write({'attachment_ids': [(4, attachment.id)]})
            self.env['line.image.set'].create({
                'image_set_id': image_set_id,
                'message_id': msg.id
            })
        else:
            existing_image_set.message_id.write({'attachment_ids': [(4, attachment.id)]})
            # count = len(existing_image_set.message_id.attachment_ids)

            if(is_last_one):
                existing_image_set.unlink()
        
    def _post_odoo_audio_message(self, channel, audio_bytes, content_type, filename, partner_id):
        attachment = self.env['ir.attachment'].create({
            'name': f'{filename}.mp3',
            'datas': base64.b64encode(audio_bytes).decode('utf-8'),
            'res_model': 'discuss.channel',
            'res_id': channel.id,
            'mimetype': content_type,
        })
        msg = channel.message_post(
            body='(audio)',
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            author_id=partner_id.id
        )
        msg.write({'attachment_ids': [(4, attachment.id)]})
        print("msg.id is : ", msg.id)


    def _html_to_text_with_newlines(self, html):
        soup = BeautifulSoup(html or '', 'html.parser')

        for br in soup.find_all("br"):
            br.replace_with("\n")
        
        for p in soup.find_all("p"):
            p.insert_after("\n")

        text = soup.get_text()

        # 移除連續空白行
        # text = "\n".join(line.strip() for line in text.splitlines() if line.strip())

        return text.rstrip()
    

    def _text_to_html_with_linebreaks_and_links(self, text: str) -> str:
        if not text:
            return ""

        def linkify(line: str) -> str:
            url_pattern = re.compile(r'(https?://[^\s<>"]+)')
            return url_pattern.sub(r'<a href="\1">\1</a>', line)
        
        lines = text.splitlines()
        while lines and not lines[-1].strip():
            lines.pop()

        processed_lines = [linkify(line.strip()) if line.strip() else "" for line in lines]

        # 用 <br> 串起來，包在單一 <p> 裡
        html = "<p>" + "<br>".join(processed_lines) + "</p>"

        return Markup(html)