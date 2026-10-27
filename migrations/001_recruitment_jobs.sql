-- 新安装：在云数据库SQL控制台依次执行001、002、003；已有v1统一表执行002和003。保留旧表。
BEGIN;
CREATE TABLE IF NOT EXISTS recruitment_jobs (
  job_id text NOT NULL,
  type text,
  title text,
  sub_title text,
  job_code text,
  description text,
  requirement text,
  job_category_id text,
  job_category_name text,
  job_category_en_name text,
  recruit_type_id text,
  recruit_type_name text,
  recruit_type_en_name text,
  city_code text,
  city_name text,
  city_en_name text,
  city_list jsonb,
  address text,
  job_url text,
  address_list jsonb,
  job_hot_flag boolean,
  job_subject jsonb,
  job_function jsonb,
  department_id text,
  job_process_id text,
  min_salary bigint,
  max_salary bigint,
  currency text,
  head_count bigint,
  required_degree text,
  min_level text,
  max_level text,
  storefront_mode bigint,
  process_type bigint,
  publish_time timestamptz,
  expiry_time timestamptz,
  raw_data jsonb,
  source text NOT NULL,
  company text NOT NULL,
  business_unit text,
  business_units jsonb,
  recruitment_type text NOT NULL,
  recruitment_name text,
  batch_id text NOT NULL DEFAULT '',
  batch_name text,
  source_site text NOT NULL DEFAULT '',
  program_tags jsonb NOT NULL DEFAULT '[]'::jsonb,
  organization_assignments jsonb NOT NULL DEFAULT '[]'::jsonb,
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (source, recruitment_type, batch_id, source_site, job_id)
);
CREATE INDEX IF NOT EXISTS recruitment_jobs_classification ON recruitment_jobs(company,business_unit,recruitment_type);
-- 旧表存在时导入历史数据。新表已存在的记录保留，以免覆盖新格式。
DO $migration$
BEGIN
  IF to_regclass('public.bytedance_jobs') IS NOT NULL THEN
    INSERT INTO recruitment_jobs (job_id, type, title, sub_title, job_code, description, requirement, job_category_id, job_category_name, job_category_en_name, recruit_type_id, recruit_type_name, recruit_type_en_name, city_code, city_name, city_en_name, city_list, address, address_list, job_hot_flag, job_subject, job_function, department_id, job_process_id, min_salary, max_salary, currency, head_count, required_degree, min_level, max_level, storefront_mode, process_type, publish_time, expiry_time, raw_data, source, company, business_unit, business_units, recruitment_type, recruitment_name, batch_id, batch_name, program_tags, organization_assignments, source_site)
    SELECT job_id::text, type::text, title::text, sub_title::text, job_code::text, description::text, requirement::text, job_category_id::text, job_category_name::text, job_category_en_name::text, recruit_type_id::text, recruit_type_name::text, recruit_type_en_name::text, city_code::text, city_name::text, city_en_name::text, city_list::jsonb, address::text, address_list::jsonb, job_hot_flag::boolean, job_subject::jsonb, job_function::jsonb, department_id::text, job_process_id::text, min_salary::bigint, max_salary::bigint, currency::text, head_count::bigint, required_degree::text, min_level::text, max_level::text, storefront_mode::bigint, process_type::bigint, publish_time::timestamptz, expiry_time::timestamptz, raw_data::jsonb, COALESCE(NULLIF(source,''),'bytedance'), CASE COALESCE(NULLIF(source,''),'bytedance') WHEN 'bytedance' THEN '字节跳动' WHEN 'tencent' THEN '腾讯' ELSE COALESCE(NULLIF(source,''),'bytedance') END, CASE WHEN source='tencent' THEN raw_data->>'BGName' ELSE NULL END, CASE WHEN source='tencent' AND raw_data->>'BGName' IS NOT NULL THEN jsonb_build_array(raw_data->>'BGName') ELSE '[]'::jsonb END, type::text, CASE type WHEN 'society' THEN '社招' ELSE '校招' END, CASE WHEN source='alibaba' THEN COALESCE(raw_data->>'batchId','') ELSE '' END, CASE WHEN source='alibaba' THEN raw_data->>'batchName' END, '[]'::jsonb, '[]'::jsonb, CASE WHEN source='alibaba' AND type='society' THEN 'taotian' ELSE '' END
    FROM bytedance_jobs WHERE type IN ('society','campus')
    ON CONFLICT (source,recruitment_type,batch_id,source_site,job_id) DO NOTHING;
  END IF;
END;
$migration$;
COMMIT;
-- 请按云平台的访问控制配置该新表的读写策略；客户端 key 不自动获得新表权限。
