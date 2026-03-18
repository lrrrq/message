import os
import datetime
import time
import json
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

import google.generativeai as genai
from openai import OpenAI

# ==========================================
# 0. 配置加载与初始化
# ==========================================
load_dotenv()

# 日志配置
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
LOG_FILE = os.path.join(LOG_DIR, "app.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 读取全量 API 密钥
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

WECHAT_WEBHOOK_URL = os.getenv("WECHAT_WEBHOOK_URL")

# === 企业微信自建应用 (用于微信插件首屏弹窗) ===
QYWECHAT_CORPID = os.getenv("QYWECHAT_CORPID")
QYWECHAT_SECRET = os.getenv("QYWECHAT_SECRET")
QYWECHAT_AGENTID = os.getenv("QYWECHAT_AGENTID")

# === 行业穿透：高权重关键词 (触发时自动标星并加权重) ===
FOCUS_KEYWORDS = ["传统行业自动化", "降本增效", "AI视频生成", "Sora", "效率工具", "视频模型", "Automation", "Efficiency", "Luma AI", "Runway", "Kling", "可灵"]

# 去重记录文件
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.json")


# ==========================================
# 1. 通用辅助函数
# ==========================================
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            logging.error(f"读取历史记录失败: {e}")
    return set()

def save_history(history_set):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(list(history_set), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"保存历史记录失败: {e}")

# ==========================================
# 2. 数据采集模块
# ==========================================
def fetch_github_trending(history):
    """抓取 GitHub Trending Python 区块的数据，包含防爬伪装和去重"""
    logging.info("正在抓取 GitHub Trending (Python)...")
    url = "https://github.com/trending/python?since=daily"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
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
                
                # 去重逻辑：如果该 URL 已经推送过，则跳过
                if repo_url in history:
                    continue
                    
                desc = desc_elem.text.strip() if desc_elem else "无描述"
                stars = star_elem.text.strip() if star_elem else "0"
                
                new_items.append({
                    "title": title,
                    "desc": desc,
                    "url": repo_url,
                    "stars": stars,
                    "pub_time": datetime.datetime.now().strftime("%Y-%m-%d") # Trending daily
                })
                # 记录到历史中（在推送成功后保存）
                history.add(repo_url)
                
                if len(new_items) >= 5: # 每次只取最新 5 个未推送过的避免单次报告过长
                    break
                    
        return new_items
    except requests.exceptions.RequestException as e:
        logging.error(f"GitHub 抓取请求失败: {e}")
        return []
    except Exception as e:
        logging.error(f"GitHub 解析失败: {e}")
        return []

def fetch_hackernews_ai(history):
    """抓取 Hacker News 上带有 AI/LLM 关键词且高赞的新闻"""
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
            
            # 过滤：必须有链接，且点赞数大于 20，且标题包含 AI 相关词汇
            if not url_link or points < 20: 
                continue
                
            if url_link in history:
                continue
                
            new_items.append({
                "title": title,
                "desc": f"HackerNews 热门讨论，热度分数: {points}",
                "url": url_link,
                "stars": str(points),
                "pub_time": hit.get("created_at", "").split("T")[0] # 提取 YYYY-MM-DD
            })
            history.add(url_link)
            
            if len(new_items) >= 3: # HN只取前3个
                break
        return new_items
    except Exception as e:
        logging.error(f"Hacker News 抓取失败: {e}")
        return []

def fetch_huggingface_papers(history):
    """抓取 Hugging Face Daily Papers (最火的AI前沿论文)"""
    logging.info("正在抓取 Hugging Face 每日论文...")
    # HF 官方提供了一个非正式但好用的论文列表页面，我们通过爬虫简化提取
    url = "https://huggingface.co/papers"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    new_items = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 查找论文区块
        articles = soup.select('article')
        for article in articles:
            title_elem = article.select_one('h3 a')
            if title_elem:
                title = title_elem.text.strip()
                paper_url = "https://huggingface.co" + title_elem['href']
                
                if paper_url in history:
                    continue
                    
                new_items.append({
                    "title": f"📄 论文: {title}",
                    "desc": "Hugging Face 今日推荐学术论文",
                    "url": paper_url,
                    "stars": "HF Recommend",
                    "pub_time": datetime.datetime.now().strftime("%Y-%m-%d")
                })
                history.add(paper_url)
                
                if len(new_items) >= 2: # 最多推 2 篇核心论文
                    break
        return new_items
    except Exception as e:
        logging.error(f"Hugging Face 抓取失败: {e}")
        return []

def fetch_web_aggregators(history):
    """抓取用户提供的中转站 (ThreadReader, Trends24) 并过滤出包含 AI 关键词的热点"""
    logging.info("正在扫描中转热点站 (ThreadReader, Trends24)...")
    urls_to_check = {
        "ThreadReader": "https://threadreaderapp.com/thread/popular",
        "YouTubeTrends": "https://youtube.trends24.in/",
        "TwitterTrends": "https://trends24.in/"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    
    keywords = [" AI ", "AI", "LLM", "ChatGPT", "GPT", "DeepSeek", "OpenAI", "Anthropic", "大模型", "人工智能"]
    new_items = []
    
    for site_name, url in urls_to_check.items():
        try:
            response = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 全局搜索所有超链接文本
            for a_tag in soup.find_all('a'):
                text = a_tag.get_text(strip=True)
                link = a_tag.get('href', '')
                
                # 排除空链接或相对短/异常链接
                if not text or len(text) < 5 or not link.startswith('http'):
                    continue
                    
                # 检查是否包含 AI 关键词
                if any(kw.lower() in text.lower() for kw in keywords):
                    if link in history:
                        continue
                        
                    new_items.append({
                        "title": f"[{site_name} 爆款] {text}",
                        "desc": f"从 {site_name} 榜单中意外捕获的 AI 话题",
                        "url": link,
                        "stars": "Trending"
                    })
                    history.add(link)
                    
                    if len(new_items) >= 3: # 防止单平台搜出太多噪音，最多取 3 个
                        break
        except Exception as e:
            logging.error(f"{site_name} 抓取失败: {e}")
            
    return new_items

def fetch_lab_updates(history):
    """抓取顶级 AI 实验室和视频生成领域的官方动态 (Kling, Runway, Luma)"""
    logging.info("正在潜伏侦察 AI 实验室动态 (Luma/Runway/Kling)...")
    fetch_list = [
        {"name": "Runway Blog", "url": "https://runwayml.com/blog"},
        {"name": "Luma AI", "url": "https://lumalabs.ai/blog"},
        {"name": "Kling AI", "url": "https://klingai.com/"}
    ]
    new_items = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    for lab in fetch_list:
        try:
            response = requests.get(lab['url'], headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            # 简单策略：提取前两个含有关键技术词汇的超链接
            links = soup.find_all('a', href=True)
            count = 0
            for link in links:
                text = link.get_text(strip=True)
                full_url = link['href'] if link['href'].startswith('http') else lab['url'].rstrip('/') + link['href']
                if len(text) > 15 and any(kw in text.lower() for kw in ["release", "model", "video", "gen", "new"]):
                    if full_url in history: continue
                    new_items.append({"title": f"🔬 [{lab['name']}] {text}", "desc": "官方实验室一手前沿动态", "url": full_url, "stars": "Official"})
                    history.add(full_url)
                    count += 1
                if count >= 1: break
        except Exception as e:
            logging.error(f"实验室 {lab['name']} 抓取失败: {e}")
    return new_items

def fetch_ai_commercial_news(history):
    """抓取全球关于 AI 商业化与变现的顶级创投资讯 (TechCrunch 等)"""
    logging.info("正在搜寻 AI 商业与变现风向标...")
    url = 'https://techcrunch.com/category/artificial-intelligence/feed/'
    new_items = []
    try:
        import xml.etree.ElementTree as ET
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        root = ET.fromstring(res.text)
        count = 0
        for item in root.findall('./channel/item'):
            title = item.find('title').text
            link = item.find('link').text
            if link in history:
                continue
            pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
            new_items.append({
                "title": f"💰 [商业破局] {title}",
                "desc": "最具变现潜力的硅谷 AI 商业动作与创投情报",
                "url": link,
                "stars": "Business",
                "pub_time": pub_date
            })
            history.add(link)
            count += 1
            if count >= 2: break # 取前两条
    except Exception as e:
        logging.error(f"商业风向抓取失败: {e}")
    return new_items

def fetch_visual_inspiration(history):
    """抓取高审美视觉灵感 (Civitai 真实最高赞图片)"""
    logging.info("正在提取高质量视觉模型参考图...")
    url = 'https://civitai.com/api/v1/images?limit=3&sort=Most%20Reactions&period=Day&nsfw=None'
    text_items = []
    visual_articles = []
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15).json()
        items = res.get('items', [])
        for i, item in enumerate(items):
            img_url = item.get('url')
            created_at = item.get('createdAt', '')[:10] if item.get('createdAt') else ""
            if not img_url or img_url in history:
                continue
            
            post_url = img_url # 【免登录优化】直接链接到无墙高清水印原图，不跳回强制登录的主页
            author = item.get('username', '匿名大神')
            prompt_data = item.get('meta', {}).get('prompt', '（艺术家未公开提示词，纯享视觉震撼）') if isinstance(item.get('meta'), dict) else '（提示词未公开）'
            
            # 给 LLM 用来在早报里排版的素材
            text_items.append({
                "title": f"🎨 视觉巅峰Top{i+1}: 创作者 {author}",
                "desc": f"Civitai顶级渲染原作。灵感提示：{prompt_data[:150]}...",
                "url": post_url,
                "stars": "Top 1% Aesthetic",
                "pub_time": created_at
            })
            
            # 真实画报大图 (用于独立 News 推广)
            visual_articles.append({
                "title": f"🎨 视觉巅峰Top{i+1} | 作者: {author}",
                "description": "来源: Civitai | 点击欣赏完整画质",
                "url": post_url,
                "picurl": img_url
            })
            history.add(img_url)
    except Exception as e:
        logging.error(f"Civitai 视觉获取失败: {e}")

    # 补充高质量画源：DeviantArt 专属 AI 艺术热门板块
    try:
        import xml.etree.ElementTree as ET
        da_url = 'https://backend.deviantart.com/rss.xml?q=special:popular+ai_art'
        da_res = requests.get(da_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        root = ET.fromstring(da_res.text)
        
        count = 0
        for item in root.findall('./channel/item'):
            title = item.find('title').text
            link = item.find('link').text
            media = item.find('{http://search.yahoo.com/mrss/}content')
            img_url = media.get('url') if media is not None else ''
            
            if not img_url or img_url in history:
                continue
                
            post_url = img_url # 【免登录优化】同样直接跳原图
                
            text_items.append({
                "title": f"🖌️ 艺术潮流: {title}",
                "desc": "DeviantArt 全球顶级艺术家生成范式参考",
                "url": post_url,
                "stars": "Trending Art"
            })
            
            visual_articles.append({
                "title": f"🖌️ 行家原作 | {title[:20]}",
                "description": "来源: DeviantArt | 前沿流派范式",
                "url": post_url,
                "picurl": img_url
            })
            history.add(img_url)
            count += 1
            if count >= 2: break
    except Exception as e:
        logging.error(f"DeviantArt 视觉获取失败: {e}")
        
    return text_items, visual_articles

def fetch_avant_garde_art(history):
    """从全球顶尖艺术/设计平台 (Colossal, Designboom) 抓取前卫审美源"""
    logging.info("正在搜索全球前卫艺术与先锋设计 (Colossal/Designboom)...")
    sources = [
        "https://www.thisiscolossal.com/feed/",
        "https://www.designboom.com/feed/"
    ]
    items = []
    import re
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for url in sources:
        try:
            res = requests.get(url, headers=headers, timeout=15)
            import xml.etree.ElementTree as ET
            root = ET.fromstring(res.text)
            
            for item in root.findall('./channel/item')[:5]:
                title = item.find('title').text
                link = item.find('link').text
                # 提取描述和图片
                content = item.find('{http://purl.org/rss/1.0/modules/content/}encoded')
                content_text = content.text if content is not None else ''
                
                # 正则提取第一张高质量大图
                img_urls = re.findall(r'src="([^"]+)"', content_text)
                target_img = ""
                for img in img_urls:
                    if any(ext in img.lower() for ext in ['.jpg', '.png', '.webp']) and 'avatar' not in img:
                        target_img = img
                        break
                
                if not target_img or target_img in history:
                    continue
                    
                pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
                items.append({
                    "title": f"🖼️ 前卫艺术: {title[:50]}...",
                    "desc": "来自全球顶级当代艺术平台的审美范式参考",
                    "url": link,
                    "stars": "Avant-Garde",
                    "picurl": target_img,
                    "pub_time": pub_date
                })
        except Exception as e:
            logging.error(f"前卫艺术平台抓取失败 ({url}): {e}")
            
    return items



# ==========================================
# 3. AI 处理模块 (三路回退机制策略)
# ==========================================
class AIFallbackProcessor:
    def __init__(self):
        self.providers = []
        
        # 1. 优先级最高：DeepSeek
        if DEEPSEEK_API_KEY:
            self.providers.append({
                "name": "DeepSeek",
                "func": self._call_deepseek
            })
            
        # 2. 优先级第二：Groq
        if GROQ_API_KEY:
            self.providers.append({
                "name": "Groq",
                "func": self._call_groq
            })
            
        # 3. 优先级兜底：Gemini
        if GEMINI_API_KEY:
            # 兼容旧版本调用
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                self.providers.append({
                    "name": "Gemini",
                    "func": self._call_gemini
                })
            except: pass
            
    def _call_deepseek(self, prompt):
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content
        
    def _call_groq(self, prompt):
        client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content
        
    def _call_gemini(self, prompt):
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text

    def process(self, prompt):
        if not self.providers:
            logging.warning("未检测到任何有效的 API Key，AI 步骤将被跳过。")
            return None
            
        for provider in self.providers:
            name = provider["name"]
            func = provider["func"]
            logging.info(f"👉 尝试调用 AI 提供商: {name} ...")
            try:
                result = func(prompt)
                if result:
                    logging.info(f"✅ 成功从 {name} 获取响应。")
                    return result
            except Exception as e:
                logging.error(f"❌ {name} 调用失败，准备降级。错误信息: {e}")
                continue
                
        logging.error("所有 AI 提供商全军覆没！")
        return None

class AgenticCurator:
    """受 ui-ux-pro-max 和 internal-comms 启发的 AI 策展人"""
    def __init__(self, processor):
        self.processor = processor

    def score_and_filter(self, items, top_n=8):
        """对原始抓取项进行多维度评分并筛选"""
        if not items: return []
        
        logging.info(f"🔬 AI 策展人正在对 {len(items)} 条内容进行多维审计...")
        
        # 批量评分 Prompt (减少 API 调用次数)
        items_text = ""
        for i, item in enumerate(items):
            items_text += f"ID:{i} | Title:{item['title']} | Desc:{item['desc'][:100]}\n"
            
        scoring_prompt = f"""
        你是一位顶级 AI 行业主编，兼具先锋设计师 (ui-ux-pro-max) 与 商业分析师 (internal-comms) 的眼光。
        请对以下内容进行评分，并返回一个 JSON 格式的列表。
        
        【评分标准 (0-10分)】:
        1. 💎 搞钱潜力 (Commercial): 变现路径是否清晰？是否涉及大额融资？
        2. ⚡ 技术硬核 (Tech): 是否是突破性架构？是否有 SOTA 表现？
        3. 🎨 审美高度 (Aesthetic): 是否符合先锋审美？(Brutalism, Minimalism, Glassmorphism)?
        4. 🌊 稀缺度 (Rarity): 是否是一手独家？
        
        要求：返回严谨的 JSON 数组，格式为: [{"id": 0, "score": 15.5, "reason": "..."}]
        score = 以上四项加和。
        
        【待评分列表】:
        {items_text}
        """
        
        try:
            res = self.processor.process(scoring_prompt)
            if not res:
                logging.warning("AI 策展人未返回评分结果，使用默认排序。")
                return items[:top_n]
                
            # 简单清理可能的 Markdown 标记
            json_str = res.strip().replace('```json', '').replace('```', '')
            import json as json_lib
            scores = json_lib.loads(json_str)
            
            # 兼容性检查：如果返回的不是列表
            if not isinstance(scores, list):
                logging.warning("AI 返回评分格式异常。")
                return items[:top_n]
            
            # 映射评分回到原始 items
            for s in scores:
                idx = s.get('id')
                if idx is not None and idx < len(items):
                    items[idx]['ai_score'] = s.get('score', 0)
                    items[idx]['ai_reason'] = s.get('reason', '')
            
            # 排序并取 Top N
            items.sort(key=lambda x: x.get('ai_score', 0), reverse=True)
            filtered = [it for it in items if it.get('ai_score', 0) > 12] # 过滤掉平庸内容
            logging.info(f"✅ 审计完毕，筛选出 {len(filtered[:top_n])} 条高价值信号。")
            return filtered[:top_n]
        except Exception as e:
            logging.error(f"AI 评分解析失败: {e}")
            return items[:top_n] # 降级：返回前 N 条

def refine_content_with_gemini(raw_items):
    """最终合成：注入 internal-comms 的专业叙事风格"""
    if not raw_items: return ""
    
    # 按照板块分类组织数据
    formatted_items = ""
    for item in raw_items:
        score_tag = f" (💎AI评级: {item.get('ai_score', 'N/A')}/40)"
        formatted_items += f"【{item['title']}】{score_tag}\n- 链接: {item['url']}\n- 深度点评: {item.get('ai_reason', '暂无')}\n\n"

    prompt = f"""
    你是 AI 趋势观察者 的主编。请基于以下筛选出的“高信噪比”信号，撰写一份极具质感的推送简报。
    
    【写作风格指南 (internal-comms)】:
    - 语气：专业、克制、富有洞察力。
    - 视角：以“我们” (Team / Agent) 的视角进行播报。
    - 结构：
        1. 🚀 [前沿雷达] - 覆盖技术突破与开源硬核。
        2. 💰 [金钱永不眠] - 覆盖商业变现与投融资动态。
        3. 🎨 [视觉实验室] - 覆盖顶级审美、先锋设计与多模态生成。
        4. 🧘‍♂️ [AI 禅意时刻] - 一句总结今日价值。
        
    - 注意：使用 Emoji 增加呼吸感，但严禁使用 Markdown 链接格式。
    
    【今日高价值信号】:
    {formatted_items}
    """
    
    processor = AIFallbackProcessor()
    refined_text = processor.process(prompt)
    
    if refined_text:
        return refined_text
    else:
        logging.warning("AI 最终合成失败，使用原始数据兜底。")
        # 兜底：简单拼接
        fallback_text = "AI 简报合成出现波动，以下为今日精选：\n\n"
        for it in raw_items:
            fallback_text += f"📍 {it['title']}\n🔗 {it['url']}\n\n"
        return fallback_text
      
    # 执行行业关键词加权与标星
    processed_text_list = []
    for item in raw_items:
        is_priority = any(kw.lower() in item['title'].lower() or kw.lower() in item['desc'].lower() for kw in FOCUS_KEYWORDS)
        prefix = "🌟【重点关注】" if is_priority else ""
        pub_info = f"\n⏰ 发布时间: {item.get('pub_time', '实时')}"
        processed_text_list.append(f"{prefix}标题: {item['title']}\n描述: {item['desc']}\n热度: {item['stars']}{pub_info}\n链接: {item['url']}")
        
    raw_text = "\n\n".join(processed_text_list)
    
    # 判定当前人格：06:00 - 11:59 为早报（决策者简报），其余为晚报（极客脱口秀）
    current_hour = datetime.datetime.now().hour
    is_morning = 6 <= current_hour < 12
    
    if is_morning:
        persona_name = "决策者简报模式 (早报)"
        style_instruction = """
        【人格设定：顶级商业分析师】
        当前是 09:30 早报时间，你的任务是：极致精简与分类。
        1. 你必须将所有提供的情报严格按照以下板块分类输出，不得遗漏任何一块：
           🔹 [行业风向与 AI 商业化]（重点提炼硅谷投资与变现破局）
           🔹 [开源与极客项目] 
           🔹 [大厂巨头与实验室动态]
           🎨 [高审美与视觉艺术体验]
        2. 风格：专业、冷静、干货。严禁废话，重点突出“商业变现”或“降本增效”。
        """
    else:
        persona_name = "极客脱口秀模式 (晚报/手动)"
        style_instruction = """
        【人格设定：幽默极客脱口秀专家】
        当前是晚间时间，你的任务是：深度、犀利分类播报。
        1. 你必须将所有提供的情报严格分类输出，不得遗漏任何一块：
           🔹 [铜臭味与搞钱思路]（重点关注那些拿了融资或者想通过AI变现的新闻）
           🔹 [硬核开源代码库]
           🔹 [实验室疯狂科学家们]
           🎨 [惊掉下巴的高级视觉审美]
        2. 风格：口语化、辛辣点评。针对高审美内容，展现你顶级的艺术细胞。
        """

    prompt = f"""
    你是一个拥有双重人格的“超级 AI 动态引擎”。当前正处于：{persona_name}。
    
    {style_instruction}

    【通用排版审美要求 (Text 纯文字直给)】
    - 使用丰富的 Emoji 增加视觉层次感。不要使用 Markdown 语法（如 #, **, []() 等），因为有些客户端无法完美渲染。
    - 结构必须分大板块输出（不同类型的情报放在对应的板块下）。
    - 单个项目的输出格式必须包含发布时间，建议如下：
      💡 项目：项目标题 (🔥热度)
      ⏰ 时间：原数据中的发布时间
      🔗 链接：http://...
      💬 简评：...
      ⭐ 评分：X/10
    - 请用行云流水的方式串写，让阅读有连贯体验。
    - 结尾必须单独成段落：【🧘‍♂️ AI 禅意时刻】，提炼今日价值，带点哲理。

    【以下是待处理原始数据】：
    {raw_text}
    """
    
    processor = AIFallbackProcessor()
    refined_text = processor.process(prompt, raw_text)
    
    if refined_text:
        return refined_text
    else:
        return "数据清洗失败，直接展示原始数据：\n" + raw_text

# ==========================================
# 4. 微信推送模块 (支持企微群机器人 Webhook)
# ==========================================
def send_wechat_notification(content):
    """将结果通过 Webhook 推送到企业微信群 (Text 格式，确保兼容性)"""
    logging.info("正在执行群 Webhook 推送 (Text)...")
    if not WECHAT_WEBHOOK_URL or WECHAT_WEBHOOK_URL == "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your_webhook_key_here":
        logging.warning("未配置有效的企业微信 Webhook URL，改为打印到日志。")
        logging.info(f"\n推文内容:\n{'-'*40}\n{content}\n{'-'*40}")
        return True

    payload = {
        "msgtype": "text",
        "text": {
            "content": f"👾 AI 极客动态\n================\n{content}\n\n================\n*By Antigravity Agent*"
        }
    }
    try:
        response = requests.post(WECHAT_WEBHOOK_URL, json=payload, headers={"Content-Type": "application/json"})
        if response.status_code == 200:
            logging.info("微信群 Webhook (Text) 推送成功！")
            return True
        else:
            logging.error(f"微信群推送失败: {response.text}")
            return False
    except Exception as e:
        logging.error(f"微信请求异常: {e}")
        return False

def send_wechat_news(articles):
    """发送【图文并茂】卡片（用于次要信息聚合）"""
    if not articles:
        return False
    logging.info("正在推送图文卡片画报...")
    payload = {"msgtype": "news", "news": {"articles": articles}}
    try:
        response = requests.post(WECHAT_WEBHOOK_URL, json=payload, headers={"Content-Type": "application/json"})
        return response.status_code == 200
    except:
        return False

def send_wechat_raw_image(img_url):
    """【黑科技】通过 Base64 将图片作为原生消息直接发送到对话框，实现 1:1 直显"""
    if not WECHAT_WEBHOOK_URL: return False
    logging.info(f"正在直接投送高清原图: {img_url[:50]}...")
    try:
        import base64
        import hashlib
        # 1. 下载图片
        resp = requests.get(img_url, timeout=20)
        if resp.status_code != 200: return False
        img_data = resp.content
        
        # 2. 计算 MD5
        md5_obj = hashlib.md5()
        md5_obj.update(img_data)
        md5_hex = md5_obj.hexdigest()
        
        # 3. Base64 编码
        b64_data = base64.b64encode(img_data).decode('utf-8')
        
        # 4. 发送
        payload = {
            "msgtype": "image",
            "image": {
                "base64": b64_data,
                "md5": md5_hex
            }
        }
        res = requests.post(WECHAT_WEBHOOK_URL, json=payload, headers={"Content-Type": "application/json"})
        if res.status_code == 200:
            logging.info("原生图片推送成功！")
            return True
        else:
            logging.error(f"图片推送失败: {res.text}")
    except Exception as e:
        logging.error(f"图片处理异常: {e}")
    return False

# ==========================================
# 5. 主流程控制 (未来对话能力架构说明)
# ==========================================
# [Speculation: 对话能力架构调整建议]
# 当前系统是单向推送模式（Cron-based Push）。
# 若要增加对话功能，架构需做如下调整：
# 1. 存储层：引入数据库（如 SQLite/Redis）存储 history.json 之外的消息上下文（Message Context），用于对话记忆。
# 2. 交互层：需要搭建一个 Web API 服务（如 FastAPI），作为企业微信自建应用的 Callback URL。
# 3. 路由层：解析用户消息 -> 提取意图（Query）-> 检索历史或实时搜索 -> AI 生成回复 -> 下发机器人 API。
# 4. 异步层：对话响应需要异步处理，防止 Webhook 超时。
# ==========================================
def job():
    logging.info("🚀 开始执行自动化 Agent 任务...")
    
    history = load_history()
    processor = AIFallbackProcessor()
    curator = AgenticCurator(processor)
    
    # 采集多平台数据
    github_items = fetch_github_trending(history)
    hn_items = fetch_hackernews_ai(history)
    hf_papers = fetch_huggingface_papers(history)
    aggregator_items = fetch_web_aggregators(history)
    lab_items = fetch_lab_updates(history)            
    commercial_items = fetch_ai_commercial_news(history) 
    visual_text_items, visual_news_articles = fetch_visual_inspiration(history)  
    avant_garde_items = fetch_avant_garde_art(history)
    
    # 汇总待发送文本的数据
    all_raw_items = github_items + hn_items + hf_papers + aggregator_items + lab_items + commercial_items + visual_text_items + avant_garde_items

    if not all_raw_items:
        logging.info("各大平台风平浪静，无新增数据。")
        return
        
    # --- Agentic Curating ---
    # 利用 AI 策展人进行高标准的评分和筛选，确保推送的每一条都是精品
    curated_items = curator.score_and_filter(all_raw_items, top_n=6)
    
    # 1. 发送文字主简报
    text_success = False
    if curated_items:
        refined_report = refine_content_with_gemini(curated_items)
        text_success = send_wechat_notification(refined_report)
        
    # 2. 视觉震撼：原生大图 1:1 直发
    raw_images_to_send = []
    # 优先选高分的视觉内容
    visual_pool = [it for it in all_raw_items if 'picurl' in it]
    visual_pool.sort(key=lambda x: x.get('ai_score', 0), reverse=True)
    
    for v in visual_pool: raw_images_to_send.append(v['picurl'])
    
    img_count = 0
    for img_url in raw_images_to_send:
        if img_count >= 3: break 
        if send_wechat_raw_image(img_url):
            img_count += 1
            history.add(img_url) 
            time.sleep(1) 
        
    if text_success or img_count > 0:
        save_history(history) 
    
    logging.info(f"🏁 本轮任务执行完毕。经过 AI 策展筛选，推送了 {len(curated_items)} 条高价值资讯和 {img_count} 张视觉炸弹。")


if __name__ == "__main__":
    job()

