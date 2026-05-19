from grlibs.lm import LM
from grlibs.mdb import client
from grlibs.prompts import get_prompt
from grlibs.url_downloader import UrlDownloader

table = client.db1.newrank.wechat.article.list
ud = UrlDownloader()


def chat(query, prompt_name):
    prompt = get_prompt(prompt_name)
    user_prompt = prompt.replace('{query}', query)
    _messages = [{"role": "user", "content": user_prompt}]
    result = LM('openrouter/minimax/minimax-m2.7').chat(_messages)
    return result


class Base(object):
    @staticmethod
    def get_article(url):
        print(url)
        article = table.find_one({'url': url})
        if 'content' in article and article['content']:
            return
        content = ud.download_by_requests(url)
        table.update_one({'url': url}, {'$set': {'content': content}}, upsert=False)

    @staticmethod
    def get_summary(url):
        print(url)
        article = table.find_one({'url': url})
        content = article['content']
        dic = {}
        if 'summary' in article and article['summary']:
            summary = article['summary']
        else:
            dic.update(chat(content, 'summarize_wechat'))
            summary = dic['summary']
        print(summary)
        if 'embedding' in article and article['embedding']:
            return
        embed(article['uuid'], summary)
        dic['embedding'] = True
        table.update_one({'url': url}, {'$set': dic}, upsert=False)

    @staticmethod
    def extract_individuals(url):
        print(url)
        article = table.find_one({'url': url})
        content = article['content']
        data = chat(content, 'extract_individuals')
        print(data)
        data = data.get('result', []) or data.get('individuals', []) if isinstance(data, dict) else data
        table.update_one({'url': url}, {'$set': {'individuals': data}}, upsert=False)


if __name__ == '__main__':
    b = Base()
    # _url = 'https://mp.weixin.qq.com/s/Em3kvOHLD_y0b2gg3PIimQ'
    # b.get_article(_url)
    # exit()

    query = {}
    query["publicTime"] = {
        u"$gte": u"2025-06-01"
    }
    query["account_type"] = u"AI"
    query["content"] = {
        u"$exists": True
    }
    query["individuals"] = {
        u"$exists": False
    }
    articles = table.find(query)
    for article in articles:
        try:
            b.extract_individuals(article['url'])
        except Exception as e:
            print(e)
            continue
