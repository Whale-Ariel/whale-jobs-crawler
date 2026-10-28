"""在独立新内核中逐本运行、校验并导出HTML；第一次运行创建固定数据快照。"""
from pathlib import Path
import json
import os
import sys
import time
import tempfile

ROOT = Path(__file__).resolve().parents[1]
runtime = Path(tempfile.gettempdir()) / 'jobscrawler-course-runtime'
runtime.mkdir(exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', str(runtime / 'matplotlib'))
os.environ.setdefault('IPYTHONDIR', str(runtime / 'ipython'))
os.environ.setdefault('JUPYTER_RUNTIME_DIR', str(runtime / 'jupyter'))
os.environ.setdefault('XDG_CACHE_HOME', str(runtime / 'cache'))
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')

import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter
from jupyter_client.kernelspec import KernelSpecManager


def main():
    reports = ROOT / 'reports'
    reports.mkdir(exist_ok=True)
    # 为当前解释器生成临时kernelspec，避免误用系统里损坏的SciPy环境。
    kernels = runtime / 'kernels'
    spec = kernels / 'course-python'
    spec.mkdir(parents=True, exist_ok=True)
    (spec / 'kernel.json').write_text(json.dumps({
        'argv': [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}'],
        'display_name': '招聘数据分析课程', 'language': 'python',
    }))
    ksm = KernelSpecManager(kernel_dirs=[str(kernels)])
    records = []
    for path in sorted((ROOT / 'notebooks').glob('*.ipynb')):
        start = time.monotonic()
        print('RUN', path.name, flush=True)
        notebook = nbformat.read(path, as_version=4)
        client = NotebookClient(notebook, timeout=600, kernel_name='course-python',
                                resources={'metadata': {'path': str(ROOT)}},
                                record_timing=True)
        # NotebookClient把额外参数转交KernelManager。
        from jupyter_client import KernelManager
        client.km = KernelManager(kernel_name='course-python', kernel_spec_manager=ksm)
        try:
            client.execute()
        except Exception:
            nbformat.write(notebook, path)
            print('FAILED', path.name, flush=True)
            raise
        nbformat.validate(notebook)
        nbformat.write(notebook, path)
        exporter = HTMLExporter(template_name='lab')
        body, _ = exporter.from_notebook_node(notebook)
        html_path = reports / (path.stem + '.html')
        html_path.write_text(body, encoding='utf-8')
        outputs = [output for cell in notebook.cells if cell.cell_type == 'code' for output in cell.outputs]
        errors = [o for o in outputs if o.output_type == 'error']
        assert not errors
        code_cells = [c for c in notebook.cells if c.cell_type == 'code']
        assert all(c.execution_count is not None for c in code_cells)
        record = {'notebook': path.name, 'seconds': round(time.monotonic()-start, 2),
                  'code_cells': len(code_cells), 'errors': len(errors),
                  'embedded_images': sum('image/png' in o.get('data', {}) for o in outputs),
                  'html': html_path.name}
        records.append(record)
        print('PASS', json.dumps(record, ensure_ascii=False), flush=True)
        (reports / 'execution_results.json').write_text(json.dumps(records, ensure_ascii=False, indent=2))
    print('四本Notebook全部执行成功。', flush=True)


if __name__ == '__main__':
    main()
