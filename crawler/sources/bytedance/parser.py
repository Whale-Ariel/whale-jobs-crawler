"""字节职位字段映射。"""
from datetime import datetime, timezone

from crawler.taxonomy import classify

SOURCE = "bytedance"

def _ms_to_ts(ms):
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()
    except Exception:  # noqa: BLE001
        return None


def parse_job(job: dict, jtype: str) -> dict:
    """把一条原始职位记录解析为数据库行 dict。

    注意：必须始终返回全量 key（None 保留为 null），
    否则 PostgREST 批量插入会因各行 key 不一致报 PGRST102。
    """
    cat = job.get("job_category") or {}
    rt = job.get("recruit_type") or {}
    city = job.get("city_info") or {}
    info = job.get("job_post_info") or {}
    row = {
        "job_id": str(job.get("id") or ""),
        "type": jtype,
        "title": job.get("title"),
        "sub_title": job.get("sub_title"),
        "job_code": job.get("code"),
        "description": job.get("description"),
        "requirement": job.get("requirement"),
        "job_category_id": str(cat.get("id")) if cat.get("id") else None,
        "job_category_name": cat.get("name"),
        "job_category_en_name": cat.get("en_name"),
        "recruit_type_id": str(rt.get("id")) if rt.get("id") else None,
        "recruit_type_name": rt.get("name"),
        "recruit_type_en_name": rt.get("en_name"),
        "city_code": city.get("code"),
        "city_name": city.get("name"),
        "city_en_name": city.get("en_name"),
        "city_list": job.get("city_list"),
        "address": info.get("address"),
        "address_list": info.get("address_list"),
        # 云端该列为 boolean，接口可能返回整数（如 2），统一转为 True/False/None
        "job_hot_flag": (bool(job["job_hot_flag"]) if job.get("job_hot_flag") is not None else None),
        "job_subject": job.get("job_subject"),
        "job_function": job.get("job_function"),
        "department_id": str(job.get("department_id")) if job.get("department_id") else None,
        "job_process_id": str(job.get("job_process_id")) if job.get("job_process_id") else None,
        "min_salary": info.get("min_salary"),
        "max_salary": info.get("max_salary"),
        "currency": info.get("currency"),
        "head_count": info.get("head_count"),
        "required_degree": info.get("required_degree"),
        "min_level": str(info.get("min_level")) if info.get("min_level") is not None else None,
        "max_level": str(info.get("max_level")) if info.get("max_level") is not None else None,
        "storefront_mode": job.get("storefront_mode"),
        "process_type": job.get("process_type"),
        "publish_time": _ms_to_ts(job.get("publish_time")),
        "expiry_time": _ms_to_ts(info.get("expiry_time")),
        "raw_data": job,
        "source": SOURCE,
    }
    row.update(classify(SOURCE, jtype, job))
    from crawler.core.model import normalize_job_location
    return normalize_job_location(row)


