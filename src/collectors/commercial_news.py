import requests
import logging
import xml.etree.ElementTree as ET
from src.collectors.base import BaseCollector

class CommercialNewsCollector(BaseCollector):
    def fetch(self):
        logging.info("正在搜寻 AI 商业与变现风向标 (TechCrunch)...")
        url = 'https://techcrunch.com/category/artificial-intelligence/feed/'
        new_items = []
        try:
            res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            root = ET.fromstring(res.text)
            count = 0
            for item in root.findall('./channel/item'):
                title = item.find('title').text
                link = item.find('link').text
                if link in self.history:
                    continue
                pub_date_raw = item.find('pubDate').text if item.find('pubDate') is not None else ""
                from email.utils import parsedate_to_datetime
                try:
                    pub_time = parsedate_to_datetime(pub_date_raw).strftime("%Y-%m-%d")
                except:
                    pub_time = "2026-03-19" # 兜底
                
                new_items.append({
                    "title": f"💰 [AI 商业] {title}",
                    "desc": "硅谷 AI 商业动作与创投情报",
                    "url": link,
                    "stars": "Business",
                    "pub_time": pub_time
                })
                count += 1
                if count >= 2: break
            return new_items
        except Exception as e:
            logging.error(f"TechCrunch 抓取失败: {e}")
            return []
