"""环境变量优先，本机配置仅存于被 git 忽略的 config.local.json。"""
import json
import os
from pathlib import Path


def cloud_access_key():
    value = os.environ.get('CRAWLER_CLOUD_ACCESS_KEY')
    if value:
        return value
    path = Path(__file__).resolve().parents[1] / 'config.local.json'
    if path.exists():
        with path.open(encoding='utf-8') as f:
            return json.load(f).get('cloud_access_key', '')
    return ''
