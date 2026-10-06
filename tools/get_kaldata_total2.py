import sys
sys.path.insert(0, r'F:\-SAM-\WWW\samlab.ws_bot')
import kaldata
total = 10000  # 1-200
for p in range(201, 501):
    url = 'https://www.kaldata.com/%%D1%%81%%D0%%BE%%D1%%84%%D1%%82%%D1%%83%%D0%%B5%%D1%%80/feed?paged=%d' % p
    its = kaldata.fetch_feed(url)
    total += len(its)
    if p % 50 == 0:
        print(p, total)
print('total', total)
