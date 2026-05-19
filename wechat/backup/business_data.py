import time

from grlibs.feishu import Feishu
from grlibs.lm import LM
from grlibs.mdb import client

from wechat.search import JZL

table2 = client.db1.wechat.articles
feishu = Feishu()


def run_ai_cn():
    ds = feishu.get_datasheet('QWysb4f13aJVspsqjYNccaTCn9e', 'tbl1UxW2sX95MLY1')
    records = ds.get_records_all(view_id='vewda8RwyX')
    jzl = JZL()
    # jzl._get(kw=['收入'], any_kw=[record['项目名称'] for record in records], period=365)
    # exit()
    for record in records:
        jzl._get(kw=[record['项目名称']], any_kw=['收入', '出货量', '销售额', '发布'], period=365)
        time.sleep(1)
        # exit()


def _extract_data(record):
    print(record['title'])
    text = f"""你的任务是从一篇文章中提取公司{record['kw']}的关键业务信息。请识别以下指标：收入、出货量、销售额、新发布，没有的话返回空字符串。将提取的数据以JSON格式返回。文章内容可以在下方提供的引号中找到：
文章内容：
'''
{record['title']}

{record['content']}
'''
请返回如下结构的JSON：
{{
  "收入": "...",
  "出货量": "...",
  "销售额": "...",
  "新发布": "..."
}}
"""
    _messages = [{"role": "user", "content": text}]
    data = LM('openrouter/google/gemini-2.5-flash').chat(_messages)
    print(data)
    table2.update_one({'_id': record['_id']}, {'$set': {'data': data}}, upsert=False)


def extract_data():
    records = table2.find({'any_kw': ' '.join(['收入', '出货量', '销售额', '发布']), 'data': {
        u"$exists": False
    }})
    for record in records:
        _extract_data(record)


if __name__ == '__main__':
    # run_ai_cn()
    extract_data()
