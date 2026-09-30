#!/usr/bin/env python3
"""生成“内容变更清单”：对照数据库当前内容，把要改的地方写成精确的 old → new，供 content-apply.py 执行或回退。

输入（都在仓库 content/ 下）：
  homepage-blocks.json   首页区块要改的字段：[{path, set 或 replace_in, note}]
  sources/certs-*.json   证书/资质/信息图的替代文字（page、src、alt）
  articles/<slug>/       要发布的文章：article.html、meta.json、封面图（和数据库里一样的不再重复写）
  edits/*.json           其他页面改动，每条是下面一种：
      {"page": "/profile", "find": "原文", "replace": "新文", "note": "说明"}          页面正文里替换一段文字
      {"page": "/article/13", "field": "meta_description", "set": "新值", "note": ""}  整个字段改成新值
      {"page": "/article/13", "field": "content", "set_file": "edits/tutors/13.html"}  字段内容取自文件
      {"article": 13, "tags_remove": ["ICF PCC"], "tags_add": ["ICF MCC"], "note": ""} 改导师页标签
      {"table": "menu", "key": {"id": 2}, "field": "extra", "find": "原文", "replace": "新文"}  改其他表（如导航菜单说明）
  categories.json        要新建的文章分类：[{slug, title, parent（上级分类别名）, order_number}]
用法：content-build.py content/changes/<清单名>.json [--from homepage,certs,articles,edits]
      不写 --from 就四类都看。
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


def page_key(url):
    p = re.sub(r'^https?://(www\.)?cccoach\.cn', '', url)
    m = re.match(r'^/article/(\d+)/?$', p)
    if m:
        return ('article', 'id', int(m.group(1)))
    p = p.strip('/')
    return ('single_page', 'slug', p) if p else None


def field_of(table, col, val, field):
    rows = q("SELECT JSON_OBJECT('v', %s) FROM %s WHERE %s=%s" % (field, table, col, sqlstr(val)))
    return rows[0]['v'] if len(rows) == 1 else None


ops, missing = [], []
kinds = set(sys.argv[sys.argv.index('--from') + 1].split(',')) if '--from' in sys.argv else {'homepage', 'certs', 'articles', 'edits'}

# 0) 新建分类（content/categories.json：[{slug, title, parent, order_number}]）
cpath = os.path.join(C, 'categories.json')
if 'articles' in kinds and os.path.exists(cpath):
    for c in json.load(open(cpath, encoding='utf-8')):
        if not q("SELECT JSON_OBJECT('id', id) FROM article_category WHERE slug=%s" % sqlstr(c['slug'])):
            ops.append(dict(type='category', slug=c['slug'], title=c['title'], parent=c['parent'],
                            order_number=c.get('order_number', 0), note='新建分类'))

# 1) 首页区块
if 'homepage' in kinds:
    blocks = json.load(open(os.path.join(C, 'homepage-blocks.json'), encoding='utf-8'))
    tid = 'top.jstart'
    data = json.loads(q("SELECT JSON_OBJECT('o', options) FROM template_block_option WHERE template_id=%s" % sqlstr(tid))[0]['o'])
    for b in blocks:
        cur = getpath(data, b['path'])
        if 'set' in b:
            new = b['set']
        else:
            frm, to = b['replace_in']
            if frm not in cur and to in cur:
                continue
            if frm not in cur:
                raise SystemExit('首页区块字段里找不到要替换的文字：%s' % b['note'])
            new = cur.replace(frm, to)
        if new != cur:
            ops.append(dict(type='block_option', template_id=tid, path=b['path'], old=cur, new=new, note=b['note']))


# 2) 图片替代文字
def clean_alt(s):
    s = re.sub(r'\s+', ' ', s).strip()
    return s.replace('&', '&amp;').replace('"', '“').replace('<', '').replace('>', '')


if 'certs' in kinds:
    items = []
    for fn in sorted(os.listdir(os.path.join(C, 'sources'))):
        if fn.startswith('certs-') and fn.endswith('.json'):
            items += json.load(open(os.path.join(C, 'sources', fn), encoding='utf-8'))
    by_page = {}
    for it in items:
        k = page_key(it.get('page', ''))
        if k and it.get('src') and it.get('alt'):
            by_page.setdefault(k, []).append(it)
    for (table, col, val), its in sorted(by_page.items(), key=lambda x: str(x[0])):
        content = field_of(table, col, val, 'content')
        if content is None:
            missing.append('%s %s=%s：找不到这一行' % (table, col, val))
            continue
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
                    new = re.sub(r'''\salt\s*=\s*"[^"]*"''', lambda _: ' alt="%s"' % alt, tag, count=1)
                elif re.search(r"""\salt\s*=\s*'[^']*'""", tag):
                    new = re.sub(r"""\salt\s*=\s*'[^']*'""", lambda _: ' alt="%s"' % alt, tag, count=1)
                else:
                    new = tag.replace('<img', '<img alt="%s"' % alt, 1)
                if new != tag:
                    ops.append(dict(type='replace', table=table, key={col: val}, field='content',
                                    old=tag, new=new, count=content.count(tag), note=it.get('name') or it.get('kind') or ''))

# 3) 文章（和数据库里一模一样的跳过）
if 'articles' in kinds:
    adir = os.path.join(C, 'articles')
    for slug in sorted(os.listdir(adir)):
        d = os.path.join(adir, slug)
        if not os.path.isdir(d):
            continue
        meta = json.load(open(os.path.join(d, 'meta.json'), encoding='utf-8'))
        body = open(os.path.join(d, 'article.html'), encoding='utf-8').read()
        cur = q("SELECT JSON_OBJECT('title',title,'content',content,'summary',summary,'meta_title',meta_title,"
                "'meta_description',meta_description,'meta_keywords',meta_keywords,'status',status,'thumbnail',thumbnail) "
                "FROM article WHERE slug=%s" % sqlstr(meta['slug']))
        want = dict(title=meta['title'], content=body, summary=meta['summary'], meta_title=meta['meta_title'],
                    meta_description=meta['meta_description'], meta_keywords=','.join(meta['keywords']), status='normal',
                    thumbnail='/attachment/%s/%s%s' % (meta['cover_dir'], meta['slug'], os.path.splitext(meta['cover'])[1] or '.jpg'))
        if cur and all((cur[0].get(k) or '') == v for k, v in want.items()):
            continue
        ops.append(dict(type='article', dir='content/articles/' + slug))

# 4) 其他页面改动
if 'edits' in kinds and os.path.isdir(os.path.join(C, 'edits')):
    tagid = {r['title']: r['id'] for r in q("SELECT JSON_OBJECT('id', id, 'title', title) FROM article_category WHERE type='tag'")}
    for fn in sorted(os.listdir(os.path.join(C, 'edits'))):
        if not fn.endswith('.json'):
            continue
        for e in json.load(open(os.path.join(C, 'edits', fn), encoding='utf-8')):
            note = e.get('note', '')
            if 'article' in e:
                aid = int(e['article'])
                have = {r['c'] for r in q("SELECT JSON_OBJECT('c', category_id) FROM article_category_mapping WHERE article_id=%d" % aid)}
                rm = [tagid[t] for t in e.get('tags_remove', [])]
                add = [tagid[t] for t in e.get('tags_add', [])]
                if all(t not in have for t in rm) and all(t in have for t in add):
                    continue
                ops.append(dict(type='mapping', article_id=aid, remove=rm, add=add, note=note))
                continue
            if 'table' in e:
                table = e['table']
                (col, val), = e['key'].items()
            else:
                table, col, val = page_key(e['page'])
            field = e.get('field', 'content')
            cur = field_of(table, col, val, field)
            if cur is None and not q("SELECT JSON_OBJECT('n', COUNT(*)) FROM %s WHERE %s=%s" % (table, col, sqlstr(val)))[0]['n']:
                missing.append('%s：找不到这一页' % e.get('page', '%s %s' % (table, val)))
                continue
            cur = cur or ''
            if 'find' in e:
                n_old, n_new = cur.count(e['find']), cur.count(e['replace'])
                if n_old == 0 and n_new > 0:
                    continue
                if n_old == 0:
                    missing.append('%s：找不到要替换的文字“%s”' % (e.get('page', '%s %s' % (table, val)), e['find'][:40]))
                    continue
                ops.append(dict(type='replace', table=table, key={col: val}, field=field,
                                old=e['find'], new=e['replace'], count=n_old, note=note))
            else:
                new = e['set'] if 'set' in e else open(os.path.join(C, e['set_file']), encoding='utf-8').read()
                if new != cur:
                    ops.append(dict(type='set', table=table, key={col: val}, field=field, old=cur, new=new, note=note))

out = sys.argv[1]
json.dump(dict(id=os.path.splitext(os.path.basename(out))[0], ops=ops), open(out, 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
cnt = lambda t: sum(o['type'] == t for o in ops)  # noqa: E731
print('清单：%s，共 %d 项（分类 %d、区块 %d、文字替换 %d、整段改写 %d、标签 %d、文章 %d）' % (
    out, len(ops), cnt('category'), cnt('block_option'), cnt('replace'), cnt('set'), cnt('mapping'), cnt('article')))
for m in missing:
    print('  未处理：' + m)
