"""独立检查数据守恒、统计口径、Notebook输出和交付文件。"""
from pathlib import Path
import json
import re
import sqlite3
import sys
import ast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from course_utils import *
import pandas as pd
import numpy as np
from PIL import Image
import nbformat


def main():
    results = []
    def check(name, condition):
        assert condition, name
        results.append({'check': name, 'status': 'PASS'})

    snapshot, manifest = snapshot_database()
    jobs = pd.read_parquet(DATA / 'processed' / 'jobs_clean.parquet')
    features = pd.read_parquet(DATA / 'processed' / 'jobs_features.parquet')
    clustered = pd.read_parquet(DATA / 'processed' / 'jobs_clustered.parquet')
    log = json.loads((REPORTS / 'cleaning_log.json').read_text())
    with sqlite3.connect(snapshot.as_uri() + '?mode=ro', uri=True) as conn:
        original = pd.read_sql_query('SELECT seq,source,portal,batch_id,source_site,job_id,payload FROM pending_jobs', conn)
    check('快照行数等于清洗+隔离', len(original) == len(jobs) + log['rejected_json_rows'])
    check('完整职位身份键唯一', not jobs.duplicated(KEY).any())
    check('行键唯一且各课全量表守恒', jobs.job_key.is_unique and jobs.job_key.equals(features.job_key))
    check('源公司计数与清洗表一致（本快照无隔离）', log['rejected_json_rows'] == 0 and
          original.source.value_counts().sort_index().equals(jobs.source.value_counts().sort_index()))
    check('快照完整性与哈希有效', manifest['integrity_check'] == 'ok' and sha256(snapshot) == manifest['sha256'])
    # 用原始JSON独立复核样本，不依赖清洗表的标题生成逻辑。
    by_seq = jobs.set_index('seq')
    for row in original.sample(min(50, len(original)), random_state=7).itertuples():
        d = json.loads(row.payload)
        check(f'原始标题可回溯 seq={row.seq}', by_seq.loc[row.seq, 'title'] == d['title'])

    counts = pd.read_csv(TABLES / '02_company_counts.csv')
    check('公司职位数之和等于全量职位', counts.jobs.sum() == len(jobs))
    check('公司样本占比之和为1', np.isclose(counts.share.sum(), 1))
    types = pd.read_csv(TABLES / '02_type_share.csv').set_index('company_name')
    check('公司内招聘类型占比之和为1', np.allclose(types.sum(axis=1), 1))
    city_counts = pd.read_csv(TABLES / '02_city_counts.csv')
    city_lists = jobs.cities.map(json.loads)
    check('城市计数守恒于职位城市关联', city_counts.jobs.sum() == city_lists.map(len).sum())
    check('每职位城市列表无重复', city_lists.map(lambda x: len(x) == len(set(x))).all())
    check('省级地点未进入城市榜', not city_counts.city.isin(PROVINCES).any() and
          not city_counts.city.str.endswith(('省', '自治区')).any())
    check('每城市岗位覆盖率不超过1', city_counts.coverage_rate.between(0, 1).all())
    check('字典列表及复合字符串地名正确清洗',
          normalize_locations([{'name': '北京市'}, {'name': 'Shanghai'}], None) == ['北京', '上海'] and
          normalize_locations(['北京市,上海市'], None) == ['北京', '上海'] and
          normalize_locations(['安徽省·合肥市'], None) == ['合肥'])
    check('SQL和Java边界反例正确', skill_hits('NoSQL JavaScript CPython')['SQL'] == 0 and
          skill_hits('NoSQL JavaScript CPython')['Java'] == 0 and skill_hits('NoSQL JavaScript CPython')['Python'] == 0)
    check('技能中文邻接正例正确', skill_hits('熟悉Python、MySQL和JAVA开发')['Python'] == 1 and
          skill_hits('熟悉Python、MySQL和JAVA开发')['SQL'] == 1 and skill_hits('熟悉Python、MySQL和JAVA开发')['Java'] == 1)
    check('工作年限不误取规划或上限', np.isnan(experience_min('制定3年规划')) and
          np.isnan(experience_min('3年以下工作经验')) and np.isnan(experience_min('3年及以下相关经验')))
    check('明确经验区间提取下限', experience_min('3-5年数据分析经验') == 3)
    co = pd.read_csv(TABLES / '03_skill_cooccurrence.csv', index_col=0)
    focus = features.loc[features.focus_candidate]
    check('技能共现矩阵对称', np.array_equal(co.to_numpy(), co.to_numpy().T))
    check('技能共现对角线等于命中数', all(co.loc[s, s] == focus['skill_' + s].sum() for s in co.index))
    check('所有技能列为0或1', features[['skill_' + s for s in SKILLS]].isin([0, 1]).all().all())
    check('合并文本提及是职责与要求的并集', all(
        features['skill_' + s].eq(features[['req_' + s, 'desc_' + s]].max(axis=1)).all() for s in SKILLS))
    teacher = pd.read_csv(TABLES / '03_skill_teacher_review.csv')
    check('教师参考核验15条且全部可回溯命中片段', len(teacher) == 15 and teacher.human_label.eq(1).all()
          and teacher.snippet.str.len().gt(0).all())
    summary = pd.read_csv(TABLES / '04_cluster_summary.csv')
    check('聚类群规模之和等于合格候选数', summary.jobs.sum() == len(clustered))
    check('聚类候选严格来自规则子集', set(clustered.job_key).issubset(set(focus.job_key)))
    check('群标签无遗漏', clustered.cluster.notna().all() and clustered.cluster.nunique() == len(summary))
    reps = pd.read_csv(TABLES / '04_cluster_representatives.csv')
    check('每群有3条代表职位', reps.groupby('cluster').size().eq(3).all())
    comparison = pd.read_csv(TABLES / '04_k_comparison.csv')
    check('比较4个K且评估指标有效', set(comparison.k) == {3,4,5,6} and
          comparison.silhouette_cosine.between(-1,1).all() and comparison.seed_ARI.between(-1,1).all())
    metrics = json.loads((REPORTS / 'cluster_metrics.json').read_text())
    check('聚类语言筛选数量守恒', metrics['initial_candidates'] == metrics['candidate_jobs'] + metrics['excluded_language'])
    check('正式模型不使用纯编号或标点词项', pd.read_csv(TABLES / '04_model_vocabulary.csv').term.map(
        lambda s: bool(re.fullmatch(r'[a-z][a-z0-9_+#.-]+|[\u4e00-\u9fff]{2,}', s))).all())

    # 增强版：独立复核替代口径和新特征，不只检查文件存在。
    organization_demo = pd.read_csv(TABLES / '01_organization_join_demo.csv', dtype={'job_key': str})
    check('组织聚合关联仍保持一行一职位', len(organization_demo) == len(jobs) and organization_demo.job_key.is_unique)
    check('组织关系数为非负整数', organization_demo.organization_count.ge(0).all() and
          np.allclose(organization_demo.organization_count, organization_demo.organization_count.astype(int)))
    city_methods = pd.read_csv(TABLES / '02_city_counting_methods.csv')
    check('城市分摊加未识别城市守恒', np.isclose(city_methods.fractional_jobs.sum() + city_lists.map(len).eq(0).sum(), len(jobs)))
    beijing_fraction = sum(1 / len(xs) for xs in city_lists if '北京' in xs)
    check('北京折算数可从职位列表直接复核', np.isclose(
        city_methods.loc[city_methods.city.eq('北京'), 'fractional_jobs'].iloc[0], beijing_fraction))
    check('折算数不大于覆盖数', city_methods.fractional_jobs.le(city_methods.jobs + 1e-10).all())
    concentration = pd.read_csv(TABLES / '02_concentration.csv')
    check('累计贡献单调且最终为1', concentration.cumulative_share.is_monotonic_increasing and
          np.isclose(concentration.cumulative_share.iloc[-1], 1))
    adjustment = pd.read_csv(TABLES / '02_standardized_beijing.csv')
    check('标准化覆盖率范围正确且有可比公司', len(adjustment) >= 2 and
          adjustment[['raw_rate', 'standardized_rate']].stack().between(0, 1).all())
    check('百分点变化正确', np.allclose(adjustment.change_pp,
          (adjustment.standardized_rate - adjustment.raw_rate) * 100))

    long_skills = pd.read_csv(TABLES / '03_focus_skill_long.csv', dtype={'job_key': str})
    check('长表行数等于候选技能命中关系数', len(long_skills) == focus.skill_count.sum())
    check('长表职位技能关系唯一且来源范围正确', not long_skills.duplicated(['job_key', 'skill']).any() and
          set(long_skills.job_key).issubset(set(focus.job_key)))
    pairs = pd.read_csv(TABLES / '03_skill_pairs.csv')
    check('技能对数量为18选2', len(pairs) == len(SKILLS) * (len(SKILLS)-1) // 2)
    py_sql = pairs.loc[pairs.a.eq('Python') & pairs.b.eq('SQL')].iloc[0]
    py, sql = focus.skill_Python.eq(1), focus.skill_SQL.eq(1)
    check('Python-SQL联合计数独立复核', py_sql.n_ab == int((py & sql).sum()))
    check('Jaccard与条件概率的分母正确', np.isclose(py_sql.jaccard, (py & sql).sum() / (py | sql).sum()) and
          np.isclose(py_sql.p_b_given_a, (py & sql).sum() / py.sum()))
    check('Lift与独立预期比值一致', np.isclose(py_sql.lift, (py & sql).mean() / (py.mean() * sql.mean())))
    allowed_contexts = {'未提及', '否定提示', '加分提示', '明确要求提示', '仅提及', '多种语境'}
    for skill in ['Python', 'SQL', 'Excel']:
        contexts, evidence = features['req_context_' + skill], features['req_evidence_' + skill]
        check(f'{skill}语境取值与证据对应', set(contexts).issubset(allowed_contexts) and
              contexts.eq('未提及').equals(evidence.fillna('').eq('')))
        check(f'{skill}语境抽取没有丢失原始要求命中', contexts.ne('未提及').equals(features['req_' + skill].eq(1)))
    check('实习标题对照标记不覆盖原入口编码', features.internship_hint_outside_intern_type.equals(
        features.title_internship_hint & ~features.recruitment_type.isin(['internship', 'regular_intern', 'research_intern'])))

    # 仅提取Notebook中的函数定义，避免为了测试语义边界而重复运行全课。
    text_notebook = nbformat.read(next((ROOT / 'notebooks').glob('03_*.ipynb')), as_version=4)
    context_node = next(node for cell in text_notebook.cells if cell.cell_type == 'code'
                        for node in ast.parse(cell.source).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'requirement_context')
    namespace = {'re': re, 'SKILLS': SKILLS}
    exec(compile(ast.Module(body=[context_node], type_ignores=[]), '<context-rule>', 'exec'), namespace)
    context_rule = namespace['requirement_context']
    for text, expected in [('不要求SQL经验', '否定提示'), ('无需熟练掌握SQL', '否定提示'),
                           ('SQL能力加分', '加分提示'), ('熟练使用MySQL', '明确要求提示'),
                           ('NoSQL经验', '未提及'), ('SQL加分；精通SQL', '多种语境')]:
        check(f'语境正反例：{text}', context_rule(text, 'SQL')[0] == expected)

    representation = pd.read_csv(TABLES / '04_representation_comparison.csv').set_index('text_cluster')
    check('双表征比较使用同一候选数量', representation.to_numpy().sum() == len(clustered))
    retrieval = pd.read_csv(TABLES / '04_query_retrieval.csv', dtype={'job_key': str})
    check('检索结果有序且可回溯', len(retrieval) == 8 and retrieval.cosine_similarity.is_monotonic_decreasing and
          retrieval.job_key.is_unique and set(retrieval.job_key).issubset(set(clustered.job_key)))
    check('检索相似度不是超范围数值', retrieval.cosine_similarity.between(-1e-12, 1+1e-12).all())
    check('群中心距离与间隔有限且非负', np.isfinite(clustered[['cluster_distance', 'cluster_distance_gap']]).all().all()
          and clustered.cluster_distance_gap.ge(-1e-12).all())
    extended_report = (REPORTS / '项目分析报告_增强版.md').read_text()
    check('增强报告章节真实换行且包含扩展实验', '\n## 扩展分析与比较实验\n' in extended_report and
          '表征敏感性' in extended_report and '文本检索' in extended_report)
    classifier = json.loads((REPORTS / 'classifier_metrics.json').read_text())
    scores = pd.read_csv(TABLES / '04_classifier_scores.csv')
    predicted = pd.read_csv(TABLES / '04_classifier_test_predictions.csv')
    check('监督分类样本与分组留出数量正确', classifier['train_n'] + classifier['test_n'] ==
          clustered.recruitment_type.isin(['society', 'campus']).sum() and classifier['text_groups_overlap'] == 0)
    check('分类分数与测试样本有效', len(scores) == 2 and scores[['accuracy', 'macro_f1']].stack().between(0, 1).all()
          and len(predicted) == classifier['test_n'])
    from sklearn.metrics import accuracy_score, f1_score
    check('分类Accuracy和Macro-F1可由测试预测底稿复算', np.isclose(scores.iloc[1].accuracy,
          accuracy_score(predicted.recruitment_type, predicted.predicted_type)) and np.isclose(scores.iloc[1].macro_f1,
          f1_score(predicted.recruitment_type, predicted.predicted_type, average='macro')))

    images = sorted(FIGURES.glob('*.png'))
    check('图表文件齐全', len(images) == 18)
    for p in images:
        with Image.open(p) as im:
            check(f'图像完整可读 {p.name}', im.width >= 600 and im.height >= 400)
            im.verify()
    notebooks = sorted((ROOT / 'notebooks').glob('*.ipynb'))
    check('4本Notebook齐全', len(notebooks) == 4)
    for p in notebooks:
        nb = nbformat.read(p, as_version=4)
        nbformat.validate(nb)
        check(f'教材无误转义控制字符 {p.name}', all(
            not any(ord(char) < 32 and char not in '\n\t' for char in cell.source) for cell in nb.cells))
        cells = [c for c in nb.cells if c.cell_type == 'code']
        outputs = [o for c in cells for o in c.outputs]
        check(f'全部代码执行且无错误 {p.name}', all(c.execution_count is not None for c in cells) and
              all(o.output_type != 'error' for o in outputs))
        # 检查输出中的常见渲染警告，不靠静默屏蔽警告通过。
        output_text = json.dumps(outputs, ensure_ascii=False)
        check(f'无字体缺字与数值异常警告 {p.name}', not re.search(
            r'Glyph .* missing|overflow encountered|invalid value encountered|divide by zero encountered', output_text))
        check(f'HTML预览存在 {p.name}', (REPORTS / (p.stem + '.html')).exists())
        comments = sum(line.lstrip().startswith('#') for c in cells for line in c.source.splitlines())
        check(f'教学注释和扩展内容已生成 {p.name}', comments >= 40 and len(cells) >= 12)
    report = (REPORTS / '项目分析报告.md').read_text()
    check('报告包含真实职位规模', f'{len(jobs):,}' in report)
    check('环境锁文件存在', (ROOT / 'requirements-lock.txt').exists())
    output = {'passed': len(results), 'failed': 0, 'checks': results}
    write_json(REPORTS / 'validation_results.json', output)
    print(json.dumps({'passed': len(results), 'failed': 0, 'jobs': len(jobs),
                      'clustered_jobs': len(clustered), 'figures': len(images)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
