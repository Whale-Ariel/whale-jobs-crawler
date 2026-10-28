# -*- coding: utf-8 -*-
"""试抓拼多多社招：按官网总数翻页，逐条补详情，写入 CSV。

列表和详情的 anti_content 由官网自己的请求封装生成，脚本只在已打开的职位页里调用它。
"""
import argparse
import csv
import math
import sys
import time
from pathlib import Path

from crawler.core.text import text

ROOT = Path(__file__).resolve().parent
LIST_URL = 'https://careers.pddglobalhr.com/jobs'
PAGE_SIZE = 10
COLUMNS = [
    'code', 'name', 'work_location', 'job', 'recruit_type',
    'update_time', 'update_date', 'job_duty', 'serve_requirement', 'bonus', 'job_url',
]

LIST_CALL = """
async (page) => {
  const api = window.__pddRequire(78948);
  try {
    const data = await api.Go({
      job: '', page, pageSize: 10, name: '', workLocationList: [],
    });
    if (!data || !Array.isArray(data.list)) {
      throw new Error('列表返回缺少 list: ' + JSON.stringify(data));
    }
    return {list: data.list, total: data.total};
  } catch (error) {
    const detail = error && (error.message || error.errorMsg) || JSON.stringify(error);
    throw new Error('第 ' + page + ' 页列表失败: ' + detail);
  }
}
"""

DETAIL_CALL = """
async (code) => {
  const http = window.__pddRequire(33401);
  try {
    const data = await http.AT({
      url: 'api/recruit/position/detail',
      body: {code},
      isVerification: true,
    });
    if (!data || data.code !== code) {
      throw new Error('详情 code 不一致: ' + code + ' / ' + JSON.stringify(data));
    }
    return data;
  } catch (error) {
    const detail = error && (error.message || error.errorMsg) || JSON.stringify(error);
    throw new Error('详情 ' + code + ' 失败: ' + detail);
  }
}
"""


def page_count(total):
    """总数向上取整。779 条、每页 10 条是 78 页。"""
    if total < 0:
        raise ValueError(f'职位总数不是非负整数: {total}')
    return math.ceil(total / PAGE_SIZE) if total else 0


def launch(playwright, headed):
    options = {
        'headless': not headed,
        'args': ['--disable-blink-features=AutomationControlled'],
        'ignore_default_args': ['--enable-automation'],
    }
    try:
        return playwright.chromium.launch(channel='chrome', **options)
    except Exception:
        return playwright.chromium.launch(**options)


class Session:
    """在职位页里调用官网自己的请求封装。54001 时留在当前窗口，等人完成验证。"""

    def __init__(self, playwright, headed):
        self.playwright = playwright
        self.headed = headed
        self.browser = None
        self.page = None
        self.open()

    def open(self):
        self.close()
        self.browser = launch(self.playwright, self.headed)
        self.page = self.browser.new_page(locale='zh-CN')
        self.page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.page.goto(LIST_URL, wait_until='domcontentloaded', timeout=60000)
        self.page.wait_for_function('() => !!self.webpackChunk_N_E', timeout=30000)
        self.page.evaluate(
            """() => new Promise((resolve) => {
              self.webpackChunk_N_E.push([[Symbol('pdd-test')], {}, (require) => {
                window.__pddRequire = require;
                resolve(true);
              }]);
            })"""
        )

    def close(self):
        if self.browser is not None:
            self.browser.close()
            self.browser = None
            self.page = None

    def call(self, expression, argument):
        announced = False
        deadline = None
        while True:
            try:
                return self.page.evaluate(expression, argument)
            except Exception as error:
                message = str(error)
                if '54001' not in message:
                    raise
                if not announced:
                    print('页面要求验证。请在脚本打开的浏览器窗口里完成验证，完成后会自动继续。', flush=True)
                    self.page.bring_to_front()
                    announced = True
                    deadline = time.time() + 600
                if time.time() > deadline:
                    raise RuntimeError('等待验证超过 10 分钟') from error
                time.sleep(5)


def crawl(max_pages=None, max_details=None, headed=True, output=None):
    from playwright.sync_api import sync_playwright

    rows = []
    seen = set()
    handle = None
    with sync_playwright() as playwright:
        session = Session(playwright, headed)
        try:
            first = session.call(LIST_CALL, 1)
            total = int(first['total'])
            pages = page_count(total)
            if max_pages is not None:
                pages = min(pages, max_pages)
            print(f'总数 {total}，每页 {PAGE_SIZE}，抓取 {pages} 页', flush=True)
            lists = {1: first['list']}
            for number in range(2, pages + 1):
                time.sleep(0.6)
                payload = session.call(LIST_CALL, number)
                lists[number] = payload['list']
                print(f'列表 {number}/{pages}，本页 {len(payload["list"])} 条', flush=True)
            collected = []
            for number in range(1, pages + 1):
                jobs = lists[number]
                last = number == page_count(total)
                if not jobs:
                    raise RuntimeError(f'第 {number} 页是空页，总数 {total} 还没抓完')
                if not last and len(jobs) != PAGE_SIZE and max_pages is None:
                    raise RuntimeError(f'第 {number} 页只有 {len(jobs)} 条，不满 {PAGE_SIZE}')
                fresh = 0
                for job in jobs:
                    code = str(job.get('code') or '')
                    if not code:
                        raise RuntimeError(f'第 {number} 页有职位缺少 code')
                    if code in seen:
                        continue
                    seen.add(code)
                    collected.append(job)
                    fresh += 1
                if fresh == 0:
                    raise RuntimeError(f'第 {number} 页没有新的 code，分页没有前进')
            if max_details is not None:
                collected = collected[:max_details]
            print(f'列表去重后 {len(seen)} 条，接口总数 {total}，准备补详情 {len(collected)} 条', flush=True)
            handle = None
            writer = None
            if output is not None:
                output.parent.mkdir(parents=True, exist_ok=True)
                handle = output.open('w', encoding='utf-8-sig', newline='')
                writer = csv.DictWriter(handle, fieldnames=COLUMNS)
                writer.writeheader()
            for index, job in enumerate(collected, 1):
                code = str(job['code'])
                time.sleep(0.15)
                detail = session.call(DETAIL_CALL, code)
                row = {
                    'code': code,
                    'name': detail.get('name') or job.get('name') or '',
                    'work_location': detail.get('workLocation') or job.get('workLocation') or '',
                    'job': job.get('job') or '',
                    'recruit_type': detail.get('recruitType') or '',
                    'update_time': detail.get('updateTime') or job.get('updateTime') or '',
                    'update_date': job.get('updateDate') or '',
                    'job_duty': text(detail.get('jobDuty')) or '',
                    'serve_requirement': text(detail.get('serveRequirement')) or '',
                    'bonus': text(detail.get('bonus')) or '',
                    'job_url': f'https://careers.pddglobalhr.com/jobs/detail?code={code}',
                }
                rows.append(row)
                if writer is not None:
                    writer.writerow(row)
                    handle.flush()
                if index == 1 or index % 20 == 0 or index == len(collected):
                    print(f'详情 {index}/{len(collected)} {code}', flush=True)
        finally:
            if handle is not None:
                handle.close()
            session.close()
    return rows, total


def main():
    parser = argparse.ArgumentParser(description='试抓拼多多社招并保存 CSV')
    parser.add_argument('--max-pages', type=int, default=None, help='只抓前 N 页，默认按总数抓完')
    parser.add_argument('--max-details', type=int, default=None, help='只补前 N 条详情，默认全部')
    parser.add_argument('--output', default=str(ROOT / 'output' / 'pdd_society.csv'))
    parser.add_argument('--headless', action='store_true', help='不显示浏览器。连续翻页时更容易被 54001 拦住')
    args = parser.parse_args()
    path = Path(args.output)
    rows, total = crawl(args.max_pages, args.max_details, headed=not args.headless, output=path)
    print(f'已写入 {len(rows)} 行（接口总数 {total}）: {path}', flush=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\n已中断', flush=True)
        sys.exit(130)
