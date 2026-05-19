from datetime import datetime, timedelta, timezone

import pandas as pd
from grlibs.d import today_str
from grlibs.feishu_message import Card
from grlibs.mdb import db3


def run():
    bj_timezone = timezone(timedelta(hours=8))
    now = datetime.now(bj_timezone)
    one_day_ago = now - timedelta(days=1)
    data = pd.DataFrame(db3.zhiwei.news.find({'stime': {'$gt': one_day_ago.timestamp() * 1000}, 'related': True}))
    positive = data[data['markCacheMaps'].apply(lambda x: x[0]['name'] == '正面')]
    neutral = data[data['markCacheMaps'].apply(lambda x: x[0]['name'] == '中性')]
    negative = data[data['markCacheMaps'].apply(lambda x: x[0]['name'] == '负面')]
    medias = '，'.join(list(set(data['source']))[:3])
    _content = f"""{one_day_ago.strftime("%Y年%m月%d日%H点")}-{now.strftime("%Y年%m月%d日%H点")}
高榕资本有效声量 {len(data)} 条
正面{len(positive)}条，占比{int(len(positive) / len(data) * 100)}%
中性{len(neutral)}条，占比{int(len(neutral) / len(data) * 100)}%
敏感{len(negative)}条，占比{int(len(negative) / len(data) * 100)}%
参与头部媒体主要有{medias}等

重要舆情回顾：
【正面】
{build(positive)}

【中性】
{build(neutral)}

【敏感】
{build(negative)}
"""
    webhook = 'https://open.feishu.cn/open-apis/bot/v2/hook/a5d55c55-3462-4ab9-835f-5ac774ea0e36'
    Card(webhook).send(_content, title=f'高榕资本品牌传播汇总 {today_str}')


def build(records):
    _contents = []
    df_deduplicated = records.drop_duplicates(subset=['title'], keep='first')
    for _, record in df_deduplicated.iterrows():
        _content = f"""【{record['realSource']}】{record['source']} [{record['title']}]({record['url']})
{record['reason']}"""
        _contents.append(_content)
    return '\n'.join(_contents)


if __name__ == '__main__':
    run()
