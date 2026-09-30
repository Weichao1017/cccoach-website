#!/usr/bin/env python3
"""用新站（JPress）自己的数据库配置连接 MySQL。密码只从配置文件读出，写进一个仅 root 可读的临时文件，用完即删，不打印。

用法：
  cc_db.py json  "SELECT JSON_OBJECT(...) FROM ..."   # 每行输出一个 JSON（查询用 JSON_OBJECT 包起来最稳）
  cc_db.py sql   "UPDATE ..."                        # 执行一条语句
  cc_db.py file  改动.sql                             # 执行 SQL 文件
  cc_db.py dump  表名 [--where "条件"]                 # mysqldump 这张表（可加条件），输出到 stdout
"""
import os
import re
import subprocess
import sys
import tempfile

CONF = '/www/wwwroot/jpress/config/jboot.properties'


def _props():
    d = {}
    for line in open(CONF, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        d[k.strip()] = re.sub(r'\\(.)', r'\1', v.strip())  # 去掉 .properties 的转义
    return d


def _defaults_file():
    p = _props()
    m = re.match(r'jdbc:mysql://([^:/?]+)(?::(\d+))?/([^?]+)', p['jboot.datasource.url'])
    host, port, db = m.group(1), m.group(2) or '3306', m.group(3)

    def q(v):
        return '"' + v.replace('\\', '\\\\').replace('"', '\\"') + '"'
    fd, path = tempfile.mkstemp(prefix='ccdb-', dir='/dev/shm' if os.path.isdir('/dev/shm') else None)
    os.fchmod(fd, 0o600)
    os.write(fd, ('[client]\nuser=%s\npassword=%s\nhost=%s\nport=%s\ndefault-character-set=utf8mb4\n'
                  % (q(p['jboot.datasource.user']), q(p['jboot.datasource.password']), host, port)).encode('utf-8'))
    os.close(fd)
    return path, db


def run(args, stdin=None):
    path, db = _defaults_file()
    try:
        return subprocess.run(args[:1] + ['--defaults-extra-file=' + path] + args[1:] + [db],
                              input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finally:
        os.remove(path)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd in ('json', 'sql'):
        r = run(['mysql', '--batch', '--raw', '--skip-column-names', '-e', arg])
    elif cmd == 'file':
        r = run(['mysql', '--batch', '--raw', '--skip-column-names'], stdin=open(arg, 'rb').read())
    elif cmd == 'dump':
        extra = ['--where=' + sys.argv[4]] if len(sys.argv) > 4 and sys.argv[3] == '--where' else []
        path, db = _defaults_file()
        try:
            r = subprocess.run(['mysqldump', '--defaults-extra-file=' + path, '--skip-extended-insert',
                                '--no-create-info', '--complete-insert'] + extra + [db, arg],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        finally:
            os.remove(path)
    else:
        print(__doc__)
        sys.exit(1)
    sys.stdout.buffer.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr.decode('utf-8', 'replace'))
        sys.exit(r.returncode)


if __name__ == '__main__':
    main()
