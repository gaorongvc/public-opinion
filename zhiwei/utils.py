import json

from grlibs.gpt import GPT

prompt = f"""你将获得一篇包含标题和内容的新闻文章。你的任务是确定该文章是否涉及以下主题中的任何一个：高榕资本、高榕创投、高榕资本的创始人或高榕资本的被投企业。
高榕资本是一家风险投资机构，如果文章中的"高榕"是人名、公司等其他信息，则为不相关。
你需要以JSON格式返回结果，该结果包含两个字段："related" 和 "reason"。

请按照以下步骤操作：

1. 评估文章的标题和内容，判断其是否涉及上述任何主题。
2. 如果相关，将"related"字段设置为true，否则设置为false。
3. 如果相关，用中文摘要填写"reason"字段，20字以内的概要信息，并说明文章如何与上述主题相关。如果不相关，将reason字段的值设为"不相关。"

以下是提供的文章，包含标题和内容：

{{content}}

请执行相关性评估，并返回包含"related"和"reason"字段的JSON结果。
"""

gpt = GPT()


def get_related_data(record):
    # print(record['content'], record['title'], record['realSource'], record['source'], record['url'])
    content = f"Title: {record.get('title', '')}\nContent: {record.get('content', '')}"
    result = gpt.completion(prompt.format(content=content), model_name='gpt-4.1')
    data = json.loads(result)
    return data
