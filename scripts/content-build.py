#!/usr/bin/env python3
"""生成“内容变更清单”：对照数据库当前内容，把要改的地方写成精确的 old → new，供 content-apply.py 执行或回退。

输入（都在仓库 content/ 下）：
  homepage-blocks.json   首页区块要改的字段：[{path, set 或 replace_in, note}]
  sources/certs-*.json   证书/资质/信息图的替代文字（page、src、alt）
  articles/<slug>/       要发布的文章：article.html、meta.json、封面图
用法：content-build.py content/changes/<清单名>.json
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cc_db  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = os.path.join(ROOT, 'content')


def q(sql):
    r = cc_db.run(['mysql', '--batch', '--raw', '--skip-column-names', '-e', sql])
    if r.returncode:
        raise SystemExit(r.stderr.decode('utf-8', 'replace'))
    return [json.loads(line) for line in r.stdout.decode('utf-8').splitlines() if line.strip()]


def sqlstr(v):
    return str(v) if isinstance(v, int) else "'" + str(v).replace("\\", "\\\\").replace("'", "''") + "'"


def getpath(d, path):
    for k in path:
        d = d[k]
    return d


ops = []

# 1) 首页区块
blocks = json.load(open(os.path.join(C, 'homepage-blocks.json'), encoding='utf-8'))
tid = 'top.jstart'
data = json.loads(q("SELECT JSON_OBJECT('o', options) FROM template_block_option WHERE template_id=%s" % sqlstr(tid))[0]['o'])
for b in blocks:
    cur = getpath(data, b['path'])
    if 'set' in b:
        new = b['set']
    else:
        frm, to = b['replace_in']
        if frm not in cur:
            raise SystemExit('首页区块字段里找不到要替换的文字：%s' % b['note'])
        new = cur.replace(frm, to)
    if new != cur:
        ops.append(dict(type='block_option', template_id=tid, path=b['path'], old=cur, new=new, note=b['note']))

# 2) 图片替代文字
def page_key(url):
    p = re.sub(r'^https?://(www\.)?cccoach\.cn', '', url)
    m = re.match(r'^/article/(\d+)/?$', p)
    if m:
        return ('article', 'id', int(m.group(1)))
    p = p.strip('/')
    return ('single_page', 'slug', p) if p else None


def clean_alt(s):
    s = re.sub(r'\s+', ' ', s).strip()
    return s.replace('&', '&amp;').replace('"', '“').replace('<', '').replace('>', '')


items = []
for fn in sorted(os.listdir(os.path.join(C, 'sources'))):
    if fn.startswith('certs-') and fn.endswith('.json'):
        items += json.load(open(os.path.join(C, 'sources', fn), encoding='utf-8'))
by_page = {}
for it in items:
    k = page_key(it.get('page', ''))
    if k and it.get('src') and it.get('alt'):
        by_page.setdefault(k, []).append(it)
missing = []
for (table, col, val), its in sorted(by_page.items(), key=lambda x: str(x[0])):
    rows = q("SELECT JSON_OBJECT('v', content) FROM %s WHERE %s=%s" % (table, col, sqlstr(val)))
    if len(rows) != 1:
        missing.append('%s %s=%s：找不到这一行' % (table, col, val))
        continue
    content = rows[0]['v'] or ''
    done = set()
    for it in its:
        src = it['src']
        tags = sorted({m.group(0) for m in re.finditer(r'<img\b[^>]*>', content)
                       if re.search(r'''\ssrc\s*=\s*["']%s["']''' % re.escape(src), m.group(0))})
        if not tags:
            missing.append('%s %s=%s：正文里没有 %s（可能在模板里，不在正文）' % (table, col, val, src))
            continue
        alt = clean_alt(it['alt'])
        for tag in tags:
            if tag in done:
                continue
            done.add(tag)
            if re.search(r'''\salt\s*=\s*"[^"]*"''', tag):
                new = re.sub(r'''\salt\s*=\s*"[^"]*"''', ' alt="%s"' % alt, tag, count=1)
            elif re.search(r"""\salt\s*=\s*'[^']*'""", tag):
                new = re.sub(r"""\salt\s*=\s*'[^']*'""", ' alt="%s"' % alt, tag, count=1)
            else:
                new = tag.replace('<img', '<img alt="%s"' % alt, 1)
            if new != tag:
                ops.append(dict(type='replace', table=table, key={col: val}, field='content',
                                old=tag, new=new, count=content.count(tag), note=it.get('name') or it.get('kind') or ''))

# 3) 文章
adir = os.path.join(C, 'articles')
for slug in sorted(os.listdir(adir)):
    if os.path.isdir(os.path.join(adir, slug)):
        ops.append(dict(type='article', dir='content/articles/' + slug))

out = sys.argv[1]
json.dump(dict(id=os.path.splitext(os.path.basename(out))[0], ops=ops), open(out, 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('清单：%s，共 %d 项（区块 %d、替代文字 %d、文章 %d）' % (
    out, len(ops), sum(o['type'] == 'block_option' for o in ops), sum(o['type'] == 'replace' for o in ops),
    sum(o['type'] == 'article' for o in ops)))
for m in missing:
    print('  未处理：' + m)
