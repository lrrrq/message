import os
import logging
import json
from dotenv import load_dotenv

load_dotenv()

# 项目根目录
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# API Keys (使用 .strip() 防止 GitHub Secrets 带有不可见换行符或多余引号)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip().strip('"').strip("'")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip().strip('"').strip("'")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip().strip('"').strip("'")

# WeChat
WECHAT_WEBHOOK_URL = os.getenv("WECHAT_WEBHOOK_URL", "").strip().strip('"').strip("'")

# WeChat
WECHAT_WEBHOOK_URL = os.getenv("WECHAT_WEBHOOK_URL")

# 行业关键词
FOCUS_KEYWORDS = ["传统行业自动化", "降本增效", "AI视频生成", "Sora", "效率工具", "视频模型", "Automation", "Efficiency", "Luma AI", "Runway", "Kling", "可灵"]

# 文件路径
HISTORY_FILE = os.path.join(ROOT_DIR, "history.json")
LOG_DIR = os.path.join(ROOT_DIR, "logs")

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "app.log"), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

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
