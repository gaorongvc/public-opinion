import random
import time
import uuid

import requests
from vika import Vika

from wechat.base import Base, table

vika = Vika("uskmELPfrvtsNvsvXFMKubN")
datasheet = vika.datasheet("dstH3GuLbwjp9Fi6ui", field_key="name")


class JZL(Base):
    def get(self, record, page=1):
        data = {
            "key": "JZL9145b9c50fc2d48f",
            "biz": record.biz,
            "page": page
        }
        url = "https://www.jzl.com/fbmain/monitor/v3/post_history"
        res = requests.get(url=url, json=data).json()
        for article in res['data']:
            key = {'url': article['url']}
            article['account'] = record.wechat_id
            article['account_name'] = record.名称
            article['account_type'] = record.类型
            article['uuid'] = uuid.uuid4().hex
            article['publicTime'] = article['post_time_str']
            table.update_one(key, {'$set': article}, upsert=True)
            self.get_article(article['url'])


def run(account_type):
    records = list(datasheet.records.filter(类型=account_type))
    for record in records:
        try:
            for page in range(1, 2):
                JZL().get(record, page=page)
        except Exception as e:
            print(f'{record.biz} need repair!\n{e}')
        s = random.randint(1, 3)
        print('sleeping: {}s'.format(s))
        time.sleep(s)


if __name__ == '__main__':
    run('AI')
