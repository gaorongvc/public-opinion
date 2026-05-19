from py4j.java_gateway import JavaGateway

gateway = JavaGateway()

app = gateway.entry_point

data = {
    'account': 'SouthReviews',
}

value = app.genXYZ('https://newrank.cn/xdnphb/detail/v1/rank/article/lists', data, 'c16ad0b92')
print(value)
