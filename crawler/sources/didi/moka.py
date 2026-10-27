"""滴滴校园门户使用的 Moka 公开响应解码。只处理官网页面里的临时 key。"""
import base64
import html
import json
import re

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from crawler.sources.base import SourceError


def decode_moka(payload, iv):
    if payload.get('necromancer'):
        try:
            decrypted = AES.new(payload['necromancer'].encode(), AES.MODE_CBC, iv.encode()).decrypt(
                base64.b64decode(payload['data'], validate=True))
            payload = json.loads(unpad(decrypted, 16))
        except (ValueError, KeyError, TypeError) as error:
            raise SourceError('Moka公开响应解码失败') from error
    if payload.get('code') != 0 or not isinstance(payload.get('data'), dict):
        raise SourceError('Moka业务错误：' + str(payload.get('msg')))
    return payload['data']


def moka_bootstrap(body):
    for value in re.findall(r'value="([^"]+)"', body):
        try:
            data = json.loads(html.unescape(value))
        except ValueError:
            continue
        if isinstance(data, dict) and 'jobs' in data and 'aesIv' in data:
            return data
    raise SourceError('Moka官网初始化数据缺失')
