import logging
import json as json_lib
import datetime
from src.processors.ai_processor import AIFallbackProcessor

class AgenticCurator:
    def __init__(self, processor):
        self.processor = processor

    def score_and_filter(self, items, top_n=8):
        if not items: return []
        
        logging.info(f"🔬 AI 策展人正在对 {len(items)} 条内容进行多维审计...")
        
        items_text = ""
        for i, item in enumerate(items):
            items_text += f"ID:{i} | Title:{item['title']} | Desc:{item.get('desc', '')[:100]}\n"
            
        scoring_prompt = f"""
        你是一位顶级 AI 行业主编，兼具先锋设计师 (ui-ux-pro-max) 与 商业分析师 (internal-comms) 的眼光。
        请对以下内容进行评分，并返回一个 JSON 格式的列表。
        
        【评分核心原则】:
        1. 💎 搞钱潜力 (Commercial): 是否有清晰变现逻辑？
        2. ⚡ 技术硬核 (Tech): SOTA 表现或底层突破。
        3. 🎨 审美高度 (Aesthetic): 先锋视觉或结构美。
        4. 🌊 稀缺/时效 (Freshness): 一手信号或今日最新。
        
        【重要：来源多样化要求】:
        我们不希望简报里全是同一个网站（如全是 GitHub 或全是 TechCrunch）。
        请在综合评分时，对于那些能够补充现有维度多样性的条目给予额外关注。
        
        要求：返回严谨的 JSON 数组，格式为: [{{"id": 0, "score": 8.5, "reason": "..."}}]
        
        【待评分列表】:
        {items_text}
        """
        
        try:
            res = self.processor.process(scoring_prompt)
            if not res:
                logging.warning("AI 策展人未返回评分结果，使用默认排序。")
                return items[:top_n]
                
            json_str = res.strip().replace('```json', '').replace('```', '')
            import json as json_lib
            scores = json_lib.loads(json_str)
            
            # 映射评分
            for s in scores:
                idx = s.get('id')
                if idx is not None and idx < len(items):
                    items[idx]['ai_score'] = s.get('score', 0)
                    items[idx]['ai_reason'] = s.get('reason', '')
            
            # 加入来源多样化排序补丁
            seen_sources = {}
            for it in items:
                # Ensure 'url' key exists before trying to split
                if 'url' in it and isinstance(it['url'], str) and len(it['url'].split('/')) > 2:
                    source = it['url'].split('/')[2] # 提取域名
                else:
                    source = "unknown_source" # Default for items without a valid URL
                
                count = seen_sources.get(source, 0)
                # 每出现一次相同来源，分数递减（软过滤）
                it['final_rank_score'] = it.get('ai_score', 0) - (count * 1.5)
                seen_sources[source] = count + 1
            
            items.sort(key=lambda x: x.get('final_rank_score', 0), reverse=True)
            filtered = [it for it in items if it.get('ai_score', 0) > 6] # 评分大于 6 分入选
            return filtered[:top_n]
        except Exception as e:
            logging.error(f"AI 评分解析失败: {e}")
            return items[:top_n]

    def refine_content(self, raw_items):
        """最终合成：注入极致极客风格，严格遵循用户喜爱的模板"""
        if not raw_items: return ""
        
        # 1. 数据预处理
        processed_text_list = []
        for item in raw_items:
            # 这里的 raw_items 已经是经过 score_and_filter 筛选过的 Top N
            # 格式化原始数据供 AI 加工
            processed_text_list.append(
                f"ID:{item.get('url')} | Title:{item['title']} | Score:{item.get('ai_score', 'N/A')} "
                f"| Time:{item.get('pub_time', '实时')} | Reason:{item.get('ai_reason', '暂无')}"
            )
        
        raw_text = "\n".join(processed_text_list)
        
        # 2. 判定人格
        import datetime
        current_hour = datetime.datetime.now().hour
        is_morning = 6 <= current_hour < 12
        
        if is_morning:
            persona_name = "决策者简报模式 (早报)"
            intro_style = "🎤 各位早起布局的决策者、技术开拓者，早安！我是你的 AI 商业引擎。在咖啡馆或会议室的间隙，为你速递今晨最有价值的深层信号。"
            flavor = "专业、冷峻、高信息密度，侧重逻辑与趋势。"
        else:
            persona_name = "极客脱口秀模式 (晚报)"
            intro_style = "🎤 咳咳，各位夜猫子极客、审美先锋、以及屏幕前想搞钱想到睡不着的朋友们，晚上好！欢迎收看由“超级 AI 动态引擎”为您带来的《极客晚报》。我是你们今晚的主持人，一个在代码和钞票之间反复横跳的赛博灵魂。"
            flavor = "辛辣、幽默、毒舌但精准，侧重技术吐槽与搞钱思路。"

        prompt = f"""
        你是一位拥有双重人格的“超级 AI 动态引擎”，当前正处于：{persona_name}。
        
        【今日核心任务】:
        将下方提供的原始信号，转换成极具分量、排版考究的简报。
        
        【排版准则（必须严格执行）】:
        1. 每一个项目必须使用以下固定模板：
           💡 项目：[标题] ([标签，如 💰 Business / 🔥 GitHub Stars / 📄 Paper])
           ⏰ 时间：[发布时间，若原始数据无则写“实时”]
           🔗 链接：[URL，禁止 Markdown 格式，直接展示链接]
           💬 简评：[极具洞察力的 1-2 句话点评，必须精简、带点极客黑话/梗，{flavor}]
           ⭐ 评分：[0-10] / 10
        
        2. 板块划分：
           严格按照 🔹 [铜臭味与搞钱思路]、🔹 [硬核黑料与技术真相]、🎨 [惊掉下巴的高级视觉审美] 划分。
        
        3. 整体结构：
           - 震撼开场白：{intro_style}
           - 板块内容（每板块 1-2 条，确保来源不重复、种类多样）
           - 🧘‍♂️ [AI 禅意时刻]：一段提炼今日价值、带点哲理的极简金句。
        
        4. 禁令：
           - 严禁使用任何 Markdown 链接（如 [xx](yy)）。
           - 严禁使用 Markdown 代码块包裹正文。
           - 文案必须精简，禁止长篇大论。
        
        【待处理原始信号列表】:
        {raw_text}
        """
        
        refined_text = self.processor.process(prompt)
        
        if refined_text:
            return refined_text
        else:
            # 兜底逻辑
            return f"👾 AI 简报合成出现波动，请查收实时情报：\n\n" + "\n".join([f"📍 {it['title']}\n🔗 {it['url']}" for it in raw_items])
