"""生成四节教学 Notebook。重新生成会清除执行输出；随后执行 run_course.py。"""
from pathlib import Path
import ast
import json
import textwrap
import uuid
from code_annotations import annotate_code
from lesson_extensions import extend_lesson

ROOT = Path(__file__).resolve().parents[1]


def md(source):
    return {'cell_type': 'markdown', 'id': uuid.uuid4().hex[:8], 'metadata': {},
            'source': textwrap.dedent(source).strip()}


def code(source):
    return {'cell_type': 'code', 'id': uuid.uuid4().hex[:8], 'metadata': {},
            'source': annotate_code(textwrap.dedent(source).strip()), 'execution_count': None, 'outputs': []}


BOOT = r'''
from pathlib import Path
import sys, json, re
import numpy as np
import pandas as pd
from IPython.display import display, Markdown

# 支持从项目根目录、课程目录或 notebooks 目录启动。
candidates = [Path.cwd(), *Path.cwd().parents]
ROOT = next((p for p in candidates if (p / 'course_utils.py').exists()), None)
if ROOT is None:
    ROOT = next((p / 'data_analysis202612' for p in candidates
                 if (p / 'data_analysis202612' / 'course_utils.py').exists()), None)
assert ROOT is not None, '请从项目根目录或课程目录启动 Jupyter'
sys.path.insert(0, str(ROOT))
from course_utils import *
pd.set_option('display.max_columns', 14)
pd.set_option('display.max_colwidth', 65)
pd.set_option('display.max_rows', 20)
print('课程目录：', ROOT)
print('Python：', sys.version.split()[0])
print('解释器：', sys.executable)
'''


def split_long_cell(cell, target_lines=32):
    """按完整的顶层Python语句拆单元，避免拆开循环、函数或多行字符串。"""
    if cell['cell_type'] != 'code':
        return [cell]
    source = cell['source']
    lines = source.splitlines()
    nodes = ast.parse(source).body
    cuts, chunk_start, previous_end = [0], 0, 0
    for node in nodes:
        statement_start = node.lineno - 1
        # 把语句前的解释注释带到新单元，而不是留在上一个单元末尾。
        while statement_start > previous_end and (
                not lines[statement_start-1].strip() or lines[statement_start-1].lstrip().startswith('#')):
            statement_start -= 1
        if node.end_lineno - chunk_start > target_lines and statement_start - chunk_start >= 12:
            cuts.append(statement_start)
            chunk_start = statement_start
        previous_end = node.end_lineno
    cuts.append(len(lines))
    parts = []
    for a, b in zip(cuts, cuts[1:]):
        chunk = '\n'.join(lines[a:b]).strip()
        if chunk:
            ast.parse(chunk)
            metadata = dict(cell['metadata'])
            if len(chunk.splitlines()) > 65 and 'report =' in chunk:
                metadata['jupyter'] = {'source_hidden': True}
            parts.append({**cell, 'id': uuid.uuid4().hex[:8], 'metadata': metadata, 'source': chunk})
    return parts


MATERIAL_STATS = {}


def save(name, cells):
    cells = extend_lesson(name, cells, md, code)
    cells.insert(1, md('''
> **增强版阅读方法**：先看本节问题，预测输出，再运行代码，最后解释数字。
> 关键代码已加中文注释，说明“为什么做、参数是什么、结果的行列单位是什么”。
> 标有【主线】的段落用于课堂；【拓展】用于教师演示或课后，不要求90分钟内完成所有扩展。
> 长代码按完整步骤拆成较短单元；每本仍需从上到下依次运行。
'''))
    cells = [part for cell in cells for part in split_long_cell(cell)]
    MATERIAL_STATS[name] = {
        'cells': len(cells), 'code_cells': sum(c['cell_type'] == 'code' for c in cells),
        'comment_lines': sum(line.lstrip().startswith('#') for c in cells if c['cell_type'] == 'code'
                             for line in c['source'].splitlines()),
        'code_source_lines': sum(len(c['source'].splitlines()) for c in cells if c['cell_type'] == 'code'),
    }
    notebook = {'cells': cells, 'metadata': {
        'kernelspec': {'display_name': '招聘数据分析课程', 'language': 'python', 'name': 'jobs-course'},
        'language_info': {'name': 'python', 'version': '3.10'},
    }, 'nbformat': 4, 'nbformat_minor': 5}
    path = ROOT / 'notebooks' / name
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding='utf-8')


save('01_数据分析基础与JSON结构化.ipynb', [
md('''
# 第 1 课｜从招聘数据库到可分析的数据集

**90 分钟：问题定义 15′ → Python/Pandas 25′ → SQLite/JSON 35′ → 质量检查 15′**

本课结束，你能解释“一行是什么”、读取 SQLite、拆开 JSON，并交付可追溯的职位明细表。

业务任务：描述这批官网职位样本的公司、地点与招聘类型结构，为技能分析做准备。
数据分析是“提出问题 → 定义指标 → 整理数据 → 比较与解释 → 支持决策”，不等于画图。

本项目采集工作已完成；你的任务是分析。职位条目不是招聘人数；历史保留、来源覆盖差异、
队列同步删除都会影响样本。我们分析的是固定快照中的待同步记录，不能称为当前全网职位总量。

**运行顺序**：四本 Notebook 按 01→04 执行，每本均从顶部运行。教师版已保留真实执行输出。
'''),
code(BOOT),
md('''
## 1. 必要的 Python：字典、列表、函数、DataFrame

字典像一条职位，列表像多条职位；函数把重复规则封装起来。
DataFrame 是有行列标签的表格，`loc` 筛选、`groupby` 分组、`agg` 聚合。
下面用小数据先练习，再处理真实数据。缺失值不是零。
'''),
code('''
examples = [
    {'title': '数据分析师', 'city': '北京', 'years': 2},
    {'title': '算法实习生', 'city': '上海', 'years': None},
    {'title': '商业分析师', 'city': '北京', 'years': 3},
]
def title_contains(job, keyword):
    return keyword in job['title']

print([x['title'] for x in examples if title_contains(x, '分析')])
demo = pd.DataFrame(examples)
display(demo)
display(demo.groupby('city', as_index=False).agg(岗位数=('title', 'size'), 已知年限均值=('years', 'mean')))
display(demo.loc[demo['years'].ge(2), ['title', 'city']])
'''),
md('''
**练习 1（3 分钟）**：统计示例中经验年限缺失的数量；把筛选条件改成“岗位名称包含分析”。
预测 `size` 与 `count` 在缺失值存在时会不会相同，再运行验证。
'''),
code('''
# 参考解答：课堂可先折叠本单元，学生在上方新增代码单元练习。
print('年限缺失数：', demo['years'].isna().sum())
display(demo.loc[demo['title'].str.contains('分析', na=False)])
display(demo.groupby('city')['years'].agg(['size', 'count']))
assert demo['years'].isna().sum() == 1
'''),
md('''
## 2. 建立一致、只读的原始快照

直接复制 `.db` 可能遗漏 WAL 中已提交的记录。这里用 SQLite backup API 读取原库，
生成课程快照，并记录 SHA-256、创建时间、表行数和完整性校验。已有快照不会自动覆盖。
原库不执行写入，后续课程只读取这份固定快照。复制过程由 `course_utils.py` 封装。
'''),
code('''
snapshot, manifest = snapshot_database()
display(pd.Series(manifest, name='数据接收台账'))
import sqlite3
with sqlite3.connect(snapshot.as_uri() + '?mode=ro', uri=True) as conn:
    schema = pd.read_sql_query("SELECT name, sql FROM sqlite_master WHERE type='table'", conn)
    raw = pd.read_sql_query('SELECT * FROM pending_jobs ORDER BY seq', conn)
display(schema)
print('快照职位数：', len(raw), '；原始列数：', len(raw.columns))
assert len(raw) == manifest['table_rows']['pending_jobs']
'''),
md('''
## 3. 展开 payload，并防止同名字段相互覆盖

`json.loads` 把 JSON 文本变为字典；`json_normalize(max_level=0)` 展开顶层字段，
保留数组/对象。若直接与队列表横向合并，`source`、`job_id` 会重名，所以先加 `payload.` 前缀。
坏 JSON 单独隔离，身份键不一致则停止处理。`portal` 是渠道标识，不强行等同于 `recruitment_type`。
'''),
code('''
records, valid_indices, rejected = [], [], []
for idx, value in raw['payload'].items():
    try:
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError('payload 不是对象')
        records.append(parsed)
        valid_indices.append(idx)
    except (ValueError, TypeError) as exc:
        rejected.append({'seq': int(raw.loc[idx, 'seq']), 'reason': str(exc)})

payload = pd.json_normalize(records, max_level=0)
payload.index = valid_indices
flat = raw.loc[valid_indices].drop(columns='payload').join(payload.add_prefix('payload.'))
identity_mismatches = {}
for col in ['source', 'job_id', 'batch_id', 'source_site']:
    a = flat[col].fillna('').astype(str)
    b = flat['payload.' + col].fillna('').astype(str)
    identity_mismatches[col] = int(a.ne(b).sum())
assert not any(identity_mismatches.values()), identity_mismatches
assert not flat.duplicated(KEY).any(), '完整职位身份键重复'

# 保留队列身份列；raw_data 原文仍在快照，不复制到轻量分析表。
business_cols = [c for c in payload.columns if c not in ['source', 'job_id', 'batch_id', 'source_site', 'raw_data']]
jobs = flat[list(raw.columns.drop('payload'))].copy()
for col in business_cols:
    jobs[col] = flat['payload.' + col]
jobs = jobs.reset_index(drop=True)
jobs['job_key'] = jobs['seq'].astype(str)  # 仅在本固定快照内使用的便捷行键
display(jobs[['job_key', 'source', 'portal', 'title', 'city_name', 'recruitment_type']].head())
print('payload 顶层字段数：', len(payload.columns), '；隔离记录数：', len(rejected))
'''),
md('''
## 4. 保留原文，新增清洗列

清洗不是把空值随意补齐。这里去掉 HTML、规范空白，对标题缺失做标记；
学历、薪资保留缺失，不推测。原始城市字段保留，清洗后的地点标签另存。

真实差异：字节城市列表含字典，百度可能一个元素含多个城市，讯飞使用“安徽省·合肥市”，
京东有省级地点，携程有英文城市。城市映射是可审计规则，不是完美地理编码。
'''),
code('''
jobs['company_name'] = jobs['source'].map(COMPANIES).fillna(jobs['source'])
for col in ['title', 'description', 'requirement']:
    jobs[col + '_clean'] = jobs[col].map(clean_text)
jobs['text_missing'] = jobs['description_clean'].eq('') & jobs['requirement_clean'].eq('')
jobs['title_missing'] = jobs['title_clean'].eq('')
jobs['locations'] = [normalize_locations(a, b) for a, b in zip(jobs['city_list'], jobs['city_name'])]
jobs['cities'] = jobs['locations'].map(lambda xs: [x for x in xs if location_level(x) == '城市候选'])
jobs['city_count'] = jobs['cities'].map(len)
jobs['publish_datetime'] = pd.to_datetime(jobs['publish_time'], errors='coerce', utc=True, format='mixed')

location_audit = jobs[['job_key', 'source', 'locations']].explode('locations').dropna(subset=['locations'])
location_audit['level'] = location_audit['locations'].map(location_level)
location_counts = location_audit.groupby(['locations', 'level'], as_index=False).agg(关联数=('job_key', 'nunique'))
display(location_counts.sort_values('关联数', ascending=False).head(20))
print('人工核验候选：')
display(location_counts.loc[location_counts['level'].ne('城市候选')].sort_values('关联数', ascending=False).head(20))
'''),
md('''
## 5. 数据质量画像与导出

分来源检查字段覆盖率，避免把“解析器没有提供学历”误解成“公司不看学历”。
主表保持一行一条职位；多城市分析下一课再展开。
Parquet 保存列表类型和空值，比把嵌套对象直接塞进 CSV 更适合课间传递。
'''),
code('''
quality = jobs.groupby('company_name').agg(
    岗位数=('job_key', 'size'), 标题缺失率=('title_missing', 'mean'),
    文本全缺失率=('text_missing', 'mean'), 有城市候选率=('city_count', lambda s: s.gt(0).mean()),
    学历字段有值率=('required_degree', lambda s: s.fillna('').astype(str).str.strip().ne('').mean()),
    发布日期可解析率=('publish_datetime', lambda s: s.notna().mean()),
)
display(quality.round(3))
cleaning_log = {
    'raw_rows': len(raw), 'clean_rows': len(jobs), 'rejected_json_rows': len(rejected),
    'duplicate_identity_rows': int(jobs.duplicated(KEY).sum()),
    'identity_mismatches': identity_mismatches,
    'title_missing_rows': int(jobs['title_missing'].sum()),
    'text_missing_rows': int(jobs['text_missing'].sum()),
    'no_city_candidate_rows': int(jobs['city_count'].eq(0).sum()),
    'missing_publish_time_rows': int(jobs['publish_time'].fillna('').astype(str).str.strip().eq('').sum()),
    'unparseable_nonempty_publish_time_rows': int((
        jobs['publish_time'].fillna('').astype(str).str.strip().ne('') & jobs['publish_datetime'].isna()).sum()),
    'unparsed_or_missing_publish_time_rows': int(jobs['publish_datetime'].isna().sum()),
    'location_associations_by_level': location_audit['level'].value_counts().to_dict(),
    'actions': ['隔离坏JSON', '验证复合身份键', '原文保留并新增清洗列', '城市别名映射与地点层级标记',
                '保留多城市', '薪资学历不填0', '复杂字段JSON序列化以稳定跨课传递'],
}
write_json(REPORTS / 'cleaning_log.json', cleaning_log)
write_json(REPORTS / 'rejected_json.json', rejected)
csv_export(quality.reset_index(), '01_source_quality')
csv_export(location_counts, '01_location_audit')

# 复杂列统一存 JSON 字符串，避免不同来源结构冲突；下课只解码所需列表。
export = jobs.copy()
for col in export.columns:
    if export[col].map(lambda x: isinstance(x, (list, dict))).any():
        export[col] = export[col].map(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (list, dict)) else None)
export.to_parquet(DATA / 'processed' / 'jobs_clean.parquet', index=False)
jobs[['job_key', 'source', 'title_clean', 'city_name', 'recruitment_type', 'job_url']].to_csv(
    DATA / 'processed' / 'jobs_preview.csv', index=False, encoding='utf-8-sig')
assert len(jobs) + len(rejected) == len(raw)
assert jobs['job_key'].is_unique
display(pd.Series(cleaning_log))
'''),
md('''
## 课堂练习与验收

1. 查看 `raw.iloc[0]['payload']` 的类型，再对比 `json.loads(...)` 的类型。
2. 为什么只用 `job_id` 去重不可靠？请给出两家公司可能使用同一 ID 的例子。
3. 找出城市数最多的 5 条职位，检查原始城市字段和清洗后列表。
4. 从质量表选择一个缺失率高的字段，解释为什么它不适合直接跨公司比较。

**参考解答思路**：原始 payload 是字符串、解析后是字典；职位身份包含来源、渠道、批次与站点；
多城市不能压成一个随意选择的城市；缺失可能来自接口或解析覆盖差异。

**验收**：原始行数=清洗行数+隔离行数，复合键唯一，原文仍可回溯，导出成功。
下一课读取 `data/processed/jobs_clean.parquet`。
'''),
code('''
display(jobs.sort_values('city_count', ascending=False)[['source', 'title_clean', 'city_name', 'cities']].head(5))
print('第1课完成：', DATA / 'processed' / 'jobs_clean.parquet')
'''),
])


save('02_招聘结构与可视化分析.ipynb', [
md('''
# 第 2 课｜招聘结构与可视化分析

**90 分钟：指标口径 15′ → 分组聚合 25′ → 图表实践 35′ → 结论表达 15′**

目标：用公司、招聘类型和城市三个维度回答样本结构问题；每张图附“数字证据＋边界”。
不做薪资排行：缺失覆盖率和币种口径尚不足。不开场就画时间趋势：当前快照不是历史存量序列。
'''), code(BOOT),
code('''
import matplotlib.pyplot as plt
import seaborn as sns
setup_plotting()
path = DATA / 'processed' / 'jobs_clean.parquet'
assert path.exists(), '请先运行第1课'
jobs = pd.read_parquet(path)
jobs['cities'] = jobs['cities'].map(json.loads)
N = len(jobs)
print(f'固定快照：{N:,} 条职位，{jobs.source.nunique()} 家公司')
'''),
md('''
## 1. 指标先于图表

| 指标 | 公式与分母 |
|---|---|
| 公司职位数 | 该来源不同 `job_key` 的数量 |
| 公司样本占比 | 公司职位数 / 全部职位数 |
| 公司内招聘类型占比 | 公司某类型职位数 / 该公司全部职位数 |
| 城市岗位覆盖数 | 包含该城市的不同职位数 |
| 城市覆盖率 | 城市岗位覆盖数 / 全部职位数 |

一条职位可覆盖北京和上海，因此城市覆盖数之和可能超过职位总数，城市覆盖率也不要求合计100%。
同一职位跨城市展开后，在同一个城市只计一次。省份、范围标签和待核验地点不进入城市图。
'''),
code('''
company_counts = (jobs.groupby(['source', 'company_name'], as_index=False)
                  .agg(jobs=('job_key', 'nunique')).sort_values('jobs', ascending=False))
company_counts['share'] = company_counts['jobs'] / N
display(company_counts)
fig, ax = plt.subplots(figsize=(9, 6))
data = company_counts.iloc[::-1]
ax.barh(data['company_name'], data['jobs'], color='#377eb8')
ax.set(title='各公司职位条目数量：样本覆盖并不均衡', xlabel='职位条目数（条）', ylabel='公司')
save_figure(fig, '02_company_counts', '每职位计一次；数量反映样本结构，不代表招聘人数或市场份额。')
csv_export(company_counts, '02_company_counts')
'''),
md('''
## 2. 公司内比较：数量和占比回答不同问题

使用 `recruitment_type` 的统一编码，不使用格式不一致的 `portal`。
这里把应届、科研实习等保留为独立类型，避免“校招一定等于全职”的混淆。
'''),
code('''
type_names = {'society': '社招', 'campus': '校招', 'graduate': '应届批次',
              'internship': '实习', 'regular_intern': '日常实习', 'research_intern': '科研实习', 'dispatch': '派遣'}
jobs['recruitment_group'] = jobs['recruitment_type'].map(type_names).fillna('未分类')
type_table = pd.crosstab(jobs['company_name'], jobs['recruitment_group'])
type_share = type_table.div(type_table.sum(axis=1), axis=0)
assert np.allclose(type_share.sum(axis=1), 1)
fig, ax = plt.subplots(figsize=(10, 6))
type_share.loc[company_counts['company_name'].iloc[::-1]].plot.barh(stacked=True, ax=ax, colormap='tab20')
ax.set(title='各公司内部招聘类型构成', xlabel='公司内职位占比', ylabel='公司', xlim=(0, 1))
from matplotlib.ticker import PercentFormatter
ax.xaxis.set_major_formatter(PercentFormatter(1))
ax.legend(title='统一招聘类型', bbox_to_anchor=(1.01, 1), loc='upper left')
save_figure(fig, '02_recruitment_mix', '分母=每家公司全部职位；比较样本类型构成，不推断实际招聘政策。')
csv_export(type_table.reset_index(), '02_type_counts')
csv_export(type_share.reset_index(), '02_type_share')
'''),
md('''
## 3. 多城市展开与 Top 城市

先 `explode`，再按“职位＋城市”去重。空列表展开产生空值，需要剔除。
保留“无城市候选”职位在总分母中，并单独报告覆盖情况。
'''),
code('''
city_jobs = (jobs[['job_key', 'source', 'company_name', 'cities']].explode('cities')
             .dropna(subset=['cities']).rename(columns={'cities': 'city'}))
city_jobs = city_jobs.drop_duplicates(['job_key', 'city'])
city_counts = city_jobs.groupby('city', as_index=False).agg(jobs=('job_key', 'nunique')).sort_values('jobs', ascending=False)
city_counts['coverage_rate'] = city_counts['jobs'] / N
top = city_counts.head(12).iloc[::-1]
fig, ax = plt.subplots(figsize=(9, 6))
ax.barh(top['city'], top['jobs'], color='#4daf4a')
ax.set(title='Top 12 城市的岗位覆盖数', xlabel='覆盖职位条目数（条）', ylabel='城市候选')
save_figure(fig, '02_city_coverage', '每职位在每城市最多计一次；多城市职位重复出现在不同城市中；未核验地点不计。')
csv_export(city_counts, '02_city_counts')
print('职位—城市关联总数：', len(city_jobs))
print('至少有一个城市候选的职位数：', city_jobs.job_key.nunique())
print('无城市候选的职位数：', N - city_jobs.job_key.nunique())
display(city_counts.head(12))
'''),
md('''
## 4. 公司×城市热力图：同时看两种结构

热力图用公司全部职位数作分母，问“该公司样本中多少职位覆盖这个城市”。
一行可超过100%，因为职位支持多城市。只展示 Top 10 城市，其余仍保留在底稿。
'''),
code('''
cross_counts = pd.crosstab(city_jobs['company_name'], city_jobs['city'])
denominators = jobs.groupby('company_name')['job_key'].nunique()
cross_rate = cross_counts.div(denominators, axis=0)
assert cross_rate.max().max() <= 1
fig, ax = plt.subplots(figsize=(11, 7))
view = cross_rate.reindex(index=company_counts.company_name, columns=city_counts.city.head(10), fill_value=0)
sns.heatmap(view, ax=ax, annot=True, fmt='.0%', cmap='Blues', vmin=0, vmax=1,
            cbar_kws={'label': '占该公司全部职位的比例'})
ax.set(title='不同公司的城市覆盖结构', xlabel='城市候选', ylabel='公司')
save_figure(fig, '02_company_city', '每单元格=该公司覆盖该城市的职位数/该公司全部职位数；不是地区市场占有率。')
csv_export(cross_rate.reset_index(), '02_company_city_rate')
'''),
md('''
## 5. 分析前先看数据质量；可选检查日期

覆盖率图解释“能不能比较”。学历字段缺失不等于无学历要求，正文里可能另有说明。
发布日期可解析也不代表适合做趋势：历史保留、采集范围与下架机制都可能导致偏差。
'''),
code('''
coverage = jobs.groupby('company_name').agg(
    学历有值率=('required_degree', lambda s: s.fillna('').astype(str).str.strip().ne('').mean()),
    薪资有值率=('min_salary', lambda s: s.notna().mean()),
    发布日期可解析率=('publish_datetime', lambda s: s.notna().mean()),
)
fig, ax = plt.subplots(figsize=(9, 6))
sns.heatmap(coverage.reindex(company_counts.company_name), annot=True, fmt='.0%', vmin=0, vmax=1,
            cmap='YlGnBu', ax=ax, cbar_kws={'label': '字段覆盖率'})
ax.set(title='字段覆盖率决定可比较范围', xlabel='质量指标', ylabel='公司')
save_figure(fig, '02_field_coverage', '覆盖率只衡量字段有值/日期可解析，不等于内容准确率。')
csv_export(coverage.reset_index(), '02_field_coverage')
assert company_counts.jobs.sum() == N
assert city_counts.jobs.sum() == len(city_jobs)
'''),
md('''
## 6. 从图表写出有依据的结论

下面的文字由实际底稿生成，不预先写死数值。每条结论都带范围与限制。
因果归因需要额外证据，本课只能描述关联和样本结构。
'''),
code('''
first = company_counts.iloc[0]
city_first = city_counts.iloc[0]
facts = {
    'jobs': N, 'companies': int(jobs.source.nunique()),
    'top_company': first.company_name, 'top_company_jobs': int(first.jobs), 'top_company_share': float(first.share),
    'top_city': city_first.city, 'top_city_jobs': int(city_first.jobs),
    'top_city_coverage': float(city_first.coverage_rate),
    'city_associations': len(city_jobs), 'jobs_with_city': int(city_jobs.job_key.nunique()),
}
write_json(REPORTS / 'structure_metrics.json', facts)
display(Markdown(f"""**现象**：样本中{first.company_name}职位最多，共 {first.jobs:,} 条，占 {first.share:.1%}。

**解读边界**：样本受到采集覆盖及历史保留影响，不能据此认定该公司实际招聘需求最大。

**现象**：{city_first.city}覆盖 {city_first.jobs:,} 条职位，占全部职位 {city_first.coverage_rate:.1%}。

**解读边界**：这是多城市岗位覆盖率，非互斥城市份额。"""))
'''),
md('''
## 练习（含参考方向）

1. 仅选择“社招”重做公司数量图，比较排序是否变化。（先过滤再聚合，分母也要改变。）
2. 为什么城市覆盖率不能直接用饼图？（类别不互斥。）
3. 选择一家小样本公司与一家大样本公司，分别比较数量和公司内占比。
4. 某公司学历覆盖率为0，能否说它不要求学历？（不能，下一课回到文本核验。）

**验收**：公司计数之和=职位数；公司内类型占比合计100%；城市底稿与展开关联数一致。
输出：5 张 PNG、对应 CSV 底稿、`structure_metrics.json`。
'''),
])


save('03_职位文本分析与技能特征.ipynb', [
md('''
# 第 3 课｜职位文本分析与技能特征

**90 分钟：文本处理 20′ → 技能词典与关键词 30′ → 特征分析 30′ → 抽查 10′**

目标：把职责与要求变成可分析特征。使用可解释技能词典，并用 TF-IDF 探索额外关键词。
“文本提及”不等于“必须掌握”；没有提及也不代表不需要。先分开职责/要求，再分析合并文本。
'''), code(BOOT),
code('''
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.feature_extraction.text import TfidfVectorizer
import jieba
setup_plotting()
jobs = pd.read_parquet(DATA / 'processed' / 'jobs_clean.parquet')
jobs['analysis_text'] = jobs['description_clean'] + ' ' + jobs['requirement_clean']
jobs['text_length'] = jobs['analysis_text'].str.strip().str.len()
jobs['has_requirement'] = jobs['requirement_clean'].str.len().gt(0)
display(jobs[['title_clean', 'description_clean', 'requirement_clean']].sample(4, random_state=SEED))
'''),
md('''
## 1. 词典规则：边界、别名与误报

SQL 包含 MySQL/PostgreSQL 等明确别名；Java 不匹配 JavaScript；英语词前后使用字母数字边界。
这些都是可修改的规则。`沟通协作` 是宽泛提及，不适合当作可量化能力评分。
中文短语和英文词边界不同：`熟悉Python开发` 仍应命中 Python。
'''),
code('''
display(pd.DataFrame({'技能': list(SKILLS), '匹配规则': list(SKILLS.values())}))
examples = ['熟悉JavaScript和MySQL', '掌握JAVA与Python开发', 'NoSQL经验', '有机器学习和跨部门沟通经验']
display(pd.DataFrame([{'文本': x, **skill_hits(x)} for x in examples]))
assert skill_hits('JavaScript')['Java'] == 0
assert skill_hits('熟悉JAVA开发')['Java'] == 1
assert skill_hits('NoSQL')['SQL'] == 0
assert skill_hits('MySQL')['SQL'] == 1
assert skill_hits('CPython')['Python'] == 0
assert clean_text('<p>Python &amp; SQL</p>') == 'Python & SQL'
'''),
code('''
requirements = pd.DataFrame(jobs['requirement_clean'].map(skill_hits).tolist(), index=jobs.index)
descriptions = pd.DataFrame(jobs['description_clean'].map(skill_hits).tolist(), index=jobs.index)
# 分别识别再取并集，避免两个字段拼接后产生原文并不存在的跨字段词组。
combined = requirements.combine(descriptions, np.maximum)
for skill in SKILLS:
    jobs['skill_' + skill] = combined[skill].astype('int8')
    jobs['req_' + skill] = requirements[skill].astype('int8')
    jobs['desc_' + skill] = descriptions[skill].astype('int8')
jobs['skill_count'] = combined.sum(axis=1)
jobs['experience_years_min'] = jobs['requirement_clean'].map(experience_min)
jobs['degree_text'] = jobs['requirement_clean'].map(degree_from_text)
assert experience_min('3-5年数据分析经验') == 3
assert np.isnan(experience_min('制定3年规划'))
assert np.isnan(experience_min('3年以下工作经验'))  # 上限不冒充最低年限
display(jobs[['title_clean', 'skill_Python', 'skill_SQL', 'skill_count', 'experience_years_min', 'degree_text']].head(10))
'''),
md('''
## 2. 全量样本中的技能提及率

给出两个口径：职责或要求提及数/全部职位；要求提及数/有要求文本的职位。
两个分母不同，不能把两列差值当作技能重要性的差值。空要求列不会被当作“不需要技能”。
'''),
code('''
skills_summary = pd.DataFrame({
    'skill': list(SKILLS), 'mentioned_jobs': combined.sum().values,
    'all_job_rate': combined.mean().values,
    'requirement_mentions': requirements.sum().values,
    'requirement_rate': requirements.loc[jobs.has_requirement].mean().values,
    'requirement_denominator': int(jobs.has_requirement.sum()),
}).sort_values('all_job_rate', ascending=False)
display(skills_summary.round(3))
fig, ax = plt.subplots(figsize=(9, 6))
v = skills_summary.iloc[::-1]
ax.barh(v.skill, v.all_job_rate, color='#984ea3')
from matplotlib.ticker import PercentFormatter
ax.xaxis.set_major_formatter(PercentFormatter(1))
ax.set(title='职责或任职要求中的技能提及率', xlabel='占全部职位的比例', ylabel='词典技能')
save_figure(fig, '03_skill_mentions', '词典覆盖18类技能；分母=全部职位；提及不等于硬性要求，0不等于无需掌握。')
csv_export(skills_summary, '03_skill_mentions')
'''),
md('''
## 3. 聚焦数据相关岗位，比较公司与技能共现

先用标题正则筛选“数据分析/数据科学/数据挖掘/商业分析/商业智能”等候选，属于规则子集，
不是经过人工标注的完整岗位类别。对候选标题抽查后再解释结果。
跨公司对比只展示候选数≥20的公司，并保留各公司样本量。
'''),
code('''
jobs['focus_candidate'] = jobs['title_clean'].str.contains(FOCUS_PATTERN, case=False, regex=True, na=False)
focus = jobs.loc[jobs.focus_candidate].copy()
assert len(focus) >= 50, '候选过少，请调整聚焦规则'
display(focus[['job_key', 'company_name', 'title_clean']].sample(min(12, len(focus)), random_state=SEED))
focus_counts = focus.groupby('company_name').size().rename('n')
skill_cols = ['skill_' + s for s in SKILLS]
company_skills = focus.groupby('company_name')[skill_cols].mean()
eligible = focus_counts[focus_counts.ge(20)].sort_values(ascending=False).index
chosen_skills = ['Python', 'SQL', 'Excel', 'BI工具', '机器学习', '统计分析', 'A/B测试', '沟通协作']
fig, ax = plt.subplots(figsize=(11, 6))
view = company_skills.loc[eligible, ['skill_' + s for s in chosen_skills]].copy()
view.columns = chosen_skills
view.index = [f'{name} (n={focus_counts[name]})' for name in view.index]
sns.heatmap(view, annot=True, fmt='.0%', cmap='Blues', vmin=0, vmax=1, ax=ax)
ax.set(title='数据相关候选岗位的公司内技能提及率', xlabel='技能', ylabel='公司及候选职位数')
save_figure(fig, '03_focus_company_skills', '按标题规则筛选；仅展示n≥20公司；岗位级别与子类差异仍可能造成混杂。')
csv_export(company_skills.join(focus_counts).reset_index(), '03_focus_company_skills')

binary = focus[['skill_' + s for s in chosen_skills]].astype('int64')
cooccurrence = binary.T @ binary  # 必须转int64，避免int8矩阵乘法溢出
cooccurrence.index = chosen_skills
cooccurrence.columns = chosen_skills
fig, ax = plt.subplots(figsize=(9, 7))
sns.heatmap(cooccurrence, annot=True, fmt='d', cmap='Purples', ax=ax, cbar_kws={'label': '共同提及职位数（条）'})
ax.set(title='数据相关候选岗位的技能共现', xlabel='技能', ylabel='技能')
save_figure(fig, '03_skill_cooccurrence', '对角线=单技能提及数；非对角线=两技能同时提及数；不解释为因果。')
csv_export(cooccurrence.reset_index(names='skill'), '03_skill_cooccurrence')
assert np.array_equal(np.diag(cooccurrence), binary.sum().values)
'''),
md('''
## 4. 用 TF-IDF 探索词典外关键词

TF：词在职位文本中的频率；IDF：在很多职位中都出现的词权重更低。
先分词与停用词过滤，再提取候选岗位的平均 TF-IDF Top词。
这是一种探索分数，不是提及率，也不是技能重要性的客观分数。
'''),
code('''
stopwords = set('我们 你们 他们 以及 相关 工作 岗位 职责 要求 负责 具有 能够 良好 优秀 熟悉 优先 能力 以上 进行 包括 公司 团队 业务 经验 具备 使用 参与 通过 方向 支持 完成 基于 对于 了解 掌握 任职 本科 硕士 学历 职位'.split())
for word in ['数据分析', '商业分析', '数据科学', '数据挖掘', '机器学习', '深度学习', '用户增长', '实验设计', '数据仓库']:
    jieba.add_word(word)

def tokenize(text):
    return [w for w in jieba.lcut(text.lower())
            if len(w.strip()) >= 2 and w not in stopwords
            and re.fullmatch(r'[a-z][a-z0-9_+#.-]*|[\u4e00-\u9fff]{2,}', w)]

vectorizer = TfidfVectorizer(tokenizer=tokenize, token_pattern=None, min_df=5, max_df=0.85, max_features=3000)
X = vectorizer.fit_transform(focus['analysis_text'])
keywords = pd.DataFrame({'term': vectorizer.get_feature_names_out(),
                         'mean_tfidf': np.asarray(X.mean(axis=0)).ravel()}).sort_values('mean_tfidf', ascending=False)
display(keywords.head(25))
csv_export(keywords, '03_tfidf_keywords')
print('候选职位×词项矩阵：', X.shape)
'''),
md('''
## 5. 人工抽查：规则验证不等于准确率验证

自动边界断言只证明规则按预期执行。没有人工标签，就不能报告精确率/召回率。
下面为每个技能抽取最多3个命中片段，保存核验表。教师/学生填写 `human_label`（1/0）与备注。
若要估计召回率，还须随机抽取未命中样本人工判断，不能只审核正例。

经验年限仅处理明确阿拉伯数字表达；“3年以下”是上限，不生成最低年限。
学历提取也是启发式，不覆盖所有英文或“本科/硕士”等复杂写法。请检查样本再使用。
'''),
code('''
audit_rows = []
for name, pattern in SKILLS.items():
    matched = jobs.loc[jobs['skill_' + name].eq(1)]
    for row in matched.sample(min(3, len(matched)), random_state=SEED).itertuples():
        hit = re.search(pattern, row.analysis_text, re.I)
        audit_rows.append({'job_key': row.job_key, 'skill': name, 'title': row.title_clean,
                           'snippet': row.analysis_text[max(0, hit.start()-45):hit.end()+65],
                           'human_label': '', 'comment': ''})
audit = pd.DataFrame(audit_rows)
display(audit.head(12))
csv_export(audit, '03_skill_manual_audit')
# 对当前快照15条片段的教师参考审核；学生空白核验表另存，不被覆盖。
review = json.loads((ROOT / 'teacher_skill_review.json').read_text())
if review['snapshot_sha256'] == json.loads((DATA / 'raw' / 'manifest.json').read_text())['sha256']:
    teacher_review = audit.drop(columns=['human_label', 'comment']).merge(
        pd.DataFrame(review['rows']), on=['job_key', 'skill'], how='inner', validate='one_to_one')
    csv_export(teacher_review, '03_skill_teacher_review')
    display(teacher_review[['skill', 'snippet', 'human_label', 'comment']].head(6))
    print(review['scope'])
display(jobs.loc[jobs.experience_years_min.notna(), ['title_clean', 'requirement_clean', 'experience_years_min']].sample(
    min(8, jobs.experience_years_min.notna().sum()), random_state=SEED))

jobs.to_parquet(DATA / 'processed' / 'jobs_features.parquet', index=False)
write_json(REPORTS / 'text_metrics.json', {
    'focus_candidates': len(focus), 'all_jobs': len(jobs), 'skills': len(SKILLS),
    'with_requirement': int(jobs.has_requirement.sum()),
    'experience_extracted': int(jobs.experience_years_min.notna().sum()),
    'focus_python_rate': float(focus['skill_Python'].mean()),
    'focus_sql_rate': float(focus['skill_SQL'].mean()),
    'tfidf_features': X.shape[1], 'manual_audit_rows': len(audit),
})
'''),
md('''
## 课堂练习与验收

1. 新增“Git”技能，先写正例/反例，再统计；不要让 GitHub/GitLab 是否算别名成为隐含规则。
2. SQL 是硬性要求还是加分项？现有0/1列不能区分，尝试定位包含它的句子。
3. 完成核验表的10条人工判断，记录误报原因，修改词典并重新运行。
4. 比较职责提及率与要求提及率时，明确分母。不要把共现图称为因果关系。

**验收**：边界断言通过；共现对角线等于单技能计数；特征表可回溯 `job_key`；无虚构准确率。
输出：技能特征表、3 张图、关键词底稿、待人工标注核验表。
'''),
])


save('04_岗位聚类与项目交付.ipynb', [
md('''
# 第 4 课｜岗位聚类与项目交付

**90 分钟：原理与向量化 20′ → KMeans 30′ → 解释与聚焦分析 25′ → 项目汇报 15′**

目标：在数据相关候选岗位中，探索文本相似的岗位群，用关键词和代表职位解释聚类。
聚类是无监督探索，不是招聘预测，也没有“分类准确率”。若分群主要反映语言或公司模板，
这也是需要报告的发现，而不是强行命名成职业方向。
'''), code(BOOT),
code('''
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, adjusted_rand_score
from sklearn.decomposition import TruncatedSVD
from threadpoolctl import threadpool_limits
setup_plotting()
jobs = pd.read_parquet(DATA / 'processed' / 'jobs_features.parquet')
candidate = jobs.loc[jobs.focus_candidate & jobs.text_length.ge(40)].copy()
candidate['han_share'] = candidate['analysis_text'].map(
    lambda s: len(re.findall(r'[\u4e00-\u9fff]', s)) / max(1, len(re.findall(r'[a-zA-Z\u4e00-\u9fff]', s))))
# 此课聚焦中文为主的岗位；阈值是教学规则，不是经过训练的语言识别器。
focus = candidate.loc[candidate.han_share.ge(0.3)].copy()
intro_pattern = r'(?:团队|部门|公司)介绍[：:].*?(?=\s*1[、.．）)])'
intern_pattern = r'(?:日常实习|项目实习|转正实习)[：:][^。]*。'
focus['description_core'] = (focus['description_clean'].str.replace(intro_pattern, ' ', regex=True)
                             .str.replace(intern_pattern, ' ', regex=True))
focus['text_normalized'] = (focus['description_core'] + ' ' + focus['requirement_clean']).str.lower().str.replace(
    r'\s+', ' ', regex=True).str.strip()
# 只在有明确介绍标记和编号职责时移除介绍；无编号文本保留，避免贪婪删除。
assert re.sub(intro_pattern, ' ', '团队介绍：公司简介。 1、分析数据').strip() == '1、分析数据'
assert re.sub(intro_pattern, ' ', '团队介绍：无编号职责需保留') == '团队介绍：无编号职责需保留'
training = focus.drop_duplicates('text_normalized').copy()
print('初始候选：', len(candidate), '；语言范围外：', len(candidate)-len(focus))
print('中文为主候选：', len(focus), '；唯一文本：', len(training), '；重复文本：', len(focus)-len(training))
assert len(training) >= 50
display(training[['company_name', 'title_clean']].sample(10, random_state=SEED))
'''),
md('''
## 1. 先看一个失败基线，再改进表征

第一次试验使用原文字符2—4元片段，聚类中心充满编号、标点、公司介绍。
指标看起来更高，也未必对应职业方向。下面保留一个K=4的反例供课堂观察。

正式模型改用jieba分词，移除标点编号、常见套话和公司名称；只对中文字符占字母/汉字至少30%的候选训练。
英文为主职位留在全量分析表，另列排除数量，不能把中文子集结论推广到英文岗位。
公司/团队介绍仅在明确标记与编号职责之间删除，原文不覆盖，便于回查。
模型输入仍只有职责与要求，没有直接输入标题、公司和城市；残留模板依然可能影响分群。
'''),
code('''
baseline_vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(2, 4), min_df=5, max_df=.8, max_features=6000)
baseline_X = baseline_vectorizer.fit_transform(training['analysis_text'])
with threadpool_limits(limits=1):
    baseline = KMeans(n_clusters=4, n_init=5, random_state=SEED).fit(baseline_X)
baseline_terms = baseline_vectorizer.get_feature_names_out()
baseline_terms_table = pd.DataFrame([
    {'cluster': i, 'top_fragments': repr(baseline_terms[np.argsort(center)[::-1][:8]].tolist())}
    for i, center in enumerate(baseline.cluster_centers_)])
display(baseline_terms_table)
csv_export(baseline_terms_table, '04_failed_char_baseline')

import jieba
stopwords = set('我们 你们 他们 以及 相关 工作 岗位 职责 要求 负责 具有 能够 良好 优秀 熟悉 优先 能力 以上 进行 包括 公司 团队 业务 经验 具备 使用 参与 通过 方向 支持 完成 基于 对于 了解 掌握 任职 本科 硕士 学历 职位 我们的 字节 跳动 字节跳动 抖音 今日头条 腾讯 美团 阿里巴巴 快手 小红书 京东 拼多多 滴滴 携程 tiktok bytedance about us and the of to in for with on is are be as or that you your our we will have at an a it can from this their global products team skills experience role work ability strong preferred responsibilities qualifications opportunity equal employment diversity inclusive inclusion candidate candidates disability reasonable accommodation accommodations provide needs request requests apply qualified applicants all people world join also more other which who was were has not one across development new including related good etc such years year degree bachelor master phd'.split())
for word in ['数据分析', '商业分析', '数据科学', '数据挖掘', '机器学习', '深度学习', '用户增长', '实验设计', '数据仓库',
             '指标体系', '因果推断', '数理统计', '数据建模', '可视化', '推荐算法', '经营分析', '数据治理', '数据产品', '统计分析', '增长策略']:
    jieba.add_word(word)

def tokenize(text):
    return [w for w in jieba.lcut(text.lower()) if w not in stopwords
            and re.fullmatch(r'[a-z][a-z0-9_+#.-]+|[\u4e00-\u9fff]{2,}', w)]

vectorizer = TfidfVectorizer(tokenizer=tokenize, token_pattern=None, min_df=5, max_df=.8,
                             max_features=4000, sublinear_tf=True)
X = vectorizer.fit_transform(training['text_normalized'])
assert (X.getnnz(axis=1) > 0).all(), '存在零向量，请检查文本/分词参数'
assert np.isfinite(X.data).all(), '向量包含非有限值'
csv_export(pd.DataFrame({'term': vectorizer.get_feature_names_out()}), '04_model_vocabulary')
print('训练矩阵：', X.shape, '；非零元素：', X.nnz)
'''),
md('''
## 2. 比较 K=3、4、5、6，并检查稳定性

KMeans 将文本分成K群，最小化群内距离。固定种子让课堂结果可复现。
轮廓系数用于比较本次候选方案；分值低说明分群边界较弱，没有普适“合格线”。
同时检查最小群大小和两个随机种子下的 ARI（一致性指标，不是准确率）。
选择：优先保留最小群≥20且ARI≥0.6的方案，再取轮廓系数较高者；若无方案则回退并提示。
0.6是本课堂预设的稳定性筛选规则，不是行业通用标准。规则公开且可修改。
这只是起点，最终解释仍依赖代表文本审核。
'''),
code('''
models, rows = {}, []
with threadpool_limits(limits=1):
    for k in [3, 4, 5, 6]:
        model = KMeans(n_clusters=k, random_state=SEED, n_init=10, max_iter=200)
        labels = model.fit_predict(X)
        assert np.isfinite(model.cluster_centers_).all() and np.isfinite(model.inertia_)
        other = KMeans(n_clusters=k, random_state=SEED+1, n_init=10, max_iter=200).fit_predict(X)
        score = silhouette_score(X, labels, metric='cosine', sample_size=min(600, X.shape[0]), random_state=SEED)
        models[k] = model
        rows.append({'k': k, 'silhouette_cosine': score, 'inertia': model.inertia_,
                     'smallest_cluster': int(np.bincount(labels).min()),
                     'seed_ARI': adjusted_rand_score(labels, other)})
comparison = pd.DataFrame(rows)
eligible = comparison.loc[comparison.smallest_cluster.ge(20) & comparison.seed_ARI.ge(0.6)]
if eligible.empty:
    eligible = comparison.loc[comparison.smallest_cluster.ge(20)]
    print('警示：没有方案满足稳定性门槛，仅作探索，需人工检查。')
if eligible.empty:
    eligible = comparison
    print('警示：所有方案都有小群，需人工检查。')
best_k = int(eligible.sort_values(['silhouette_cosine', 'k'], ascending=[False, True]).iloc[0]['k'])
model = models[best_k]
training['cluster'] = model.labels_
focus_X = vectorizer.transform(focus['text_normalized'])
focus['cluster'] = model.predict(focus_X)
display(comparison.round(4))
print('按预先声明规则选择 K =', best_k)
csv_export(comparison, '04_k_comparison')
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
axes[0].plot(comparison.k, comparison.silhouette_cosine, 'o-', color='#377eb8')
axes[0].set(title='不同K的余弦轮廓系数', xlabel='群数K', ylabel='轮廓系数（抽样）')
axes[1].plot(comparison.k, comparison.seed_ARI, 'o-', color='#984ea3')
axes[1].set(title='两个随机种子的聚类一致性', xlabel='群数K', ylabel='ARI（非准确率）', ylim=(-0.05, 1.05))
save_figure(fig, '04_model_comparison', '唯一文本上训练；轮廓系数最多抽600条；ARI仅比较两个种子的结果。')
'''),
md('''
## 3. 用关键词、代表岗位和公司集中度解释群

从每个中心取权重最高的词，并按到中心的欧氏距离找代表文本。
输出至少3条代表职位。`human_name`留给学生阅读后填写；`reference_name`是教师审阅当前快照代表岗位后给出的教学参考。
参考名称按关键词签名对应编号，不是模型识别出的职业真值，也未审核群内每一条职位。
模板化、来源结构和岗位级别都属于模型局限，不能凭一个词命名。
'''),
code('''
terms = vectorizer.get_feature_names_out()
distances = model.transform(X)
cluster_rows, examples = [], []
for cluster in range(best_k):
    indices = np.flatnonzero(training.cluster.to_numpy() == cluster)
    nearest = indices[np.argsort(distances[indices, cluster])[:3]]
    top_terms = terms[np.argsort(model.cluster_centers_[cluster])[::-1][:12]].tolist()
    assigned = focus.loc[focus.cluster.eq(cluster)]
    company_mix = assigned['company_name'].value_counts(normalize=True)
    cluster_rows.append({'cluster': cluster, 'unique_training_texts': len(indices), 'jobs': len(assigned),
                         'top_terms': ' / '.join(top_terms), 'largest_company': company_mix.index[0],
                         'largest_company_share': float(company_mix.iloc[0]), 'human_name': '待人工命名'})
    for idx in nearest:
        row = training.iloc[idx]
        examples.append({'cluster': cluster, 'job_key': row.job_key, 'company': row.company_name,
                         'title': row.title_clean, 'text_excerpt': row.analysis_text[:700],
                         'distance_to_center': float(distances[idx, cluster]), 'review_note': ''})
cluster_summary = pd.DataFrame(cluster_rows)
representatives = pd.DataFrame(examples)
# 以下参考解释来自教师对当前快照每群3条代表文本的审阅，不是自动职业真值。
# 按关键词签名对应群编号，避免编号本身被误认为具有业务含义。
def reference_interpretation(terms):
    if '异常情况' in terms and '脚本语言' in terms:
        return '电商分析实习模板倾向'
    if '商业分析' in terms and '行业' in terms:
        return '经营与商业分析倾向'
    if '实验' in terms and '模型' in terms:
        return '实验评估与模型分析倾向'
    return '待人工解释'

cluster_summary['reference_name'] = cluster_summary['top_terms'].map(reference_interpretation)
display(cluster_summary)
for cluster in range(best_k):
    display(Markdown(f'### 群 {cluster}：代表职位（先阅读，再命名）'))
    display(representatives.loc[representatives.cluster.eq(cluster), ['company', 'title', 'text_excerpt']])
csv_export(cluster_summary, '04_cluster_summary')
csv_export(representatives, '04_cluster_representatives')
'''),
md('''
## 4. 聚焦分析：群体技能差异与二维投影

技能词典没有参与模型训练，可作为辅助解释，但与模型输入同来自文本，不能算独立真值验证。
二维SVD只展示高维文本的投影，不用肉眼看散点替代高维评估；类别颜色不表示优劣。
'''),
code('''
selected_skills = ['Python', 'SQL', 'Excel', 'BI工具', '机器学习', '深度学习', 'A/B测试', '统计分析']
profile = focus.groupby('cluster')[['skill_' + s for s in selected_skills]].mean()
profile.columns = selected_skills
fig, ax = plt.subplots(figsize=(10, 4.5))
sns.heatmap(profile, annot=True, fmt='.0%', vmin=0, vmax=1, cmap='Blues', ax=ax)
ax.set(title='岗位群的技能提及画像', xlabel='词典技能', ylabel='聚类编号')
save_figure(fig, '04_cluster_skills', '分母=各群全部候选职位（含重复文本映射回的职位）；提及率不等于能力或录用概率。')
csv_export(profile.reset_index(), '04_cluster_skills')

projection = TruncatedSVD(n_components=2, random_state=SEED)
xy = projection.fit_transform(X)
assert np.isfinite(xy).all(), '二维投影包含非有限值'
fig, ax = plt.subplots(figsize=(8, 5))
for cluster in range(best_k):
    mask = training.cluster.to_numpy() == cluster
    ax.scatter(xy[mask, 0], xy[mask, 1], s=12, alpha=0.5, label=f'群{cluster}')
ax.set(title=f'唯一文本的二维SVD投影（解释方差 {projection.explained_variance_ratio_.sum():.1%}）',
       xlabel='SVD分量1', ylabel='SVD分量2')
ax.legend()
save_figure(fig, '04_cluster_projection', '二维降维损失大量信息；聚类在原始TF-IDF空间训练，投影不证明群真实存在。')

focus['cities_list'] = focus['cities'].map(json.loads)
cluster_cities = focus[['job_key', 'cluster', 'cities_list']].explode('cities_list').dropna(subset=['cities_list'])
cluster_city_counts = cluster_cities.groupby(['cluster', 'cities_list'], as_index=False).agg(jobs=('job_key', 'nunique'))
csv_export(cluster_city_counts, '04_cluster_city_counts')
csv_export(pd.crosstab(focus.cluster, focus.company_name).reset_index(), '04_cluster_company_counts')
assert len(focus) == cluster_summary.jobs.sum()
assert representatives.groupby('cluster').size().eq(3).all()
'''),
md('''
## 5. 形成报告与可写入简历的项目成果

报告中的数字自动来自前三课底稿和本课结果。手工命名与技能准确率未完成，不伪造。
把“发现一个可探索的群”与“证实一个真实职业类别”区分开来。
下一步行动：审核每群3条代表岗位和技能核验表，标记模板/语言影响，再决定调整分词或候选范围。
'''),
code(r'''
structure = json.loads((REPORTS / 'structure_metrics.json').read_text())
text_metrics = json.loads((REPORTS / 'text_metrics.json').read_text())
best = comparison.loc[comparison.k.eq(best_k)].iloc[0]
cluster_metrics = {'initial_candidates': len(candidate), 'excluded_language': len(candidate)-len(focus),
                   'candidate_jobs': len(focus), 'unique_texts': len(training), 'selected_k': best_k,
                   'silhouette_cosine': float(best.silhouette_cosine), 'seed_ARI': float(best.seed_ARI),
                   'svd_2d_variance': float(projection.explained_variance_ratio_.sum()),
                   'feature_count': X.shape[1], 'random_seed': SEED}
write_json(REPORTS / 'cluster_metrics.json', cluster_metrics)
focus.drop(columns=['cities_list']).to_parquet(DATA / 'processed' / 'jobs_clustered.parquet', index=False)

summary_lines = '\n'.join(f"- 群{int(r.cluster)}（参考：{r.reference_name}）：{int(r.jobs)}条职位；最大来源{r.largest_company}占{r.largest_company_share:.1%}。"
                          for r in cluster_summary.itertuples())
business_ids = cluster_summary.loc[cluster_summary.reference_name.eq('经营与商业分析倾向'), 'cluster']
model_ids = cluster_summary.loc[cluster_summary.reference_name.eq('实验评估与模型分析倾向'), 'cluster']
interpretation = '群名需要结合代表职位与岗位构成继续审核。'
if len(business_ids) == 1 and len(model_ids) == 1:
    b, m = int(business_ids.iloc[0]), int(model_ids.iloc[0])
    interpretation = (
        f'参考解释中，群{m}的机器学习提及率为{profile.loc[m, "机器学习"]:.1%}，'
        f'群{b}为{profile.loc[b, "机器学习"]:.1%}；'
        f'A/B测试提及率分别为{profile.loc[m, "A/B测试"]:.1%}和{profile.loc[b, "A/B测试"]:.1%}。'
        '这提示数据相关岗位存在技能侧重点差异，可用于进一步筛选岗位与安排学习重点；'
        '分群边界较弱，且公司、级别、招聘类型构成不同，不能当作确定职业分类或因果效应。')
report = f"""# 招聘职位样本分析｜课程项目报告

## 摘要与数据范围
固定快照包含 {structure['jobs']:,} 条待同步职位、{structure['companies']} 家公司。
原库只读，通过SQLite backup API建立一致快照；原文、校验摘要和清洗日志均归档。
样本不是整个招聘市场，也不一定全部仍在线；职位条目不等于招聘人数。

## 数据质量与结构发现
- {structure['top_company']}有{structure['top_company_jobs']:,}条，占样本{structure['top_company_share']:.1%}，来源结构不均衡。
- {structure['top_city']}覆盖{structure['top_city_jobs']:,}条职位，占全部职位{structure['top_city_coverage']:.1%}；多城市覆盖率不互斥。
- 字段覆盖率存在来源差异，学历缺失不能解释为无学历要求；本项目不报告薪资排行或市场增速。
- 日期可解析率、地理层级及缺失情况见01/02课质量底稿。

## 文本分析
标题规则筛出{text_metrics['focus_candidates']}条数据相关候选岗位。
候选中Python提及率{text_metrics['focus_python_rate']:.1%}、SQL相关词提及率{text_metrics['focus_sql_rate']:.1%}。
这是职责或要求的词典命中率；不是硬性要求率或个人能力评价。
已导出{text_metrics['manual_audit_rows']}条技能命中核验样本，尚未形成带人工真值的精确率/召回率。

## 岗位聚类探索
文本长度至少40的初始候选{len(candidate)}条；排除{len(candidate)-len(focus)}条英文为主的文本后，中文为主候选{len(focus)}条。
移除明确的团队介绍、套话并分词，按处理后文本去重得到{len(training)}条训练；词级TF-IDF，固定种子42。
字符n-gram失败基线主要反映编号/模板，保留为教学反例，不用于职业方向结论。
比较K=3/4/5/6，优先筛选最小群≥20且两个种子ARI≥0.6，再选轮廓系数最高的K={best_k}。
抽样余弦轮廓系数{best.silhouette_cosine:.3f}，两个随机种子的ARI={best.seed_ARI:.3f}。
这些指标用于模型内部比较，不是分类准确率；分群仍需人工解释。
{summary_lines}

### 聚焦发现与解释边界
{interpretation}
电商分析实习模板倾向群的代表岗位正文高度相似，不能视为独立验证出的通用职业类别。
参考名称来自每群3条代表文本的人工阅读，不是对群内全部岗位的完整标注。
虽然随机种子一致性较高，轮廓系数仍较低；稳定的结果不一定有清晰职业边界。

## 可执行后续行动
1. 为每群阅读3条代表文本，填写群名称、命名理由、模板或语言影响，再决定是否保留分群。
2. 完成技能核验表的人工标注，另外抽取未命中样本，审核误报和漏报后迭代词典。
3. 对需要比较的岗位先限定招聘类型、语言与级别，并在图表中显示样本量，避免构成混杂。

## 局限与复现
京东社招采集汇总显示中断；各来源批次和采集规则不同；历史职位保留；队列不是永久全量仓库。
城市是规则清洗后的候选，省级和待核验地点不进入城市榜；词典、经验/学历正则并非完美标注。
聚类可能反映公司、语言或模板；二维投影不代表高维可分性；未作因果推断。
依次运行四本Notebook；环境版本见requirements-lock.txt；原始快照SHA见data/raw/manifest.json。
"""
(REPORTS / '项目分析报告.md').write_text(report, encoding='utf-8')
display(Markdown(report))
'''),
md('''
## STAR 项目表述与课堂汇报

**S**：多公司招聘数据嵌套在 JSON 中，岗位职责与要求难以直接比较。  
**T**：构建分析表，描述样本结构，提取技能并探索数据相关岗位的细分群体。  
**A**：使用 SQLite/Pandas 清洗与展开，Matplotlib/Seaborn 可视化，技能词典/TF-IDF 文本特征，KMeans聚类。  
**R**：交付可复现分析、图表底稿和报告；具体样本量、候选数、群数以运行结果为准。

简历示例：
> 基于16家公司官网采集样本完成招聘岗位分析，使用Python/SQL展开JSON并统一多城市统计口径；
> 结合技能词典与TF-IDF提取文本特征，使用KMeans探索数据相关岗位群，交付可复现Notebook与分析报告。

请在完成独立练习后补充一条经核验的具体发现。不要声称自己完成了原始采集系统，也不要把聚类写成录用预测。

## 最后15分钟：项目答辩

1. 用30秒说明样本和研究问题，60秒讲一张图，60秒讲一个技能/岗位群，30秒讲局限。
2. 为什么选择这个K？如果ARI较低怎么办？（检查稳定性，缩小范围，修改表征，而非只挑漂亮图。）
3. 可选拓展：改变停用词、min_df或标题筛选范围，对比关键词、代表职位与结果稳定性，不只比一个指标。

**验收**：候选数与群计数对齐；每群有3条代表文本；指标口径公开；报告中的数字与底稿一致。
'''),
])

print('已生成4本Notebook：', ROOT / 'notebooks')
(ROOT / 'reports' / 'material_structure.json').write_text(
    json.dumps(MATERIAL_STATS, ensure_ascii=False, indent=2), encoding='utf-8')
