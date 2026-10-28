"""实际启动课程Jupyter，确认可见4本教材与正确内核，最后关闭测试服务器。"""
from pathlib import Path
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    runtime = ROOT / '.runtime'
    runtime.mkdir(exist_ok=True)
    token = secrets.token_urlsafe(24)
    env = dict(os.environ, JUPYTER_TOKEN=token)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    log = runtime / 'jupyter_smoke.log'
    log.touch(mode=0o600, exist_ok=True)
    with log.open('w') as stream:
        process = subprocess.Popen(['bash', str(ROOT / 'scripts/start_jupyter.sh'), '--no-browser',
                                    '--ServerApp.ip=127.0.0.1', f'--ServerApp.port={port}',
                                    '--ServerApp.port_retries=0'], cwd=ROOT, env=env,
                                   stdout=stream, stderr=subprocess.STDOUT)
        try:
            def get(path):
                request = urllib.request.Request(f'http://127.0.0.1:{port}{path}',
                                                 headers={'Authorization': 'token ' + token})
                with urllib.request.urlopen(request, timeout=3) as response:
                    return json.load(response)
            last_error = None
            for _ in range(60):
                if process.poll() is not None:
                    raise RuntimeError('Jupyter启动失败，请查看.runtime/jupyter_smoke.log')
                try:
                    kernels = get('/api/kernelspecs')
                    break
                except Exception as exc:
                    last_error = exc
                    time.sleep(0.5)
            else:
                raise RuntimeError(f'Jupyter启动超时: {last_error}')
            spec = kernels['kernelspecs']['jobs-course']['spec']
            assert Path(spec['argv'][0]).absolute() == Path(sys.executable).absolute()
            contents = get('/api/contents/')
            notebooks = [x['name'] for x in contents['content'] if x['name'].endswith('.ipynb')]
            assert len(notebooks) == 4, notebooks
            result = {'server_start': 'PASS', 'course_kernel': 'PASS', 'notebooks_visible': notebooks,
                      'server_closed_after_check': True}
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    (ROOT / 'reports' / 'jupyter_smoke.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
