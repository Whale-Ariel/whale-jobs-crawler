
参考和引用 antdesign 文件夹里的内容，在 backend 文件夹下做如下的事情。

1. 登录页面，仿照 http://localhost:8000/user/login?redirect=%2F

网站的名字：思佳职位检索器
Slogon：用 AI 帮助你找到更适合你的好职位

手机号登录不需要了

更多登录方式不需要了。

2. 按照 http://localhost:8000/welcome 做一个欢迎页面，把项目的 README.md 显示出来


3. 按照 http://localhost:8000/list/table-list 做一个查询表格页面

4. 第三步要实现的具体内容如下

   1. 对 /Users/luosen/WorkBuddy/JobsCrawler/state/pending_queue.db 进行链接
   2. 对 pending_jobs 进行查询
   3. 分页显示，每一页 20 条