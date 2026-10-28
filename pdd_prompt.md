
## 拼多多的社招的第一页


curl --url 'https://careers.pddglobalhr.com/api/recruit/position/list' \
  -H 'accept: */*' \
  -H 'accept-language: zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7' \
  -H 'cache-control: no-cache' \
  -H 'content-type: application/json' \
  -b 'bnc-uuid=49abf1f1-5297-4611-a2ba-b3309616101b; _nano_fp=XpmbX5Conp9on5TJXC_cMqGC5hzrHfVJir12agtQ' \
  -H 'dnt: 1' \
  -H 'origin: https://careers.pddglobalhr.com' \
  -H 'pragma: no-cache' \
  -H 'priority: u=1, i' \
  -H 'referer: https://careers.pddglobalhr.com/jobs' \
  -H 'sec-ch-ua: "Not:A-Brand";v="8", "Chromium";v="156", "Google Chrome";v="156"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "macOS"' \
  -H 'sec-fetch-dest: empty' \
  -H 'sec-fetch-mode: cors' \
  -H 'sec-fetch-site: same-origin' \
  -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36' \
  --data-raw '{"job":"","page":1,"pageSize":10,"name":"","workLocationList":[],"anti_content":"0aqWfxUeMwVE9qdJX4qVAs4fklF1t0E_-NmlDgKnDzKztNVf_difYN1X_WU_4N3QjumtYR1Mg6ULi-LZaQ5mJVNeP8n09ycpTanGXyOGEqX06dnY_8n0TyX0E8X0EJn9xKuPIt730XFvMezsUfv-QHMv87M34pIMRKetBUbf5eS317Fs8AEtJUM-kpMt99ssQq0s_Pd09J50dJUYpdv69Otu-G0d3lNXyoypEJniEYns0_NQdfNC7TduUtYdx7ud3lYNYdvS0ltNSnpiTjnYCTXTs9Zl0gcO_VpIIv2PLPVnqS4j0FmHN9qQNNyx4o4lpreci0A8p_UIOVUGuaHONUTt0BifG40kfdpxB6Zvs3WH1WWS3RWFaKlS1zX8xV7jIIC77829T9QrBJO1DxOR9m"}'


## 拼多多的社招第一页的返回值

{
    "success": true,
    "errorCode": 1000000,
    "errorMsg": null,
    "result": {
        "verifyAuthToken": null,
        "list": [
            {
                "name": "招聘经理",
                "code": "C013594",
                "workLocation": "上海",
                "job": "综合类",
                "updateTime": "2026-10-27",
                "updateDate": 1793068159000
            },
            {
                "name": "用户增长产品经理",
                "code": "PR024083",
                "workLocation": "上海",
                "job": "产品类",
                "updateTime": "2026-10-27",
                "updateDate": 1793063766000
            },
            {
                "name": "招商运营（庭院/宠物/乐器）",
                "code": "I020650",
                "workLocation": "深圳",
                "job": "招商运营类",
                "updateTime": "2026-10-26",
                "updateDate": 1793004778000
            },
            {
                "name": "创意广告设计师",
                "code": "VID019637",
                "workLocation": "上海",
                "job": "视觉设计类",
                "updateTime": "2026-10-26",
                "updateDate": 1792983316000
            },
            {
                "name": "供应商管理专家",
                "code": "I013160",
                "workLocation": "上海",
                "job": "招商运营类",
                "updateTime": "2026-10-26",
                "updateDate": 1792981896000
            },
            {
                "name": "搜索算法-图像方向",
                "code": "T013636",
                "workLocation": "上海",
                "job": "研发类",
                "updateTime": "2026-10-26",
                "updateDate": 1792978828000
            },
            {
                "name": "【商业化方向】搜索广告算法工程师",
                "code": "T010589",
                "workLocation": "上海",
                "job": "研发类",
                "updateTime": "2026-10-26",
                "updateDate": 1792978828000
            },
            {
                "name": "【商业化方向】广告算法工程师（内容方向）",
                "code": "T010591",
                "workLocation": "上海",
                "job": "研发类",
                "updateTime": "2026-10-26",
                "updateDate": 1792978828000
            },
            {
                "name": "Web前端研发工程师（商业化方向）",
                "code": "T000196",
                "workLocation": "上海",
                "job": "研发类",
                "updateTime": "2026-10-26",
                "updateDate": 1792978828000
            },
            {
                "name": "【商业化方向】展示广告算法工程师",
                "code": "T010590",
                "workLocation": "上海",
                "job": "研发类",
                "updateTime": "2026-10-26",
                "updateDate": 1792978828000
            }
        ],
        "total": "779"
    }
}


"total": "779" 是总数的意思

那么可以根据这个来进行计算

总页数： (779%10) + 1

可以根据这个页面来判断最终要爬取多少页。


## 拼多多的社招第二页

curl --url 'https://careers.pddglobalhr.com/api/recruit/position/list' \
  -H 'accept: */*' \
  -H 'accept-language: zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7' \
  -H 'cache-control: no-cache' \
  -H 'content-type: application/json' \
  -b 'bnc-uuid=49abf1f1-5297-4611-a2ba-b3309616101b; _nano_fp=XpmbX5Conp9on5TJXC_cMqGC5hzrHfVJir12agtQ' \
  -H 'dnt: 1' \
  -H 'origin: https://careers.pddglobalhr.com' \
  -H 'pragma: no-cache' \
  -H 'priority: u=1, i' \
  -H 'referer: https://careers.pddglobalhr.com/jobs' \
  -H 'sec-ch-ua: "Not:A-Brand";v="8", "Chromium";v="156", "Google Chrome";v="156"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "macOS"' \
  -H 'sec-fetch-dest: empty' \
  -H 'sec-fetch-mode: cors' \
  -H 'sec-fetch-site: same-origin' \
  -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36' \
  --data-raw '{"job":"","page":2,"pageSize":10,"name":"","workLocationList":[],"anti_content":"0aqWtxUkM_VesKzTn0YFX7x_3UZZlxIShhOhiIB6ke2Lzl9WVMwCVQMHrPRVAGiP_gLG12WaEQtipQwEOcYMH7iv3ZZGNN2jF-9WV4T_ckAwPKoYjH7K82LgWcznX8Di_MvEcaBKEA8VApoeHyl1-WqCKdpUAyVWVEH_g0iSPzxlyUincklwPK4Y8X7GygL9nN5j5AVW5PHlq2iF6u2DxowtbAb3HshZifrKT_JfXymDl4NEM66ddqm7du0Dv7wx0hV_QGLvVS1P3qCoVZc3hHNGSp9DikEfwhzUtGpVMfHCCJFxGXvjGt5oeGv-Tpu4GdsSfa5oWdNET8O4G_52K8okROAgKU4b46wnYwYldpJcg9jOU0ylgeqlAeBNKalgwxlUsycYwyg6Za5K1CFnq_7k-e7O-WvRhkEkWmFtQImLZFKDTVMtMCM-WwEkjVHWQDz1QeK99vv4fnzfZwngWfldWTll_vu0a1qvOldFraYp4_lUuJjUnyvlXaiwSxiA2_qnHldBAxdFrTYl_7unbHqujTjgvJli9x9v0sbnp8xG2QI1vsUK59JGuXvQdRoagf4YYdsGNf3TcMJylJklGQIq0ncY0hYql9KnmyFOflK-_TsewBzE-Lh-3LCS3Ld0VLC-vYm62C7I1iACes290RKy-6-o6Yb4"}'


## 第一页和第二页的关系的判断

--data-raw '{"job":"","page":2,"pageSize":10,"name":  中的 "page":2 是当前第二页的意思。


## 职位详情不在以上抓取到的结果中

https://careers.pddglobalhr.com/jobs/detail?code=PR024083 这是职位详情的页面。

其中 PR024083 是从列表也的结果中找到的

{
    "name": "用户增长产品经理",
    "code": "PR024083",
    "workLocation": "上海",
    "job": "产品类",
    "updateTime": "2026-10-27",
    "updateDate": 1793063766000
},


中的 code 部分


## 具体的详情的获取方式


curl --url 'https://careers.pddglobalhr.com/api/recruit/position/detail' \
  -H 'accept: */*' \
  -H 'accept-language: zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7' \
  -H 'cache-control: no-cache' \
  -H 'content-type: application/json' \
  -b 'bnc-uuid=49abf1f1-5297-4611-a2ba-b3309616101b; _nano_fp=XpmbX5Conp9on5TJXC_cMqGC5hzrHfVJir12agtQ' \
  -H 'dnt: 1' \
  -H 'origin: https://careers.pddglobalhr.com' \
  -H 'pragma: no-cache' \
  -H 'priority: u=1, i' \
  -H 'referer: https://careers.pddglobalhr.com/jobs/detail?code=PR024083' \
  -H 'sec-ch-ua: "Not:A-Brand";v="8", "Chromium";v="156", "Google Chrome";v="156"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "macOS"' \
  -H 'sec-fetch-dest: empty' \
  -H 'sec-fetch-mode: cors' \
  -H 'sec-fetch-site: same-origin' \
  -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36' \
  --data-raw '{"code":"PR024083","anti_content":"0aqAfqnZrjtay99C2nyu6ApBjQTJsJp_x1sDXMTQbQvF1Ic7ffHmKkk_qi7O9zxZR9Hl0IfGR0ObZ5bXILZCCNCJKDxWvh-EeZuh1i17e_6g4edXkethy5pIe9xse-qgY-6vYPhEmSy3APUU_UrrFRCkCJv6mQLWGicol3RrDpJISCToyETxOVYkI3rC0JWaTVrGOBlJiNySHW-ybZhRBIxWDyX3eSGT_BxgD24-o2mqYPr91jmXasR20CDC9VCnXeUrsv9OqCgh8wx58cP6Xi87B0j8OQau2NPQ-lCxeteHP9CdJGlP4kh57b29YIVZoNcBqOI3Msg91U7oOYfO2Osbqwmc9t_HvvrXh1qVkcyIOKoKjyR-qK-bajRhQOaoCslRz1o1DxOR9K"}'


  其中 -H 'referer: https://careers.pddglobalhr.com/jobs/detail?code=PR024083' \ 这一行是关键


   --data-raw '{"code":"PR024083","anti_content":"0aqAfqnZrjtay99C2nyu6ApBjQTJsJp_x1sDXMTQbQvF1Ic7ffHmKkk_qi7O9zxZR9Hl0IfGR0ObZ5bXILZCCNCJKDxWvh-EeZuh1i17e_6g4edXkethy5pIe9xse-qgY-6vYPhEmSy3APUU_UrrFRCkCJv6mQLWGicol3RrDpJISCToyETxOVYkI3rC0JWaTVrGOBlJiNySHW-ybZhRBIxWDyX3eSGT_BxgD24-o2mqYPr91jmXasR20CDC9VCnXeUrsv9OqCgh8wx58cP6Xi87B0j8OQau2NPQ-lCxeteHP9CdJGlP4kh57b29YIVZoNcBqOI3Msg91U7oOYfO2Osbqwmc9t_HvvrXh1qVkcyIOKoKjyR-qK-bajRhQOaoCslRz1o1DxOR9K"}'

   中的 code 也是从列表中来的。



## 职位详情的内容


{
    "success": true,
    "errorCode": 1000000,
    "errorMsg": null,
    "result": {
        "verifyAuthToken": null,
        "name": "用户增长产品经理",
        "code": "PR024083",
        "recruitType": "产品类",
        "workLocation": "上海",
        "job": "product",
        "serveRequirement": "<p>1、本科及以上学历，1年及以上互联网产品工作经验，有知名互联网公司工作经验优先；</p><p>2、对业务数据敏感，有较好的数据分析能力和优秀的逻辑思维，可以从业务数据波动中发现问题，提炼需求；</p><p>3、具有优秀的沟通能力、执行力和产品判断力；</p><p>4、主动追踪业务结果，对产品全生命周期（规划→落地→优化）负责，敢于为决策担责，推动问题闭环解决。</p>",
        "jobDuty": "<p>岗位职责</p><p>1、负责平台物流产品规划与迭代，基于用户分层、场景化策略及增长实验等方法，持续完善用户体验，优化GMV与用户规模等核心指标；</p><p>2、基于消费者端物流体验和供应链全链路视角，持续优化核心物流能力，提升商家履约效率，助力业务规模化增长；</p><p>3、聚焦产品体验，提升全场景物流感知，结合用户调研与数据分析形成用户增长与留存策略。</p>",
        "bonus": "<p>无</p>",
        "updateTime": "2026-10-27"
    }
}