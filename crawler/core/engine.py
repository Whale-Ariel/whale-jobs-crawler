"""可靠分页：逐页提交后推进断点，增量扫描不依赖排序；状态和 tqdm 同步更新。"""
import os
import time
from datetime import datetime
from tqdm.auto import tqdm
from crawler import paths
from crawler.core import state as state_store
from crawler.core import queue as pending_queue


def crawl(*, source, portal, namespace, fetch, parse, page_size, offset_mode=False,
          full=False, max_pages=50, interval=0.4, queue=None, context=None, skip_existing=True):
    if not 1 <= page_size <= 50 or max_pages < 1 or interval < 0:
        raise ValueError('page_size 必须在1至50之间，pages 必须为正数，interval 不得小于零')
    paths.ensure_dirs()
    queue = queue if queue is not None else pending_queue.default_queue()
    summary_path = os.path.join(paths.OUTPUT_DIR, namespace+'_last_run_summary.json')
    summary = dict(portal=portal if source == 'bytedance' else f'{source}-{portal}',
                   source=source, mode='full' if full else 'incremental', new_rows=0,
                   queued=0, skipped_existing=0, pages=0, complete=False, status='running',
                   started_at=datetime.now().astimezone().isoformat())
    summary.update({key:value for key,value in (context or {}).items() if key in {'batch_id','batch_name','source_site','business_unit'}})
    with state_store.channel_lock(namespace):
        try:
            known = state_store.load_known_ids(namespace)
            default = 0 if offset_mode else 1
            cursor = state_store.load_progress(namespace, default, page_size=page_size) if full else default
            initial = cursor if offset_mode else (cursor-1)*page_size
            state_store.atomic_json(summary_path, summary)
            with tqdm(desc=f'{source}/{portal}', unit='职位', initial=initial,
                      dynamic_ncols=True) as bar:
                while full or summary['pages'] < max_pages:
                    jobs, total = fetch(cursor)
                    if total is not None:
                        if not isinstance(total, int) or total < 0:
                            raise ValueError('接口职位总数不是非负整数')
                        bar.total = total
                    if not isinstance(jobs, list):
                        raise ValueError('接口职位列表结构错误')
                    if not jobs:
                        consumed = cursor if offset_mode else (cursor-1)*page_size
                        if total is not None and consumed < total:
                            raise RuntimeError(f'{source}/{portal}: 总数 {total} 尚未抓完却返回空页，保留断点')
                        summary['complete'] = True
                        break
                    rows = []
                    for job in jobs:
                        raw_id = job.get('id') or job.get('PostId') or job.get('job_id')
                        if skip_existing and raw_id and queue.contains(source,portal,str(raw_id),
                            batch_id=summary.get('batch_id',''),source_site=summary.get('source_site','')):
                            known.add(str(raw_id))
                            summary['skipped_existing'] += 1
                            continue
                        row = parse(job)
                        jid = row['job_id']
                        if not jid:
                            raise ValueError(f'{source}/{portal}: 接口返回缺少 ID 的职位')
                        if jid not in known:
                            summary['new_rows'] += 1
                        known.add(jid)
                        rows.append(row)
                    # 先提交职位，再推进断点。后续写状态失败时，重抓只会幂等入队。
                    summary['queued'] += queue.enqueue(rows, source, portal)
                    state_store.save_known_ids(namespace, known)
                    cursor += len(jobs) if offset_mode else 1
                    if full:
                        state_store.save_progress(namespace, cursor, page_size=page_size)
                    summary['pages'] += 1
                    summary['next_cursor'] = cursor
                    summary['total'] = total
                    bar.update(len(jobs))
                    bar.set_postfix(page=summary['pages'], queued=summary['queued'], new=summary['new_rows'], skipped=summary['skipped_existing'])
                    consumed = cursor if offset_mode else (cursor-1)*page_size
                    # 有 total 的源：总数抓满即止；页不满也视作末页。
                    # 无 total 的源（如京东社招）：翻页靠空页（jobs==[]）终止，
                    # 不满页不作为结束依据（服务端可能稳定返回满页，仅末页不满），
                    # 交给 max_pages 兜底，避免第 N 页因 skip/去重导致误停。
                    if total is not None:
                        if consumed >= total or len(jobs) < page_size:
                            summary['complete'] = True
                            break
                    else:
                        if len(jobs) == 0:
                            summary['complete'] = True
                            break
                    state_store.atomic_json(summary_path, summary)
                    if full or summary['pages'] < max_pages:
                        time.sleep(interval)
            if full and summary['complete']:
                state_store.clear_progress(namespace)
            summary.update(status='finished', stop_reason='exhausted' if summary['complete'] else 'page_limit',
                           finished_at=datetime.now().astimezone().isoformat())
            state_store.atomic_json(summary_path, summary)
            return summary
        except BaseException as error:
            summary.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                           error=str(error)[:500], finished_at=datetime.now().astimezone().isoformat())
            try:
                state_store.atomic_json(summary_path, summary)
            except OSError:
                pass  # 磁盘故障时保留原异常；已提交的队列/断点仍可恢复。
            raise
