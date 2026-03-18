import requests
import datetime
import logging
from bs4 import BeautifulSoup
from src.collectors.base import BaseCollector

class GithubTrendingCollector(BaseCollector):
    def fetch(self):
        logging.info("正在抓取 GitHub Trending (Python)...")
        url = "https://github.com/trending/python?since=daily"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        
        new_items = []
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            repos = soup.select('article.Box-row')
            
            for repo in repos:
                title_elem = repo.select_one('h2 a')
                desc_elem = repo.select_one('p')
                star_elem = repo.select_one('a.Link--muted')
                
                if title_elem:
                    title = title_elem.text.strip().replace('\n', '').replace(' ', '')
                    repo_url = "https://github.com" + title_elem['href']
                    
                    if repo_url in self.history:
                        continue
                        
                    desc = desc_elem.text.strip() if desc_elem else "无描述"
                    stars = star_elem.text.strip() if star_elem else "0"
                    
                    new_items.append({
                        "title": f"🚀 [GitHub] {title}",
                        "desc": desc,
                        "url": repo_url,
                        "stars": stars,
                        "pub_time": datetime.datetime.now().strftime("%Y-%m-%d")
                    })
                    
                    if len(new_items) >= 5:
                        break
            return new_items
        except Exception as e:
            logging.error(f"GitHub 抓取失败: {e}")
            return []
