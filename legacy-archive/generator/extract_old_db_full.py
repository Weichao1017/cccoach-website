# 只读解析旧站 SQL 导出里的内容表（不碰会员/订单/支付表），输出 JSON
import re, json, sys
DUMP = '/home/coach_backup.sql'
TABLES = {
    'coa_list': ['id','cate_id','title','thumb','files','video','intro','content','create_time','update_time','is_recommend'],
    'coa_page': ['id','title','intro','thumb','content','create_time','temp'],
    'coa_activity': ['id','category_id','title','type','city','image','teacher','begin_date','end_date','address','linkman','max_order_number','price','other_price','intro','status','create_time','update_time','is_recommend','introduction','sort','qr_code','pm','is_del'],
    'coa_cate': ['id','name','parent_id','path','sort','type','create_time','update_time','listtemp','actiontemp'],
    'coa_category': ['id','name','type','is_pay','create_time','update_time'],
    'coa_city': ['id','name','status','is_del'],
}
KEEP = {'coa_list': ['id','cate_id','title','thumb','intro','content','create_time','update_time'],
        'coa_page': ['id','title','intro','thumb','content','create_time'],
        'coa_activity': ['id','category_id','title','type','city','image','teacher','begin_date','end_date','intro','introduction','status','is_del','create_time'],
        'coa_cate': ['id','name','parent_id','path','sort','type'],
        'coa_category': ['id','name','type'],
        'coa_city': ['id','name','status','is_del']}
FULL = True
ESC = {'0':'\0','n':'\n','r':'\r','t':'\t','Z':'\x1a','b':'\b'}
def parse_values(s, i):
    rows = []
    n = len(s)
    while i < n:
        while i < n and s[i] in ' ,\n': i += 1
        if i >= n or s[i] == ';': break
        assert s[i] == '(', s[i:i+20]
        i += 1; row = []
        while True:
            c = s[i]
            if c == "'":
                i += 1; buf = []
                while True:
                    c = s[i]
                    if c == '\\': buf.append(ESC.get(s[i+1], s[i+1])); i += 2
                    elif c == "'":
                        if s[i+1] == "'": buf.append("'"); i += 2
                        else: i += 1; break
                    else: buf.append(c); i += 1
                row.append(''.join(buf))
            else:
                j = i
                while s[i] not in ',)': i += 1
                v = s[j:i].strip(); row.append(None if v == 'NULL' else v)
            if s[i] == ',': i += 1; continue
            if s[i] == ')': i += 1; break
        rows.append(row)
    return rows
def text(h, k=400):
    h = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', '', h or '')
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>|&nbsp;', ' ', h)).strip()[:k]
out = {t: [] for t in TABLES}
with open(DUMP, encoding='utf-8', errors='replace') as f:
    for line in f:
        m = re.match(r'INSERT INTO `(\w+)` VALUES ', line)
        if not m or m.group(1) not in TABLES: continue
        t = m.group(1); cols = TABLES[t]
        for r in parse_values(line, m.end()):
            d = dict(zip(cols, r))
            rec = {k: d.get(k) for k in KEEP[t]}
            if not globals().get('FULL'):
                for k in ('content', 'intro'):
                    if k in rec:
                        rec[k + '_len'] = len(text(rec[k], 10**9)); rec[k] = text(rec[k])
            out[t].append(rec)
json.dump(out, open('/root/cccoach_legacy_20260929/old_content_full.json', 'w'), ensure_ascii=False)
print({t: len(v) for t, v in out.items()})
