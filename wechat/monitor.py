from wechat.search import JZL


def run():
    period = 90
    page_count = 10
    kw = "林俊旸"
    any_kw = ""
    ex_kw = ""
    mode = 1
    JZL().get(kw, any_kw, ex_kw, period, page_count, mode)


if __name__ == '__main__':
    run()
