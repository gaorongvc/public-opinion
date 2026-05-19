import http.client
import json

from grlibs.d import today_str
from grlibs.mdb import client

table = client.db1.wechat.search
table2 = client.db1.wechat.articles


class JZL(object):
    @staticmethod
    def _get(kw='', any_kw='', ex_kw='', period=1, page=1, mode=3):
        conn = http.client.HTTPSConnection("www.dajiala.com")
        dic = {
            "sort_type": 1,
            "mode": mode,
            "period": period,
            "page": page,
            "key": "JZL9145b9c50fc2d48f",
            "kw": kw,
            "any_kw": any_kw,
            "ex_kw": ex_kw,
            "verifycode": ""
        }
        payload = json.dumps(dic)
        headers = {'Content-Type': 'application/json'}
        conn.request("POST", "/fbmain/monitor/v3/kw_search", payload, headers)
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        # print(data)
        data = json.loads(data)['data']
        if not data:
            return False
        for article in data:
            if table2.find_one({'title': article['title']}):
                continue
            key = {'url': article['url']}
            article['kw'] = kw
            article['any_kw'] = any_kw
            article['ex_kw'] = ex_kw
            article['batch'] = today_str
            table2.update_one(key, {'$set': article}, upsert=True)
        return True

    def get(self, kw='', any_kw='', ex_kw='', period=1, page_count=1, mode=3):
        if table.find_one({'batch': today_str, 'kw': kw, 'any_kw': any_kw, 'ex_kw': ex_kw}):
            return
        for page in range(1, page_count + 1):
            ret = self._get(kw, any_kw, ex_kw, period, page, mode=mode)
            if not ret:
                break
        table.insert_one({'batch': today_str, 'kw': kw, 'any_kw': any_kw, 'ex_kw': ex_kw})

    def get_all(self, keywords, period):
        self._get(kw=keywords, period=period)

    def get_any(self, keywords, period):
        self._get(any_kw=keywords, period=period)


if __name__ == '__main__':
    JZL().get_any(keywords='高榕资本 高榕创投', period=7)
    JZL().get_all("蓝驰创投", 7)
