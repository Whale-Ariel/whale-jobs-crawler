"""列表页文本、时间与地名的共用整理。各公司解析器只处理自己的字段。"""
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {'p', 'br', 'div', 'li'}:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in {'p', 'div', 'li'}:
            self.parts.append('\n')

    def handle_data(self, data):
        self.parts.append(data)


def text(value):
    if value is None:
        return None
    parser = PlainText()
    parser.feed(str(value).replace('\\n', '\n'))
    return re.sub(r'\n[ \t]*\n+', '\n\n', ''.join(parser.parts)).strip() or None


def split_duty(value):
    value = text(value)
    if not value:
        return None, None
    parts = re.split(r'(?:\n|^)(?:工作要求|任职要求|任职资格|岗位要求|职位要求)\s*[:：]?\s*', value, maxsplit=1)
    return parts[0].strip() or None, parts[1].strip() if len(parts) > 1 else None


def timestamp(value):
    if value is None or value == '':
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000 if value > 1e11 else value, timezone.utc).isoformat()
    dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
    return dt.isoformat()


def date(value):
    if value is None or str(value).startswith(('0001-', '1900-')):
        return None
    if isinstance(value, str):
        # 北森使用 .NET 七位小数秒；Python 3.10 只接受六位微秒。
        value = re.sub(r'(\.\d{6})\d+', r'\1', value)
    return timestamp(value)


def unique(values):
    return list(dict.fromkeys(str(v) for v in values if v is not None and v != ''))


def names(value):
    if not value:
        return []
    if not isinstance(value, list):
        value = [value]
    return list(dict.fromkeys(str(x.get('name')) if isinstance(x, dict) else str(x)
                             for x in value if (x.get('name') if isinstance(x, dict) else x)))


def place_names(value):
    if not value:
        return []
    if not isinstance(value, list):
        value = [value]
    result = []
    for item in value:
        if isinstance(item, dict):
            item = next((item[k] for k in ('name', 'Name', 'cityName', 'addressDetail', 'workCityName') if item.get(k)), None)
        if item:
            result.extend(re.split(r'[，,、;；]', str(item)))
    return unique(part.strip() for part in result)
