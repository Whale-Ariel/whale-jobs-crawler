我读了项目说明、采集代码、查询后台和实际数据。这个项目是一个**招聘官网职位采集与检索系统**，目前包含三部分：

- **采集主程序**：通过 [run.py](/Users/luosen/WorkBuddy/JobsCrawler/run.py) 统一采集字节、腾讯、阿里、网易、京东、美团等 **16 家公司**的职位，涵盖社招、校招和部分实习渠道。
- **职位查询网站**：代码在 [backend](/Users/luosen/WorkBuddy/JobsCrawler/backend)，名字是“思佳职位检索器”。已实现登录、README 欢迎页、职位筛选和每页 20 条的查询表格，直接只读查询本地数据库。配置的启动地址是 `http://127.0.0.1:8001`。
- **拼多多社招专项脚本**：独立通过浏览器调用官网接口、补充职位详情，再导出 CSV；尚未纳入主采集入口的社招流程。

**项目的主要特点**

- **统一字段**：不同公司的数据统一成 48 个字段，包括职位名称、职责、要求、城市、组织、批次、官网链接和原始数据。
- **增量去重、断点续跑**：已采集职位默认跳过，也支持显式刷新；整页保存成功后才推进断点。
- **针对官网差异适配**：例如阿里社招覆盖 18 个站点、校招动态发现批次，部分来源需要补详情或处理分页重复。
- **采集与云同步分开**：先保存本地，再单独同步到云端 `recruitment_jobs` 表；同步失败保留队列。
- **保留历史职位**：不会因为官网列表里消失就自动判定职位下架。

**成果物保存位置**

| 成果物 | 位置 | 当前实际情况 |
|---|---|---|
| 核心职位数据 | [state/pending_queue.db](/Users/luosen/WorkBuddy/JobsCrawler/state/pending_queue.db) | `pending_jobs` 表有 **40,661 条**记录，覆盖 16 家公司；同时保存指纹、组织关系、接口缓存和批次信息 |
| 采集运行汇总 | [output](/Users/luosen/WorkBuddy/JobsCrawler/output) 下的 `*_last_run_summary.json` | 共 **56 份**，记录页数、新增、跳过、完成状态和时间 |
| 拼多多社招导出 | [output/pdd_society.csv](/Users/luosen/WorkBuddy/JobsCrawler/output/pdd_society.csv) | 当前 **733 条**，包含职责、要求及职位链接 |
| 拼多多试抓样本 | [pdd_jobs_smoke.csv](/Users/luosen/WorkBuddy/JobsCrawler/pdd_jobs_smoke.csv) | **2 条**样本 |
| 去重及运行状态 | [state](/Users/luosen/WorkBuddy/JobsCrawler/state) | 包含已知 ID 文件、锁文件及运行时数据库文件 |
| 云端成果 | 云表 `recruitment_jobs` | 已有同步代码和建表迁移；本次未连接云端，无法确认云端实际条数 |

目前需要注意：**56 份运行汇总中，55 份显示完成，京东社招一份显示中断、未完成**。因此，本地已经积累了较完整的多公司职位数据，但不能把所有渠道都视为已全量采集完成。