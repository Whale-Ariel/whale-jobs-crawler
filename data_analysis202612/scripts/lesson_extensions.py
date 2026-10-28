"""四课增强内容：保留课堂主线，增加可独立运行的比较实验与课后题。"""


def extend_lesson(name, cells, md, code):
    """按章节锚点插入内容；不存在锚点即报错，避免升级时把内容插错位置。"""
    def before(heading, additions):
        index = next(i for i, cell in enumerate(cells)
                     if cell['cell_type'] == 'markdown' and heading in cell['source'])
        cells[index:index] = additions

    if name.startswith('01_'):
        before('## 2. 建立一致', [
            md(r'''
## 1A. 【主线】从业务问题到分析字段：先写一条可计算的问题

“招聘市场怎么样”无法直接计算。把它改写为：
**在这份固定采集样本中，各公司社招职位的城市覆盖有何不同？**

| 部分 | 本课约定 | 常见错误 |
|---|---|---|
| 对象 | 固定快照中的职位条目 | 把职位条目当作招聘人数 |
| 范围 | 明确公司、招聘类型、采集快照 | 忽略历史保留或渠道缺失 |
| 维度 | source、recruitment_type、cities | 用同名但不同口径的字段混比 |
| 指标 | 职位数、覆盖率、字段缺失率 | 先画图，再临时寻找解释 |
| 输出 | 底稿、图表、证据和限制 | 只展示一张没有分母的百分比图 |

先练Python必要知识：`str/int/float/bool/list/dict/None`；变量是对象的名字，
`=`是赋值、`==`是比较。`.get()`在键缺失时返回备用值；`[]`取不存在的键会抛错。
'''),
            code('''
# 这是一条教学示例，不是新增的真实职位；用它观察类型和安全取值。
sample_job = {'title': '数据分析师', 'cities': ['北京', '上海'], 'salary': None}
for field, value in sample_job.items():
    print(field, '→', repr(value), '→', type(value).__name__)

# get只处理“键不存在”；salary键存在且为None时，不会自动得到备用数字。
print('安全读取未知字段：', sample_job.get('unknown', '未提供'))
assert sample_job.get('salary', 0) is None

# 用清晰的中间变量构建布尔掩码，便于解释每一步，而非写一长串嵌套表达式。
is_analysis = demo['title'].str.contains('分析', na=False)
has_known_years = demo['years'].notna()
display(demo.loc[is_analysis & has_known_years, ['title', 'years']])

# Series条件用&/|/~逐元素组合，每个比较加括号；不要使用Python标量and/or。
mask = (demo['years'] >= 2) & (demo['city'] == '北京')
assert mask.sum() == 2
display(demo.loc[mask])
'''),
            md(r'''
## 1B. 【主线】行索引、位置和类型转换

`loc`根据行标签选择，`iloc`根据第几行选择。筛选后旧索引不会自动重排，
这正是合并表格时发生错位的常见原因。`pd.to_numeric(errors='coerce')`把不合法数值留作缺失，
不能把“面议”转成0后计算平均薪资。

**先预测再运行**：索引改成101/205/309后，第一行的标签和位置分别是什么？
'''),
            code('''
# 复制演示表，不改动之前单元的demo；loc与iloc可以指向相同的行，但含义不同。
indexed_demo = demo.copy()
indexed_demo.index = [101, 205, 309]
display(indexed_demo.loc[[101], ['title', 'city']])
display(indexed_demo.iloc[[0], [0, 1]])
assert indexed_demo.loc[101, 'title'] == indexed_demo.iloc[0]['title']

# 示例工资仅用于展示脏值转换；它们不是本项目的真实薪资统计。
raw_numbers = pd.Series(['10000', '面议', None, '20000'])
numeric_values = pd.to_numeric(raw_numbers, errors='coerce')
display(pd.DataFrame({'原始值': raw_numbers, '转换后': numeric_values}))
print('忽略缺失的均值：', numeric_values.mean())
print('错误补0后的均值：', numeric_values.fillna(0).mean())
assert numeric_values.isna().sum() == 2
'''),
        ])
        before('## 3. 展开 payload', [
            md(r'''
## 2A. 【主线】SQL与Pandas对照：同一问题，两种表达

SQL先在数据库执行筛选与聚合，适合少读数据；Pandas适合进入内存后的灵活转换。
`WHERE`对应布尔筛选、`GROUP BY`对应`groupby`、`ORDER BY`对应`sort_values`。
SQL参数使用占位符`?`传入，不把用户输入拼接成SQL。

本节只比较**队列source层面的条数**，与payload字段清洗无关。
'''),
            code('''
# 数据库侧计算公司条数：无需先把每条payload展开。
with sqlite3.connect(snapshot.as_uri() + '?mode=ro', uri=True) as conn:
    sql_counts = pd.read_sql_query(
        'SELECT source, COUNT(*) AS n FROM pending_jobs GROUP BY source ORDER BY source', conn)
    sql_sample = pd.read_sql_query(
        'SELECT seq, source, portal, job_id FROM pending_jobs WHERE source = ? ORDER BY seq LIMIT ?',
        conn, params=('tencent', 3))

# 内存侧回答同一问题。两边先统一行顺序与索引，避免“值相同、索引不同”的假失败。
pandas_counts = raw.groupby('source').size().rename('n').reset_index().sort_values('source').reset_index(drop=True)
pd.testing.assert_frame_equal(sql_counts, pandas_counts)
display(sql_counts)
display(sql_sample)
print('SQL与Pandas公司计数完全一致')
'''),
            md(r'''
## 2B. 【主线】观察一条JSON：字符串 → 字典 → 顶层表格

JSON中的`null/true/false`对应Python的`None/True/False`。
对象通常展开为列，数组通常保留为列表，直到决定统计单位时才展开为行。
下一单元的批量处理正是把这里的一条扩展到全部职位。
'''),
            code('''
# 一次只查看第一条的结构；不把数百KB原文全部打印到屏幕。
one_text = raw.iloc[0]['payload']
one_object = json.loads(one_text)
print('解析前：', type(one_text).__name__, '；解析后：', type(one_object).__name__)
one_fields = pd.DataFrame([
    {'字段': key, 'Python类型': type(value).__name__, '值预览': repr(value)[:100]}
    for key, value in one_object.items()
])
display(one_fields.head(15))

# 对比两种展开深度：嵌套字段越深，列越多；列数增加并不意味着分析价值一定增加。
top_level = pd.json_normalize([one_object], max_level=0)
deep_level = pd.json_normalize([one_object])
display(pd.DataFrame({'方案': ['只展开顶层', '递归展开对象'],
                      '行数': [len(top_level), len(deep_level)],
                      '列数': [top_level.shape[1], deep_level.shape[1]]}))
assert len(top_level) == len(deep_level) == 1
'''),
        ])
        before('## 5. 数据质量画像', [
            md(r'''
## 4A. 【拓展】一对多关联为什么会把职位数“变多”？

一个职位可以关联多个组织。把组织关系直接并入明细后，表格可能变长，
却没有产生新职位。`merge(validate=...)`用来检查关联基数：
`one_to_one`是一对一，`one_to_many`是一对多，`many_to_many`可能造成笛卡尔膨胀。

如果只需要“组织关系条数”，先聚合关系表再关联，才能保持一行一职位。
'''),
            code('''
with sqlite3.connect(snapshot.as_uri() + '?mode=ro', uri=True) as conn:
    organizations = pd.read_sql_query('SELECT * FROM job_organizations', conn)

# 关联键采用同一空值约定；只修正演示副本，不改数据库。
for column in KEY:
    organizations[column] = organizations[column].fillna('').astype(str)
left_jobs = jobs[KEY + ['job_key']].copy()
expanded_join = left_jobs.merge(organizations, on=KEY, how='left', validate='one_to_many')

# 先把关系表聚合为唯一职位键，再关联，得到可分析的单行特征。
organization_counts = organizations.groupby(KEY, dropna=False).size().rename('organization_count').reset_index()
safe_join = left_jobs.merge(organization_counts, on=KEY, how='left', validate='one_to_one')
safe_join['organization_count'] = safe_join['organization_count'].fillna(0).astype(int)
display(pd.DataFrame({'指标': ['原职位行数', '直接关联后的行数', '直接关联后的不同职位数', '聚合后关联行数'],
                      '数值': [len(left_jobs), len(expanded_join), expanded_join.job_key.nunique(), len(safe_join)]}))
assert expanded_join.job_key.nunique() == len(jobs)
assert len(safe_join) == len(jobs)
csv_export(safe_join[['job_key', 'organization_count']], '01_organization_join_demo')
'''),
            md(r'''
## 4B. 【主线练习】故意放入脏数据，验证你是否理解清洗

以下是人工构造的测试数据，不混入真实职位。请先指出：重复、无法解析、类型错误、
缺失分别位于哪里，再运行参考检查。不要只凭真实数据本次“恰好没错”就认为代码可靠。
'''),
            code('''
# 两行共享同一演示ID；还有坏JSON、合法但不是对象的JSON、空payload。
dirty_demo = pd.DataFrame({'id': ['A', 'A', 'B', 'C', 'D'],
                           'payload': ['{"title":"分析师"}', '{"title":null}', '{broken', '[]', None]})
def inspect_demo_json(value):
    try:
        obj = json.loads(value)
        if not isinstance(obj, dict):
            return 'JSON合法但不是职位对象'
        return '标题缺失' if not obj.get('title') else '可用'
    except (ValueError, TypeError):
        return '无法解析或缺失'

dirty_demo['问题'] = dirty_demo['payload'].map(inspect_demo_json)
dirty_demo['重复ID'] = dirty_demo.duplicated('id', keep=False)
display(dirty_demo)
assert dirty_demo['重复ID'].sum() == 2
assert dirty_demo['问题'].eq('无法解析或缺失').sum() == 2
assert dirty_demo['问题'].eq('JSON合法但不是职位对象').sum() == 1
'''),
        ])

    elif name.startswith('02_'):
        before('## 6. 从图表', [
            md(r'''
## 5A. 【主线】结构集中度与累计贡献：不要预设“二八规律”成立

将公司按条数排序，累计占比回答“前几家公司覆盖了多少样本”。
HHI是各公司样本占比平方之和，越大代表来源越集中；这里衡量**数据来源结构**，不是市场垄断程度。
“前20%公司贡献80%职位”必须计算，不能看到头部较大就套用。
'''),
            code('''
concentration = company_counts.copy().reset_index(drop=True)
concentration['rank'] = np.arange(1, len(concentration) + 1)
concentration['cumulative_share'] = concentration['share'].cumsum()
companies_to_80 = int(concentration.loc[concentration.cumulative_share.ge(.8), 'rank'].iloc[0])
hhi = float((concentration['share'] ** 2).sum())
head_n = max(1, int(np.ceil(len(concentration) * .2)))
head_share = float(concentration.head(head_n)['share'].sum())
print(f'覆盖80%样本需要前{companies_to_80}家公司；前20%公司向上取整为{head_n}家，贡献{head_share:.1%}；HHI={hhi:.3f}')

# 用两个子图避免双Y轴让条数和比例难以分辨；条形图横轴从0开始。
fig, axes = plt.subplots(1, 2, figsize=(11, 4))
axes[0].bar(concentration['rank'], concentration['jobs'], color='#377eb8')
axes[0].set(title='公司排名与职位数', xlabel='公司排名', ylabel='职位数（条）')
axes[1].plot(concentration['rank'], concentration['cumulative_share'], 'o-', color='#e6550d')
axes[1].axhline(.8, color='gray', linestyle='--', label='80%参考线')
axes[1].set(title='累计样本贡献', xlabel='累计公司数', ylabel='累计职位占比', ylim=(0, 1.05))
axes[1].yaxis.set_major_formatter(PercentFormatter(1))
axes[1].legend()
save_figure(fig, '02_concentration', '按公司样本条数排序；累计贡献与HHI只描述采集样本来源集中度。')
csv_export(concentration, '02_concentration')
'''),
            md(r'''
## 5B. 【主线】多城市的第二种口径：覆盖数与分摊数

假设某职位同时支持北京、上海：覆盖口径为两城各1条；平均分摊口径为两城各0.5条。
前者问“有多少职位允许在此地工作”，后者是**人为设定的折算方案**，不能解释为实际人员分配。
无城市候选的职位单独保留，这样可检查分摊质量是否守恒。

**练习**：如果一个职位支持50个城市，它在覆盖图与分摊图中的总贡献分别是多少？
'''),
            code('''
# 将每条城市关联补上该职位的城市数；关联基数必须是多对一。
weighted_links = city_jobs.merge(jobs[['job_key', 'city_count']], on='job_key', validate='many_to_one')
weighted_links['fractional_weight'] = 1 / weighted_links['city_count']
fractional = weighted_links.groupby('city', as_index=False).agg(fractional_jobs=('fractional_weight', 'sum'))
city_methods = city_counts.merge(fractional, on='city', validate='one_to_one')
missing_city_jobs = int(jobs['city_count'].eq(0).sum())
assert np.allclose(weighted_links.groupby('job_key')['fractional_weight'].sum(), 1)
assert np.isclose(fractional.fractional_jobs.sum() + missing_city_jobs, N)

# 两个系列都表示条目贡献，但一个计覆盖、一个计平均分摊，必须明确图例。
top_city_methods = city_methods.head(10).set_index('city')[['jobs', 'fractional_jobs']]
top_city_methods.columns = ['覆盖职位数', '平均分摊折算数']
fig, ax = plt.subplots(figsize=(10, 5))
top_city_methods.plot.barh(ax=ax, color=['#377eb8', '#ff7f00'])
ax.invert_yaxis()
ax.set(title='相同岗位数据，两种城市计数口径', xlabel='职位条目贡献（条/折算条）', ylabel='城市候选')
save_figure(fig, '02_city_counting_methods', '平均分摊假设每职位在各候选城市等权；不是实际招聘人数或办公人数。')
display(city_methods.head(10).round(2))
csv_export(city_methods, '02_city_counting_methods')
'''),
            md(r'''
## 5C. 【拓展】比较前统一构成：招聘类型标准化

公司A与B的北京覆盖率可能不同，是因为岗位地点不同，也可能因为社招/校招比例不同。
这里仅比较社招和校招两类，要求每家公司每类至少30条，再把各公司内两类覆盖率按同一组权重加权。

公式：**标准化北京覆盖率 = 社招北京覆盖率×统一社招权重 + 校招北京覆盖率×统一校招权重**。
统一权重来自入选公司在这两类中的合并构成。没有这类样本的公司不填0，也不外推。
这是描述性构成调整，不是随机试验，无法消除岗位级别、业务线等其他混杂。
'''),
            code('''
comparison_jobs = jobs.loc[jobs['recruitment_type'].isin(['society', 'campus'])].copy()
comparison_jobs['covers_beijing'] = comparison_jobs['cities'].map(lambda xs: '北京' in xs)
stratum_counts = pd.crosstab(comparison_jobs.company_name, comparison_jobs.recruitment_type)
qualified = stratum_counts.reindex(columns=['society', 'campus'], fill_value=0).ge(30).all(axis=1)
qualified_names = qualified.index[qualified]
comparison_jobs = comparison_jobs.loc[comparison_jobs.company_name.isin(qualified_names)]
assert len(qualified_names) >= 2, '可比公司过少，应调整研究范围，不能硬填缺失层'

# 同一组权重给每家公司使用，消除这一项招聘类型构成差异。
common_weights = comparison_jobs.recruitment_type.value_counts(normalize=True).reindex(['society', 'campus'])
within_rates = comparison_jobs.groupby(['company_name', 'recruitment_type']).covers_beijing.mean().unstack()
standardized = within_rates.mul(common_weights, axis=1).sum(axis=1)
adjustment = pd.DataFrame({'raw_rate': comparison_jobs.groupby('company_name').covers_beijing.mean(),
                           'standardized_rate': standardized,
                           'n': comparison_jobs.groupby('company_name').size()})
adjustment['change_pp'] = (adjustment.standardized_rate - adjustment.raw_rate) * 100
display(common_weights.rename('统一权重'))
display(adjustment.sort_values('change_pp', ascending=False).round(3))
assert np.isclose(common_weights.sum(), 1)
assert adjustment[['raw_rate', 'standardized_rate']].stack().between(0, 1).all()
fig, ax = plt.subplots(figsize=(10, 5))
adjustment[['raw_rate', 'standardized_rate']].rename(columns={
    'raw_rate': '各公司原构成', 'standardized_rate': '统一社招/校招构成'}).plot.barh(ax=ax)
ax.xaxis.set_major_formatter(PercentFormatter(1))
ax.set(title='招聘类型构成调整前后的北京覆盖率', xlabel='职位覆盖率', ylabel='两类样本均≥30的公司')
save_figure(fig, '02_standardized_beijing', '仅限社招/校招且各层n≥30；统一权重来自入选样本，不是因果效应。')
csv_export(adjustment.reset_index(), '02_standardized_beijing')
write_json(REPORTS / 'structure_extension_metrics.json', {
    'companies_to_80pct': companies_to_80, 'top_20pct_company_n': head_n,
    'top_20pct_company_share': head_share, 'source_hhi': hhi,
    'fractional_city_total': float(fractional.fractional_jobs.sum()), 'no_city_jobs': missing_city_jobs,
    'standardization_companies': len(qualified_names), 'standardization_weights': common_weights.to_dict(),
})
'''),
            md(r'''
## 5D. 【练习与参考】下钻，而不是追加一张排行榜

任务：只看北京可工作的社招职位，比较其公司结构与全量样本公司结构。
答案应同时包括子集条数、子集内占比、相对全量的百分点差，避免拿两个分母不同的数量直接相减。
'''),
            code('''
# 列表包含检查仍在一行一职位的主表上做，避免explode后反复统计。
drill_mask = jobs['recruitment_type'].eq('society') & jobs['cities'].map(lambda xs: '北京' in xs)
drill_jobs = jobs.loc[drill_mask]
drill_counts = drill_jobs.groupby('company_name').size().rename('subset_jobs')
drill = company_counts.set_index('company_name')[['jobs', 'share']].join(drill_counts).fillna({'subset_jobs': 0})
drill['subset_share'] = drill['subset_jobs'] / len(drill_jobs)
drill['share_change_pp'] = (drill['subset_share'] - drill['share']) * 100
assert np.isclose(drill.subset_share.sum(), 1)
print('北京可工作的社招子集：', len(drill_jobs), '条')
display(drill.sort_values('subset_jobs', ascending=False).round(3))
csv_export(drill.reset_index(), '02_beijing_society_drilldown')
'''),
        ])

    elif name.startswith('03_'):
        before('## 1. 词典规则', [
            md(r'''
## 0A. 【主线】文本分析的四个层次

1. **清洗**：去HTML和空白，保留职责/要求边界，不随意删除业务句子。
2. **特征抽取**：词典命中、经验、学历、文本长度，把文字变成列。
3. **语境识别**：区分“熟悉SQL”“SQL加分”“不要求SQL”，同一关键词含义不同。
4. **探索表征**：分词、词频、TF-IDF，用于寻找可解释的相似性。

正则入门：`|`表示或，`(...)`分组，`\s*`允许空白，`re.I`忽略大小写。
`(?<![a-z0-9_])`检查前方不是英文标识符，避免把CPython算成Python。
中文紧邻英文时，不能直接照搬英文`\b`词边界规则。

本课新列是规则特征，并非真实能力标签，也不把“沟通”等词出现次数作为个人评价。
'''),
        ])
        before('## 4. 用 TF-IDF', [
            md(r'''
## 3A. 【主线】宽表变长表：一条职位有多个技能

宽表适合机器学习：每个技能一列。长表适合统计：每条命中是一行“职位—技能”关系。
使用`melt`把技能列转成长表，再筛命中值1。长表行数是技能提及关系数，不是职位数。
顺便生成标题规则提示类别，用于对比技能侧重点；它不是官网统一职业分类。
'''),
            code('''
# 保留所有命中提示与第一个提示；规则优先级公开，避免重叠类别被悄悄覆盖。
role_rules = [
    ('商业/经营分析', r'商业分析|经营分析|business intelligence'),
    ('数据挖掘', r'数据挖掘'),
    ('数据科学', r'数据科学|data scientist'),
    ('数据分析', r'数据分析|data analyst'),
]
def title_role_hints(title):
    return [label for label, pattern in role_rules if re.search(pattern, title, re.I)]

role_lists = jobs.title_clean.map(title_role_hints)
jobs['role_hints_json'] = role_lists.map(lambda xs: json.dumps(xs, ensure_ascii=False))
jobs['role_hint_primary'] = role_lists.map(lambda xs: xs[0] if xs else '其他/未识别')
# 官网campus入口可能包含实习；保留标题提示来对照，而不是强行覆盖原始招聘类型。
jobs['title_internship_hint'] = jobs.title_clean.str.contains(
    r'实习|(?<![a-z])intern(?:ship)?(?![a-z])', case=False, regex=True, na=False)
jobs['internship_hint_outside_intern_type'] = (jobs.title_internship_hint &
    ~jobs.recruitment_type.isin(['internship', 'regular_intern', 'research_intern']))
display(pd.crosstab(jobs.recruitment_type, jobs.title_internship_hint).rename(columns={False: '无实习标题提示', True: '有实习标题提示'}))
csv_export(pd.crosstab(jobs.recruitment_type, jobs.title_internship_hint).reset_index(), '03_internship_title_vs_type')

# 限定数据相关候选生成长表，控制教学时的屏幕与内存规模。
focus = jobs.loc[jobs.focus_candidate].copy()
skill_long = focus.melt(id_vars=['job_key', 'company_name', 'recruitment_type', 'role_hint_primary'],
                         value_vars=skill_cols, var_name='skill', value_name='mentioned')
skill_long = skill_long.loc[skill_long.mentioned.eq(1)].copy()
skill_long['skill'] = skill_long['skill'].str.removeprefix('skill_')
assert len(skill_long) == int(focus['skill_count'].sum())
assert not skill_long.duplicated(['job_key', 'skill']).any()
display(skill_long.head(10))
csv_export(skill_long, '03_focus_skill_long')

# 图只显示样本量足够的提示类别；未识别不强行推断归属。
role_n = focus.groupby('role_hint_primary').size()
role_profile = focus.groupby('role_hint_primary')[['skill_' + s for s in chosen_skills]].mean()
role_profile = role_profile.loc[role_n.ge(30)]
role_profile.columns = chosen_skills
fig, ax = plt.subplots(figsize=(11, 4))
role_profile.index = [f'{label} (n={role_n[label]})' for label in role_profile.index]
sns.heatmap(role_profile, annot=True, fmt='.0%', vmin=0, vmax=1, cmap='Blues', ax=ax)
ax.set(title='标题规则提示类别的技能提及侧重点', xlabel='技能', ylabel='标题提示类别')
save_figure(fig, '03_role_hint_skills', '规则提示不是官方分类；取首个命中作为主提示，仅展示n≥30类别。')
csv_export(focus.groupby('role_hint_primary')[skill_cols].mean().join(role_n.rename('n')).reset_index(), '03_role_hint_skills')
'''),
            md(r'''
## 3B. 【拓展】共现多不等于关联强：条件概率、Jaccard与Lift

设A为提及Python，B为提及SQL：

| 指标 | 公式 | 回答的问题 |
|---|---|---|
| 共现数 | 同时提及A、B的职位数 | 数量有多少？ |
| P(B\|A) | AB共现数 / A提及数 | 提及A时，有多大比例也提及B？ |
| Jaccard | AB共现数 / A或B提及数 | 两组职位的重叠程度？ |
| Lift | P(AB) / [P(A)P(B)] | 比独立假设下预期共现多多少？ |

Lift>1不代表因果、技能互补或统计显著。稀有词的Lift可能很高，必须同时查看支持数。
这里只展示共同提及≥20条且两技能各自≥30条的组合，完整底稿保留所有技能对。
'''),
            code('''
from itertools import combinations
pair_rows = []
for a, b in combinations(SKILLS, 2):
    a_mask, b_mask = focus['skill_' + a].eq(1), focus['skill_' + b].eq(1)
    n_a, n_b = int(a_mask.sum()), int(b_mask.sum())
    n_ab, n_union = int((a_mask & b_mask).sum()), int((a_mask | b_mask).sum())
    pair_rows.append({'a': a, 'b': b, 'n_a': n_a, 'n_b': n_b, 'n_ab': n_ab,
                      'p_b_given_a': n_ab / n_a if n_a else np.nan,
                      'p_a_given_b': n_ab / n_b if n_b else np.nan,
                      'jaccard': n_ab / n_union if n_union else np.nan,
                      'lift': n_ab * len(focus) / (n_a * n_b) if n_a and n_b else np.nan})
skill_pairs = pd.DataFrame(pair_rows)
supported_pairs = skill_pairs.loc[(skill_pairs.n_ab >= 20) & (skill_pairs.n_a >= 30) & (skill_pairs.n_b >= 30)]
supported_pairs = supported_pairs.sort_values('lift', ascending=False)
display(supported_pairs.head(10).round(3))
assert skill_pairs.jaccard.dropna().between(0, 1).all()
assert skill_pairs.p_b_given_a.dropna().between(0, 1).all()
assert (skill_pairs.n_ab <= skill_pairs[['n_a', 'n_b']].min(axis=1)).all()

top_pairs = supported_pairs.head(10).iloc[::-1]
fig, ax = plt.subplots(figsize=(10, 5))
ax.barh(top_pairs.a + ' × ' + top_pairs.b, top_pairs.lift, color='#756bb1')
ax.axvline(1, color='gray', linestyle='--')
ax.set(title='有最低支持数的技能组合Lift', xlabel='Lift（相对独立预期的倍数）', ylabel='技能组合')
save_figure(fig, '03_skill_lift', f'仅数据相关候选n={len(focus)}；共同命中≥20且各自≥30；相关不等于因果。')
csv_export(skill_pairs, '03_skill_pairs')
'''),
            md(r'''
## 3C. 【主线】新增语境列：明确要求、加分、否定和仅提及

“SQL加分”与“必须掌握SQL”不能使用同一个名称解释。下面用短语片段识别**语境提示**，
保存证据并保留“仅提及/多种语境”。这是可检查的规则，不是可靠的法律或招聘语义解析器。
同一句可能列出多个技能，修饰范围可能不清；因此输出叫“提示”，不要称为硬性要求标签。
'''),
            code('''
def requirement_context(text, skill):
    # 先按句号、分号、逗号分片；保留顿号，避免打断“熟练SQL、Python”的并列修饰。
    hits = []
    for sentence in re.split(r'[。；;，,\\n]+', text):
        for match in re.finditer(SKILLS[skill], sentence, re.I):
            before_hit = sentence[max(0, match.start()-16):match.start()]
            after_hit = sentence[match.end():match.end()+16]
            context = before_hit + match.group() + after_hit
            if re.search(r'不要求|无需|不必', before_hit):
                label = '否定提示'
            elif re.search(r'优先|加分', context):
                label = '加分提示'
            elif re.search(r'必须|熟练|精通|掌握|熟悉', before_hit):
                label = '明确要求提示'
            else:
                label = '仅提及'
            hits.append((label, context))
    if not hits:
        return '未提及', ''
    labels = sorted({label for label, _ in hits})
    return (labels[0] if len(labels) == 1 else '多种语境'), ' | '.join(context for _, context in hits)[:250]

# 先验证语义不同的最小例子，再对真实数据运行；这些断言不等于总体准确率评估。
assert requirement_context('不要求SQL经验', 'SQL')[0] == '否定提示'
assert requirement_context('有SQL能力加分', 'SQL')[0] == '加分提示'
assert requirement_context('熟练掌握SQL', 'SQL')[0] == '明确要求提示'
assert requirement_context('负责日报制作', 'SQL')[0] == '未提及'

for skill in ['Python', 'SQL', 'Excel']:
    extracted = jobs['requirement_clean'].map(lambda text: requirement_context(text, skill))
    jobs['req_context_' + skill] = extracted.map(lambda pair: pair[0])
    jobs['req_evidence_' + skill] = extracted.map(lambda pair: pair[1])

context_table = pd.crosstab(jobs.recruitment_type, jobs.req_context_SQL)
display(context_table)
display(jobs.loc[jobs.req_context_SQL.eq('加分提示'), ['job_key', 'title_clean', 'req_evidence_SQL']].head(6))
csv_export(context_table.reset_index(), '03_sql_context_by_type')
csv_export(jobs[['job_key', 'title_clean', 'req_context_SQL', 'req_evidence_SQL']].sample(30, random_state=SEED), '03_context_review_sample')
'''),
        ])
        before('## 5. 人工抽查', [
            md(r'''
## 4A. 【主线】词频和TF-IDF差在哪？用3条文本手算一次

词频只看出现次数；TF-IDF降低语料中常见词的权重。下面关闭归一化，观察原始权重。
scikit-learn默认平滑公式为`idf = log((1+文档数)/(1+含该词文档数)) + 1`。
默认TF-IDF还会做L2归一化，所以大语料中的得分不能直接当词频。

**思考**：如果所有职位都出现SQL，它的IDF会降到0吗？（此公式下为1。）
'''),
            code('''
from sklearn.feature_extraction.text import CountVectorizer
toy_documents = ['python sql 数据分析', 'sql excel 业务分析', 'python 机器学习 模型']
# 教学示例已用空格分词，使用默认词项规则即可；不把它当作真实中文分词方案。
toy_counts = CountVectorizer()
toy_count_matrix = toy_counts.fit_transform(toy_documents)
toy_tfidf = TfidfVectorizer(norm=None, smooth_idf=True)
toy_tfidf_matrix = toy_tfidf.fit_transform(toy_documents)
toy_terms = toy_tfidf.get_feature_names_out()
display(pd.DataFrame(toy_count_matrix.toarray(), columns=toy_counts.get_feature_names_out()).rename_axis('示例文档'))
display(pd.DataFrame(toy_tfidf_matrix.toarray(), columns=toy_terms).round(3).rename_axis('示例文档'))
doc_frequency = np.asarray((toy_tfidf_matrix > 0).sum(axis=0)).ravel()
manual_idf = np.log((1 + len(toy_documents)) / (1 + doc_frequency)) + 1
assert np.allclose(manual_idf, toy_tfidf.idf_)
display(pd.DataFrame({'term': toy_terms, 'document_frequency': doc_frequency, 'idf': toy_tfidf.idf_}).round(3))
'''),
            md(r'''
## 4B. 【拓展】特征覆盖率：提取了更多列，哪些列真的能使用？

分别查看原结构化学历、文本学历、文本经验的覆盖率。两种来源都应保留，
不能把文本提取结果无条件覆盖官网字段。覆盖率高也不等于准确率高。
'''),
            code('''
feature_coverage = jobs.groupby('company_name').agg(
    n=('job_key', 'size'),
    structured_degree_rate=('required_degree', lambda s: s.fillna('').astype(str).str.strip().ne('').mean()),
    text_degree_rate=('degree_text', lambda s: s.ne('未抽取').mean()),
    text_experience_rate=('experience_years_min', lambda s: s.notna().mean()),
    explicit_sql_hint_rate=('req_context_SQL', lambda s: s.eq('明确要求提示').mean()),
)
display(feature_coverage.round(3))
csv_export(feature_coverage.reset_index(), '03_feature_coverage')
write_json(REPORTS / 'text_extension_metrics.json', {
    'focus_jobs': len(focus), 'long_skill_relations': len(skill_long),
    'skill_pairs': len(skill_pairs), 'supported_pairs': len(supported_pairs),
    'top_supported_pair': supported_pairs.iloc[0].to_dict(),
    'sql_context_counts': jobs.req_context_SQL.value_counts().to_dict(),
    'new_columns': ['role_hints_json', 'role_hint_primary', 'title_internship_hint', 'internship_hint_outside_intern_type'] + [prefix + skill for skill in ['Python', 'SQL', 'Excel']
                     for prefix in ['req_context_', 'req_evidence_']],
})
'''),
        ])

    elif name.startswith('04_'):
        before('## 1. 先看一个失败', [
            md(r'''
## 0A. 【主线】先用二维例子理解“分配—更新”，再进入文本矩阵

KMeans反复执行：选中心 → 把每点分到最近中心 → 用群内均值更新中心。
它优化群内平方距离，不理解职位含义。特征的尺度、相似度定义和样本范围都会影响结果。
下面6条记录是人工构造的二维教学示例，不是模型对真实岗位的结论。
'''),
            code('''
toy_points = np.array([[0, 1], [1, 0], [1, 1], [7, 8], [8, 7], [8, 8]], dtype=float)
initial_centers = np.array([[0, 0], [8, 8]], dtype=float)
# 广播得到6×2×2差值：6个点、2个中心、2个坐标；沿坐标轴求平方和。
squared_distances = ((toy_points[:, None, :] - initial_centers[None, :, :]) ** 2).sum(axis=2)
toy_labels = squared_distances.argmin(axis=1)
updated_centers = np.vstack([toy_points[toy_labels == group].mean(axis=0) for group in range(2)])
display(pd.DataFrame({'x': toy_points[:, 0], 'y': toy_points[:, 1], '分配群': toy_labels}))
print('更新前中心：', initial_centers.tolist())
print('更新后中心：', updated_centers.round(3).tolist())
assert np.bincount(toy_labels).tolist() == [3, 3]
assert np.allclose(updated_centers[0], [2/3, 2/3])
'''),
        ])
        before('## 5. 形成报告', [
            md(r'''
## 4A. 【拓展】换一种特征，是否还得到同样的群？

用8个0/1技能特征再做一次相同K的聚类，与文本聚类比较ARI。
若结果不同，不代表某一方一定错误：词级模型读到了业务与职责，技能模型只看词典技能。
这种比较检验**结论对表征的敏感性**，不等同于随机种子稳定性，也没有分类准确率。
'''),
            code('''
skill_features = focus[['skill_' + skill for skill in selected_skills]].astype(float)
with threadpool_limits(limits=1):
    skill_model = KMeans(n_clusters=best_k, n_init=10, random_state=SEED).fit(skill_features)
representation_ari = adjusted_rand_score(focus['cluster'], skill_model.labels_)
print('文本分群 vs 词典技能分群的ARI：', round(representation_ari, 3))

# 这里同一职位都保留：目的是对比职位标签，不混入两种去重策略的差异。
representation_table = pd.crosstab(focus['cluster'], skill_model.labels_)
representation_table.index.name = 'text_cluster'
representation_table.columns.name = 'skill_cluster'
display(representation_table)
display(skill_features.assign(skill_cluster=skill_model.labels_).groupby('skill_cluster').mean().round(3))
csv_export(representation_table.reset_index(), '04_representation_comparison')
assert representation_table.to_numpy().sum() == len(focus)
'''),
            md(r'''
## 4B. 【主线】追问：岗位群差异是否混入招聘类型差异？

先看各群社招、校招、实习的构成；再在同一招聘类型内比较技能。
不存在该类型的群显示缺失或不展示，不把“没有样本”填成“技能提及率0”。
即使分层后仍有差异，也只能说明描述性关联，不能认定某种岗位导致某项技能要求。
'''),
            code('''
cluster_type_counts = pd.crosstab(focus.cluster, focus.recruitment_type)
cluster_type_rates = cluster_type_counts.div(cluster_type_counts.sum(axis=1), axis=0)
fig, ax = plt.subplots(figsize=(10, 4))
cluster_type_rates.plot.barh(stacked=True, ax=ax, colormap='tab20')
from matplotlib.ticker import PercentFormatter
ax.xaxis.set_major_formatter(PercentFormatter(1))
ax.set(title='先看岗位群的招聘类型构成', xlabel='群内职位占比', ylabel='文本聚类编号', xlim=(0, 1))
ax.legend(title='统一招聘类型', bbox_to_anchor=(1.01, 1), loc='upper left')
save_figure(fig, '04_cluster_type_mix', '分母=每群全部合格候选；构成差异可能影响技能画像，不是因果证明。')
csv_export(cluster_type_counts.reset_index(), '04_cluster_type_counts')

stratified_skills = focus.groupby(['cluster', 'recruitment_type']).agg(
    n=('job_key', 'size'), machine_learning_rate=('skill_机器学习', 'mean'),
    ab_testing_rate=('skill_A/B测试', 'mean'), python_rate=('skill_Python', 'mean'))
display(stratified_skills.loc[stratified_skills.n.ge(20)].round(3))
csv_export(stratified_skills.reset_index(), '04_stratified_cluster_skills')
assert np.allclose(cluster_type_rates.sum(axis=1), 1)
'''),
            md(r'''
## 4C. 【主线】从“分群”到“检索”：按技能兴趣找到相近岗位

聚类是先给样本分群；检索是给定查询，按相似度排序。
输入“Python SQL 实验 因果推断 数据分析”，用训练时的同一词表与IDF转换，计算余弦相似度。
相似度只代表文本接近，不代表求职者适合度、匹配成功率或录用概率。

查询词全部不在词表时会得到零向量，此时必须提示改写查询，不能把任意岗位当推荐结果。
'''),
            code('''
from sklearn.metrics.pairwise import cosine_similarity
query_text = 'Python SQL 实验 因果推断 数据分析'
query_vector = vectorizer.transform([query_text])
assert query_vector.nnz > 0, '查询词未进入训练词表，请改写查询'
similarities = cosine_similarity(focus_X, query_vector).ravel()

# 排序前保留job_key；同一正文只展示一次，避免Top结果被复制模板占满。
retrieval = focus[['job_key', 'company_name', 'title_clean', 'city_name', 'job_url', 'text_normalized']].copy()
retrieval['cosine_similarity'] = similarities
retrieval = retrieval.sort_values(['cosine_similarity', 'job_key'], ascending=[False, True])
retrieval = retrieval.drop_duplicates('text_normalized').head(8)
display(retrieval.drop(columns=['text_normalized']).round(3))
assert retrieval.cosine_similarity.between(-1e-12, 1 + 1e-12).all()
assert retrieval.text_normalized.is_unique
csv_export(retrieval.drop(columns=['text_normalized']), '04_query_retrieval')
print('有效查询词：', [term for term in tokenize(query_text) if term in vectorizer.vocabulary_])
'''),
            md(r'''
## 4D. 【拓展】不只看代表样本，还要看边界样本

到最近群中心距离较大的文本可能是离群岗位；第一、第二近中心距离差很小，说明归属模糊。
距离差只是诊断量，不是概率，也不能用“99%置信度”描述。
阅读这些岗位可以发现混合职责、词典不足或样本范围过宽，而不是只展示最漂亮的中心样本。
'''),
            code('''
all_distances = model.transform(focus_X)
two_nearest = np.sort(all_distances, axis=1)[:, :2]
focus['cluster_distance'] = two_nearest[:, 0]
focus['cluster_distance_gap'] = two_nearest[:, 1] - two_nearest[:, 0]
boundary_jobs = focus.nsmallest(8, 'cluster_distance_gap')[
    ['job_key', 'company_name', 'title_clean', 'cluster', 'cluster_distance', 'cluster_distance_gap']]
display(boundary_jobs.round(4))
assert np.isfinite(all_distances).all()
assert focus.cluster_distance_gap.ge(-1e-12).all()
csv_export(boundary_jobs, '04_boundary_jobs')
write_json(REPORTS / 'model_extension_metrics.json', {
    'representation_ari': float(representation_ari), 'query': query_text,
    'retrieval_count': len(retrieval), 'top_retrieval_title': retrieval.iloc[0].title_clean,
    'top_retrieval_cosine': float(retrieval.iloc[0].cosine_similarity),
    'boundary_jobs': len(boundary_jobs), 'distance_is_probability': False,
})
'''),
            md(r'''
## 4E. 【课后拓展】入门监督学习：预测招聘入口编码，先战胜简单基线

聚类没有标签；分类需要标签。这里使用已有的`society/campus`编码做一个入门二分类实验，
研究问题是**文本能否帮助区分本样本的招聘入口编码**。这不是学历、岗位价值、是否能投递或个人录用预测。
campus中可能包含实习，标签来自数据入口编码，不能改称“正式工作与实习”的真值。

流程：固定子集 → 按相同处理后正文分组留出测试集 → 只在训练集fit TF-IDF → 逻辑回归 → 与多数类基线比较。
逻辑回归虽有“回归”二字，此处用于分类。测试集不能参与词表、IDF或模型参数学习。

| 指标 | 含义 |
|---|---|
| Accuracy | 全部预测中正确的比例；类别不平衡时可能误导 |
| Precision | 预测为某类的记录中，真实为该类的比例 |
| Recall | 真实为某类的记录中，被找回的比例 |
| Macro-F1 | 先对每类算F1，再等权平均，避免大类完全主导结果 |

同文分组只能防止完全相同正文跨集合，不能完全消除近似模板泄漏。结果只限同一快照留出集，
没有验证新公司或未来数据；不要把较高分数写成对招聘市场的普遍预测能力。
'''),
            code('''
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.dummy import DummyClassifier
from sklearn.metrics import accuracy_score, f1_score, classification_report, ConfusionMatrixDisplay

# 沿用中文为主的数据相关候选，仅保留两个已知入口编码，不重新标注其他类型。
classification_jobs = focus.loc[focus.recruitment_type.isin(['society', 'campus'])].copy().reset_index(drop=True)
splitter = GroupShuffleSplit(n_splits=1, test_size=.25, random_state=SEED)
train_indices, test_indices = next(splitter.split(
    classification_jobs, groups=classification_jobs.text_normalized))
train_jobs = classification_jobs.iloc[train_indices]
test_jobs = classification_jobs.iloc[test_indices]
assert set(train_jobs.text_normalized).isdisjoint(set(test_jobs.text_normalized))
assert train_jobs.recruitment_type.nunique() == test_jobs.recruitment_type.nunique() == 2
display(pd.DataFrame({'训练集': train_jobs.recruitment_type.value_counts(),
                      '测试集': test_jobs.recruitment_type.value_counts()}).fillna(0).astype(int))

# Pipeline保证向量化与模型按顺序只在训练集学习；不复用已在全候选fit过的聚类词表。
classification_model = Pipeline([
    ('tfidf', TfidfVectorizer(tokenizer=tokenize, token_pattern=None, min_df=3, max_df=.9,
                             max_features=3000, sublinear_tf=True)),
    ('classifier', LogisticRegression(max_iter=500, class_weight='balanced', random_state=SEED)),
])
with threadpool_limits(limits=1):
    classification_model.fit(train_jobs.text_normalized, train_jobs.recruitment_type)
predictions = classification_model.predict(test_jobs.text_normalized)

# 多数类基线完全不看文本；如果新模型没有超过它，就不应只展示Accuracy宣传效果。
dummy = DummyClassifier(strategy='most_frequent')
dummy.fit(np.zeros((len(train_jobs), 1)), train_jobs.recruitment_type)
dummy_predictions = dummy.predict(np.zeros((len(test_jobs), 1)))
classification_scores = pd.DataFrame([
    {'model': label, 'accuracy': accuracy_score(test_jobs.recruitment_type, predicted),
     'macro_f1': f1_score(test_jobs.recruitment_type, predicted, average='macro'), 'test_n': len(test_jobs)}
    for label, predicted in [('多数类基线', dummy_predictions), ('TF-IDF+逻辑回归', predictions)]
])
display(classification_scores.round(3))
class_report = pd.DataFrame(classification_report(
    test_jobs.recruitment_type, predictions, output_dict=True, zero_division=0)).T
display(class_report.round(3))
csv_export(classification_scores, '04_classifier_scores')
csv_export(class_report.reset_index(names='label'), '04_classifier_report')

fig, ax = plt.subplots(figsize=(6.5, 5))
ConfusionMatrixDisplay.from_predictions(test_jobs.recruitment_type, predictions,
                                       labels=['campus', 'society'], cmap='Blues', ax=ax, colorbar=False)
ax.set(title='同快照留出集：招聘入口编码分类', xlabel='预测编码', ylabel='真实入口编码')
save_figure(fig, '04_classifier_confusion', '按相同正文分组留出；未验证跨公司/跨时间；编码不等于正式/实习身份。')

# 保存测试行号、实际值与预测值，供人工检查误分类，不只保留一个汇总分数。
prediction_audit = test_jobs[['job_key', 'title_clean', 'company_name', 'recruitment_type']].copy()
prediction_audit['predicted_type'] = predictions
prediction_audit['correct'] = predictions == test_jobs.recruitment_type.to_numpy()
csv_export(prediction_audit, '04_classifier_test_predictions')
write_json(REPORTS / 'classifier_metrics.json', {
    'train_n': len(train_jobs), 'test_n': len(test_jobs), 'text_groups_overlap': 0,
    'target': '原始招聘入口编码campus/society', 'evaluation_scope': '同快照分组留出，非跨公司/未来验证',
    'scores': classification_scores.to_dict(orient='records'),
})
'''),
        ])
        before('## STAR 项目表述', [
            md(r'''
## 6. 【项目交付】把扩展实验写进一份有证据的报告

结论应写成：现象→比较→数值证据→解释边界→下一步核验。
下面自动汇总累计贡献、多城市分摊、技能关联、表征敏感性与检索实验，
给出更完整的项目报告。学生应替换为自己的独立问题和经核验发现。
'''),
            code('''
structure_more = json.loads((REPORTS / 'structure_extension_metrics.json').read_text())
text_more = json.loads((REPORTS / 'text_extension_metrics.json').read_text())
model_more = json.loads((REPORTS / 'model_extension_metrics.json').read_text())
classifier_more = json.loads((REPORTS / 'classifier_metrics.json').read_text())
pair = text_more['top_supported_pair']

# 从真实底稿取数，不把先前版本的结论复制成不可更新的常量。
extended_findings = [
    f"样本累计贡献：前{structure_more['companies_to_80pct']}家公司达到80%职位覆盖，来源HHI为{structure_more['source_hhi']:.3f}；这是样本集中度。",
    f"城市分摊守恒：折算贡献{structure_more['fractional_city_total']:,.0f}条，加无城市候选{structure_more['no_city_jobs']:,}条，回到全量职位数。",
    f"技能组合：{pair['a']}与{pair['b']}共同提及{int(pair['n_ab'])}条，Lift={pair['lift']:.2f}；有最低支持数，但不是因果或显著性结论。",
    f"表征敏感性：同一候选下文本与技能特征分群ARI={model_more['representation_ari']:.3f}；研究对象和特征定义会影响岗位群。",
    f"文本检索：查询“{model_more['query']}”返回{model_more['retrieval_count']}条去重结果，最高相似度{model_more['top_retrieval_cosine']:.3f}；不是录用概率。",
    f"监督学习拓展：同快照分组测试集{classifier_more['test_n']}条，逻辑回归Macro-F1={classifier_more['scores'][1]['macro_f1']:.3f}，多数类基线={classifier_more['scores'][0]['macro_f1']:.3f}；仅预测入口编码，未验证新公司或未来数据。",
]
extra_report = report + '\\n\\n## 扩展分析与比较实验\\n' + '\\n'.join('- ' + line for line in extended_findings)
extra_report += '\\n\\n## 独立练习后的STAR补充\\n'
extra_report += ('完成SQL与Pandas一致性核验、一对多关联检查、多城市双口径分析；'
                 '将职责和要求转为技能、语境与证据列，比较文本与技能表征下的聚类，建立可解释的相似岗位检索原型。'
                 '仅完成独立练习和人工核验后，才将这些步骤写成自己的项目贡献。')
(REPORTS / '项目分析报告_增强版.md').write_text(extra_report, encoding='utf-8')
display(Markdown('\\n\\n'.join('**发现**：' + line for line in extended_findings)))
'''),
            md(r'''
### 综合练习：从一个真实问题独立完成闭环

三选一：①数据分析与数据科学的技能差异；②限定社招后两家公司的岗位侧重点；③修改查询词构建技能学习方向的职位检索。

交付要求：
1. 写清样本筛选条件、行单位、分母与至少一项数据质量限制。
2. 自己新增1个特征或1条技能规则，并提供正反例与10条人工检查。
3. 提交2张自己的图、1张底稿、3条带数字结论；解释至少一种替代口径。
4. 模型方向须比较至少两个方案，阅读中心与边界岗位；检索方向须说明零向量和重复文本的处理。
5. 用STAR写150字项目概括，明确自己做了哪些分析，不把教师代码与原始采集算成独立开发。

**教师参考追问**：你改了分母吗？你排除了哪些样本？如果换一种特征，结论还成立吗？
如果不能成立，应报告适用边界，而不是删掉不支持结论的结果。
'''),
        ])
    return cells
