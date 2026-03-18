import requests
import logging
from bs4 import BeautifulSoup
from src.collectors.base import BaseCollector

class WebAggregatorCollector(BaseCollector):
    def fetch(self):
        logging.info("正在扫描中转热点站 (ThreadReader, Trends24)...")
        urls_to_check = {
            "ThreadReader": "https://threadreaderapp.com/thread/popular",
            "Trends24": "https://trends24.in/"
        }
        
        headers = {"User-Agent": "Mozilla/5.0"}
        keywords = [" AI ", "AI", "LLM", "ChatGPT", "GPT", "DeepSeek", "OpenAI", "大模型", "人工智能"]
        new_items = []
        
        for site_name, url in urls_to_check.items():
            try:
                response = requests.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(response.text, 'html.parser')
                for a_tag in soup.find_all('a'):
                    text = a_tag.get_text(strip=True)
                    link = a_tag.get('href', '')
                    if not text or len(text) < 5 or not link.startswith('http'):
                        continue
                    if any(kw.lower() in text.lower() for kw in keywords):
                        if link in self.history:
                            continue
                        new_items.append({
                            "title": f"🔥 [{site_name}] {text}",
                            "desc": f"从 {site_name} 榜单捕获的 AI 话题",
                            "url": link,
                            "stars": "Trending"
                        })
                        if len(new_items) >= 3:
                            break
            except Exception as e:
                logging.error(f"{site_name} 抓取失败: {e}")
        return new_items
