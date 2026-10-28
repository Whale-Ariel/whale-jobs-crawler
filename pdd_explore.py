"""探查 careers.pddglobalhr.com 前端的 anti_content 生成机制。

目标：在真实浏览器页面上下文里找到签名函数，验证能否随用随取 fresh token。
"""

import json

from playwright.sync_api import sync_playwright

URL = "https://careers.pddglobalhr.com/jobs"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
        )

        # 记录页面发出的 API 请求，看 anti_content 如何被注入
        api_calls = []

        def on_request(req):
            if "/api/recruit/" in req.url and req.method == "POST":
                api_calls.append({"url": req.url, "body": req.post_data})

        page.on("request", on_request)
        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)

        print("=== 页面自动发出的 API 请求 ===")
        for c in api_calls:
            print(json.dumps(c, ensure_ascii=False)[:300])

        # 在 window 上找可疑的签名函数/对象
        suspects = page.evaluate(
            """() => {
                const keys = Object.keys(window).filter(k =>
                    /anti|sign|token|content|risk|moka/i.test(k));
                const result = {};
                for (const k of keys) {
                    try { result[k] = typeof window[k]; } catch (e) {}
                }
                return result;
            }"""
        )
        print("\n=== window 上的可疑全局 ===")
        print(json.dumps(suspects, ensure_ascii=False, indent=2))

        browser.close()


if __name__ == "__main__":
    main()
