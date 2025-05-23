import base64
import contextlib
import io
import os
import json
import wave

import requests
import httpx
import datetime
import tempfile
import time
import hmac
import hashlib
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.wave import WAVE

# from dotenv import load_dotenv

from odoo import api, fields, models, exceptions, tools
from odoo.tools.config import config
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.fields import Command
from flask import Flask, request
from bs4 import BeautifulSoup

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



class LineChat(models.Model):
    _name = 'line.chat'

    name = fields.Char(string='客戶 LINE 名稱', readonly=True, copy=False)
    line_user_id = fields.Char(string='Line ID', readonly=True, copy=False)
    partner_id = fields.Many2one(
        'res.partner', string='聯絡人名稱', index=True, readonly=True, copy=False, 
    )
    agent_partner_id = fields.Many2one(
        'res.partner', string='客服人員', index=True, readonly=True, copy=False, 
    )
    channel = fields.Many2one('discuss.channel', string='聊天室', readonly=True)


    # --------------------------------------------------------------------------
    
    @api.model
    def handle_webhook_getMsg(self, body, signature):
        """處理從 controller 傳來的 LINE 資料並回覆訊息"""

        json_data = json.loads(body) 

        access_token = os.environ.get('LINE_ACCESS_TOKEN')
        secret = os.environ.get('LINE_SECRET')

        configuration = Configuration(access_token=access_token)
        handler = WebhookHandler(secret)

        self._validate_signature(handler, body, signature)

        line_bot_api = MessagingApi(ApiClient(configuration))
        # line_bot_api = LineBotApi(access_token)
        print('json_data')
        print(json_data)
        # event = json_data['events'][0]
        for event in json_data['events']:
            try:
                message_type = event['message']['type']
                reply_token = event['replyToken']
                line_user_id = event['source']['userId']
                profile = line_bot_api.get_profile(line_user_id)
                line_name = profile.display_name
                timestamp = event['timestamp'] / 1000
                dt = datetime.datetime.fromtimestamp(timestamp)
                filename = dt.strftime('%Y%m%d_%H%M%S')  # '20230520_153025'

                existing_user = self.env['line.chat'].search([('line_user_id', '=', line_user_id)], limit=1)
                if not existing_user:
                    print("new user")
                    existing_user = self._create_new_line_chat_user(line_name, line_user_id)
                else:
                    print("existing user")

                curr_partner_id = existing_user.partner_id
                curr_agent_partner_id = existing_user.agent_partner_id
                curr_channel = existing_user.channel
                    
            except Exception as e:
                raise exceptions.ValidationError(f"創建資料時錯誤: {e}")
            

            print(message_type)
            if curr_channel:
                if message_type == 'text':
                    text = event['message']['text'] if message_type == 'text' else None
                    reply = f"已收到您說：\n{text}\n請稍等客服回應"
                    
                    self._post_odoo_text_message(curr_channel, text, curr_partner_id)
                    # auto reply
                    self._reply_line_message(line_bot_api, reply_token, reply)
                    self._post_odoo_text_message(curr_channel, reply, curr_agent_partner_id)

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
                        
                else:
                    text = '非文字訊息'
                    reply= f"暫時無法解析 {message_type} 類別的訊息"
                    self._post_odoo_text_message(curr_channel, text, curr_partner_id)
                    self._reply_line_message(line_bot_api, reply_token, reply)
                    self._post_odoo_text_message(curr_channel, reply, curr_agent_partner_id)
            else:
                print("尚未建立聊天室。")



    # 
    def _validate_signature(self, handler, body, signature):
        try:
            handler.handle(body, signature)
        except Exception as e:
            raise exceptions.ValidationError(f"LINE 簽章驗證失敗: {e}")
    

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
        
    
    def _create_new_line_chat_user(self, line_name, line_user_id):
        fake_partner = self.env['res.partner'].create({'name': f"{line_name} (LINE)"})

        least_busy_agent = self.env['line.chat.status'].search([], order='serving_count ASC', limit=1)
        if least_busy_agent and least_busy_agent.partner_id:
            members_to_add = [Command.link(least_busy_agent.partner_id.id)]
        else:
            least_busy_agent = self.env.ref('base.user_admin')
            members_to_add = [Command.link(least_busy_agent.partner_id.id)]

        least_busy_agent.serving_count += 1

        # print('user id:', self.env.user.id)
        # print('user name:', self.env.user.name)
        # print('partner id:', members_to_add[0])
        # print('partner name:', self.env.user.partner_id.name)

        members_to_add.append(Command.link(fake_partner.id))

        channel = self.env['discuss.channel'].create({
            'name': line_name,
            'channel_type': 'chat',
            'channel_partner_ids': members_to_add
        })

        print("實際聊天室成員：")
        for p in channel.channel_partner_ids:
            print(f"- {p.name} (ID: {p.id})")

        return self.env['line.chat'].create({
            'name': line_name,
            'line_user_id': line_user_id,
            'partner_id': fake_partner.id,
            'channel': channel.id,
            'agent_partner_id': least_busy_agent.partner_id.id
        })
    

    def _reply_line_message(self, line_bot_api, reply_token, text):
        try:
            messages = [
                TextMessage(text=text),
                TextMessage(text="請稍等客服回應")
            ]
            reply_request = ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages
            )
            line_bot_api.reply_message(reply_request)
            # line_bot_api.reply_message(reply_token, [TextSendMessage(text), TextSendMessage("請稍等客服回應")])

        except Exception as e:
            raise exceptions.ValidationError(f"即時回覆 LINE 訊息時錯誤: {e}")


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
            raise exceptions.ValidationError(f"回覆 LINE 訊息時錯誤: {e}")
    
    def _send_line_image_message(self, line_bot_api, attachments, expire_seconds=300):
        
        secret = os.environ.get('LINE_SIGN_SECRET')  # 要跟 Controller 中一樣

        try:
            messages = []
            for attachment in attachments:
                # expires = int(time.time()) + expire_seconds
                # data = f"{attachment.id}:{expires}".encode('utf-8')
                data = f"{attachment.id}".encode('utf-8')
                signature = hmac.new(secret.encode(), data, hashlib.sha256).hexdigest()

                BASE_URL = os.environ.get('BASE_URL')
                IMAGE_PATH = os.environ.get('IMAGE_PATH')
                ext = os.path.splitext(attachment.name or '')[1] or '.jpg'
                # params = urlencode({'signature': signature, 'expires': expires})
                # params = urlencode({'signature': signature})
                url = f"{BASE_URL}{IMAGE_PATH}/{attachment.id}{ext}" # ?{params}"
                print(url)

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
            print(messages)    
            push_request = PushMessageRequest(
                to=self.line_user_id,
                messages=messages
            )

            line_bot_api.push_message(push_request)
        except Exception as e:
            raise exceptions.ValidationError(f"LINE 傳送圖片失敗：{e}")
        
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
                    
                    print('audio')
                    print(audio)
                    if audio and audio.info.length:
                        duration_ms = int(audio.info.length * 1000)
                        return duration_ms
                except Exception as e:
                    raise ValueError(f"無法讀取音訊：{e}")  
                  
            elif suffix in ['.wav']:
                try:
                    with contextlib.closing(wave.open(io.BytesIO(audio_data), 'rb')) as wf:
                        frames = wf.getnframes()
                        rate = wf.getframerate()
                        duration = frames / float(rate)
                        duration_ms = int(duration * 1000)
                        return duration_ms
                except Exception as e:
                    raise exceptions.ValidationError(f"無法讀取wav音訊：{e}")
            else:
                raise exceptions.ValidationError(f"不支援的音訊格式：{suffix}")
        except Exception as e:
            raise exceptions.ValidationError(f"無法取得語音長度：{e}")

    def _send_line_audio_message(self, line_bot_api, attachment, expire_seconds=300):
        
        secret = os.environ.get('LINE_SIGN_SECRET')  # 要跟 Controller 中一樣

        try:
            messages = []
            # expires = int(time.time()) + expire_seconds
            # data = f"{attachment.id}:{expires}".encode('utf-8')
            data = f"{attachment.id}".encode('utf-8')
            signature = hmac.new(secret.encode(), data, hashlib.sha256).hexdigest()

            BASE_URL = os.environ.get('BASE_URL')
            AUDIO_PATH = os.environ.get('AUDIO_PATH')  # 假設你有 audio 路徑
            ext = os.path.splitext(attachment.name or '')[1] or '.m4a'
            url = f"{BASE_URL}{AUDIO_PATH}/{attachment.id}{ext}"

            print(f"Audio URL: {url}")

            duration_ms = self.get_audio_duration_ms(attachment)
            # 預設語音長度，如果你無法解析 duration，可暫時寫死或後續補強
            # duration_ms = 5000  # 假設為 5 秒，之後可從 metadata 抓

            # 建立 LINE AudioMessage
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
            raise exceptions.ValidationError(f"LINE 傳送語音失敗：{e}")

    def _post_odoo_text_message(self, channel, text, partner_id):
        try:
            print(text)
            msg = channel.message_post(
                body=text,
                # subject= subject if subject else None,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                author_id=partner_id.id
            )
            # print("訊息 ID：", msg.id)
            # print("發送者 ID：", partner_id.id)

        except Exception as e:
            raise exceptions.ValidationError(f"發送訊息時錯誤: {e}")
        
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

    def _post_odoo_image_set_message(self, channel, image_bytes, content_type, filename, image_set_id, is_lest_one, partner_id):
        attachment = self.env['ir.attachment'].create({
            'name': f'{filename}.jpg',
            'datas': base64.b64encode(image_bytes).decode('utf-8'),  # Odoo 附件要 base64 字串
            'res_model': 'discuss.channel',
            'res_id': channel.id,  # 討論頻道ID
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
            count = len(existing_image_set.message_id.attachment_ids)
            print('iiiiiiiiiiiiiiiiiiiiiiii')
            print(count)
            if(is_lest_one):
                existing_image_set.unlink()
        
    def _post_odoo_audio_message(self, channel, audio_bytes, content_type, filename, partner_id):
        attachment = self.env['ir.attachment'].create({
            'name': f'{filename}.mp3',  # 檔名改成音訊檔
            'datas': base64.b64encode(audio_bytes).decode('utf-8'),  # base64編碼音訊資料
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

        # 把 <br> 換成換行
        for br in soup.find_all("br"):
            br.replace_with("\n")
        
        # 把 <p> 標籤後面加換行
        for p in soup.find_all("p"):
            p.insert_after("\n")

        # 擷取文字
        text = soup.get_text()

        # 移除連續空白行（可選）
        # text = "\n".join(line.strip() for line in text.splitlines() if line.strip())

        return text
        
    # -----------------------------------------------------------------------------
    # @api.depends('fakeId')
    def action_create_channel(self):
        print("hiiiiiiiiiiiiiii")
        fake_partner = self.env['res.partner'].create({
            'name': f"Guest{666}",
            # 'email': f"fake{00}@example.com",
        })
        line_name = '名字'
        members_to_add = [Command.link(self.env.user.partner_id.id)]
        print('user id:', self.env.user.id)
        print('user name:', self.env.user.name)
        print('partner id:', self.env.user.partner_id.id)
        print('partner name:', self.env.user.partner_id.name)
        members_to_add.append(Command.link(fake_partner.id))
        group = self.env['discuss.channel'].create({
            'name': line_name,
            'channel_type': 'group',
            # 'visibility': 'private',
            'channel_partner_ids': members_to_add #[(6, 0, test_user.partner_id.id)]
        })
        self.channel = group
        print("實際聊天室成員：")
        for p in group.channel_partner_ids:
            print(f"- {p.name} (ID: {p.id})")

        reply = '非文字訊息'
        if self.channel:
            msg = self.channel.message_post(
                body=reply,
                subject='訊息標題（可選）',
                # subtype_xmlid='mail.mt_note',  # 留言類型（可選）
                # partner_ids=[fake_partner.id],
                # attachment_ids=[附件ID],
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
            print("訊息 ID：", msg.id)
        else:
            print("尚未建立聊天室。")


    def action_message(self):
        if self.channel:
            msg = self.channel.message_post(
                body='你的訊息內容',
                subject='訊息標題（可選）',
                # subtype_xmlid='mail.mt_note',  # 留言類型（可選）
                # partner_ids=[fake_partner.id],
                # attachment_ids=[附件ID],
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
            print("訊息 ID：", msg.id)
        else:
            print("尚未建立聊天室。")