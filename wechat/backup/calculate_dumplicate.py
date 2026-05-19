from tqdm import tqdm

from grlibs.embedding import Embedding
from grlibs.mdb import db
from grlibs.d import days_ago, date2str


def calculate_dumplicate(account_type, start_date):
    client = Embedding()
    articles = list(db.newrank.wechat.article.list.find({'account_type': account_type, 'publicTime': {'$gte': start_date}, 'summary': {'$exists': True}}).sort('publicTime', 1))

    embeddings = []

    for article in tqdm(articles):
        if 'is_duplicate' in article:
            embedding = article['summary_embedding']
            embeddings.append(embedding)
        else:
            # 计算及获取embedding
            if 'summary_embedding' in article:
                embedding = article['summary_embedding']
            else:
                embedding = client.get_embedding(article['summary'])
                article['summary_embedding'] = embedding
                db.newrank.wechat.article.list.update_one({'_id': article['_id']}, {'$set': {'summary_embedding': embedding}})
            
            if len(embeddings) > 0:
                is_duplicate = client.is_duplicate(embedding, embeddings)
            else:
                is_duplicate = False

            db.newrank.wechat.article.list.update_one({'_id': article['_id']}, {'$set': {'is_duplicate': bool(is_duplicate)}})
            embeddings.append(embedding)

if __name__ == '__main__':
    calculate_dumplicate('AI', date2str(days_ago(3)))
        



