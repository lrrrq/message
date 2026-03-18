import requests
import logging
import re
import xml.etree.ElementTree as ET
from src.collectors.base import BaseCollector

class AvantGardeCollector(BaseCollector):
    def fetch(self):
        logging.info("正在搜索全球前卫艺术与先锋设计 (Colossal/Designboom)...")
        sources = ["https://www.thisiscolossal.com/feed/", "https://www.designboom.com/feed/"]
        items = []
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        for url in sources:
            try:
                res = requests.get(url, headers=headers, timeout=15)
                root = ET.fromstring(res.text)
                for item in root.findall('./channel/item')[:3]:
                    title = item.find('title').text
                    link = item.find('link').text
                    content = item.find('{http://purl.org/rss/1.0/modules/content/}encoded')
                    content_text = content.text if content is not None else ''
                    img_urls = re.findall(r'src="([^"]+)"', content_text)
                    target_img = next((img for img in img_urls if any(ext in img.lower() for ext in ['.jpg', '.png', '.webp']) and 'avatar' not in img), "")
                    
                    if link in self.history: continue
                    items.append({
                        "title": f"🖼️ [Avant-Garde] {title[:40]}...",
                        "desc": "当代艺术审美范式参考",
                        "url": link,
                        "picurl": target_img if target_img else None,
                        "stars": "Avant-Garde"
                    })
            except Exception as e:
                logging.error(f"前卫艺术站抓取失败 ({url}): {e}")
        return items
