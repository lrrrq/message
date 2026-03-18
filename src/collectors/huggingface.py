import requests
import datetime
import logging
from bs4 import BeautifulSoup
from src.collectors.base import BaseCollector

class HuggingFaceCollector(BaseCollector):
    def fetch(self):
        logging.info("正在抓取 Hugging Face 每日论文...")
        url = "https://huggingface.co/papers"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        new_items = []
        try:
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = soup.select('article')
            for article in articles:
                title_elem = article.select_one('h3 a')
                if title_elem:
                    title = title_elem.text.strip()
                    paper_url = "https://huggingface.co" + title_elem['href']
                    
                    if paper_url in self.history:
                        continue
                        
                    new_items.append({
                        "title": f"📄 [HF Paper] {title}",
                        "desc": "Hugging Face 今日推荐学术论文",
                        "url": paper_url,
                        "stars": "HF Recommend",
                        "pub_time": datetime.datetime.now().strftime("%Y-%m-%d")
                    })
                    
                    if len(new_items) >= 2:
                        break
            return new_items
        except Exception as e:
            logging.error(f"Hugging Face 抓取失败: {e}")
            return []
