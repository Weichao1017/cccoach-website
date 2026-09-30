#!/usr/bin/env python3
"""把 content/articles/<别名>/article.md 转成官网正文 article.html（去掉一级标题；外链新窗口打开）。
用法：md2html.py content/articles/<别名>   （需要本机装 markdown、beautifulsoup4）
"""
import re
import sys
from urllib.parse import urlparse

import markdown
from bs4 import BeautifulSoup

d = sys.argv[1].rstrip('/')
md = open(d + '/article.md', encoding='utf-8').read()
soup = BeautifulSoup(markdown.markdown(md, extensions=['tables'], output_format='html'), 'html.parser')
for h1 in soup.find_all('h1'):
    h1.decompose()
ALLOWED = {'h2', 'h3', 'p', 'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'strong', 'a', 'blockquote', 'br'}
for tag in soup.find_all(True):
    if tag.name not in ALLOWED:
        raise SystemExit('不支持的标签：%s' % tag.name)
    if tag.name == 'a':
        href = tag.get('href')
        tag.attrs = {'href': href}
        if urlparse(href).netloc.lower() not in {'www.cccoach.cn', 'cccoach.cn'}:
            tag['target'] = '_blank'
            tag['rel'] = 'noopener'
    else:
        tag.attrs = {}
out = str(soup).replace('rel="noopener" target="_blank"', 'target="_blank" rel="noopener"')
out = re.sub(r'\n{2,}', '\n', out).strip() + '\n'
open(d + '/article.html', 'w', encoding='utf-8').write(out)
print('已生成 %s/article.html（%d 字符）' % (d, len(out)))
