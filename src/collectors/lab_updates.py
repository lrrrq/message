import requests
import logging
from bs4 import BeautifulSoup
from src.collectors.base import BaseCollector

class LabUpdatesCollector(BaseCollector):
    def fetch(self):
        logging.info("正在潜伏侦察 AI 实验室动态 (Luma/Runway/Kling)...")
        labs = [
            {"name": "Runway", "url": "https://runwayml.com/blog"},
            {"name": "Luma AI", "url": "https://lumalabs.ai/blog"},
            {"name": "Kling AI", "url": "https://klingai.com/"}
        ]
        new_items = []
        headers = {"User-Agent": "Mozilla/5.0"}
        
        for lab in labs:
            try:
                response = requests.get(lab['url'], headers=headers, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                links = soup.find_all('a', href=True)
                for link in links:
                    text = link.get_text(strip=True)
                    full_url = link['href'] if link['href'].startswith('http') else lab['url'].rstrip('/') + link['href']
                    if len(text) > 15 and any(kw in text.lower() for kw in ["release", "model", "video", "gen", "new"]):
                        if full_url in self.history: continue
                        new_items.append({
                            "title": f"🔬 [{lab['name']}] {text}",
                            "desc": "官方实验室一手前沿动态",
                            "url": full_url,
                            "stars": "Official"
                        })
                        break # 每个实验室取一条
            except Exception as e:
                logging.error(f"实验室 {lab['name']} 抓取失败: {e}")
        return new_items
