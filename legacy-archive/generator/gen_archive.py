# 用旧站数据库原文，生成旧网址的静态存档页（新站没有对应页面的那部分）
# 输出：build/__legacy/{a,p,c,e,ei}/…  线上放到 /www/wwwroot/cccoach-legacy/__legacy/
import json, re, os, html, shutil, math
from datetime import datetime
from mapping_manual import ACTIVITY_KEYWORDS

SITE = 'https://www.cccoach.cn'
OUT = 'build/__legacy'
d = json.load(open('old_content_full.json'))
deployed = json.load(open('deploy_rows.json'))
R301 = {(k, str(i)) for k, i, _, _ in deployed}          # 已 301 的，不生成
cates = {c['id']: c for c in d['coa_cate']}
cities = {c['id']: c['name'] for c in d['coa_city']}
acat = {c['id']: c['name'].strip() for c in d['coa_category']}

# ---------- 正文清理 ----------
MOBILE = re.compile(r'(?<![\d.])1[3-9]\d{9}(?![\d])')
def mask_text(s):
    # 只改标签外的文字，不碰链接和图片地址
    parts = re.split(r'(<[^>]+>)', s)
    return ''.join(p if p.startswith('<') else MOBILE.sub('（已隐去）', p) for p in parts)

def fix_url(u):
    u = html.unescape(u.strip())
    u = re.sub(r'^https?://(?:www\.)?cccoach\.cn', '', u)
    return u

def clean_html(h):
    h = h or ''
    h = re.sub(r'(?is)<(script|style|form|input|button|select|textarea|object)[^>]*>.*?</\1>', '', h)
    h = re.sub(r'(?is)<(script|input|button|link|meta)[^>]*/?>', '', h)
    # 腾讯视频 Flash → 网页播放器
    def embed(m):
        vid = re.search(r'vid=([A-Za-z0-9]+)', m.group(0))
        if vid:
            return f'<div class="video"><iframe src="https://v.qq.com/txp/iframe/player.html?vid={vid.group(1)}" allowfullscreen frameborder="0"></iframe></div>'
        return ''
    h = re.sub(r'(?is)<embed[^>]*>(?:</embed>)?', embed, h)
    # 图片：去 1px 占位图，data-src 补成 src，地址改成站内相对
    def img(m):
        t = m.group(0)
        if 'spacer.gif' in t and 'data-src' not in t.replace('data-src="http://wxedit', ''):
            return ''
        src = re.search(r'\ssrc="([^"]*)"', t)
        dsrc = re.search(r'data-src="([^"]*)"', t)
        u = src.group(1) if src else ''
        if (not u or 'spacer.gif' in u) and dsrc and 'spacer.gif' not in dsrc.group(1):
            u = dsrc.group(1)
        if not u or 'spacer.gif' in u or u.startswith('file:'):
            return ''
        alt = re.search(r'alt="([^"]*)"', t)
        return f'<img src="{html.escape(fix_url(u), quote=True)}" alt="{html.escape(alt.group(1) if alt else "", quote=True)}" loading="lazy">'
    h = re.sub(r'(?is)<img[^>]*>', img, h)
    # 其他属性：去掉事件、固定宽高；链接改相对
    h = re.sub(r'(?i)\s(on\w+)="[^"]*"', '', h)
    h = re.sub(r'(?i)\s(width|height)="[^"]*"', '', h)
    h = re.sub(r'(?i)(href|src)="(https?://(?:www\.)?cccoach\.cn)?([^"]*)"',
               lambda m: f'{m.group(1)}="{m.group(3) if m.group(2) else m.group(3)}"', h)
    h = re.sub(r'(?i)<a\s', '<a rel="nofollow" ', h) if False else h
    return mask_text(h)

def plain(h, n=110):
    t = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', '', h or '')
    t = html.unescape(re.sub(r'<[^>]+>', ' ', t))
    t = re.sub(r'\s+', ' ', t).strip()
    return MOBILE.sub('', t)[:n]

def has_body(h):
    return bool(plain(h, 10**6).strip()) or any(t in (h or '') for t in ('<img', '<video', 'iframe', '<embed'))

def cn_date(s, with_time=False):
    try:
        dt = datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S')
    except Exception:
        return ''
    if dt.year < 2000:
        return ''
    return f'{dt.year} 年 {dt.month} 月 {dt.day} 日' + (f' {dt:%H:%M}' if with_time and (dt.hour or dt.minute) else '')

def year_of(s):
    return s[:4] if s and s[:4].isdigit() and s[:4] > '2000' else ''

# ---------- 页面骨架 ----------
CSS = """
:root{--g:#007855;--g2:#198264;--bg:#F3FAF0;--ink:#1f2a26;--mut:#5d6b66;--line:#dfe8e2}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:#fff;color:var(--ink);font:16px/1.8 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
a{color:var(--g)}
.top{background:var(--g);color:#fff}
.top .in{max-width:1100px;margin:0 auto;padding:12px 16px;display:flex;flex-wrap:wrap;align-items:center;gap:8px 24px}
.brand{color:#fff;text-decoration:none;font-weight:600;font-size:18px;letter-spacing:1px}
.nav{display:flex;flex-wrap:wrap;gap:4px 18px;font-size:15px}
.nav a{color:#e6f4ee;text-decoration:none}.nav a:hover{color:#fff;text-decoration:underline}
.note{background:var(--bg);border-bottom:1px solid var(--line);font-size:14px;color:var(--mut)}
.note .in{max-width:860px;margin:0 auto;padding:10px 16px}
main{max-width:860px;margin:0 auto;padding:20px 16px 48px}
.crumb{font-size:14px;color:var(--mut);margin-bottom:8px}.crumb a{color:var(--mut)}
h1{font-size:26px;line-height:1.4;margin:6px 0 10px}
.meta{font-size:14px;color:var(--mut);margin-bottom:22px}
.facts{background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:12px 16px;margin:0 0 22px;font-size:15px}
.facts div{margin:2px 0}.facts b{color:var(--g2);font-weight:600;margin-right:6px}
.tag{display:inline-block;background:#e9efec;color:#46524d;border-radius:4px;padding:0 8px;font-size:13px;margin-left:6px}
article{overflow-wrap:anywhere}
article img,article video{max-width:100%!important;height:auto!important}
article *{max-width:100%}
article table{border-collapse:collapse}article td,article th{border:1px solid var(--line);padding:4px 8px}
.video{position:relative;padding-top:56.25%;margin:12px 0}.video iframe{position:absolute;inset:0;width:100%;height:100%}
.cover{width:100%;border-radius:6px;margin-bottom:18px}
.more{margin-top:40px;border-top:1px solid var(--line);padding-top:18px}
.more h2{font-size:17px;margin:0 0 8px}
.more ul{margin:0;padding-left:20px}
.list{list-style:none;padding:0;margin:0}
.list li{border-bottom:1px solid var(--line);padding:12px 0}
.list a{font-size:17px;text-decoration:none}.list a:hover{text-decoration:underline}
.list .d{font-size:13px;color:var(--mut)}
.pager{margin-top:22px;display:flex;flex-wrap:wrap;gap:8px}
.pager a,.pager span{border:1px solid var(--line);border-radius:4px;padding:2px 10px;font-size:14px;text-decoration:none}
.pager span{background:var(--g);color:#fff;border-color:var(--g)}
.cities{margin:0 0 14px;font-size:14px}.cities a,.cities span{margin-right:12px}
footer{background:#f6f8f7;border-top:1px solid var(--line);color:var(--mut);font-size:13px;text-align:center;padding:18px 16px}
footer a{color:var(--mut)}
@media (max-width:600px){h1{font-size:22px}.brand{font-size:16px}}
"""
NAV = [('首页', '/'), ('公司简介', '/profile'), ('进化教练', '/brand-courses-evolution'),
       ('纯净教练', '/brand-courses-significant'), ('教练百科', '/article/category/encyclopedia'),
       ('核心教练', '/article/category/coachers'), ('全年课表', 'https://sica7.xetlk.com/s/4BTY7e')]

def page(title, canonical, desc, body, jsonld=None, year=''):
    nav = ''.join(f'<a href="{u}">{n}</a>' for n, u in NAV)
    when = f'（{year} 年发布）' if year else ''
    ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ''
    return f"""<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>{html.escape(title)} - 创问中国教练中心</title>
<meta name="description" content="{html.escape(desc, quote=True)}">
<link rel="canonical" href="{SITE}{canonical}">
<link rel="icon" href="/templates/4269b344/cccoach/img/icon.ico">
{ld}<style>{CSS}</style></head>
<body>
<div class="top"><div class="in"><a class="brand" href="/">创问中国教练中心</a><nav class="nav">{nav}</nav></div></div>
<div class="note"><div class="in">这是创问旧官网的存档页面{when}，内容保持原样。最新课程和活动请看<a href="/">创问官网首页</a>。</div></div>
<main>{body}</main>
<footer>© 上海创问中国教练中心 · <a href="https://beian.miit.gov.cn/">沪ICP备13018355号-1</a></footer>
</body></html>"""

def write(rel, s):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w', encoding='utf-8').write(s)

ORG = {'@type': 'Organization', 'name': '创问中国教练中心', 'url': SITE + '/'}

# ---------- 栏目 ----------
def cate_chain(cid):
    out = []
    c = cates.get(str(cid))
    while c:
        out.append(c)
        c = cates.get(c['parent_id']) if c['parent_id'] not in (None, '', '0') else None
    return list(reversed(out))

def cate_url(cid):
    return f'/Home/List/index/id/{cid}.html'

def crumb_html(items):
    return '<div class="crumb">' + ' › '.join(f'<a href="{u}">{html.escape(n)}</a>' if u else html.escape(n) for n, u in items) + '</div>'

# ---------- 文章 ----------
arts = sorted(d['coa_list'], key=lambda a: (a['create_time'] or ''), reverse=True)
by_cate = {}
for a in arts:
    by_cate.setdefault(a['cate_id'], []).append(a)
def cate_articles(cid):
    ids = {cid} | {c['id'] for c in d['coa_cate'] if c['parent_id'] == cid}
    return [a for a in arts if a['cate_id'] in ids]

n_a = 0
for a in arts:
    if ('article', a['id']) in R301 or not has_body(a['content']):
        continue
    chain = cate_chain(a['cate_id'])
    crumbs = [('首页', '/')] + [(c['name'], cate_url(c['id'])) for c in chain]
    title = a['title'].strip()
    date = cn_date(a['create_time'] or '')
    sib = [x for x in by_cate.get(a['cate_id'], []) if x['id'] != a['id'] and has_body(x['content'])][:6]
    more = ''
    if sib:
        more = '<div class="more"><h2>同栏目的其他文章</h2><ul>' + ''.join(
            f'<li><a href="/Home/List/show/id/{x["id"]}.html">{html.escape(x["title"].strip())}</a></li>' for x in sib) + '</ul></div>'
    body = crumb_html(crumbs) + f'<h1>{html.escape(title)}</h1>' + (f'<div class="meta">发布于 {date}</div>' if date else '') + \
        f'<article>{clean_html(a["content"])}</article>' + more
    ld = {'@context': 'https://schema.org', '@type': 'Article', 'headline': title, 'publisher': ORG, 'author': ORG,
          'mainEntityOfPage': f'{SITE}/Home/List/show/id/{a["id"]}.html', 'inLanguage': 'zh-CN'}
    if a['create_time'] and year_of(a['create_time']):
        ld['datePublished'] = a['create_time'][:10]
    write(f'a/{a["id"]}.html', page(title, f'/Home/List/show/id/{a["id"]}.html', plain(a['content']) or title, body, ld, year_of(a['create_time'] or '')))
    n_a += 1

# ---------- 栏目列表（分页）----------
PER = 10  # 旧站每页 10 条（从旧网址页码推出来的）
n_c = 0
for c in d['coa_cate']:
    if ('list', c['id']) in R301:
        continue
    items = [a for a in cate_articles(c['id']) if has_body(a['content'])]
    if not items:
        continue
    chain = cate_chain(c['id'])
    crumbs = [('首页', '/')] + [(x['name'], cate_url(x['id']) if x['id'] != c['id'] else '') for x in chain]
    pages = max(1, math.ceil(len(items) / PER))
    for p in range(1, pages + 1):
        chunk = items[(p - 1) * PER:p * PER]
        lis = ''.join(f'<li><a href="/Home/List/show/id/{a["id"]}.html">{html.escape(a["title"].strip())}</a>'
                      f'<div class="d">{cn_date(a["create_time"] or "")}</div></li>' for a in chunk)
        pager = ''
        if pages > 1:
            pager = '<div class="pager">' + ''.join(
                f'<span>{i}</span>' if i == p else f'<a href="/Home/List/index/id/{c["id"]}' + ('' if i == 1 else f'/p/{i}') + f'.html">{i}</a>'
                for i in range(1, pages + 1)) + '</div>'
        canon = f'/Home/List/index/id/{c["id"]}' + ('' if p == 1 else f'/p/{p}') + '.html'
        body = crumb_html(crumbs) + f'<h1>{html.escape(c["name"])}</h1><div class="meta">共 {len(items)} 篇</div><ul class="list">{lis}</ul>{pager}'
        write(f'c/{c["id"]}/{p}.html', page(c['name'], canon, f'创问旧官网「{c["name"]}」栏目文章存档，共 {len(items)} 篇。', body))
        n_c += 1

# ---------- 全部文章列表（旧网址 /Home/List/index/p/N，不带栏目号）----------
items = [a for a in arts if has_body(a['content']) and ('article', a['id']) not in R301] + [a for a in arts if ('article', a['id']) in R301]
items.sort(key=lambda a: (a['create_time'] or ''), reverse=True)
pages = max(1, math.ceil(len(items) / PER))
for p in range(1, pages + 1):
    chunk = items[(p - 1) * PER:p * PER]
    lis = ''.join(f'<li><a href="/Home/List/show/id/{a["id"]}.html">{html.escape(a["title"].strip())}</a>'
                  f'<div class="d">{cn_date(a["create_time"] or "")}</div></li>' for a in chunk)
    def purl(i):
        return '/Home/List/index' + ('' if i == 1 else f'/p/{i}') + '.html'
    show = sorted({1, pages, *range(max(1, p - 3), min(pages, p + 3) + 1)})
    pager, last = '', 0
    for i in show:
        if i - last > 1:
            pager += '<span style="background:none;color:inherit;border:0">…</span>'
        pager += f'<span>{i}</span>' if i == p else f'<a href="{purl(i)}">{i}</a>'
        last = i
    body = crumb_html([('首页', '/'), ('全部文章', '')]) + f'<h1>全部文章</h1><div class="meta">共 {len(items)} 篇</div><ul class="list">{lis}</ul><div class="pager">{pager}</div>'
    write(f'c/all/{p}.html', page('全部文章', purl(p), f'创问旧官网文章存档，共 {len(items)} 篇。', body))
    n_c += 1

# ---------- 单页 ----------
n_p = 0
for pg in d['coa_page']:
    if ('page', pg['id']) in R301 or not has_body(pg['content']):
        continue
    raw = pg['title'].strip()
    sec, _, name = raw.partition('-') if '-' in raw and not raw.startswith('“') and not raw.startswith('《') else ('', '', raw)
    name = name or raw
    crumbs = [('首页', '/')] + ([(sec, '')] if sec else [])
    body = crumb_html(crumbs) + f'<h1>{html.escape(name)}</h1>' + \
        (f'<img class="cover" src="/uploads/{html.escape(pg["thumb"])}" alt="">' if pg.get('thumb') else '') + \
        f'<article>{clean_html(pg["content"])}</article>'
    ld = {'@context': 'https://schema.org', '@type': 'WebPage', 'name': name, 'publisher': ORG, 'inLanguage': 'zh-CN'}
    write(f'p/{pg["id"]}.html', page(name, f'/Home/Page/index/id/{pg["id"]}.html', plain(pg['content']) or name, body, ld, year_of(pg['create_time'] or '')))
    n_p += 1

# ---------- 活动 ----------
acts = [a for a in d['coa_activity'] if a['is_del'] != '1']
acts.sort(key=lambda a: (a['begin_date'] or ''), reverse=True)
def course_link(title):
    for kw, url in ACTIVITY_KEYWORDS:
        if kw.lower() in (title or '').lower():
            return url
    return None
COURSE_NAME = {'/brand-courses-team4c': '4C团队教练', '/brand-courses-dialogue': '与教练对话', '/brand-courses-coach-senior': '高阶进化教练',
               '/brand-courses-team-pcc': 'PCC直通车', '/brand-courses-pure-pcc': '纯净PCC', '/brand-courses-team-acc': 'ACC 辅导',
               '/brand-courses-significant': '纯净教练', '/brand-courses-evolution': '进化教练', '/brand-courses-coach-mcc': 'MCC认证',
               '/brand-courses-coach-supervisor': '督导教练', '/brand-courses-coach-social-theater': '社会大剧院',
               '/brand-courses-coach-speechmaker': '成为演说家', '/social_social': '社会责任'}
n_e = 0
for a in acts:
    title = a['title'].strip()
    b, e = a['begin_date'] or '', a['end_date'] or ''
    when = cn_date(b, True)
    if e and e[:10] != b[:10]:
        when += ' 至 ' + cn_date(e, True)
    elif e and e[11:16] and b[11:16] != e[11:16]:
        when += f'–{e[11:16]}'
    facts = '<div class="facts"><div><b>状态</b>活动已结束，报名已关闭</div>'
    if when.strip():
        facts += f'<div><b>时间</b>{when}</div>'
    if cities.get(a['city']):
        facts += f'<div><b>地点</b>{html.escape(cities[a["city"]])}</div>'
    if (a.get('teacher') or '').strip():
        facts += f'<div><b>带领</b>{html.escape(a["teacher"].strip())}</div>'
    facts += '</div>'
    cl = course_link(title)
    more = '<div class="more"><h2>想参加最近的课程？</h2><ul>'
    if cl:
        more += f'<li>这门课的最新介绍：<a href="{cl}">{COURSE_NAME.get(cl, "课程介绍")}</a></li>'
    more += '<li>最新开课时间：<a href="https://sica7.xetlk.com/s/4BTY7e">创问全年课表</a></li><li><a href="/Home/Activity/index.html">更多往期活动</a></li></ul></div>'
    cover = f'<img class="cover" src="/uploads/{html.escape(a["image"])}" alt="">' if a.get('image') else ''
    main_html = a['intro'] if has_body(a['intro']) else a.get('introduction') or ''
    body = crumb_html([('首页', '/'), ('往期活动', '/Home/Activity/index.html')]) + \
        f'<h1>{html.escape(title)}<span class="tag">已结束</span></h1>' + facts + cover + f'<article>{clean_html(main_html)}</article>' + more
    ld = {'@context': 'https://schema.org', '@type': 'Event', 'name': title, 'organizer': ORG, 'inLanguage': 'zh-CN'}
    if year_of(b):
        ld['startDate'] = b[:19].replace(' ', 'T')
    if year_of(e):
        ld['endDate'] = e[:19].replace(' ', 'T')
    if cities.get(a['city']):
        ld['location'] = {'@type': 'Place', 'name': cities[a['city']]}
    write(f'e/{a["id"]}.html', page(title, f'/Home/Activity/show/id/{a["id"]}.html', plain(a.get('introduction') or main_html) or title, body, ld, year_of(b)))
    n_e += 1

# ---------- 往期活动列表（全部 + 按城市，分页）----------
PER_E = 10
n_ei = 0
city_ids = [c for c in ['2', '5', '6', '1', '3'] if any(a['city'] == c for a in acts)]
def act_list(items, base, title, cur_city):
    global n_ei
    pages = max(1, math.ceil(len(items) / PER_E))
    tabs = '<div class="cities">' + ('<span>全部</span>' if cur_city is None else '<a href="/Home/Activity/index.html">全部</a>')
    seen = set()
    for c in city_ids:
        nm = cities[c]
        if nm in seen and c != cur_city:
            continue
        seen.add(nm)
        tabs += f'<span>{nm}</span>' if c == cur_city else f'<a href="/Home/Activity/index/city/{c}.html">{nm}</a>'
    tabs += '</div>'
    for p in range(1, pages + 1):
        chunk = items[(p - 1) * PER_E:p * PER_E]
        lis = ''.join(f'<li><a href="/Home/Activity/show/id/{a["id"]}.html">{html.escape(a["title"].strip())}</a>'
                      f'<div class="d">{cn_date(a["begin_date"] or "")}{" · " + cities[a["city"]] if cities.get(a["city"]) else ""}</div></li>' for a in chunk)
        def purl(i):
            return base + ('' if i == 1 else f'/p/{i}') + '.html'
        # 页码太多时只显示前后几页
        show = sorted({1, pages, *range(max(1, p - 3), min(pages, p + 3) + 1)})
        pager, last = '', 0
        for i in show:
            if i - last > 1:
                pager += '<span style="background:none;color:inherit;border:0">…</span>'
            pager += f'<span>{i}</span>' if i == p else f'<a href="{purl(i)}">{i}</a>'
            last = i
        body = crumb_html([('首页', '/'), ('往期活动', '')]) + f'<h1>{title}</h1><div class="meta">共 {len(items)} 场，均已结束。最新开课时间请看<a href="https://sica7.xetlk.com/s/4BTY7e">创问全年课表</a>。</div>' + \
            tabs + f'<ul class="list">{lis}</ul>' + (f'<div class="pager">{pager}</div>' if pages > 1 else '')
        rel = ('ei/all' if cur_city is None else f'ei/city{cur_city}') + f'/{p}.html'
        write(rel, page(title, purl(p), f'创问旧官网往期活动存档，共 {len(items)} 场。', body))
        n_ei += 1
act_list(acts, '/Home/Activity/index', '往期活动', None)
for c in city_ids:
    act_list([a for a in acts if a['city'] == c], f'/Home/Activity/index/city/{c}', f'往期活动 · {cities[c]}', c)

print(f'文章 {n_a}  栏目页 {n_c}  单页 {n_p}  活动 {n_e}  活动列表页 {n_ei}')

# ---------- 按日期的活动页（旧站日历）：只生成当天确实有活动的日期 ----------
from datetime import date, timedelta
by_day = {}
for a in acts:
    try:
        b = date.fromisoformat((a['begin_date'] or '')[:10])
        e = date.fromisoformat((a['end_date'] or a['begin_date'])[:10])
    except Exception:
        continue
    if e < b or (e - b).days > 60:
        e = b
    x = b
    while x <= e:
        by_day.setdefault(x, []).append(a)
        x += timedelta(1)
n_ed = 0
for day, items in by_day.items():
    items = sorted(items, key=lambda a: a['begin_date'] or '')
    lis = ''.join(f'<li><a href="/Home/Activity/show/id/{a["id"]}.html">{html.escape(a["title"].strip())}</a>'
                  f'<div class="d">{cn_date(a["begin_date"] or "", True)}{" · " + cities[a["city"]] if cities.get(a["city"]) else ""}</div></li>' for a in items)
    t = f'{day.year} 年 {day.month} 月 {day.day} 日的活动'
    body = crumb_html([('首页', '/'), ('往期活动', '/Home/Activity/index.html'), (f'{day:%Y-%m-%d}', '')]) + \
        f'<h1>{t}</h1><div class="meta">共 {len(items)} 场，均已结束。最新开课时间请看<a href="https://sica7.xetlk.com/s/4BTY7e">创问全年课表</a>。</div><ul class="list">{lis}</ul>'
    write(f'ed/{day:%Y-%m-%d}.html', page(t, f'/Home/Activity/index/day/{day:%Y-%m-%d}.html', f'创问 {day:%Y-%m-%d} 的活动存档，共 {len(items)} 场。', body, year=str(day.year)))
    n_ed += 1
print(f'按日期活动页 {n_ed}')
