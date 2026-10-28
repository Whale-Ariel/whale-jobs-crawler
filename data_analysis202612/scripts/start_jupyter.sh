#!/bin/bash
set -euo pipefail
COURSE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$COURSE_DIR"
if [ ! -x .venv/bin/python ]; then
  echo '请先按 开始上课.md 创建 .venv 并安装依赖。'
  exit 1
fi
export PATH="$COURSE_DIR/.venv/bin:$PATH"
export MPLCONFIGDIR="$COURSE_DIR/.runtime/matplotlib"
export IPYTHONDIR="$COURSE_DIR/.runtime/ipython"
export JUPYTER_RUNTIME_DIR="$COURSE_DIR/.runtime/jupyter"
mkdir -p "$MPLCONFIGDIR" "$IPYTHONDIR" "$JUPYTER_RUNTIME_DIR"
.venv/bin/python -m ipykernel install --prefix "$COURSE_DIR/.venv" --name jobs-course --display-name '招聘数据分析课程'
exec .venv/bin/python -m notebook notebooks "$@"
