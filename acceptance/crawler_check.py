# 验收：扮成各家 AI/搜索爬虫抓原始 HTML（不执行 JS），检查关键内容是否可读
import subprocess, re, json, html, sys
UAS = {
 'GPTBot': 'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.2; +https://openai.com/gptbot',
 'OAI-SearchBot': 'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot',
 'ClaudeBot': 'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)',
 'PerplexityBot': 'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)',
 'Bytespider(豆包)': 'Mozilla/5.0 (Linux; Android 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Mobile Safari/537.36 (compatible; Bytespider; spider-feedback@bytedance.com)',
 'Baiduspider': 'Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)',
 'Googlebot': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
}
B = 'https://www.cccoach.cn'
def get(path, ua):
    r = subprocess.run(['curl', '-s', '-m', '40', '-A', ua, '-w', '\n__CODE__%{http_code}', B + path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    body, _, code = r.stdout.decode('utf-8', 'ignore').rpartition('\n__CODE__')
    return code, body
def text_of(h):
    t = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', ' ', h)
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', t)))
def alts(h): return [html.unescape(a) for a in re.findall(r'<img\b[^>]*\balt="([^"]*)"', h)]
def lds(h):
    out = []
    for s in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
        try: out.append(json.loads(s))
        except Exception: out.append({'@type': 'JSON坏了'})
    return out
def links(h): return set(re.findall(r'<a\b[^>]*href="([^"#]+)"', h))

CHECKS = [
 # (页面, 检查名, 函数(html)->bool)
 ('/article/icf-coaching-career-block', '一级标题', lambda h: '跟 ICF 教练做教练对话，能帮我解决职业卡点吗？' in h and '<h1' in h),
 ('/article/icf-coaching-career-block', '开头直接回答', lambda h: '能帮上忙，但教练不替你做决定' in text_of(h)),
 ('/article/icf-coaching-career-block', 'ICF 认证表（ACC 100 小时/75 付费）', lambda h: '75 小时付费' in text_of(h) or '至少 75 小时付费' in text_of(h)),
 ('/article/icf-coaching-career-block', '品牌数字（学员中 ICF 认证）', lambda h: 'MCC 19 人' in text_of(h) and 'PCC 180+' in text_of(h)),
 ('/article/icf-coaching-career-block', 'Article 结构化数据', lambda h: any(d.get('@type') == 'Article' for d in lds(h))),
 ('/article/icf-coaching-career-block', '参考资料链接（ICF 官网）', lambda h: any('coachingfederation.org' in l for l in links(h))),
 ('/article/new-coach-first-100-hours', '一级标题', lambda h: '没有企业资源的新教练如何获客并积累小时数？' in h and '<h1' in h),
 ('/article/new-coach-first-100-hours', '关键事实（公益最多 25 小时）', lambda h: '25 小时' in text_of(h)),
 ('/article/new-coach-first-100-hours', 'Article 结构化数据', lambda h: any(d.get('@type') == 'Article' for d in lds(h))),
 ('/article/icf-cce-credits-renewal', '一级标题', lambda h: 'CCE学分是什么？中文教练如何高效获取ICF续证学分？' in h and '<h1' in h),
 ('/article/icf-cce-credits-renewal', '续证规则（40 个 / 至少 24 个 / 175 美元）', lambda h: all(x in text_of(h) for x in ['40 个', '至少 24 个', '175 美元'])),
 ('/article/icf-cce-credits-renewal', '课程学时表（28 / 26 / 18.5）', lambda h: all(x in text_of(h) for x in ['28', '26', '18.5'])),
 ('/article/icf-cce-credits-renewal', 'Article 结构化数据', lambda h: any(d.get('@type') == 'Article' for d in lds(h))),
 ('/', '首页数字（13年/13城/30万+/4000+）', lambda h: all(x in text_of(h) for x in ['13年', '13城', '30万+', '4000+'])),
 ('/', '首页 ICF 认证口径', lambda h: 'ACC 150+' in text_of(h) and 'MCC 19' in text_of(h)),
 ('/', 'Marcia 错字已改', lambda h: '全球排名前三的唯ICF' not in h and 'ICF国际教练联合会第五任主席' in text_of(h)),
 ('/', '认证路径图文字（画布备用内容）', lambda h: '创问教练认证路径图' in h and '超越大师级教练（MCC认证）' in h),
 ('/', '机构结构化数据含奖项', lambda h: any(d.get('@type') == 'EducationalOrganization' and len(d.get('award', [])) == 3 for d in lds(h))),
 ('/', '页面描述含品牌数字', lambda h: '成立于 2013 年' in (re.findall(r'name="description" content="([^"]*)"', h) or [''])[0]),
 ('/profile', '获奖图替代文字（最具传播力奖）', lambda h: any('最具传播力奖' in a for a in alts(h))),
 ('/profile', '获奖图替代文字（最佳组织奖）', lambda h: any('最佳组织奖' in a for a in alts(h))),
 ('/profile', '获奖图替代文字（中国教练服务机构5强）', lambda h: any('教练服务机构5强' in a for a in alts(h))),
 ('/profile', '没有 tu1/kong 这类占位替代文字', lambda h: not any(re.fullmatch(r'tu\d+|kong', a) for a in alts(h))),
 ('/brand-courses-team-acc', '证书图替代文字（Level 1、66 小时）', lambda h: any('Level 1' in a and '66' in a for a in alts(h))),
 ('/brand-courses-significant', '证书图替代文字（Level 2、135 小时）', lambda h: any('Level 2' in a and '135' in a for a in alts(h))),
 ('/brand-courses-team-acc', 'Course 结构化数据', lambda h: any(d.get('@type') == 'Course' for d in lds(h))),
 ('/article/62', '考试信息图替代文字（80 题 / 150 分钟）', lambda h: any(('80' in a and '150' in a) for a in alts(h))),
 ('/article/63', '满意度图替代文字（59% / 33%）', lambda h: any(('59' in a and '33' in a) for a in alts(h))),
 ('/article/70', 'MCQ/CSQ 对比表替代文字', lambda h: sum(1 for a in alts(h) if 'MCQ' in a or 'CSQ' in a) >= 3),
 ('/article/12', '导师头像替代文字是导师名', lambda h: '贺拥军 Jeff' in alts(h)),
 ('/article/category/news', '知识全景列表有新文章的真链接', lambda h: all(('/article/' + s) in links(h) for s in ['icf-coaching-career-block', 'new-coach-first-100-hours', 'icf-cce-credits-renewal'])),
 ('/article/category/encyclopedia', '教练百科列表有新文章的真链接', lambda h: all(('/article/' + s) in links(h) for s in ['icf-coaching-career-block', 'new-coach-first-100-hours', 'icf-cce-credits-renewal'])),
 ('/article/category/teaching', '师资团队列表有导师页真链接', lambda h: sum(1 for l in links(h) if re.match(r'^/article/\d+$', l)) >= 20),
 ('/robots.txt', 'robots 不拦任何 AI 爬虫、站点地图写完整网址', lambda h: 'Sitemap: https://www.cccoach.cn/sitemap.xml' in h and not re.search(r'(?i)user-agent:\s*(gptbot|claudebot|perplexitybot|bytespider)', h)),
 ('/llms.txt', 'llms.txt 含三篇新文章', lambda h: all(s in h for s in ['icf-coaching-career-block', 'new-coach-first-100-hours', 'icf-cce-credits-renewal'])),
 ('/sitemap.xml', '站点地图含三篇新文章、全是 https', lambda h: all(s in h for s in ['icf-coaching-career-block', 'new-coach-first-100-hours', 'icf-cce-credits-renewal']) and 'http://www.cccoach.cn' not in h),

 # v10（2026-09-30）：获奖文字按证书、导师简介、字节时间标签
 ('/profile', '获奖文字按证书原件（最具传播力奖、最佳组织奖）', lambda h: all(x in text_of(h) for x in ['最具传播力奖', '最佳组织奖', '中国教练服务机构5强']) and '特别贡献奖' not in text_of(h)),
 ('/article/13', '刘东导师页：页面描述是简介（含飞利浦）', lambda h: '飞利浦' in (re.findall(r'name="description" content="([^"]*)"', h) or [''])[0]),
 ('/article/13', '导师人物结构化数据含简介', lambda h: any(d.get('@type') == 'Person' and '飞利浦' in d.get('description', '') for d in lds(h))),
 ('/article/13', '字节时间标签（发布、更新）', lambda h: re.search(r'property="bytedance:published_time" content="\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+08:00"', h) is not None and 'bytedance:updated_time' in h),
 ('/brand-courses-dialogue', '单页字节更新时间标签', lambda h: re.search(r'property="bytedance:updated_time" content="\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+08:00"', h) is not None),
 ('/profile', '改过的单页更新时间是今天', lambda h: re.search(r'property="bytedance:updated_time" content="2026-09-30T', h) is not None),
 ('/article/icf-coaching-career-block', '文章字节时间标签', lambda h: 'bytedance:published_time' in h and 'bytedance:updated_time' in h),

 # v10 级别更正（客户 2026-09-30 确认：尤志欣 MCC；何朝霞、徐莉俐 PCC；王艺萍 MCC）
 ('/brand-courses-dialogue', '尤志欣卡片为 MCC', lambda h: re.search(r'Eric 尤志欣\s*</div>\s*<div class="fx-f-s team-tpp">\s*<div class="team-cc[^"]*">\s*MCC', h) is not None),
 ('/brand-courses-pure-pcc', '何朝霞、徐莉俐卡片为 PCC', lambda h: all(re.search(n + r'</p>.{0,400}?<strong>PCC</strong>', h, re.S) for n in ['何朝霞 Tess', '徐莉俐 Lili Xu'])),
 ('/brand-courses-coach-social-theater', '徐莉俐卡片为 PCC', lambda h: re.search(r'徐莉俐 Lili Xu</p>.{0,400}?<strong>PCC</strong>', h, re.S) is not None),
 ('/article/18', '尤志欣导师页：ICF MCC', lambda h: 'ICF认证大师级MCC教练' in text_of(h) and 'ICF PCC' not in text_of(h)),
 ('/article/30', '王艺萍导师页：ICF MCC', lambda h: 'ICF MCC' in text_of(h)),
 ('/article/21', '谢忠民导师页：华为等高管履历、1000+ 小时', lambda h: all(x in text_of(h) for x in ['华为', '1998', '1000+'])),

 # v11 站点地图时间
 ('/sitemap.xml', '站点地图修改时间标 +08:00、不含已跳转的 /37', lambda h: 'Z</lastmod>' not in h and '+08:00</lastmod>' in h and 'cccoach.cn/37<' not in h),

 # v12（2026-09-30）：问答第二版、ACC→PCC→MCC 路径、ICF 考官、进化教练 Level 2、品牌数字统一、公益教练
 ('/article/icf-coaching-career-block', '问答一：写明从 ACC、PCC 到 MCC 的完整路径，不再句句写“来源”', lambda h: '从 ACC、PCC 到 MCC' in text_of(h) and '（来源：' not in text_of(h)),
 ('/article/new-coach-first-100-hours', '问答二：纯净ACC直通车、完整认证路径', lambda h: '纯净ACC直通车' in text_of(h) and '从 ACC、PCC 到 MCC' in text_of(h)),
 ('/article/icf-cce-credits-renewal', '问答三：ICF 认证主考官、ICF 考官，没有“请顾问出示”', lambda h: 'ICF 认证主考官' in text_of(h) and 'ICF 考官' in text_of(h) and '请顾问出示' not in text_of(h)),
 ('/article/category/news', '三篇问答各有自己的封面', lambda h: all('/attachment/20260930/%s.jpg' % s in h for s in ['icf-coaching-career-block', 'new-coach-first-100-hours', 'icf-cce-credits-renewal'])),
 ('/brand-courses-team-pcc', '课程页写 ICF 考官，不再写创问考官', lambda h: 'ICF考官' in text_of(h) and '创问考官' not in text_of(h) and '创问认证考官' not in text_of(h)),
 ('/brand-courses-coach-supervisor', '督导班页写 ICF 考官（卡片和横幅替代文字）', lambda h: 'ICF考官' in text_of(h) and '创问考官' not in h),
 ('/brand-courses-team-acc', 'ACC 页：进化教练是 Level2，替代文字写 ICF 考官', lambda h: '创问进化教练为Level2' in text_of(h) and '进化教练Level1' not in text_of(h) and '创问考官' not in h),
 ('/', '首页：刘东卡片写 ICF考官、导航写明 ACC→PCC→MCC、描述写明完整认证路径', lambda h: 'ICF考官|高管教练' in text_of(h) and '从ACC、PCC到MCC的完整认证路径' in text_of(h) and '从 ACC、PCC 到 MCC 的完整认证路径' in (re.findall(r'name="description" content="([^"]*)"', h) or [''])[0]),
 ('/social_social', '社会责任页品牌数字统一', lambda h: all(x in text_of(h) for x in ['4000+名进化与纯净教练', '30万+人', 'MCC 19人']) and '20余万' not in text_of(h) and '130+名' not in text_of(h)),
 ('/brand-courses-team4c', '隋于军小时数 6000+', lambda h: '6000小时+' in text_of(h) and '5600小时+' not in text_of(h)),
 ('/article/14', '隋于军导师页小时数 6000+', lambda h: '6000小时+' in text_of(h) and '5000小时+' not in text_of(h)),
 ('/article/15', '何朝霞导师页品牌数字', lambda h: '4000+名' in text_of(h) and '13座城市' in text_of(h) and '3000多位' not in text_of(h)),
 ('/article/category/teaching', '师资团队有“公益教练”一组和 25 位公益教练的真链接', lambda h: '创问·公益教练' in text_of(h) and len(set(re.findall(r'href="(/article/coach-[a-z-]+)"', h))) >= 28),
 ('/article/coach-yanqin-xie', '新公益教练页：简介、ICF PCC、人物结构化数据、字节时间标签', lambda h: '简介' in text_of(h) and 'ICF PCC' in text_of(h) and any(d.get('@type') == 'Person' and d.get('description') for d in lds(h)) and 'bytedance:published_time' in h),
 ('/article/coach-lucia', '新公益督导页', lambda h: '简介' in text_of(h) and 'ICF PCC' in text_of(h)),
 ('/llms.txt', 'llms.txt：认证路径和进化教练 Level 2', lambda h: '进化教练是 Level 2' in h and '纯净ACC直通车' in h),
 ('/sitemap.xml', '站点地图含新教练页', lambda h: h.count('/article/coach-') >= 28),
]
pages = sorted({p for p, _, _ in CHECKS})
res = {}
fail = 0
print('== 各爬虫能否打开（状态码 / 字节数）')
for p in pages:
    row = []
    for name, ua in UAS.items():
        code, body = get(p, ua); res[(p, name)] = (code, body); row.append('%s:%s/%d' % (name.split('(')[0], code, len(body)))
    print(p, ' '.join(row))
print('\n== 内容检查（每项对 7 个爬虫都要通过）')
for p, name, fn in CHECKS:
    oks = [fn(res[(p, ua)][1]) and res[(p, ua)][0] == '200' for ua in UAS]
    ok = all(oks); fail += not ok
    print('%s  %-34s %s%s' % ('通过' if ok else '失败', p, name, '' if ok else '  ← ' + ','.join(u for u, o in zip(UAS, oks) if not o)))
print('\n共 %d 项，失败 %d 项' % (len(CHECKS), fail))
sys.exit(1 if fail else 0)
