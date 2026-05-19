import time
from datetime import datetime

import requests
from grlibs.feishu import Feishu
# from grlibs.proxy import StaticProxy

feishu = Feishu()
configs_ds = feishu.get_datasheet('DbBobnMxxag78ZsDZeJcLCSkntf', 'tblGBixiaDu0TaUR')
# sp = StaticProxy()
# sp.bind_ip()


def get_config(config_name):
    try:
        record = configs_ds.get_record({"filter": f'CurrentValue.[name]="{config_name}"'})
        return record['value']
    except Exception:
        raise Exception(f'Prompt 【{config_name}】 not found')


def collect():
    cookies = {
        'JSESSIONID': get_config('zhiwei_JSESSIONID'),
        'gr_user_id': 'fdb6b418-e47f-44b1-a417-b9b1ffcd6c27',
    }
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Origin': 'https://brandkbs.zhiweidata.com',
        'Pragma': 'no-cache',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Token': get_config('zhiwei_TOKEN'),
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
        'pid': '68084502a7e04b0412d0245f',
        'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        # 'Cookie': 'JSESSIONID=686B24571CA12BBCDB74456928053288; gr_user_id=fdb6b418-e47f-44b1-a417-b9b1ffcd6c27',
    }
    start_time = int(time.mktime(datetime.now().date().timetuple()) * 1000)
    end_time = int(time.time() * 1000)
    json_data = {
        'sourceKeyword': None,
        'sorter': {
            'stime': 'descending',
        },
        'pageSize': 20,
        'page': 1,
        'aggreeId': None,
        'planId': '68084704a7e04b0412d02496',
        'tags': None,
        'politicsLevel': None,
        'startTime': start_time,
        'endTime': end_time,
        'dataType': [],
        'forward': None,
        'read': None,
    }
    response = requests.post(
        'https://brandkbs.zhiweidata.com/brandkbs/app/yuqing/non-manual/mark/list',
        cookies=cookies,
        headers=headers,
        json=json_data,
        # proxies=sp.proxies
    )
    # import pdb;
    # pdb.set_trace()
    records = response.json()['data']['list']
    return records


if __name__ == '__main__':
    print(get_config('zhiwei_JSESSIONID'))
    print(get_config('zhiwei_TOKEN'))
