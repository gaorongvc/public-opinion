from datetime import datetime, timedelta

import pandas as pd
import pendulum
from grlibs.mdb import db

from libs.vikaplus import VikaPlus, get_data_from_vika

vp = VikaPlus()


def days_ago(n):
    local_tz = pendulum.timezone("Asia/Shanghai")
    now = datetime.now(local_tz)
    datetime_ago = now - timedelta(days=n)
    return datetime(datetime_ago.year, datetime_ago.month, datetime_ago.day, tzinfo=local_tz)


def get_df_from_db():
    collection = db.newrank.wechat.article.list
    query = {}
    projection = {}
    projection["account"] = u"$account"
    projection["title"] = u"$title"
    projection["publicTime"] = u"$publicTime"
    projection["url"] = u"$url"
    # projection["_id"] = 0
    cursor = collection.find(query, projection=projection)
    raw = pd.DataFrame(x for x in cursor)
    return raw


def write_vika_to_mongo(sheet_id='dstnjKaic5Ym2z6LlH'):
    data = vp.get_data_from_vika(sheet_id)
    if '文章评分' not in data.columns:
        return
    data = data[~data['文章评分'].isnull()]
    for index, record in data.iterrows():
        record = record.json()
        myquery = {"id": record['id']}
        newvalues = {"$set": {"文章评分": record.get('文章评分')}}
        db.newrank.wechat.article.list.update_one(myquery, newvalues)


def write_mongo_to_vika(sheet_id='dstnjKaic5Ym2z6LlH', days=8):
    since_from = days_ago(days).strftime('%Y-%m-%d')
    records = list(db.newrank.wechat.article.list.find({'publicTime': {'$gte': since_from}},
                                                       {'id': 1, 'account': 1, 'title': 1, 'publicTime': 1,
                                                        '_id': 0, 'url': 1, '文章评分': 1}))

    # 删除vika现有的数据
    datasheet = vp.get_datasheet(sheet_id)
    vp.delete_all(datasheet)
    vp.bulk_create(datasheet, records)



if __name__ == '__main__':
    write_vika_to_mongo()
    write_mongo_to_vika()
    # datasheet = vk.datasheet("dstnjKaic5Ym2z6LlH", field_key="name")
    # raw = get_df_from_db()
    # for index, row in raw[:].iterrows():
    #     check_id = row['url']
    #     if check_id not in check_lst:
    #         row = datasheet.records.create({
    #             "title": row['title'],
    #             "author": row['account'],
    #             "publicTime": row['publicTime'],
    #             "url": row['url']
    #         })
    #         print('successfully loaded', check_id)
    #         time.sleep(1)
    #     else:
    #         print(check_id, 'is exist!')
