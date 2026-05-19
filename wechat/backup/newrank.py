import requests

from wechat.base import Base, table


class NewRank(Base):
    cookies = {
        'Hm_lvt_a19fd7224d30e3c8a6558dcb38c4beed': '1704679278',
        'token': '250E4342A1B94FCF8C5891FB92A2F03B',
        'sensorsdata2015jssdkcross': '%7B%22distinct_id%22%3A%22nr_qk9wi86b5%22%2C%22first_id%22%3A%2218c342a163f2154-0e06522c3f35ba8-16525634-2073600-18c342a16402d49%22%2C%22props%22%3A%7B%22%24latest_utm_source%22%3A%22websites%22%2C%22%24latest_utm_medium%22%3A%22newrank_banner%22%2C%22%24latest_utm_campaign%22%3A%22%E6%96%B0%E6%A6%9C%E6%9C%89%E6%95%B0%22%2C%22%24latest_utm_content%22%3A%22%E6%96%B0%E6%A6%9Cbanner-0904%22%2C%22%24latest_utm_term%22%3A%22%E6%96%B0%E8%A7%86-%E8%A7%86%E9%A2%91%E5%8F%B7%E7%9B%B4%E6%92%AD-%E7%9B%B4%E6%92%AD%E7%9B%91%E6%B5%8B%22%2C%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22%24device_id%22%3A%2218c342a163f2154-0e06522c3f35ba8-16525634-2073600-18c342a16402d49%22%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMThjMzc4MzI5YjI0NTAtMGJkZjM3ZjlkMWM5NWMtMTY1MjU2MzQtMjA3MzYwMC0xOGMzNzgzMjliMzEzYWIiLCIkaWRlbnRpdHlfbG9naW5faWQiOiJucl9xazl3aTg2YjUifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%22nr_qk9wi86b5%22%7D%7D',
        'Hm_lpvt_a19fd7224d30e3c8a6558dcb38c4beed': '1704704153',
        'acw_tc': '781bad2317047647318303556e24b69dd82e42988d0bc5261e9be56e896bf5',
        'NR_MAIN_SOURCE_RECORD': '{"locationSearch":"?account=XRLaboratory","locationHref":"https://newrank.cn/new/readDetial?account=XRLaboratory","referrer":"https://www.newrank.cn/","source":"","lastReferrer":"","keyword":""}',
    }

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'DNT': '1',
        'Origin': 'https://newrank.cn',
        'Pragma': 'no-cache',
        'Referer': 'https://newrank.cn/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'n-token': 'c85200091a0047c0aa6e786d4bd17299',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }
    path = '/xdnphb/detail/v1/rank/article/lists'

    def get(self, record):
        data = {
            'account': record.wechat_id,
        }
        response = requests.post('https://gw.newrank.cn/api/wechat/xdnphb/detail/v1/rank/article/lists',
                                 cookies=self.cookies, headers=self.headers, data=data)
        print(response.text)
        value = response.json()['value']
        articles = []
        for batch in value['articles']:
            for article in batch:
                articles.append(article)
        for batch in value['realTimeArticles']:
            for article in batch:
                articles.append(article)
        for article in articles:
            article['account'] = record.wechat_id
            article['account_type'] = record.类型
            print(record.wechat_id, article['title'])
            key = {'url': article['url']}
            table.update_one(key, {'$set': article}, upsert=True)
            self.get_article(article['url'])


if __name__ == '__main__':
    nr = NewRank()
    nr.get('AI_era')
