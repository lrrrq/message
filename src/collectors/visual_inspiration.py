import requests
import logging
import xml.etree.ElementTree as ET
from src.collectors.base import BaseCollector

class VisualInspirationCollector(BaseCollector):
    def fetch(self):
        logging.info("正在提取视觉模型参考图 (Civitai/DeviantArt)...")
        new_items = []
        
        # 1. Civitai
        try:
            url = 'https://civitai.com/api/v1/images?limit=3&sort=Most%20Reactions&period=Day&nsfw=None'
            res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15).json()
            for i, item in enumerate(res.get('items', [])):
                img_url = item.get('url')
                if not img_url or img_url in self.history: continue
                author = item.get('username', '匿名')
                new_items.append({
                    "title": f"🎨 [Civitai] 创作者 {author}",
                    "desc": f"今日高赞视觉渲染作品",
                    "url": img_url,
                    "picurl": img_url,
                    "stars": "Top Aesthetic"
                })
                if len(new_items) >= 2: break
        except Exception as e:
            logging.error(f"Civitai 抓取失败: {e}")

        # 2. DeviantArt
        try:
            da_url = 'https://backend.deviantart.com/rss.xml?q=special:popular+ai_art'
            da_res = requests.get(da_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            # 使用 content 避免编码问题引起的 mismatched tag 错误
            root = ET.fromstring(da_res.content)
            count = 0
            for item in root.findall('./channel/item'):
                title = item.find('title').text
                link = item.find('link').text
                media = item.find('{http://search.yahoo.com/mrss/}content')
                img_url = media.get('url') if media is not None else ''
                if not img_url or img_url in self.history: continue
                new_items.append({
                    "title": f"🖌️ [DeviantArt] {title[:30]}",
                    "desc": "艺术流派范式参考",
                    "url": img_url, # 使用图片 URL 作为唯一标识
                    "picurl": img_url,
                    "stars": "Trending Art"
                })
                count += 1
                if count >= 2: break
        except Exception as e:
            logging.error(f"DeviantArt 抓取失败: {e}")
            
        return new_items
