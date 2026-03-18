import requests
import logging
from src.collectors.base import BaseCollector

class HackerNewsCollector(BaseCollector):
    def fetch(self):
        logging.info("正在抓取 Hacker News (AI相关)...")
        url = "http://hn.algolia.com/api/v1/search_by_date?query=AI&tags=story"
        new_items = []
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            
            for hit in data.get("hits", []):
                title = hit.get("title", "")
                url_link = hit.get("url", "")
                points = hit.get("points", 0)
                
                if not url_link or points < 20: 
                    continue
                    
                if url_link in self.history:
                    continue
                    
                new_items.append({
                    "title": f"💡 [HackerNews] {title}",
                    "desc": f"HN 热门讨论，热度: {points}",
                    "url": url_link,
                    "stars": str(points),
                    "pub_time": hit.get("created_at", "").split("T")[0]
                })
                
                if len(new_items) >= 3:
                    break
            return new_items
        except Exception as e:
            logging.error(f"Hacker News 抓取失败: {e}")
            return []
