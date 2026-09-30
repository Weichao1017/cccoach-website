#!/bin/bash
# 把官网服务器切换到仓库里的某个版本。上线新版本、回退旧版本都用它。
# 用法：/root/cccoach-website/scripts/switch-version.sh <版本>
#   例：switch-version.sh v3      回到 v3
#       switch-version.sh v0      全部撤掉，回到最初原样
#       switch-version.sh main    回到最新版
# 管的东西：nginx 附加规则、旧站存档页、robots.txt/llms.txt、新站模板文件。
# 切换前自动备份线上文件；nginx 自检不通过、或新站重启后打不开，都会自动恢复。
set -euo pipefail

REF="${1:?用法：switch-version.sh <版本，如 v3 或 main>}"
REPO=${CCW_REPO:-/root/cccoach-website}
V=${CCW_VHOST:-/www/server/panel/vhost/nginx}
MAP=$V/0.cccoach_legacy_map.conf
SRV=$V/extension/www.cccoach.cn/legacy-redirect.conf
NG=${CCW_NGINX:-/www/server/nginx/sbin/nginx}
L=${CCW_LEGACY:-/www/wwwroot/cccoach-legacy}
SEO=${CCW_SEO:-/www/wwwroot/cccoach-seo}
TPL=${CCW_TPL:-/www/wwwroot/jpress/webapp/templates/4269b344/cccoach}
RESTART=${CCW_RESTART:-$REPO/scripts/restart-jpress.sh}
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

# 1) 备份现在线上的配置
mkdir -p "$BK"
[ -f "$MAP" ] && cp -a "$MAP" "$BK/map.conf"
[ -f "$SRV" ] && cp -a "$SRV" "$BK/server.conf"

# 2) 取出该版本的文件
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git archive "$REF" | tar x -C "$TMP"

# 3) 换 nginx 配置（该版本没有的文件就撤掉）
if [ -f "$TMP/nginx/0.cccoach_legacy_map.conf" ]; then cp "$TMP/nginx/0.cccoach_legacy_map.conf" "$MAP"; else rm -f "$MAP"; fi
if [ -f "$TMP/nginx/legacy-redirect.conf" ]; then cp "$TMP/nginx/legacy-redirect.conf" "$SRV"; else rm -f "$SRV"; fi

# 4) 换目录：存档页、SEO 静态文件（该版本没有就把线上的挪走）
swap_dir() {  # $1=仓库里的目录  $2=线上目录  $3=备份名
  if [ -d "$1" ]; then
    rm -rf "$2.new"; mkdir -p "$2.new"
    cp -a "$1/." "$2.new/"
    chown -R www:www "$2.new"
    find "$2.new" -type d -exec chmod 755 {} +
    find "$2.new" -type f -exec chmod 644 {} +
    if [ -d "$2" ]; then mv "$2" "$BK/$3"; fi
    mv "$2.new" "$2"; echo "$3" >> "$BK/.moved"
  elif [ -d "$2" ]; then
    mv "$2" "$BK/$3"; echo "$3" >> "$BK/.moved"
  fi
}
restore_dir() {  # $1=线上目录  $2=备份名
  if grep -qx "$2" "$BK/.moved" 2>/dev/null; then
    rm -rf "$1"; if [ -d "$BK/$2" ]; then mv "$BK/$2" "$1"; fi
  fi
}
if [ -d "$TMP/legacy-archive/pages/__legacy" ]; then mkdir -p "$TMP/_pages"; mv "$TMP/legacy-archive/pages/__legacy" "$TMP/_pages/"; fi
swap_dir "$TMP/_pages" "$L" pages
swap_dir "$TMP/site-seo" "$SEO" seo

# 5) nginx 自检，通过才生效；不通过全部恢复
if $NG -t >/dev/null 2>&1; then
  $NG -s reload
  sleep 1   # 等新配置接手，再报告
  echo "nginx 已生效"
else
  echo "nginx 自检没通过，已恢复原样。报错："
  $NG -t 2>&1 | tail -3
  if [ -f "$BK/map.conf" ]; then cp -a "$BK/map.conf" "$MAP"; else rm -f "$MAP"; fi
  if [ -f "$BK/server.conf" ]; then cp -a "$BK/server.conf" "$SRV"; else rm -f "$SRV"; fi
  restore_dir "$L" pages
  restore_dir "$SEO" seo
  $NG -t >/dev/null 2>&1 && $NG -s reload
  exit 1
fi

# 6) 新站模板：该版本带 jpress-template/ 就用它；不带就用原版（标签 template-original）
TPL_SRC=""
if [ -d "$TMP/jpress-template" ]; then
  TPL_SRC="$TMP/jpress-template"
elif git rev-parse -q --verify "template-original^{commit}" >/dev/null; then
  mkdir -p "$TMP/_tplorig"
  git archive template-original jpress-template | tar x -C "$TMP/_tplorig"
  TPL_SRC="$TMP/_tplorig/jpress-template"
fi
CHANGED=()
if [ -n "$TPL_SRC" ] && [ -d "$TPL_SRC" ] && [ -d "$TPL" ]; then
  while IFS= read -r f; do
    if ! cmp -s "$TPL_SRC/$f" "$TPL/$f"; then
      mkdir -p "$BK/template/$(dirname "$f")"
      [ -f "$TPL/$f" ] && cp -a "$TPL/$f" "$BK/template/$f"
      cp "$TPL_SRC/$f" "$TPL/$f"; chown www:www "$TPL/$f"; chmod 644 "$TPL/$f"
      CHANGED+=("$f")
    fi
  done < <(cd "$TPL_SRC" && find . -type f | sed 's#^\./##')
fi
if [ ${#CHANGED[@]} -gt 0 ]; then
  echo "新站模板有 ${#CHANGED[@]} 个文件变化：${CHANGED[*]}"
  echo "重启新站让模板生效（约半分钟）……"
  if "$RESTART"; then
    echo "新站已按新模板运行"
  else
    echo "新站重启后没能正常打开，恢复原模板并再次重启……"
    for f in "${CHANGED[@]}"; do
      if [ -f "$BK/template/$f" ]; then cp -a "$BK/template/$f" "$TPL/$f"; fi
    done
    "$RESTART" || echo "！！新站仍未恢复，需要人工处理"
    exit 1
  fi
fi

echo "已生效：$REF"
echo "切换前的线上文件备份在：$BK"
