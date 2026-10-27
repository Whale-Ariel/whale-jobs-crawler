-- 新安装依次执行001、002、003；已有v2表仅执行003。
BEGIN;
ALTER TABLE recruitment_jobs ADD COLUMN IF NOT EXISTS source_site text NOT NULL DEFAULT '';
-- 旧版只抓淘天社招，补全来源；校招及字节腾讯使用空站点维度。
UPDATE recruitment_jobs SET source_site='taotian'
WHERE source='alibaba' AND recruitment_type='society' AND source_site='';
ALTER TABLE recruitment_jobs DROP CONSTRAINT IF EXISTS recruitment_jobs_pkey;
ALTER TABLE recruitment_jobs ADD CONSTRAINT recruitment_jobs_pkey
PRIMARY KEY(source,recruitment_type,batch_id,source_site,job_id);
CREATE INDEX IF NOT EXISTS recruitment_jobs_source_site ON recruitment_jobs(source,source_site,recruitment_type);
DO $site_view$
BEGIN
IF current_setting('server_version_num')::integer >= 150000 THEN
EXECUTE $definition$
CREATE OR REPLACE VIEW recruitment_job_organizations WITH (security_invoker=true) AS
SELECT j.source,j.recruitment_type,j.batch_id,j.job_id,j.title,
       org.value->>'circle_code' AS circle_code,
       org.value->>'business_unit' AS business_unit,
       dept.value->>'department_code' AS department_code,
       dept.value->>'department_name' AS department_name,
       city.value->>'code' AS city_code,city.value->>'name' AS city_name,j.source_site
FROM recruitment_jobs AS j
CROSS JOIN LATERAL jsonb_array_elements(j.organization_assignments) AS org(value)
LEFT JOIN LATERAL jsonb_array_elements(COALESCE(org.value->'departments','[]'::jsonb)) AS dept(value) ON true
LEFT JOIN LATERAL jsonb_array_elements(COALESCE(dept.value->'work_cities','[]'::jsonb)) AS city(value) ON true
$definition$;
END IF;
END;
$site_view$;
COMMIT;
-- source_site必须与站点配置id一致，不按显示名称猜测域名。
