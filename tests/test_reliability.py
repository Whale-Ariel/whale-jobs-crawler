import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from crawler import paths
from crawler.core import state as state_store
from crawler.core.queue import PendingQueue
from crawler.core.engine import crawl
from crawler.sources.alibaba.portal import parse_post
from crawler.taxonomy import ALIBABA_UNITS


class ReliabilityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        for key in ('STATE_DIR', 'OUTPUT_DIR'):
            p = patch.object(paths, key, os.path.join(self.root, key))
            p.start(); self.addCleanup(p.stop)
        paths.ensure_dirs()
        self.q = PendingQueue(os.path.join(self.root, 'q.db'))

    def row(self, jid='1', title='old'):
        return {'job_id': jid, 'source': 'tencent', 'type':'society', 'title': title}

    def test_confirmation_preserves_concurrent_update(self):
        self.q.enqueue([self.row()], 'tencent', 'society')
        old = self.q.dequeue(1)
        self.q.enqueue([self.row(title='new')], 'tencent', 'society')
        self.assertEqual(self.q.mark_pushed(old), 0)
        self.assertEqual(self.q.dequeue(1)[0]['title'], 'new')

    def test_same_id_different_channel_does_not_overwrite(self):
        self.q.enqueue([self.row()], 'tencent', 'society')
        self.q.enqueue([self.row()], 'tencent', 'campus')
        self.q.mark_pushed(self.q.dequeue(1))
        self.assertEqual(self.q.pending_count(), 1)

    def test_unchanged_payload_after_sync_not_enqueued_again(self):
        self.q.enqueue([self.row()], 'tencent', 'society')
        self.q.mark_pushed(self.q.dequeue(1))
        self.assertEqual(self.q.enqueue([self.row()], 'tencent', 'society'), 0)
        self.assertEqual(self.q.enqueue([self.row(title='changed')], 'tencent', 'society'), 1)

    def test_failed_enqueue_does_not_advance_checkpoint(self):
        state_store.save_progress('test', 0)
        with patch.object(self.q, 'enqueue', side_effect=RuntimeError('disk full')):
            with self.assertRaises(RuntimeError):
                crawl(source='tencent', portal='society', namespace='test',
                      fetch=lambda n: ([self.row()], 2), parse=lambda x:x,
                      page_size=1, offset_mode=True, full=True, queue=self.q)
        self.assertEqual(state_store.load_progress('test'), 0)
        with open(os.path.join(paths.OUTPUT_DIR,'test_last_run_summary.json')) as f:
            self.assertEqual(json.load(f)['status'],'failed')

    def test_second_page_failure_first_page_durable_and_resume(self):
        def fetch(n):
            if n == 1:
                raise RuntimeError('network')
            return [self.row()], 2
        with self.assertRaises(RuntimeError):
            crawl(source='tencent', portal='society', namespace='test',fetch=fetch,
                  parse=lambda x:x,page_size=1,offset_mode=True,full=True,queue=self.q,interval=0)
        self.assertEqual(self.q.pending_count(),1)
        self.assertEqual(state_store.load_progress('test'),1)
        res=crawl(source='tencent',portal='society',namespace='test',
                  fetch=lambda n: ([self.row('2')],2),parse=lambda x:x,page_size=1,
                  offset_mode=True,full=True,queue=self.q,interval=0)
        self.assertTrue(res['complete'])
        self.assertEqual(self.q.pending_count(),2)

    def test_incremental_known_page_does_not_hide_new_next_page(self):
        state_store.save_known_ids('test',{'1'})
        res=crawl(source='tencent',portal='society',namespace='test',
                  fetch=lambda n: ([self.row(str(n+1))],2),parse=lambda x:x,
                  page_size=1,offset_mode=True,max_pages=2,queue=self.q,interval=0)
        self.assertEqual(res['new_rows'],1)
        self.assertEqual(self.q.pending_count(),2)

    def test_page_limit_reported_as_incomplete(self):
        res=crawl(source='tencent',portal='society',namespace='test',
                  fetch=lambda n: ([self.row()],100),parse=lambda x:x,page_size=1,
                  max_pages=1,queue=self.q,interval=0)
        self.assertFalse(res['complete'])
        self.assertEqual(res['stop_reason'],'page_limit')

    def test_channel_lock_rejects_overlap(self):
        with state_store.channel_lock('test'):
            with self.assertRaises(RuntimeError):
                with state_store.channel_lock('test'):
                    pass

    def test_legacy_queue_migration_preserves_data(self):
        db=os.path.join(self.root,'legacy.db')
        with sqlite3.connect(db) as c:
            c.execute('CREATE TABLE pending_jobs(seq INTEGER PRIMARY KEY AUTOINCREMENT,source TEXT,portal TEXT,job_id TEXT,payload TEXT,enqueued_at TEXT,UNIQUE(source, job_id))')
            c.execute('INSERT INTO pending_jobs VALUES(1,?,?,?,?,?)',('tencent','society','1',json.dumps(self.row()),'now'))
        q=PendingQueue(db)
        restored=q.dequeue(1)[0]
        for key,value in self.row().items():
            self.assertEqual(restored[key],value)
        self.assertEqual(restored['company'],'腾讯')
        q.enqueue([self.row()], 'tencent','campus')
        self.assertEqual(q.pending_count(),2)

    def test_legacy_unsafe_checkpoint_restarts_from_zero(self):
        state_store.atomic_json(os.path.join(paths.STATE_DIR,'legacy_checkpoint.json'), {'value':500})
        state_store.atomic_json(os.path.join(paths.STATE_DIR,'progress_legacy.json'), {'value':500})
        self.assertEqual(state_store.load_progress('legacy',0),0)

    def test_changed_page_size_restarts_paged_crawl(self):
        state_store.save_progress('test',4,page_size=10)
        self.assertEqual(state_store.load_progress('test',1,page_size=50),1)
        self.assertEqual(state_store.load_progress('test',1,page_size=10),4)


class AlibabaTest(unittest.TestCase):
    def test_society_registry_has_eighteen_sites(self):
        from crawler.sources.alibaba.society import load_sites
        self.assertEqual(len(load_sites()['sites']),18)

    def test_group_campus_preserves_actual_business_unit(self):
        row=parse_post({'id':1,'name':'工程师','circleNames':['千问办公'],
                        'circleCodeList':['1'],'workLocations':['杭州']},'regular_intern')
        self.assertEqual(row['company'],'阿里巴巴')
        self.assertEqual(row['business_unit'],'千问办公')
        self.assertEqual(row['recruitment_type'],'regular_intern')
        self.assertEqual(row['type'],'campus')

    def test_society_site_fallback_not_applied_to_unknown_campus(self):
        self.assertEqual(parse_post({'id':1},'society')['business_unit'],'淘天集团')
        self.assertIsNone(parse_post({'id':1},'ali_star')['business_unit'])

    def test_business_unit_alias_and_multi_units(self):
        row=parse_post({'id':1,'circleNames':['阿里国际数字商业集团','菜鸟驿站']},'research_intern')
        self.assertEqual(row['business_units'],['阿里国际','菜鸟驿站'])
        self.assertEqual(len(ALIBABA_UNITS),len(set(ALIBABA_UNITS)))

    def test_tracking_changes_do_not_requeue(self):
        with tempfile.TemporaryDirectory() as root:
            q=PendingQueue(root+'/q.db')
            a=parse_post({'id':1,'trackId':'a','positionUrl':'/x?id=1&track_id=a'},'society')
            b=parse_post({'id':1,'trackId':'b','positionUrl':'/x?id=1&track_id=b'},'society')
            q.enqueue([a],'alibaba','society');q.mark_pushed(q.dequeue(1))
            self.assertEqual(q.enqueue([b],'alibaba','society'),0)


class SourceProtocolTest(unittest.TestCase):
    def test_bytedance_request_uses_fifty_in_url_and_body(self):
        import io
        from crawler.sources.bytedance import client as source
        from unittest.mock import MagicMock
        response=MagicMock()
        response.__enter__.return_value.read.return_value=b'{"code":0,"data":{"count":0,"job_post_list":[]}}'
        with patch.object(source.urllib.request,'urlopen',return_value=response) as network:
            source.fetch_page(2,0,source.build_headers('society'))
        req=network.call_args[0][0]
        self.assertEqual(json.loads(req.data)['limit'],50)
        self.assertIn('limit=50',req.full_url)

    def test_tencent_society_filter_is_explicit(self):
        from crawler.sources.tencent import client as tencent_source
        self.assertEqual(tencent_source.ATTR_IDS['society'],'1')
        self.assertEqual(tencent_source.ATTR_IDS['campus'],'2,3')
