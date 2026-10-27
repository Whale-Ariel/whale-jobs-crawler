# -*- coding: utf-8 -*-
"""本地已知ID与持久化断点：原子JSON写入、频道进程锁；旧版不可靠断点自动从头扫描。"""
import json
import os
import tempfile
import fcntl
from contextlib import contextmanager
from datetime import datetime

from crawler import paths


def _known_ids_path(ns: str) -> str:
    return os.path.join(paths.STATE_DIR, f"known_ids_{ns}.json")


def _progress_path(ns: str) -> str:
    return os.path.join(paths.STATE_DIR, f"progress_{ns}.json")


def load_known_ids(ns: str) -> set:
    path = _known_ids_path(ns)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_known_ids(ns: str, ids: set):
    path = _known_ids_path(ns)
    atomic_json(path, sorted(ids))


def load_progress(ns: str, default: int = 0, page_size=None) -> int:
    """全量断点。字节按 offset（默认 0），腾讯按页码（默认 1）。"""
    path = _progress_path(ns)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data.get('durable'):
            print(f'[{ns}] 旧断点早于数据提交，安全起见从头重抓；已落盘职位会去重', flush=True)
            return default
        if page_size and data.get('page_size') and data['page_size'] != page_size:
            print(f'[{ns}] 分页大小改变，从头重抓以避免跳页', flush=True)
            return default
        # 兼容历史文件：旧版分别存 next_offset（字节）/ next_page（腾讯）
        for key in ("value", "next_offset", "next_page"):
            if key in data:
                return data[key]
    return default


def save_progress(ns: str, value: int, page_size=None):
    path = _progress_path(ns)
    atomic_json(path, {"value": value, "durable": True, "page_size": page_size, "updated_at": datetime.now().astimezone().isoformat()})


def clear_progress(ns: str):
    path = _progress_path(ns)
    if os.path.exists(path):
        os.remove(path)


def atomic_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def channel_lock(namespace):
    os.makedirs(paths.STATE_DIR, exist_ok=True)
    with open(os.path.join(paths.STATE_DIR, namespace+'.lock'), 'a') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(f'{namespace} 已有抓取进程运行') from None
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
