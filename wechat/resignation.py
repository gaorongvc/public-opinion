from concurrent.futures import ThreadPoolExecutor

from grlibs.d import today_str
# from grlibs.feishu import Feishu
from grlibs.lm import LM
from grlibs.mdb import client

from wechat.search import JZL

# feishu = Feishu()
# datasheet = feishu.get_datasheet('D5tNbaXV4a3LLHsLcbFcifocnch', 'tbl5S2QuQSv2RVnt')
table = client.db1.wechat.articles


class Resignation(object):
    def __init__(self, kw, any_kw, period, page_count=1):
        self.kw = kw
        self.any_kw = any_kw
        self.period = period
        self.page_count = page_count

    def _extract_potential_entrepreneurs(self, url):
        print(url)
        article = table.find_one({'url': url})
        content = article['content']
        prompt = """
你是一名投资分析师，你将得到一篇公众号文章，首先需要判断文章是否涉及人事变动(离职或创业)。如果涉及人事变动，则进行以下提取：

请为每个人识别并提取以下详细信息：
- 姓名
- 技术领域
- 前公司
- 前职位
- 现公司
- 现职位
- is_startup（现公司是新初创公司则为 true，无法判断也为 true，其他为 false，这里成立一年以上就不算新公司）
- is_startup_reason 解释一下你的判断
- is_chinese（中国人为 true，其他为 false，可以通过姓名与过往履历判断）
- is_chinese_reason 解释一下你的判断
- is_validate_name（完整的姓名则为 true，昵称、x总、x哥、x姐、x经理、夏夏等模糊的名称均为 false）
- is_validate_name_reason 解释一下你的判断
- is_recent_resignation（创业者最近离职或创业为 true，无法判断也为 true，其他的为 false）
- is_recent_resignation_reason 解释一下你的判断
- has_funding（有过融资为 true，不确定没有都为 false）
- is_tech_domain（科技领域为 ture，其他都为 false）
- is_strong_sign（出现“离职/卸任/从X离开/创办/联合创始人/准备创业/stealth”任一强信号。）
- has_big_company_experience（是否来自阿里/蚂蚁、腾讯、字节、美团、拼多多、百度、华为、小米、京东、快手、滴滴、OPPO/Vivo、商汤/旷视/依图、寒武纪；以及 Google、Apple、Meta、Amazon、Microsoft、NVIDIA、OpenAI、Tesla）

如果涉及人事变动，请以JSON格式返回这些信息，每个人的信息作为一个单独的JSON对象列表。格式如下：
[
  {
    "entrepreneur_name": "潜在创业者姓名",
    "technical_field": "创业者擅长的技术领域或专业，可结合履历判断",
    "former_company": "前公司名称",
    "former_position": "在前公司担任的职位",
    "current_company": "现公司名称",
    "current_position": "在现公司担任的职位",
    "is_chinese": false,
    "is_startup": false,
    "is_validate_name": false,
    "is_validate_name_reason": "",
    "is_recent_resignation": false,
    "is_recent_resignation_reason": "",
    "has_funding": false,
    "is_tech_domain": false,
    "is_strong_sign": false,
    "has_big_company_experience": false
  },
  ...
]

如果文章不涉及人事变动，请返回一个空的JSON列表。

以下是文章内容：
```
{query}
```
文章发布日期是 {today_str}，其中涉及的近期都是关联文章发布日期，你一年前离职创业的好意思说是近期吗？
"""
        user_prompt = prompt.replace('{today_str}', article['publish_time_str'][:10]).replace('{query}', content)
        print(user_prompt)
        _messages = [{"role": "user", "content": user_prompt}]
        try:
            data = LM('openrouter/minimax/minimax-m2.7').chat(_messages)
        except:
            data = []
        print(data)
        table.update_one({'url': url}, {'$set': {'individuals': data}}, upsert=False)

    def extract_all(self):
        query = {}
        query["kw"] = self.kw
        query["any_kw"] = self.any_kw
        query["content"] = {
            u"$exists": True
        }
        query["individuals"] = {
            u"$exists": False
        }
        query["batch"] = today_str
        articles = table.find(query)
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for article in articles:
                future = executor.submit(self._extract_potential_entrepreneurs, article['url'])
                futures.append(future)
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    print(e)
                    continue

    def individuals_to_feishu(self):
        data = datasheet.request_records(params={})
        # import pdb;pdb.set_trace()
        names = [item['fields']['entrepreneur_name'] for item in data['data']['items']]
        query = {}
        query["kw"] = self.kw
        query["any_kw"] = self.any_kw
        query["content"] = {
            u"$exists": True
        }
        query["individuals"] = {
            u"$exists": True
        }
        query["batch"] = today_str
        articles = table.find(query)
        for article in articles:
            if not article['individuals']:
                continue
            for individual in article['individuals']:
                if individual['entrepreneur_name'] and individual['is_chinese'] and individual['is_startup'] and \
                        individual['is_validate_name'] and individual['is_recent_resignation']:
                    record = {
                        'entrepreneur_name': individual['entrepreneur_name'],
                        "technical_field": individual['technical_field'],
                        "former_company": individual['former_company'],
                        "former_position": individual['former_position'],
                        "current_company": individual['current_company'],
                        "current_position": individual.get('current_position', ''),
                        'url': article['url'],
                        'title': article['title'],
                        'account_name': article['wx_name']
                    }
                    if individual['entrepreneur_name'] in names:
                        continue
                    print(individual['entrepreneur_name'])
                    names.append(individual['entrepreneur_name'])
                    print(record)
                    ret = datasheet.create_record(record)
                    print(ret)

    def run(self):
        JZL().get(self.kw, self.any_kw, '', self.period, self.page_count)
        self.extract_all()
        # self.individuals_to_feishu()


if __name__ == '__main__':
    # data = datasheet.request_records(params={})
    # import pdb;pdb.set_trace()
    # names = [item['fields']['entrepreneur_name'] for item in data['data']['items']]
    # print(names)
    # exit()
    # url = 'https://mp.weixin.qq.com/s?__biz=MTI3NTQ1MTY0MQ==&mid=2650663800&idx=1&sn=abc045daf346bdfb4482caf55374bc2f&chksm=989831#rd'
    # Resignation("", "", 1, 1)._extract_potential_entrepreneurs(url)
    # exit()
    days = 1
    page_count = 2
    Resignation("AI 离职 创业", "CEO CTO COO CIO CPO CAO 高管 GM MD VP 总监 天才少年 姚班 少年班", days,
                page_count).run()
    # Resignation("AI 离职 创业", "CEO CTO COO CIO CPO CAO 高管 GM MD VP 总监 天才少年 姚班 少年班", days,
    #             page_count).individuals_to_feishu()
    # Resignation("AI 离职 大牛", "CEO CTO COO CIO CPO CAO 高管 GM MD VP 总监 天才少年 姚班 少年班", days, page_count).run()
    # Resignation("具身智能 离职 创业", "CEO CTO COO CIO CPO CAO 高管 GM MD VP 总监 天才少年 姚班 少年班", days, page_count).run()
    # Resignation("加入 AI 创业", "华为 OpenAI CMU DeepMind Gemini 斯坦福 清华 大疆", days, page_count).run()
    # Resignation("加入 AI 创业", "华为 OpenAI CMU DeepMind Gemini 斯坦福 清华 大疆", days, page_count).individuals_to_feishu()
    # Resignation("技术 加入 AI 创业", "大牛 大拿 负责人", days, page_count).run()
    # Resignation("大牛 离职 AI 创业", "", days, page_count).run()
    # Resignation("离职 加入 AI 创业", "", days, page_count).run()
    # Resignation("离职 创业", "具身智能 机器人", days, page_count).run()
