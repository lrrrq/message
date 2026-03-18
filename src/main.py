import time
import logging
from src.utils.config import load_history, save_history
from src.processors.ai_processor import AIFallbackProcessor
from src.processors.curator import AgenticCurator
from src.notifiers.wechat import WeChatNotifier

# 导入所有采集器 (Skills)
from src.collectors.github_trending import GithubTrendingCollector
from src.collectors.hacker_news import HackerNewsCollector
from src.collectors.huggingface import HuggingFaceCollector
from src.collectors.web_aggregators import WebAggregatorCollector
from src.collectors.lab_updates import LabUpdatesCollector
from src.collectors.commercial_news import CommercialNewsCollector
from src.collectors.visual_inspiration import VisualInspirationCollector
from src.collectors.avant_garde import AvantGardeCollector

def main():
    logging.info("🚀 启动模块化 AI Trend Watcher (稳定性增强版)...")
    
    # 1. 初始化
    history = load_history()
    processor = AIFallbackProcessor()
    curator = AgenticCurator(processor)
    
    # 2. 注册采集器
    collectors = [
        GithubTrendingCollector(history),
        HackerNewsCollector(history),
        HuggingFaceCollector(history),
        WebAggregatorCollector(history),
        LabUpdatesCollector(history),
        CommercialNewsCollector(history),
        VisualInspirationCollector(history),
        AvantGardeCollector(history)
    ]
    
    # 3. 数据采集
    all_raw_items = []
    for c in collectors:
        try:
            items = c.fetch()
            all_raw_items.extend(items)
        except Exception as e:
            logging.error(f"采集器 {c.__class__.__name__} 异常: {e}")
            
    if not all_raw_items:
        logging.info("本轮无新增数据。")
        return

    # 4. AI 策展
    curated_items = curator.score_and_filter(all_raw_items, top_n=6)
    
    # 5. 推送文字简报 (多渠道)
    text_sent_successfully = False
    if curated_items:
        logging.info(f"正在生成简报...")
        report = curator.refine_content(curated_items)
        if report:
            # 记录生成的简报，防止推送失败后找不到内容
            logging.info(f"--- 简报生成成功 (预览前100字) ---\n{report[:100]}...")
            
            # 单渠道尝试
            text_sent_successfully = WeChatNotifier.send_text(report)
            
    # 6. 推送图片消息
    img_sent_count = 0
    visual_pool = [it for it in all_raw_items if it.get('picurl')]
    score_map = {it['url']: it.get('ai_score', 0) for it in curated_items}
    visual_pool.sort(key=lambda x: score_map.get(x['url'], 0), reverse=True)
    
    # 只有当图片推送成功才记录其 URL
    successful_img_urls = []
    for v in visual_pool[:3]:
        if WeChatNotifier.send_image(v['picurl']):
            img_sent_count += 1
            successful_img_urls.append(v['picurl'])
            time.sleep(1)

    # 7. 严格的状态持久化
    # 只有推送成功的内容才记入历史
    if text_sent_successfully:
        for item in curated_items:
            history.add(item['url'])
            
    for img_url in successful_img_urls:
        history.add(img_url)

    if text_sent_successfully or img_sent_count > 0:
        save_history(history)
        logging.info(f"🏁 任务完成。资讯送达: {text_sent_successfully}, 图片送达: {img_sent_count}")
    else:
        logging.error("❌ 本轮所有推送渠道均失败，未更新历史记录。")

if __name__ == "__main__":
    main()
