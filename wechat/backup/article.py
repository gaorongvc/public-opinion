# 规则：一篇文章消耗2unit
from datetime import datetime, timedelta

import pymongo
import requests
from grlibs.mdb import client

from libs.vikaplus import VikaPlus

vp = VikaPlus()

table = client.db1.newrank.wechat.articles

wechat_list = vp.get_data_from_vika(vp.wechat_list)
wechat_id_list = wechat_list.wechat_id.to_list()


def req_data(account):
    article = table.find_one({'account': account}, sort=[("publicTime", pymongo.DESCENDING)])
    e = datetime.now()
    if article:
        start = article['publicTime']
    else:
        s = e - timedelta(days=30)
        start = s.strftime('%Y-%m-%d %H:%M:%S')
    end = e.strftime('%Y-%m-%d %H:%M:%S')
    url = 'https://api.newrank.cn/api/sync/weixin/account/articles_content'
    headers = {'Key': '5f85646e6b4a4d4e9350cd640'}
    body = {'account': account, 'from': start, 'to': end, 'page': '1', 'size': '100'}
    print(body)
    response = requests.post(url, data=body, headers=headers)
    data = response.json()['data']
    # print(response.json())
    for article in data:
        print(account, article['title'])
        key = {'account': article['account'], 'publicTime': article['publicTime']}
        table.update_one(key, {'$set': article}, upsert=True)


if __name__ == '__main__':
    for wechat_id in wechat_id_list:
        print(wechat_id.strip())
        req_data(wechat_id.strip())
