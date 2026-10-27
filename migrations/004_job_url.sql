-- 在001—003之后执行；保留未知办公地址为NULL，不把城市冒充街道地址。
BEGIN;
ALTER TABLE recruitment_jobs ADD COLUMN IF NOT EXISTS job_url text;
UPDATE recruitment_jobs SET job_url=address, address=NULL
WHERE address ~ '^https?://' AND (job_url IS NULL OR job_url='');
UPDATE recruitment_jobs SET job_url='https://jobs.bytedance.com/' ||
CASE WHEN recruitment_type='society' THEN 'experienced' ELSE 'campus' END ||
'/position/' || job_id || '/detail' WHERE source='bytedance';
COMMENT ON COLUMN recruitment_jobs.job_url IS '官网岗位详情页链接，供客户打开';
COMMENT ON COLUMN recruitment_jobs.address IS '实际办公地址；未知为NULL，不存网页链接';
COMMIT;
