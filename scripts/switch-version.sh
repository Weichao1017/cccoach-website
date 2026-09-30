#!/bin/bash
# 把官网服务器上的“旧网址处理”切换到某个版本。上线新版本、回退旧版本都用它。
# 用法：/root/cccoach-website/scripts/switch-version.sh <版本>
#   例：switch-version.sh v3      回到 v3（只有 46 条跳转，没有存档页）
#       switch-version.sh v0      全部撤掉，回到最初原样
#       switch-version.sh main    回到最新版
# 切换前自动备份线上文件；nginx 自检不通过会自动恢复，不影响网站。
set -euo pipefail

REF="${1:?用法：switch-version.sh <版本，如 v3 或 main>}"
REPO=/root/cccoach-website
V=/www/server/panel/vhost/nginx
MAP=$V/0.cccoach_legacy_map.conf
SRV=$V/extension/www.cccoach.cn/legacy-redirect.conf
NG=/www/server/nginx/sbin/nginx
L=/www/wwwroot/cccoach-legacy
TS=$(date +%Y%m%d-%H%M%S)
BK=/root/cccoach_switch_backup/$TS-$$

cd "$REPO"
git fetch -q --tags origin 2>/dev/null || echo "（没连上 GitHub，用服务器上已有的版本）"
if ! git rev-parse -q --verify "$REF^{commit}" >/dev/null; then
  if git rev-parse -q --verify "origin/$REF^{commit}" >/dev/null; then
    REF="origin/$REF"
  else
    echo "找不到版本：$REF"; exit 1
  fi
fi
echo "切换到：$REF（$(git log -1 --format='%ad  %s' --date=format:'%Y-%m-%d %H:%M' "$REF")）"

# 1) 备份现在线上的配置和存档页
mkdir -p "$BK"
[ -f "$MAP" ] && cp -a "$MAP" "$BK/map.conf"
[ -f "$SRV" ] && cp -a "$SRV" "$BK/server.conf"

# 2) 取出该版本的文件
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git archive "$REF" | tar x -C "$TMP"

# 3) 换配置（该版本没有的文件就撤掉）
if [ -f "$TMP/nginx/0.cccoach_legacy_map.conf" ]; then cp "$TMP/nginx/0.cccoach_legacy_map.conf" "$MAP"; else rm -f "$MAP"; fi
if [ -f "$TMP/nginx/legacy-redirect.conf" ]; then cp "$TMP/nginx/legacy-redirect.conf" "$SRV"; else rm -f "$SRV"; fi

# 4) 换存档页（该版本没有存档页就把线上的挪走）
PAGES_MOVED=""
if [ -d "$TMP/legacy-archive/pages/__legacy" ]; then
  rm -rf "$L.new"; mkdir -p "$L.new"
  mv "$TMP/legacy-archive/pages/__legacy" "$L.new/"
  chown -R www:www "$L.new"
  find "$L.new" -type d -exec chmod 755 {} +
  find "$L.new" -type f -exec chmod 644 {} +
  if [ -d "$L" ]; then mv "$L" "$BK/pages"; fi
  mv "$L.new" "$L"; PAGES_MOVED=1
elif [ -d "$L" ]; then
  mv "$L" "$BK/pages"; PAGES_MOVED=1
fi

# 5) nginx 自检，通过才生效；不通过全部恢复
if $NG -t >/dev/null 2>&1; then
  $NG -s reload
  sleep 1   # 等新配置接手，再报告
  echo "已生效：$REF"
  echo "切换前的线上文件备份在：$BK"
else
  echo "nginx 自检没通过，已恢复原样。报错："
  $NG -t 2>&1 | tail -3
  if [ -f "$BK/map.conf" ]; then cp -a "$BK/map.conf" "$MAP"; else rm -f "$MAP"; fi
  if [ -f "$BK/server.conf" ]; then cp -a "$BK/server.conf" "$SRV"; else rm -f "$SRV"; fi
  if [ -n "$PAGES_MOVED" ]; then rm -rf "$L"; if [ -d "$BK/pages" ]; then mv "$BK/pages" "$L"; fi; fi
  $NG -t >/dev/null 2>&1 && $NG -s reload
  exit 1
fi
