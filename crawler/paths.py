# -*- coding: utf-8 -*-
"""目录布局常量：本地状态与产出目录的唯一事实来源。

所有模块统一从 paths 取目录（调用时求值，方便单测重定向到临时目录）。
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(BASE_DIR, "state")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


def ensure_dirs():
    """保证 state/ 与 output/ 存在（各入口 import 后调用一次）。"""
    os.makedirs(STATE_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


# 本地待同步队列数据库（抓取结果先落这里，再由 sync_cloud 慢速推云库）
def queue_db_path():
    return os.path.join(STATE_DIR, "pending_queue.db")
