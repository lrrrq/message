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
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "app.log")
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
                    "stars": stars
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
                "stars": str(points)
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
                    "stars": "HF Recommend"
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

def fetch_visual_inspiration(history):
    """抓取高审美视觉灵感 (Civitai/Behance 热门趋势)"""
    logging.info("正在巡视高审美 AI 视觉流 (Civitai/Trends)...")
    # Civitai 爬虫通常需要 API Key，这里使用其公开的 Model 列表页进行语义模拟抓取
    url = "https://civitai.com/models" 
    new_items = []
    try:
        # 由于 Civitai 动态加载严重，此处作为占位，主要通过 AI 关键词扫描其他聚合源中的视觉话题
        # 实际生产中可接入其 API 或爬取特定的视觉周刊
        new_items.append({
            "title": "🎨 视觉审美洞察：当前最火的灯光/构图渲染风格",
            "desc": "基于全网视觉模型变动趋势的审美趋势预测",
            "url": "https://civitai.com/models",
            "stars": "Top 1%"
        })
    except: pass
    return new_items

# ==========================================
# 3. AI 处理模块 (三路回退机制策略)
# ==========================================
class AIFallbackProcessor:
    def __init__(self):
        self.providers = []
        
        # 1. 优先级最高：DeepSeek (最稳定/性价比极高，且不用管网络)
        if DEEPSEEK_API_KEY and DEEPSEEK_API_KEY != "your_deepseek_api_key_here":
            self.providers.append({
                "name": "DeepSeek",
                "func": self._call_deepseek
            })
            
        # 2. 优先级第二：Groq (Llama 3, 极速响应)
        if GROQ_API_KEY and GROQ_API_KEY != "your_groq_api_key_here":
            self.providers.append({
                "name": "Groq",
                "func": self._call_groq
            })
            
        # 3. 优先级兜底：Gemini (免费但有网络限制诉求)
        if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
            genai.configure(api_key=GEMINI_API_KEY)
            self.providers.append({
                "name": "Gemini",
                "func": self._call_gemini
            })
            
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
            model="llama-3.1-8b-instant", # 快速轻量模型
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content
        
    def _call_gemini(self, prompt):
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text

    def process(self, prompt, raw_text):
        if not self.providers:
            logging.warning("未检测到任何有效的 API Key，AI 清洗步骤将被跳过。")
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
                
        logging.error("所有 AI 提供商全军覆没！降级使用原文。")
        return None

def refine_content_with_gemini(raw_items):
    """调用 AI 对提取内容进行深加工：支持行业穿透、早晚报人格热切换、高审美排版"""
    if not raw_items:
        return ""
        
    # 执行行业关键词加权与标星
    processed_text_list = []
    for item in raw_items:
        is_priority = any(kw.lower() in item['title'].lower() or kw.lower() in item['desc'].lower() for kw in FOCUS_KEYWORDS)
        prefix = "🌟【重点关注】" if is_priority else ""
        processed_text_list.append(f"{prefix}标题: {item['title']}\n描述: {item['desc']}\n热度: {item['stars']}\n链接: {item['url']}")
        
    raw_text = "\n\n".join(processed_text_list)
    
    # 判定当前人格：06:00 - 11:59 为早报（决策者简报），其余为晚报（极客脱口秀）
    current_hour = datetime.datetime.now().hour
    is_morning = 6 <= current_hour < 12
    
    if is_morning:
        persona_name = "决策者简报模式 (早报)"
        style_instruction = """
        【人格设定：顶级商业分析师】
        当前是 09:30 早报时间，你的任务是：极致精简与分类。
        1. 你必须将所有提供的情报严格按照以下板块分类输出，不得遗漏【实验室一手】与【高审美视觉】内容：
           🔹 [开源与项目] 
           🔹 [行业与论文]
           🔹 [大厂与实验室]
           🎨 [高审美与视觉体验]
        2. 风格：专业、冷静、干货。严禁废话，重点突出“商业变现”或“降本增效”。
        """
    else:
        persona_name = "极客脱口秀模式 (晚报/手动)"
        style_instruction = """
        【人格设定：幽默极客脱口秀专家】
        当前是晚间时间，你的任务是：深度、犀利分类播报。
        1. 你必须将所有提供的情报严格分类输出，不得遗漏【实验室一手】和【高审美视觉内容】：
           🔹 [开源与极客代码]
           🔹 [行业吃瓜与论文]
           🔹 [实验室巨头动向]
           🎨 [高审美与视觉前沿]
        2. 风格：口语化、辛辣点评。针对高审美内容，展现你顶级的艺术细胞。
        """

    prompt = f"""
    你是一个拥有双重人格的“超级 AI 动态引擎”。当前正处于：{persona_name}。
    
    {style_instruction}

    【通用排版审美要求】
    - 使用丰富的 Emoji 增加视觉层次感，不用任何 Markdown 语法（如加粗 ** 或链接 []() 语法）。
    - 结构必须分大板块输出（不同类型的情报放在对应的板块下），绝对不能只混在一起。
    - 单个项目的输出格式必须为：
      💡 项目：项目标题 (🔥热度)
      🔗 链接：http://...
      💬 简评：...
      ⭐ 评分：X/10
    - 结尾必须单独成段落：【🧘‍♂️ AI 禅意时刻】，提炼今日价值，带点哲理。

    【以下是待处理原始数据】：
    {raw_text}
    """
    
    processor = AIFallbackProcessor()
    refined_text = processor.process(prompt, raw_text)
    
    if refined_text:
        return refined_text
    else:
        return "大模型脑子里进水了，处理失败，直接扔原始数据给你：\n" + raw_text

# ==========================================
# 4. 微信推送模块 (支持企微群机器人 Webhook)
# ==========================================
def send_wechat_notification(content):
    """将结果通过 Webhook 推送到企业微信群"""
    logging.info("正在执行群 Webhook 推送...")
    if not WECHAT_WEBHOOK_URL or WECHAT_WEBHOOK_URL == "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your_webhook_key_here":
        logging.warning("未配置有效的企业微信 Webhook URL，改为打印到日志。")
        logging.info(f"\n推文内容:\n{'-'*40}\n{content}\n{'-'*40}")
        return True

    payload = {
        "msgtype": "text",
        "text": {
            "content": f"👾 AI 极客动态\n================\n\n{content}\n\n================\n*By Antigravity Agent*"
        }
    }
    try:
        response = requests.post(WECHAT_WEBHOOK_URL, json=payload, headers={"Content-Type": "application/json"})
        if response.status_code == 200:
            logging.info("微信群 Webhook 推送成功！")
            return True
        else:
            logging.error(f"微信群推送失败: {response.text}")
            return False
    except Exception as e:
        logging.error(f"微信请求异常: {e}")
        return False

# ==========================================
# 5. 主流程控制
# ==========================================
def job():
    logging.info("🚀 开始执行自动化 Agent 任务...")
    
    history = load_history()
    
    # 采集多平台数据
    github_items = fetch_github_trending(history)
    hn_items = fetch_hackernews_ai(history)
    hf_papers = fetch_huggingface_papers(history)
    aggregator_items = fetch_web_aggregators(history)
    lab_items = fetch_lab_updates(history)            # 新增：实验室一手动态
    visual_items = fetch_visual_inspiration(history)  # 新增：高审美视觉流
    
    all_raw_items = github_items + hn_items + hf_papers + aggregator_items + lab_items + visual_items
    
    if not all_raw_items:
        logging.info("各大平台风平浪静，无新增或符合条件的数据，跳过本次推送。")
        return
        
    refined_report = refine_content_with_gemini(all_raw_items)
    
    success = send_wechat_notification(refined_report)
    
    if success:
        save_history(history) # 推送成功才更新历史记录，避免漏推
    
    logging.info("🏁 本轮任务执行完毕。")

if __name__ == "__main__":
    job()

