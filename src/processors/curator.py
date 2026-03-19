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
        """最终合成：注入极致极客灵魂，复刻用户最满意的脱口秀风格"""
        if not raw_items: return ""
        
        # 1. 数据预处理
        processed_text_list = []
        for item in raw_items:
            processed_text_list.append(
                f"ID:{item.get('url')} | Title:{item['title']} | Score:{item.get('ai_score', 'N/A')} "
                f"| Time:{item.get('pub_time', '实时')} | Reason:{item.get('ai_reason', '暂无')}"
            )
        raw_text = "\n".join(processed_text_list)
        
        # 2. 判定人格与风格串词
        import datetime
        current_hour = datetime.datetime.now().hour
        is_morning = 6 <= current_hour < 12
        
        if is_morning:
            persona_name = "决策者简报模式 (早报)"
            intro = "🎤 各位早起布局的决策者、技术开拓者，早安！我是你的 AI 商业引擎。在咖啡馆或会议室的间隙，为你速递今晨最有价值的深层信号。"
            sections_config = """
            - [铜臭味与搞钱思路]: "各位决策者，早盘信号已经发出。让我们看看谁在重塑产业链，谁在定义新的变现范式。"
            - [硬核黑料与技术真相]: "拨开宣传层，看清底座。这里是今日最值得关注的技术底层逻辑。"
            - [惊掉下巴的高级视觉审美]: "在审美即生产力的时代，这些范式值得你关注。"
            """
        else:
            persona_name = "极客脱口秀模式 (晚报)"
            intro = "🎤 咳咳，各位夜猫子极客、审美先锋、以及屏幕前想搞钱想到睡不着的朋友们，晚上好！欢迎收看由“超级 AI 动态引擎”为您带来的《极客晚报》。我是你们今晚的主持人，一个在代码和钞票之间反复横跳，在实验室爆炸和艺术殿堂里穿梭的赛博灵魂。灯光师，音乐起，分类走起！"
            sections_config = """
            - [铜臭味与搞钱思路]: "朋友们，空气中弥漫着什么味道？啊，是金钱和 GPU 烧焦的混合香气！让我们看看今天谁在忙着数钱，谁又在画大饼。"
            - [硬核黑料与技术真相]: "好了，擦掉口水，让我们进入极客的圣殿——GitHub。这里的星数，就是我们的信仰。"
            - [惊掉下巴的高级视觉审美]: "在这个被像素填满的夜晚，我们需要一点真正的、能惊动灵魂的视觉震撼。"
            """

        prompt = f"""
        你是一位极其资深、且带有点叛逆精神的 AI 行业主编，当前模式：{persona_name}。
        
        【今日任务】:
        将原始信号转化成一份足以引爆极客圈的简报。
        
        【要求的范例风格 (以此为准)】:
        👾 AI 极客动态
        ================
        🎤 咳咳，各位夜猫子极客、审美先锋...欢迎收看《极客晚报》。我是今晚的主持人...灯光师，音乐起，分类走起！
        ---
        ### 🔹 [铜臭味与搞钱思路]
        朋友们，空气中弥漫着什么味道？啊，是金钱和 GPU 烧焦的混合香气！让我们看看今天谁在忙着数钱，谁又在画大饼。
        💡 项目：XXX (💰 Business)
        ⏰ 时间：XXX
        🔗 链接：XXX
        💬 简评：[极度犀利、像脱口秀现场一样的神吐槽。比如：这招高啊！这商业模式，简直是给自由职业者市场投下了一颗赛博核弹。]
        ⭐ 评分：[分值]/10 (由你根据原始数据的 Score 动态生成)
        
        【各板块指定灵魂串场词】:
        {sections_config}
        
        【排版规范】:
        1. 开场白必须使用：{intro}
        2. 结构必须精准包含：
           💡 项目：[标题] (标签)
           ⏰ 时间：[YYYY-MM-DD，严禁写实时、未知或发布于]
           🔗 链接：[URL]
           💬 简评：[犀利点评]
           ⭐ 评分：[此处的评分应根据原始数据的 ai_score 还原为 10 分制]/10
        3. 结尾必须包含：【🧘‍♂️ AI 禅意时刻】（只有 1 句金句）。
        
        【原始信号】:
        {raw_text}
        """
        
        refined_text = self.processor.process(prompt)
        
        if refined_text:
            return refined_text
        else:
            # 兜底逻辑
            return f"👾 AI 简报合成出现波动，请查收实时情报：\n\n" + "\n".join([f"📍 {it['title']}\n🔗 {it['url']}" for it in raw_items])
