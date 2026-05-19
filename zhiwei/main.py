import random
import time

from grlibs.feishu_message import Card
from grlibs.mdb import db3

from zhiwei.pinjian import collect
from zhiwei.utils import get_related_data


def run():
    time.sleep(random.randint(10, 60))
    records = collect()
    for record in records:
        data = record['data']
        # 避免重复采集的新闻
        if db3.zhiwei.news.find_one({'id': data['id']}):
            continue
        # 避免重复标题的新闻
        # 2025-04-28 PR team 建议保留用于了解热度
        if data.get('title', '') and db3.zhiwei.news.find_one(
                {'title': data['title'], 'realSource': data['realSource'], 'source': data['source']}):
            continue
        content = data.get('title', '') + data.get('content', '')
        if len(content) < 20:
            reason = {'related': False, 'reason': '内容过短'}
        else:
            reason = get_related_data(data)
        data.update(reason)
        db3.zhiwei.news.update_one({'id': data['id']}, {'$set': data}, upsert=True)
        record = db3.zhiwei.news.find_one({'id': data['id']})
        if record['related']:
            send(record)


def send(record):
    try:
        title = record['title'] if 'title' in record else record['questionTitle']
        url = record['url'] if 'url' in record else record['questionUrl']
    except:
        return
    if record['markCacheMaps'][0]['name'] == '负面':
        warning = '<font color=red>**负面**</font>'
    else:
        warning = '<font color=green>**正面**</font>'
    _content = f"""{warning}【{record['realSource']}】{record['source']}
[{title}]({url})
{record['reason']}
"""
    webhook = 'https://open.feishu.cn/open-apis/bot/v2/hook/a5d55c55-3462-4ab9-835f-5ac774ea0e36'
    Card(webhook).send(_content)
    webhook = 'https://open.feishu.cn/open-apis/bot/v2/hook/2b3e21a4-f348-4183-adf7-fd2205368696'
    Card(webhook).send(_content)


if __name__ == '__main__':
    run()
    # send(db3.zhiwei.news.find_one({'id': 'aced3fa22dc79b8610639a4f88f96e7e'}))
