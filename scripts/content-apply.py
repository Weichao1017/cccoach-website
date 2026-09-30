#!/usr/bin/env python3
"""执行或回退“内容变更清单”（content/changes/*.json）。
先逐项核对数据库当前内容：与清单里的“原内容”一致才改；已经是新内容的跳过；都对不上就整批放弃、一个字不写。
所有写入放在一个事务里；写之前把涉及的原内容备份到 /root/cccoach_content_backup/；写完重启新站刷新缓存。

用法：content-apply.py <清单.json> [--revert] [--dry-run] [--no-restart]
  --revert      反向执行（区块、替代文字改回原样；本清单发布的文章改为草稿下线）
  --dry-run     只核对、列出计划，不写库
"""
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cc_db  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ATTACH = '/www/wwwroot/jpress/webapp/attachment'
RESTART = os.path.join(ROOT, 'scripts', 'restart-jpress.sh')


def q(sql):
    r = cc_db.run(['mysql', '--batch', '--raw', '--skip-column-names', '-e', sql])
    if r.returncode:
        raise SystemExit(r.stderr.decode('utf-8', 'replace'))
    return [json.loads(line) for line in r.stdout.decode('utf-8').splitlines() if line.strip()]


def sqlstr(v):
    return str(v) if isinstance(v, int) else "'" + str(v).replace("\\", "\\\\").replace("'", "''") + "'"


def hexs(s):
    return "CONVERT(X'%s' USING utf8mb4)" % (s or '').encode('utf-8').hex()


def getpath(d, path):
    for k in path:
        d = d[k]
    return d


def setpath(d, path, v):
    for k in path[:-1]:
        d = d[k]
    d[path[-1]] = v


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    mpath = sys.argv[1]
    revert, dry, norestart = '--revert' in sys.argv, '--dry-run' in sys.argv, '--no-restart' in sys.argv
    M = json.load(open(mpath, encoding='utf-8'))
    ts = time.strftime('%Y%m%d-%H%M%S')
    bdir = '/root/cccoach_content_backup/%s-%s%s' % (ts, M['id'], '-revert' if revert else '')
    plan, conflicts, sql, backups, covers = [], [], ['START TRANSACTION;'], {}, []

    # 1) 首页区块（同一模板的字段一起改）
    blocks = [o for o in M['ops'] if o['type'] == 'block_option']
    if blocks:
        tid = blocks[0]['template_id']
        cur_raw = q("SELECT JSON_OBJECT('o', options) FROM template_block_option WHERE template_id=%s" % sqlstr(tid))[0]['o']
        data, changed = json.loads(cur_raw), False
        for o in blocks:
            old, new = (o['new'], o['old']) if revert else (o['old'], o['new'])
            v = getpath(data, o['path'])
            if v == new:
                plan.append('跳过（已是目标内容）  首页区块：%s' % o['note'])
            elif v == old:
                setpath(data, o['path'], new)
                changed = True
                plan.append('修改  首页区块：%s' % o['note'])
            else:
                conflicts.append('首页区块“%s”现在的内容和清单对不上：%s' % (o['note'], str(v)[:80]))
        if changed:
            backups['template_block_option-%s.json' % tid] = cur_raw
            sql.append("UPDATE template_block_option SET options=%s WHERE template_id=%s;" % (
                hexs(json.dumps(data, ensure_ascii=False, separators=(',', ':'))), sqlstr(tid)))

    # 2) 文字替换（同一行的替换合并成一次更新）
    groups = {}
    for o in [o for o in M['ops'] if o['type'] == 'replace']:
        groups.setdefault((o['table'], json.dumps(o['key'], sort_keys=True), o['field']), []).append(o)
    for (table, keyj, field), items in groups.items():
        (col, val), = json.loads(keyj).items()
        where = '%s=%s' % (col, sqlstr(val))
        rows = q("SELECT JSON_OBJECT('v', %s) FROM %s WHERE %s" % (field, table, where))
        if len(rows) != 1:
            conflicts.append('%s %s 找不到或不唯一' % (table, where))
            continue
        cur = rows[0]['v'] or ''
        newv = cur
        for o in items:
            old, new = (o['new'], o['old']) if revert else (o['old'], o['new'])
            n_old, n_new = newv.count(old), newv.count(new)
            if n_old == 0 and n_new > 0:
                plan.append('跳过（已是目标内容）  %s %s：%s' % (table, val, o.get('note', '')))
            elif n_old == o.get('count', 1):
                newv = newv.replace(old, new)
                plan.append('修改  %s %s：%s' % (table, val, o.get('note', '')))
            else:
                conflicts.append('%s %s：“%s”出现 %d 次，清单预期 %d 次' % (table, val, old[:60], n_old, o.get('count', 1)))
        if newv != cur:
            backups['%s-%s-%s.html' % (table, val, field)] = cur
            sql.append('UPDATE %s SET %s=%s WHERE %s;' % (table, field, hexs(newv), where))

    # 3) 文章
    cats = set()
    for o in [o for o in M['ops'] if o['type'] == 'article']:
        d = os.path.join(ROOT, o['dir'])
        meta = json.load(open(os.path.join(d, 'meta.json'), encoding='utf-8'))
        body = open(os.path.join(d, 'article.html'), encoding='utf-8').read()
        slug = meta['slug']
        ex = q("SELECT JSON_OBJECT('id', id, 'status', status) FROM article WHERE slug=%s" % sqlstr(slug))
        cats.update(meta['categories'])
        if revert:
            if ex and ex[0]['status'] != 'draft':
                sql.append("UPDATE article SET status='draft', modified=NOW() WHERE slug=%s;" % sqlstr(slug))
                plan.append('下线（改为草稿）  文章：%s' % meta['title'])
            continue
        cover_src = os.path.join(d, meta['cover'])
        thumb = '/attachment/%s/%s' % (meta['cover_dir'], os.path.basename(meta['cover']))
        covers.append((cover_src, ATTACH + thumb[len('/attachment'):]))
        fields = dict(title=meta['title'], content=body, summary=meta['summary'], meta_title=meta['meta_title'],
                      meta_description=meta['meta_description'], meta_keywords=','.join(meta['keywords']),
                      style=meta['style'], thumbnail=thumb, slug=slug)
        if ex:
            backups['article-%s.json' % slug] = json.dumps(q(
                "SELECT JSON_OBJECT('title',title,'content',content,'summary',summary,'meta_title',meta_title,"
                "'meta_description',meta_description,'meta_keywords',meta_keywords,'style',style,'thumbnail',thumbnail,"
                "'status',status) FROM article WHERE slug=%s" % sqlstr(slug)), ensure_ascii=False)
            sets = ', '.join('%s=%s' % (k, hexs(v)) for k, v in fields.items())
            sql.append("UPDATE article SET %s, status='normal', modified=NOW() WHERE slug=%s;" % (sets, sqlstr(slug)))
            plan.append('更新  文章：%s（/article/%s）' % (meta['title'], slug))
        else:
            cols = list(fields) + ['edit_mode', 'user_id', 'order_number', 'status', 'comment_status', 'comment_count',
                                   'view_count', 'with_allow_search', 'site_id', 'created', 'modified']
            vals = [hexs(fields[k]) for k in fields] + ["'html'", '1', '0', "'normal'", '1', '0', '0', '1', '0', 'NOW()', 'NOW()']
            sql.append('INSERT INTO article (%s) VALUES (%s);' % (', '.join(cols), ', '.join(vals)))
            plan.append('新建  文章：%s（/article/%s）' % (meta['title'], slug))
        for c in meta['categories']:
            sql.append('INSERT IGNORE INTO article_category_mapping (article_id, category_id) SELECT id, %d FROM article WHERE slug=%s;'
                       % (int(c), sqlstr(slug)))
    for c in sorted(cats):
        sql.append("UPDATE article_category SET count=(SELECT COUNT(*) FROM article_category_mapping m JOIN article a "
                   "ON a.id=m.article_id AND a.status='normal' WHERE m.category_id=%d) WHERE id=%d;" % (int(c), int(c)))
    sql.append('COMMIT;')

    print('\n'.join(plan) or '（没有要做的）')
    if conflicts:
        print('\n以下内容和清单对不上，整批放弃，数据库没有任何改动：')
        print('\n'.join('  - ' + c for c in conflicts))
        sys.exit(2)
    if dry or len(sql) <= 2 and not covers:
        print('\n（试运行，没有写库）' if dry else '\n没有需要写入的内容。')
        return

    os.makedirs(bdir, exist_ok=True)
    for name, text in backups.items():
        open(os.path.join(bdir, name), 'w', encoding='utf-8').write(text)
    open(os.path.join(bdir, 'applied.sql.txt'), 'w', encoding='utf-8').write('\n'.join(s[:300] for s in sql))
    for src, dst in covers:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        shutil.chown(dst, 'www', 'www')
        os.chmod(dst, 0o644)
    sqlfile = os.path.join(bdir, 'run.sql')
    open(sqlfile, 'w', encoding='utf-8').write('\n'.join(sql) + '\n')
    r = cc_db.run(['mysql', '--batch', '--raw', '--skip-column-names'], stdin=open(sqlfile, 'rb').read())
    os.remove(sqlfile)
    if r.returncode:
        print('写库失败（事务已回滚）：' + r.stderr.decode('utf-8', 'replace'))
        sys.exit(1)
    print('\n已写入数据库。改动前的内容备份在：' + bdir)
    if not norestart:
        print('重启新站刷新缓存……')
        rr = subprocess.run([RESTART])
        if rr.returncode:
            print('！！新站重启后没有恢复，请立即检查')
            sys.exit(1)


if __name__ == '__main__':
    main()
