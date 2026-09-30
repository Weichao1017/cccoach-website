# 创问官网 www.cccoach.cn：改动记录与回退

这个仓库记录对官网服务器做过的每一次改动，每个版本都能退回去。**官网每次上线都先提交到这里，再从这里部署。**现在管的是：

- 旧官网网址：能对上新站的 301 跳到新页面；对不上的用旧站原文在原网址恢复成存档页；旧图片、视频恢复；
- 搜索与 AI（GEO）：http 跳 https、站点地图修正、robots.txt、llms.txt、重复页处理；
- 新站模板：页面标题、描述、一级标题、结构化数据、页脚链接。

每一版改了什么，见 [CHANGELOG.md](CHANGELOG.md)。在 GitHub 上点某次提交，能看到改前改后的对比。

## 品牌部怎么回退

看 CHANGELOG 找到想回到的版本，告诉技术或 Claude“回到 vX”。

## 技术怎么回退（在服务器上执行）

```bash
/root/cccoach-website/scripts/switch-version.sh v3
```

- `v0` = 全部撤掉，回到最初原样；`main` = 回到最新版。
- 切换前会自动备份线上文件（`/root/cccoach_switch_backup/时间/`）。
- nginx 自检不通过会自动恢复，网站不受影响。
- 只动这几处：`/www/server/panel/vhost/nginx/0.cccoach_legacy_map.conf`、`/www/server/panel/vhost/nginx/extension/www.cccoach.cn/legacy-redirect.conf`、`/www/wwwroot/cccoach-legacy/`（存档页）、`/www/wwwroot/cccoach-seo/`（robots.txt、llms.txt）、新站模板目录 `/www/wwwroot/jpress/webapp/templates/4269b344/cccoach/` 里仓库跟踪的模板文件。
- 模板有变化时会自动重启新站（约 10–20 秒），首页恢复 200 才算成功；重启后打不开会自动换回原模板并再重启。
- 重启用 `scripts/restart-jpress.sh`，不要用新站目录里的 `jpress.sh stop`：它按路径杀进程，远程调用时会连调用者一起杀掉，导致新站起不来。

## 目录

| 目录 | 内容 |
|---|---|
| `nginx/` | 线上的两个 nginx 配置：旧网址跳转表 + 存档页映射，以及处理规则 |
| `nginx/reference/` | 网站主配置的副本，只作参考，回退脚本不会动它 |
| `legacy-archive/pages/` | 存档页（静态 HTML），线上放在 `/www/wwwroot/cccoach-legacy/` |
| `legacy-archive/generator/` | 生成存档页的脚本，以及 301 跳转清单 `deploy_rows.json` |
| `mapping/` | 旧网址 → 新网址对照表 |
| `site-seo/` | robots.txt、llms.txt，线上放在 `/www/wwwroot/cccoach-seo/` |
| `jpress-template/` | 新站模板文件（原版见标签 `template-original`） |
| `scripts/` | 切换版本 / 回退脚本、安全重启新站脚本 |

## 重新生成存档页

旧站数据库导出在服务器 `/home/coach_backup.sql`。步骤：

1. 在服务器上运行 `extract_old_db_full.py`，得到 `old_content_full.json`（只读文章、单页、活动、栏目表；不含联系人、价格、报名字段）；
2. 在本地运行 `python3 gen_archive.py`，输出到 `build/__legacy/`；
3. 放进 `legacy-archive/pages/__legacy/`，提交，然后用 `switch-version.sh main` 上线。

## 不放进这个仓库的

数据库密码和配置文件；会员、订单、报名、访客记录；旧站 `excel`、`files` 文件夹（疑似报名名单）；旧站数据库导出原文件。

## 待办

- 新站内容每日快照（文章、单页、导航、首页区块），用于回退后台里的内容改动。需要技术先建一个只读数据库账号，写进服务器 `/root/.my.cnf`。
