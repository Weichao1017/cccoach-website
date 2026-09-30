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

## 改网站内容（文章、首页区块、图片替代文字、页面文字、导师页）

内容存在新站数据库里，也走仓库：

1. 在 `content/` 里改：文章放 `content/articles/<网址别名>/`（article.html、meta.json、cover.jpg）；首页区块写在 `content/homepage-blocks.json`；图片替代文字来源放 `content/sources/`；其他页面改动写在 `content/edits/*.json`，每条一种写法：
   - 页面里替换一段文字：`{"page": "/profile", "find": "原文", "replace": "新文", "note": "说明"}`
   - 整个字段换成新值：`{"page": "/article/13", "field": "meta_description", "set": "新值"}`，或内容取自文件：`"set_file": "edits/tutors/13.html"`
   - 改导师页标签：`{"article": 18, "tags_remove": ["ICF PCC"], "tags_add": ["ICF MCC"]}`
2. 生成变更清单：`python3 scripts/content-build.py content/changes/<日期-名字>.json`（对照数据库当前内容，写出精确的“原内容 → 新内容”；已经是新内容的自动跳过。只想看某几类改动时加 `--from edits,certs` 之类）。
3. 提交并推送到 GitHub。
4. 执行：`python3 scripts/content-apply.py content/changes/<清单>.json`（先核对，全部对上才在一个事务里写库，写前自动备份到 /root/cccoach_content_backup/，写完重启新站刷新缓存）。先加 `--dry-run` 看计划。
5. 回退：同一命令加 `--revert`（区块、文字、整段改写、标签都改回原样，本清单发布的文章改为草稿）。改过的页面会同时更新“修改时间”，页面头部的字节时间标签随之变化。

数据库连接用 `scripts/cc_db.py`：直接读新站配置里的账号，密码不打印、不落盘。

## 验收

`python3 acceptance/crawler_check.py`：扮成 7 种 AI/搜索爬虫抓原始 HTML，逐项检查内容能否读到。

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
| `scripts/` | 切换版本 / 回退脚本、安全重启新站脚本、内容变更工具 |
| `content/` | 网站内容改动（文章、首页区块、替代文字来源、变更清单） |
| `acceptance/` | 验收脚本和结果 |

## 重新生成存档页

旧站数据库导出在服务器 `/home/coach_backup.sql`。步骤：

1. 在服务器上运行 `extract_old_db_full.py`，得到 `old_content_full.json`（只读文章、单页、活动、栏目表；不含联系人、价格、报名字段）；
2. 在本地运行 `python3 gen_archive.py`，输出到 `build/__legacy/`；
3. 放进 `legacy-archive/pages/__legacy/`，提交，然后用 `switch-version.sh main` 上线。

## 不放进这个仓库的

数据库密码和配置文件；会员、订单、报名、访客记录；旧站 `excel`、`files` 文件夹（疑似报名名单）；旧站数据库导出原文件。

## 待办

- 新站内容每日快照（文章、单页、导航、首页区块），用于回退后台里的内容改动。需要技术先建一个只读数据库账号，写进服务器 `/root/.my.cnf`。
