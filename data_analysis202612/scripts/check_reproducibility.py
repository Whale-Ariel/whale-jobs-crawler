"""捕获/比较生成结果的SHA-256；不比较含执行时间的Notebook/HTML或执行日志。"""
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def selected_files():
    # 这些都是运行生成的内容，固定输入与环境下应当可重现；不包含手工编辑文档。
    files = (list((ROOT / 'data/processed').glob('*.parquet')) +
             list((ROOT / 'artifacts/figures').glob('*.png')) +
             list((ROOT / 'artifacts/tables').glob('*.csv')))
    names = ['structure_metrics.json', 'text_metrics.json', 'cluster_metrics.json',
             'structure_extension_metrics.json', 'text_extension_metrics.json', 'model_extension_metrics.json',
             'classifier_metrics.json', '项目分析报告.md', '项目分析报告_增强版.md']
    files += [ROOT / 'reports' / name for name in names]
    return sorted(files)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['capture', 'verify'])
    args = parser.parse_args()
    baseline_path = ROOT / 'reports/reproducibility_baseline_v2.json'
    hashes = {str(p.relative_to(ROOT)): file_hash(p) for p in selected_files()}
    if args.mode == 'capture':
        baseline_path.write_text(json.dumps(hashes, ensure_ascii=False, indent=2))
        print(f'已记录{len(hashes)}个生成结果，下一次运行四课后使用verify比较。')
        return
    previous = json.loads(baseline_path.read_text())
    assert set(previous) == set(hashes), '文件集合发生变化，请核查后重新capture'
    rows = [{'file': name, 'identical': digest == hashes[name]} for name, digest in previous.items()]
    result = {'files': len(rows), 'identical': sum(row['identical'] for row in rows), 'results': rows}
    (ROOT / 'reports/reproducibility_results_v2.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({'files': result['files'], 'identical': result['identical']}, ensure_ascii=False))
    assert all(row['identical'] for row in rows), '有结果改变，请查看reproducibility_results_v2.json'


if __name__ == '__main__':
    main()
