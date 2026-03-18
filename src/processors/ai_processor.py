import logging
import google.generativeai as genai
from openai import OpenAI
from src.utils.config import DEEPSEEK_API_KEY, GROQ_API_KEY, GEMINI_API_KEY

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
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                self.providers.append({
                    "name": "Gemini",
                    "func": self._call_gemini
                })
            except Exception as e:
                logging.error(f"Gemini 初始化失败: {e}")
                
    def _call_deepseek(self, prompt):
        import requests
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
        
    def _call_groq(self, prompt):
        import requests
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}"
        }
        payload = {
            "model": "llama-3.1-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
        
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
