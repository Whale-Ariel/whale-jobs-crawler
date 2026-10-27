"""招聘职位的统一列定义。解析器和云端写入共用这一份，保证每行字段一致。"""

COLUMNS = [
    "job_id", "type", "title", "sub_title", "job_code",
    "description", "requirement",
    "job_category_id", "job_category_name", "job_category_en_name",
    "recruit_type_id", "recruit_type_name", "recruit_type_en_name",
    "city_code", "city_name", "city_en_name",
    "city_list", "address", "address_list", "job_url",
    "job_hot_flag", "job_subject", "job_function",
    "department_id", "job_process_id",
    "min_salary", "max_salary", "currency", "head_count",
    "required_degree", "min_level", "max_level",
    "storefront_mode", "process_type",
    "publish_time", "expiry_time",
    "raw_data", "source",
    "company", "business_unit", "business_units", "recruitment_type", "recruitment_name",
    "batch_id", "batch_name", "program_tags", "organization_assignments", "source_site",
]
JSONB_COLS = {"city_list", "address_list", "job_subject", "job_function", "raw_data", "business_units", "program_tags", "organization_assignments"}
BOOL_COLS = {"job_hot_flag"}
INT_COLS = {"min_salary", "max_salary", "head_count", "storefront_mode", "process_type"}
