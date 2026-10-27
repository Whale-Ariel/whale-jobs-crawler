-- 先执行001。升级既有表；不清空职位，阿里星并回应届生并保留项目标签。
BEGIN;
ALTER TABLE recruitment_jobs
  ADD COLUMN IF NOT EXISTS batch_id text NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS batch_name text,
  ADD COLUMN IF NOT EXISTS program_tags jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS organization_assignments jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE recruitment_jobs DROP CONSTRAINT IF EXISTS recruitment_jobs_pkey;
UPDATE recruitment_jobs
SET batch_id = COALESCE(NULLIF(batch_id,''), CASE WHEN source='alibaba' THEN raw_data->>'batchId' END, ''),
    batch_name = COALESCE(batch_name, CASE WHEN source='alibaba' THEN raw_data->>'batchName' END);
UPDATE recruitment_jobs SET program_tags =
    (SELECT jsonb_agg(DISTINCT tag) FROM jsonb_array_elements(program_tags || '["ali_star"]'::jsonb) AS tags(tag))
WHERE source='alibaba' AND recruitment_type='ali_star';
-- 已存在应届生全集记录时合并项目标签，再移除同一身份的旧阿里星副本。
UPDATE recruitment_jobs AS graduate SET program_tags =
    (SELECT jsonb_agg(DISTINCT tag) FROM jsonb_array_elements(graduate.program_tags || '["ali_star"]'::jsonb) AS tags(tag))
WHERE graduate.source='alibaba' AND graduate.recruitment_type='graduate' AND EXISTS (
    SELECT 1 FROM recruitment_jobs AS star WHERE star.source=graduate.source
      AND star.recruitment_type='ali_star' AND star.batch_id=graduate.batch_id AND star.job_id=graduate.job_id);
DELETE FROM recruitment_jobs AS star WHERE star.source='alibaba' AND star.recruitment_type='ali_star' AND EXISTS (
    SELECT 1 FROM recruitment_jobs AS graduate WHERE graduate.source=star.source
      AND graduate.recruitment_type='graduate' AND graduate.batch_id=star.batch_id AND graduate.job_id=star.job_id);
UPDATE recruitment_jobs SET recruitment_type='graduate', recruitment_name='应届生'
WHERE source='alibaba' AND recruitment_type='ali_star';
UPDATE recruitment_jobs SET business_unit=NULL WHERE jsonb_array_length(COALESCE(business_units,'[]'::jsonb)) > 1;
ALTER TABLE recruitment_jobs ADD CONSTRAINT recruitment_jobs_pkey
  PRIMARY KEY(source,recruitment_type,batch_id,job_id);
CREATE INDEX IF NOT EXISTS recruitment_jobs_organizations_gin ON recruitment_jobs USING gin(organization_assignments);
CREATE INDEX IF NOT EXISTS recruitment_jobs_program_tags_gin ON recruitment_jobs USING gin(program_tags);
-- 组织关系嵌入职位JSON，一次upsert原子更新；视图供按集团/部门/城市查询。
-- PostgreSQL15+建立遵循原表权限的视图；旧版本仅升级核心字段，不创建可能越权的视图。
DO $view_migration$
BEGIN
IF current_setting('server_version_num')::integer >= 150000 THEN
EXECUTE $view_definition$
CREATE OR REPLACE VIEW recruitment_job_organizations WITH (security_invoker=true) AS
SELECT j.source,j.recruitment_type,j.batch_id,j.job_id,j.title,
       org.value->>'circle_code' AS circle_code,
       org.value->>'business_unit' AS business_unit,
       dept.value->>'department_code' AS department_code,
       dept.value->>'department_name' AS department_name,
       city.value->>'code' AS city_code,city.value->>'name' AS city_name
FROM recruitment_jobs AS j
CROSS JOIN LATERAL jsonb_array_elements(j.organization_assignments) AS org(value)
LEFT JOIN LATERAL jsonb_array_elements(COALESCE(org.value->'departments','[]'::jsonb)) AS dept(value) ON true
LEFT JOIN LATERAL jsonb_array_elements(COALESCE(dept.value->'work_cities','[]'::jsonb)) AS city(value) ON true
$view_definition$;
ELSE
RAISE NOTICE '组织字段已升级；PG15以下不自动创建组织关系视图，可在原表JSON字段查询。';
END IF;
END;
$view_migration$;
COMMIT;
-- 云端原表/新表权限由数据库管理入口配置；本迁移不扩大客户端权限。
