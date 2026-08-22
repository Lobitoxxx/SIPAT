import re
import requests

UA = {"User-Agent": "Mozilla/5.0"}
url = "https://www.datosabiertos.gob.pe/search?search_api_views_fulltext=emergencia"
h = requests.get(url, headers=UA, timeout=90).text
for m in sorted(set(re.findall(r"/dataset/[^\"]+", h)))[:25]:
    print(m)
