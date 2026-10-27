import io
import json
import os
import sqlite3
import tempfile
import unittest
import urllib.error
from unittest.mock import MagicMock,patch
from crawler import paths
from crawler.sources.alibaba.client import Batch, CampusClient, parse_batches
from crawler.sources.alibaba.portal import organization_assignments, parse_post, run
from crawler.core.queue import PendingQueue


def batches_data():
    return {'graduate':[{'id':20270001,'name':'新届应届生'}],
            'internship':[{'id':303,'name':'日常实习生'},{'id':304,'name':'研究型实习生'}],
            'topTalentPlan':[{'id':20270001,'name':'阿里星','type':'aliStar'}],
            'sequence':['graduate','internship','topTalentPlan']}


def groups():
    return [{'circleCode':'b','name':'阿里云','deptList':[{'deptCode':'d2','name':'云技术',
              'workCityList':[{'code':'2','name':'杭州'}]}]},
            {'circleCode':'a','name':'淘天集团','deptList':[{'deptCode':'d1','name':'淘宝',
              'workCityList':[{'code':'1','name':'北京'}]}]}]


class BatchTests(unittest.TestCase):
    def test_discover_new_year_and_deduplicate_star_batch(self):
        found=parse_batches(batches_data())
        self.assertEqual(len(found),3)
        self.assertEqual(found[0].id,'20270001')
        self.assertTrue(found[0].has_ali_star)
        self.assertEqual(found[0].portal,'graduate')

    def test_new_internship_kind_not_silently_ignored(self):
        found=parse_batches({'internship':[{'id':99,'name':'新实习项目'}]})
        self.assertEqual(found[0].portal,'internship')

    def test_no_batches_is_error(self):
        with self.assertRaises(RuntimeError):parse_batches({'graduate':[]})

    def test_shared_role_preserves_all_orgs_and_no_fake_primary(self):
        batch=Batch('123','应届生','graduate')
        row=parse_post({'id':1,'circleNames':['阿里云','淘天集团'],
                       'circleCodeList':['a','b']},'graduate',batch,organization_assignments(groups()),['ali_star'])
        self.assertIsNone(row['business_unit'])
        self.assertEqual(row['business_units'],['淘天集团','阿里云'])
        self.assertEqual(row['organization_assignments'][0]['business_unit'],'淘天集团')
        self.assertEqual(row['organization_assignments'][0]['circle_code'],'a')
        self.assertEqual(row['batch_id'],'123')
        self.assertEqual(row['program_tags'],['ali_star'])
        self.assertIsNone(row['department_id'])


class ClientTests(unittest.TestCase):
    def response(self,content):
        r=MagicMock();r.__enter__.return_value.read.return_value=content
        return r

    def test_bootstrap_without_browser_cookie(self):
        opener=MagicMock()
        opener.open.side_effect=[self.response(b'window.__sysconfig={__token__: "fresh"}'),
            self.response(json.dumps({'success':True,'content':batches_data()}).encode())]
        c=CampusClient(opener,interval=0)
        self.assertEqual(len(c.batches()),3)
        self.assertIn('_csrf=fresh',opener.open.call_args[0][0].full_url)

    def test_full_search_does_not_send_star_or_department_filter(self):
        c=CampusClient(interval=0)
        with patch.object(c,'call',return_value={'datas':[],'totalCount':0}) as call:
            c.search(Batch('12','year','graduate'),1)
        body=call.call_args[0][1]
        self.assertNotIn('aliStar',body)
        self.assertNotIn('customDeptCode',body)
        self.assertEqual(body['pageSize'],50)

    def test_session_refresh_once_then_explicit_error(self):
        opener=MagicMock()
        opener.open.side_effect=lambda *a,**k: (_ for _ in ()).throw(
            urllib.error.HTTPError('https://campus-talent.alibaba.com',403,'forbidden',{},io.BytesIO()))
        c=CampusClient(opener,interval=0);c.csrf='old'
        with patch.object(c,'bootstrap',side_effect=lambda:setattr(c,'csrf','fresh')) as refresh:
            with self.assertRaisesRegex(RuntimeError,'刷新后仍被拒绝'):c.call('/position/search')
        self.assertEqual(refresh.call_count,1)


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        for name in ['STATE_DIR','OUTPUT_DIR']:
            p=patch.object(paths,name,os.path.join(self.tmp.name,name));p.start();self.addCleanup(p.stop)
        self.q=PendingQueue(self.tmp.name+'/q.db')

    def client(self):
        c=MagicMock()
        c.batches.return_value=parse_batches(batches_data())
        c.conditions.return_value={'searchItems':[]}
        c.star_ids.return_value={'1'}
        c.organizations.return_value=groups()
        def search(batch,page,size,ali_star=None):
            posts=[{'id':1,'name':'共享职位','modifyTime':10}] if batch.portal != 'graduate' or ali_star else [
                {'id':1,'name':'共享职位','modifyTime':10},{'id':2,'name':'普通校招','modifyTime':10}]
            return {'datas':posts,'totalCount':len(posts)}
        c.search.side_effect=search
        return c

    def test_group_flow_includes_ordinary_roles_and_distinct_batches(self):
        c=self.client();summary=run('campus',full=True,queue=self.q,client=c,request_interval=0)
        self.assertTrue(summary['complete'])
        self.assertEqual(self.q.pending_count(),4)
        rows=self.q.dequeue(10)
        graduate=[r for r in rows if r['recruitment_type']=='graduate']
        self.assertEqual(len(graduate),2)
        self.assertEqual(graduate[0]['program_tags'],['ali_star'])
        self.assertEqual(graduate[1]['program_tags'],[])
        with sqlite3.connect(self.q.db_path) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM job_organizations').fetchone()[0],8)
        # 重复抓取不重取组织关系，也不重复入队。
        run('campus',full=True,queue=self.q,client=c,request_interval=0)
        self.assertEqual(c.organizations.call_count,4)
        self.assertEqual(self.q.pending_count(),4)

    def test_star_alias_does_not_create_duplicate_identity(self):
        c=self.client()
        run('graduate',full=True,queue=self.q,client=c,request_interval=0)
        run('ali_star',full=True,queue=self.q,client=c,request_interval=0)
        self.assertEqual(self.q.pending_count(),2)
        self.assertTrue(all(r['recruitment_type']=='graduate' for r in self.q.dequeue(10)))

    def test_unknown_requested_batch_does_not_fall_back(self):
        with self.assertRaisesRegex(ValueError,'没有匹配'):
            run('campus',full=True,queue=self.q,client=self.client(),batch_id='missing')

    def test_existing_star_queue_is_migrated_into_graduate_batch(self):
        db=self.tmp.name+'/legacy.db'
        raw={'id':1,'batchId':20270001,'batchName':'新届应届生'}
        row={'job_id':'1','source':'alibaba','type':'campus','recruitment_type':'ali_star','raw_data':raw}
        with sqlite3.connect(db) as c:
            c.execute('CREATE TABLE pending_jobs(seq INTEGER PRIMARY KEY AUTOINCREMENT,source TEXT,portal TEXT,job_id TEXT,payload TEXT,enqueued_at TEXT,UNIQUE(source,portal,job_id))')
            c.execute('INSERT INTO pending_jobs VALUES(1,?,?,?,?,?)',('alibaba','ali_star','1',json.dumps(row),'now'))
        q=PendingQueue(db);record=q.dequeue(1)[0]
        self.assertEqual(record['batch_id'],'20270001')
        self.assertEqual(record['recruitment_type'],'graduate')
        self.assertEqual(record['program_tags'],['ali_star'])
        q.enqueue([record],'alibaba','graduate')
        self.assertEqual(q.pending_count(),1)

    def test_cross_batch_confirmation_does_not_delete_other_batch(self):
        for bid in ['1','2']:
            row=parse_post({'id':1},'graduate',Batch(bid,bid,'graduate'))
            self.q.enqueue([row],'alibaba','graduate')
        self.q.mark_pushed(self.q.dequeue(1))
        self.assertEqual(self.q.pending_count(),1)


class CommandTests(unittest.TestCase):
    def test_batch_id_without_portal_uses_campus_only(self):
        import run as entry
        with patch.object(entry,'crawl_source') as crawl, patch.object(entry.pending_queue,'default_queue') as q:
            q.return_value.pending_count.return_value=0
            self.assertEqual(entry.main(['crawl','--source','alibaba','--batch-id','123']),0)
        crawl.assert_called_once_with('alibaba',['campus'],False,50,0.4,50,batch_id='123')

    def test_invalid_page_size_does_not_start_network(self):
        c=MagicMock()
        with self.assertRaises(ValueError):run('campus',client=c,page_size=100)
        c.batches.assert_not_called()


class SchemaTests(unittest.TestCase):
    def test_cloud_schema_and_client_columns_match(self):
        from pathlib import Path
        import re
        from crawler.sync import push as cloud_push
        schema=(Path(__file__).resolve().parents[1]/'migrations/001_recruitment_jobs.sql').read_text()
        fields=set(re.findall(r'^  (\w+) (?:text|bigint|boolean|jsonb|timestamptz)\b',schema,re.M))
        self.assertTrue(set(cloud_push.COLUMNS) <= fields)
        self.assertIn('PRIMARY KEY (source, recruitment_type, batch_id, source_site, job_id)',schema)
        self.assertIn('on_conflict=source,recruitment_type,batch_id,source_site,job_id',cloud_push.REST_TABLE_URL)

    def test_batch_failure_preserves_other_batch_results(self):
        with tempfile.TemporaryDirectory() as root:
            q=PendingQueue(root+'/q.db')
            c=MagicMock()
            c.batches.return_value=[Batch('1','失败批次','graduate'),Batch('2','日常实习','regular_intern')]
            c.conditions.return_value={'searchItems':[]}
            c.organizations.return_value=[]
            def search(batch,*args,**kwargs):
                if batch.id=='1':raise RuntimeError('network')
                return {'datas':[{'id':9}],'totalCount':1}
            c.search.side_effect=search
            with patch.object(paths,'STATE_DIR',root+'/state'),patch.object(paths,'OUTPUT_DIR',root+'/output'):
                with self.assertRaisesRegex(RuntimeError,'失败批次: 1'):
                    run('campus',client=c,queue=q,full=True,request_interval=0)
            self.assertEqual(q.pending_count(),1)
            self.assertEqual(q.dequeue(1)[0]['batch_id'],'2')


class MigrationCollisionTests(unittest.TestCase):
    def test_existing_graduate_and_star_merge_without_losing_tag(self):
        with tempfile.TemporaryDirectory() as root:
            db=root+'/legacy.db'
            with sqlite3.connect(db) as c:
                c.execute('CREATE TABLE pending_jobs(seq INTEGER PRIMARY KEY AUTOINCREMENT,source TEXT,portal TEXT,job_id TEXT,payload TEXT,enqueued_at TEXT,UNIQUE(source,portal,job_id))')
                for index,portal in enumerate(['ali_star','graduate'],1):
                    row={'source':'alibaba','job_id':'1','type':'campus','recruitment_type':portal,
                         'raw_data':{'batchId':123}}
                    c.execute('INSERT INTO pending_jobs VALUES(?,?,?,?,?,?)',
                              (index,'alibaba',portal,'1',json.dumps(row),'now'))
            q=PendingQueue(db)
            self.assertEqual(q.pending_count(),1)
            self.assertEqual(q.dequeue(1)[0]['program_tags'],['ali_star'])
