# 招聘采集：16 家公司

统一入口是 `run.py`。抓取只写本地 SQLite，已采集的职位直接跳过。云端同步要另外执行 `run.py sync`。

阿里社招由 `crawler/sources/alibaba/sites.json` 的 18 个站点驱动。阿里校招打开集团首页后发现当前开放批次，不写死届别。

## 代码布局

根目录保留入口、依赖、配置样例和云端迁移。运行时数据在 `state/` 与 `output/`，不进入源码目录。

| 路径 | 职责 |
|---|---|
| `run.py` | 命令行与交互菜单 |
| `crawler/core/` | 分页引擎、本地队列、断点、48 字段模型 |
| `crawler/sync/` | 按限频把本地队列推到云表 `recruitment_jobs` |
| `crawler/replay/` | 从历史 SQL 抽出职位 ID，再查官网后直推云库 |
| `crawler/sources/<公司>/client.py` | 该公司的列表请求 |
| `crawler/sources/<公司>/parser.py` | 该公司的字段解析 |
| `crawler/sources/alibaba/` | 校招会话 `client.py`、社招 `society.py`、调度 `portal.py`、解析 `parser.py`、站点 `sites.json` |
| `crawler/sources/didi/moka.py` | 滴滴校园门户的公开响应解码 |
| `migrations/` | 云端表结构，由管理入口执行，客户端不改远程库 |

继承关系：

```text
Source
├── BytedanceClient          按 offset 翻页
├── TencentClient            按页码翻页
└── JsonSource               带重试的 JSON 会话
    ├── LenientSource        跨页重复 ID 跳过
    │     网易、京东、美团、百度、快手
    └── PortalSource         先做官网初始化；页内或跨页重复 ID 失败
          哔哩哔哩、小红书、滴滴、拼多多、携程、科大讯飞、米哈游、OPPO

CampusClient                 阿里校招的 urllib 会话
└── SocietyClient            阿里社招，按站点配置复用同一套会话
```

新公司在 `crawler/sources/<公司>/` 增加 `client.py` 与 `parser.py`，再登记到 `crawler/sources/__init__.py`。阿里同协议事业部只在 `sites.json` 加一条，站点 `id` 必须唯一。

## 安装与运行

需要 Python 3.10+。

```bash
python3 -m pip install -r requirements.txt

# 16 家公司全部范围，只保存未采集过的职位
python3 run.py crawl --source all --full

# 分组：new = 网易/京东/美团/百度/快手；extra = 其余 8 家
python3 run.py crawl --source new --full
python3 run.py crawl --source extra --full

# 单家、单招聘形式
python3 run.py crawl --source alibaba --portal society --full
python3 run.py crawl --source alibaba --portal campus --full
python3 run.py crawl --source kuaishou --portal internship --full

python3 run.py plan
python3 run.py status
```

不带参数时进入交互菜单。菜单编号与屏幕一致：1 字节、2 腾讯、3 全部、4/5 补录、6 状态、7 同步、8 阿里、9 为 `new`、10 为 `extra`。

默认每页 50 条。百度和拼多多服务端只接受 10 条，客户端会把更大的 `--page-size` 收成 10。`--page-size` 取值 1 到 50，`--interval` 默认 0.4 秒。进度由 `tqdm` 打到标准错误；接 `2>&1 | tail` 会丢掉实时进度。

某一频道失败时继续其余频道，结束时返回非零退出码。已落盘的页保留，重跑从断点继续。

阿里单站：

```bash
python3 -m crawler.sources.alibaba.society --site aliyun --full
```

## 运行规则

| 项目 | 行为 |
|---|---|
| 已有职位 | 用本地 SQLite 指纹判重，跳过解析、详情请求和入队 |
| 已同步职位 | 队列行删除后指纹仍在，继续跳过 |
| 新职位 | 解析后写入本地队列 |
| 列表请求 | 为发现新 ID 会翻完列表，不会因为一页全是已知职位就停 |
| `--full` | 从断点扫到接口给出的列表末尾 |
| 不带 `--full` | 每个频道、站点或批次从第一页起，最多 `--pages` 页（默认 50），汇总里 `complete=false` |
| 断点 | 一整页入队成功后才推进；全量完成后再清除 |
| 空站点 | 0 条正常结束。橙狮体育某次查询没有职位就是这种情况 |
| 云端同步 | 默认关闭 |

“已存在”只查本地指纹，不逐条查云库。删掉 `state/pending_queue.db` 会失去判重历史。

默认按职位身份跳过，官网改了同一职位的正文也不会刷新。需要刷新时：

```bash
python3 run.py crawl --source all --full --refresh-existing
```

指纹相同的不重复入队；正文变了的更新本地待同步记录。本工具保留历史记录，不根据官网列表自动判定下架。

![TKXalv](https://upiclw.oss-cn-beijing.aliyuncs.com/uPic/TKXalv.png)

## 来源与招聘形式

`--source all` 按这个顺序跑。`--portal all` 只跑该公司支持的形式。

| 来源 | 招聘形式 | 与默认规则不同的地方 |
|---|---|---|
| bytedance | society、campus | 社招 `portal_type=2`，校招 `portal_type=3`。断点文件名是 `society` / `campus` |
| tencent | society、campus | 社招 `attrId=1`，校招 `attrId=2,3`。断点文件名是 `tencent_society` / `tencent_campus` |
| alibaba | society、campus，以及 graduate、research_intern、regular_intern、internship、ali_star | 见下文 |
| netease | society、internship、dispatch | 同一列表接口，`workType` 分别为 0、1、2。全职存为 society |
| jd | society、campus | 社招带追踪 cookie，响应是没有 total 的列表，空页结束。校招固定 `planId=45`，页码从 0 开始 |
| meituan | society、campus | 社招 `jobType=3`。校招入口含 1 和 2，其中 2 写入 `program_tags=internship` |
| baidu | society、campus | 表单请求，每页 10 条 |
| kuaishou | society、internship、campus | 社招/实习用官网公开签名。校招固定子项目 `20271779425607` |
| bilibili | society、campus、internship | 先取匿名 CSRF。实习按岗位类型名含“实习”校验 |
| xiaohongshu | society、campus、internship | 校园项目从官网字典发现 regular / intern，不包含 REDstar、Ace。列表先做快照 |
| didi | society、campus、internship | 校招门户 `96064`，实习门户 `6222` 且 `commitments=[实习]` |
| pdd | campus | 每页 10 条。列表没有任职要求，详情补 `serveRequirement` |
| ctrip | society、campus | 身份和链接用稳定的 `fromId`。`retCode=201` 表示成功 |
| iflytek | society、campus | 从北森页面配置读取要展示的字段 |
| mihoyo | society、campus、internship | 校招项目 13、实习项目 4。列表没有职责，必须取详情 |
| oppo | society、campus | 应届项目动态发现，并带 `foreignRecruitmentTypeList=[Graduate]`。`batch_id` 记为 `Graduate` |

京东校招、快手校招、滴滴两个门户、米哈游两个项目的 ID 写在对应 `client.py` / `parser.py`。换届时改这些常量，并让请求参数和解析校验一致。不同 `batch_id` 使用不同断点，互不覆盖。

事业部只采用官网明确返回的组织字段。`address` 只存实际办公地址，没有时为 null；城市在 `city_name` / `city_list`。`job_url` 按官网路由生成，下架或投递时可能失效或要求登录。

### 阿里

社招 18 站：淘天、飞猪、阿里国际、淘宝闪购、阿里云、Token Foundry、千问办公、千问事业部、平头哥、高德、菜鸟、虎鲸文娱、盒马、阿里健康、灵犀互娱、菜鸟驿站、亚博科技、橙狮体育。

每个站点有独立会话、断点和运行汇总。千问事业部首页、菜鸟路径、阿里国际 API 前缀都在站点配置里。列表 channel 使用 `group_official_site`。默认用列表里的职责和要求。配置 `defaults.fetch_details` 为 true 时，只给新职位补详情；配合 `--refresh-existing` 可补已有职位。详情里的 department 留在原始机构标签，不覆盖站点事业部。

阿里云配置了 `result_window: 500`。先取基础窗口，再按城市和机构关键词交叉查询，按职位 ID 取并集。唯一职位数盖不住接口总量就失败，不会把前 500 条当成全量。

校招入口是 `crawler/sources/alibaba/client.py`。`--portal campus` 处理当前全部开放批次，也可以限定：

```bash
python3 run.py crawl --source alibaba --portal graduate --full
python3 run.py crawl --source alibaba --portal research_intern --full
python3 run.py crawl --source alibaba --portal regular_intern --full
python3 run.py crawl --source alibaba --portal campus --batch-id 当前开放批次ID --full
```

应届生全集不加 aliStar 筛选。阿里星是 `program_tags` 里的标签，兼容 `--portal ali_star`，仍写入同一 graduate 身份。一个职位可以对应多个事业部，`organization_assignments` 保留事业群、部门和城市；多个事业群时 `business_unit` 为空，`business_units` 保留全部名称。组织查询按批次、职位 ID 和修改时间缓存一天。跳过已有职位时不再请求组织详情。

### 列表重叠与详情

网易、京东、美团、百度、快手遇到跨页重复 ID 时丢掉已见 ID，继续保留本页新 ID。整页都没有新 ID 则失败。

哔哩哔哩、滴滴、拼多多、科大讯飞、米哈游、OPPO 把页内或跨页重复 ID 视为分页异常并失败。携程先按 `fromId` 去掉同一岗位的多个广告 ID，本页 `fromId` 重复则失败。

小红书先按 `positionId` 做最多 3 轮并集。唯一岗位数等于接口总数后才入库；总量中途变化、并集超出总数或三轮后仍不足都会失败。快照放在 `api_cache`。全量从第一页重跑时重建快照；断点恢复复用同一快照，快照缺失则清断点并报错。

米哈游和拼多多在入库前取详情。滴滴校招和实习在列表没有 `jobDescription` 时取详情。已有职位先跳过，新职位最多 4 个并发，整页成功后才提交。

### 京东社招 cookie

社招请求 `https://zhaopin.jd.com/web/job/job_list`，cookie 写在 `crawler/sources/jd/client.py` 的 `JD_SOCIETY_COOKIES`。这是官网列表随浏览器会话带的追踪 cookie。失效后接口返回登录页或非列表 JSON，抓取失败，不会记成 0 条成功。更新时从浏览器请求里复制最新 cookie。响应没有 total，以空页作为结束。

## 身份与本地数据

去重键是 `(source, recruitment_type, batch_id, source_site, job_id)`。

- 阿里社招：`batch_id` 为空，`source_site` 区分 18 个事业部。
- 阿里校招：`source_site` 为空，`batch_id` 区分届别和实习批次。
- 字节、腾讯：这两项为空，按来源和招聘形式隔离。
- 写死批次的公司把批次放进 `batch_id`，因此换届不会覆盖旧项目。
- 携程的 `job_id` 是 `fromId`。

本地库打开时升级到 schema version 5，保留已有职位、组织关系和已同步指纹。旧淘天社招补上 `source_site=taotian`。迁移前备份在 `state/migration_backups/`。JSON 状态原子写入。同一频道的进程锁禁止并行跑第二次。同步确认带 `seq` / `version`，避免删掉抓取过程中更新过的记录。

产出：

- `state/pending_queue.db`：待同步队列、指纹、组织关系、接口缓存、批次元数据。
- `state/progress_*.json`：未完成的全量断点，完成后删除。
- `output/*_last_run_summary.json`：状态、页数、新增、入队、跳过和完成时间。这些是本地运行产物。

## 云端同步

抓取默认不推云。云表是 `recruitment_jobs`。凭证放在 `config.local.json` 的 `cloud_access_key`，或环境变量 `CRAWLER_CLOUD_ACCESS_KEY`。`CRAWLER_CLOUD_ENDPOINT` 可覆盖默认地址。样例见 `config.example.json`。

新环境由管理入口按顺序执行：

1. `migrations/001_recruitment_jobs.sql`
2. `migrations/002_alibaba_campus_batches.sql`
3. `migrations/003_alibaba_society_sites.sql`
4. `migrations/004_job_url.sql`
5. `migrations/005_dedup_ctrip.sql`

005 删除云上携程用不稳定广告 ID 写入的重复行，保留同一 `fromId` 下较小的 `job_id`。本地升级不会改远程库。新表的读写权限由管理员配置。

```bash
python3 run.py sync --max-rows 300
python3 run.py sync --loop
python3 run.py crawl --source tencent --portal society --sync
```

每批 30 条，批间隔 10 秒。403 从 90 秒起递增冷却。失败的批次留在队列里。`replay` 只支持字节和腾讯的历史 SQL：

```bash
python3 run.py replay --source bytedance --portal society --ts all
python3 run.py replay --source tencent --portal campus --ts 20261023_091454
```

已下架职位不能靠重新查询官网恢复。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

覆盖分页与断点、旧库迁移、阿里 18 站和批次、来源隔离、已有职位跳过、显式刷新、同步确认，以及各公司的解析和分页校验。官网样例 JSON 不在仓库里时，对应样例测试会跳过。
