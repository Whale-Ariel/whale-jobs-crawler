"""腾讯职位字段映射。"""
import re
from datetime import datetime, timezone

from crawler.taxonomy import classify

SOURCE = "tencent"

_CN_DATE_RE = re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日$")


def _last_update_to_ts(s):
    """把 '2026年10月22日' 转成 UTC ISO 时间戳（精确到日）。"""
    if not s:
        return None
    m = _CN_DATE_RE.match(str(s).strip())
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return datetime(y, mo, d, 0, 0, 0, tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def parse_post(post: dict, portal: str) -> dict:
    """把一条腾讯原始职位记录解析为 bytedance_jobs 数据库行 dict。

    必须始终返回全量 key（None 保留为 null），
    否则 PostgREST 批量插入会因各行 key 不一致报 PGRST102。
    """
    from crawler.core.model import normalize_job_location
    return normalize_job_location({
        **classify(SOURCE, portal, post),
        "job_id": str(post.get("PostId") or ""),
        "type": portal,
        "title": post.get("RecruitPostName"),
        "sub_title": None,
        "job_code": post.get("ProductName") or None,          # 产品线
        "description": post.get("Responsibility"),             # 职位职责
        "requirement": post.get("RequireWorkYearsName") or None,  # 经验要求
        "job_category_id": None,
        "job_category_name": post.get("CategoryName"),         # 岗位类别
        "job_category_en_name": None,
        "recruit_type_id": None,
        "recruit_type_name": portal,                           # 社招/校招
        "recruit_type_en_name": None,
        "city_code": post.get("CountryName") or None,          # 国家
        "city_name": post.get("LocationName"),                  # 城市
        "city_en_name": None,
        "city_list": None,
        "address": post.get("PostURL"),                         # 职位详情页链接
        "address_list": None,
        "job_hot_flag": (bool(post.get("IsValid")) if post.get("IsValid") is not None else None),
        "job_subject": None,
        "job_function": None,
        "department_id": post.get("BGName") or None,           # BG 集团（IEG/S3...）
        "job_process_id": str(post.get("RecruitPostId")) if post.get("RecruitPostId") else None,
        "min_salary": None, "max_salary": None, "currency": None,
        "head_count": None, "required_degree": None,
        "min_level": None, "max_level": None,
        "storefront_mode": None, "process_type": None,
        "publish_time": _last_update_to_ts(post.get("LastUpdateTime")),
        "expiry_time": None,
        "raw_data": post,
        "source": SOURCE,
    })


