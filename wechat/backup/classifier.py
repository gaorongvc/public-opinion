import time
from dataclasses import dataclass
from typing import List, Dict, Optional

from grlibs.lm import LM


@dataclass
class NewsItem:
    title: str
    content: Optional[str] = None
    is_wanted: Optional[bool] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None


class BinaryNewsClassifier:
    def __init__(self):
        self.wanted_criteria = ""
        self.unwanted_criteria = ""

    def set_criteria(self, wanted_criteria: str, unwanted_criteria: str = ""):
        self.wanted_criteria = wanted_criteria
        self.unwanted_criteria = unwanted_criteria or f"不符合以下标准的新闻：{wanted_criteria}"

    def _build_prompt(self, title: str, content: str) -> str:
        prompt = f"""请判断以下新闻标题是否符合我的兴趣需求。

我想要的新闻：{self.wanted_criteria}

我不想要的新闻：{self.unwanted_criteria}

分类规则：
1. 仅根据新闻标题和内容进行判断
2. 输出 true（想要）或 false（不想要）
3. 提供0-1之间的置信度分数
4. 给出简短的判断理由

请严格按照以下JSON格式输出：
{{"wanted": true, "confidence": 0.95, "reason": "符合科技创新主题"}}

待分类的新闻标题：{title}
待分类的新闻内容：{content}"""

        return prompt

    def classify_single(self, title: str, content: str) -> Dict:
        prompt = self._build_prompt(title, content)
        _messages = [{"role": "system",
                      "content": "你是一个新闻过滤助手，帮助用户筛选感兴趣的新闻。请严格按照JSON格式回复。"},
                     {"role": "user", "content": prompt}]
        result = LM('openrouter/google/gemini-2.5-flash').chat(_messages)
        return result

    def classify_batch(self, news_list: List[NewsItem], delay: float = 1.0) -> List[NewsItem]:
        for i, news in enumerate(news_list):
            print(f"正在处理第 {i + 1}/{len(news_list)} 条新闻: {news.title[:50]}...")
            result = self.classify_single(news.title, news.content)
            news.is_wanted = result["wanted"]
            news.confidence = result["confidence"]
            news.reason = result["reason"]
            if delay > 0:
                time.sleep(delay)
        return news_list


# 使用示例
def main():
    classifier = BinaryNewsClassifier()
    wanted_criteria = """
    高管离职创业、天才少年创业、大牛离职创业等人事变动新闻
    """
    unwanted_criteria = """
    招聘、失业、裁员、演讲等
    """
    classifier.set_criteria(wanted_criteria, unwanted_criteria)
    test_news = [
        NewsItem("GLM-4.5 验证：智谱已完成一轮“洗牌”"),
    ]
    print("开始分类...")
    classified_news = classifier.classify_batch(test_news, delay=0.5)
    print("\n=== 分类结果 ===")
    for news in classified_news:
        status = "✅ 想要" if news.is_wanted else "❌ 不想要"
        print(f"{status} [{news.confidence:.2f}] {news.title}")
        print(f"理由: {news.reason}\n")


if __name__ == "__main__":
    main()
