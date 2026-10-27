import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock,patch
from crawler import paths
from crawler.sources.alibaba.society import load_sites, parse_post, run
from crawler.core.engine import crawl
from crawler.core.queue import PendingQueue


class SocietyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        for name in ['STATE_DIR','OUTPUT_DIR']:
            p=patch.object(paths,name,os.path.join(self.tmp.name,name));p.start();self.addCleanup(p.stop)
        self.q=PendingQueue(self.tmp.name+'/q.db')
        self.sites=load_sites()['sites']

    def test_site_name_and_detail_url_are_not_taotian(self):
        site=next(s for s in self.sites if s['id']=='aidc')
        row=parse_post({'id':1,'name':'职位','positionUrl':'/off-campus/position-detail?positionId=1&track_id=abc'},site)
        self.assertEqual(row['source_site'],'aidc')
        self.assertEqual(row['business_unit'],'阿里国际')
        self.assertEqual(row['job_url'],'https://aidc-jobs.alibaba.com/zh/off-campus/position-detail?positionId=1')

    def test_same_id_at_different_sites_is_preserved(self):
        for site in self.sites[:2]:
            self.q.enqueue([parse_post({'id':1},site)],'alibaba','society')
        self.assertEqual(self.q.pending_count(),2)
        self.q.mark_pushed(self.q.dequeue(1))
        self.assertEqual(self.q.pending_count(),1)

    def test_existing_role_skips_parse_even_when_content_changed(self):
        row={'source':'tencent','job_id':'1','title':'original'}
        self.q.enqueue([row],'tencent','society')
        parse=MagicMock(side_effect=AssertionError('must not parse'))
        result=crawl(source='tencent',portal='society',namespace='test',
                     fetch=lambda p:([{'id':1,'title':'changed'}],1),parse=parse,
                     page_size=50,full=True,queue=self.q,interval=0)
        self.assertEqual(result['skipped_existing'],1)
        self.assertEqual(result['queued'],0)
        self.assertEqual(self.q.dequeue(1)[0]['title'],'original')

    def test_synced_fingerprint_still_skips_existing_role(self):
        self.q.enqueue([{'job_id':'1'}],'tencent','society')
        self.q.mark_pushed(self.q.dequeue(1))
        parse=MagicMock(side_effect=AssertionError('must not parse'))
        result=crawl(source='tencent',portal='society',namespace='test',
                     fetch=lambda p:([{'id':1}],1),parse=parse,page_size=50,full=True,queue=self.q,interval=0)
        self.assertEqual(result['skipped_existing'],1)
        self.assertEqual(self.q.pending_count(),0)

    def test_refresh_is_explicit_and_updates_changed_role(self):
        self.q.enqueue([{'job_id':'1','title':'old'}],'tencent','society')
        result=crawl(source='tencent',portal='society',namespace='test',
                     fetch=lambda p:([{'id':1,'job_id':'1','title':'new'}],1),parse=lambda x:x,
                     page_size=50,full=True,queue=self.q,interval=0,skip_existing=False)
        self.assertEqual(result['queued'],1)
        self.assertEqual(self.q.dequeue(1)[0]['title'],'new')

    def test_registry_flow_empty_site_is_success(self):
        def client(site,defaults,interval):
            mock=MagicMock();mock.search.return_value={'datas':[],'totalCount':0};return mock
        result=run(site_id='alisports',queue=self.q,client_factory=client,full=True,request_interval=0)
        self.assertTrue(result['complete'])
        self.assertEqual(result['queued'],0)

    def test_registry_flow_default_skips_detail_requests(self):
        c=MagicMock();c.search.return_value={'datas':[{'id':1,'name':'职位'}],'totalCount':1}
        result=run(site_id='fliggy',queue=self.q,client_factory=lambda *a,**k:c,full=True,request_interval=0)
        c.detail.assert_not_called()
        self.assertEqual(result['queued'],1)
        again=run(site_id='fliggy',queue=self.q,client_factory=lambda *a,**k:c,full=True,request_interval=0)
        self.assertEqual(again['skipped_existing'],1)

    def test_v3_queue_migrates_taotian_site_and_history(self):
        db=self.tmp.name+'/old.db'
        row={'job_id':'1','source':'alibaba','type':'society','recruitment_type':'society','raw_data':{}}
        with sqlite3.connect(db) as c:
            c.execute("CREATE TABLE pending_jobs(seq INTEGER PRIMARY KEY AUTOINCREMENT,source TEXT,portal TEXT,batch_id TEXT,job_id TEXT,payload TEXT,enqueued_at TEXT,version INTEGER,UNIQUE(source,portal,batch_id,job_id))")
            c.execute('INSERT INTO pending_jobs VALUES(1,?,?,?,?,?,?,1)',('alibaba','society','','1',json.dumps(row),'now'))
        q=PendingQueue(db)
        self.assertEqual(q.dequeue(1)[0]['source_site'],'taotian')
        self.assertTrue(q.contains('alibaba','society','1',source_site='taotian'))
        self.assertFalse(q.contains('alibaba','society','1',source_site='fliggy'))


class WindowTests(unittest.TestCase):
    def test_window_partition_collects_unique_records(self):
        from crawler.sources.alibaba.society import SocietyClient
        config=load_sites();site=dict(config['sites'][0],result_window=100)
        client=SocietyClient(site,config['defaults'],interval=0)
        def search(page,size,filters=None):
            ids=list(range(100,150)) if filters else list(range(150))
            start=(page-1)*size
            return {'datas':[{'id':i} for i in ids[start:start+size]],'totalCount':len(ids)}
        with patch.object(client,'_search',side_effect=search),patch.object(client,'call',return_value=[{'code':'1','name':'城市'}]):
            self.assertEqual(client.search(3,50)['totalCount'],150)
            self.assertEqual([r['id'] for r in client.search(3,50)['datas']],list(range(100,150)))

    def test_window_missing_records_remains_failure(self):
        from crawler.sources.alibaba.society import SocietyClient
        config=load_sites();site=dict(config['sites'][0],result_window=100)
        client=SocietyClient(site,config['defaults'],interval=0)
        with patch.object(client,'_search',return_value={'datas':[{'id':1}],'totalCount':150}),patch.object(client,'call',return_value=[]):
            with self.assertRaisesRegex(RuntimeError,'仅覆盖'):client.search(1,50)


class RoutingTests(unittest.TestCase):
    def test_alibaba_society_dispatch_uses_new_registry_entry(self):
        from crawler.sources.alibaba import portal as alibaba_source
        with patch('crawler.sources.alibaba.society.run',return_value={'queued':0}) as route:
            q=MagicMock()
            alibaba_source.run('society',full=True,queue=q)
        route.assert_called_once_with(full=True,max_pages_incremental=50,request_interval=0.4,
                                      queue=q,page_size=50,skip_existing=True)

    def test_refresh_flag_reaches_source_dispatch(self):
        import run as entry
        with patch.object(entry,'crawl_source') as route,patch.object(entry.pending_queue,'default_queue') as q:
            q.return_value.pending_count.return_value=0
            entry.main(['crawl','--source','alibaba','--portal','society','--refresh-existing'])
        route.assert_called_once_with('alibaba',['society'],False,50,0.4,50,skip_existing=False)
