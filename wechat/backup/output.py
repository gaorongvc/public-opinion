import csv

from grlibs.mdb import client


def individuals_to_feishu():
    query = {}
    query["publicTime"] = {
        u"$gte": u"2025-06-01"
    }
    query["account_type"] = u"AI"
    query["content"] = {
        u"$exists": True
    }
    query["individuals"] = {
        u"$exists": True
    }
    table = client.db1.newrank.wechat.article.list
    articles = table.find(query)
    data = []
    for article in articles:
        for individual in article['individuals']:
            if individual['name'] and individual['isChinese'] and individual['isStartup']:
                print(individual)
                individual['url'] = article['url']
                individual['title'] = article['title']
                individual['account_name'] = article['account_name']
                if not data:
                    data.append(individual.keys())
                data.append(individual.values())
    with open('temp.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(data)


if __name__ == '__main__':
    individuals_to_feishu()
