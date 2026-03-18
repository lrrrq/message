import requests
import logging
import base64
import hashlib
import time
from src.utils.config import WECHAT_WEBHOOK_URL

class WeChatNotifier:
    @staticmethod
    def send_text(content):
        if not WECHAT_WEBHOOK_URL:
            logging.warning("未配置 WECHAT_WEBHOOK_URL，消息将仅打印到日志。")
            logging.info(f"\n[WeChat Content]:\n{content}")
            return True

        payload = {
            "msgtype": "text",
            "text": {
                "content": f"👾 AI 极客动态\n================\n{content}\n\n================\n*By Antigravity Agent*"
            }
        }
        try:
            response = requests.post(WECHAT_WEBHOOK_URL, json=payload, timeout=30)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"WeChat 文本推送异常: {e}")
            return False

    @staticmethod
    def send_image(img_url):
        if not WECHAT_WEBHOOK_URL: return False
        try:
            resp = requests.get(img_url, timeout=20)
            if resp.status_code != 200: return False
            img_data = resp.content
            
            md5_obj = hashlib.md5()
            md5_obj.update(img_data)
            md5_hex = md5_obj.hexdigest()
            b64_data = base64.b64encode(img_data).decode('utf-8')
            
            payload = {
                "msgtype": "image",
                "image": {
                    "base64": b64_data,
                    "md5": md5_hex
                }
            }
            res = requests.post(WECHAT_WEBHOOK_URL, json=payload, timeout=30)
            return res.status_code == 200
        except Exception as e:
            logging.error(f"WeChat 图片推送异常: {e}")
            return False
