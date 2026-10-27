import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import crawler.sources as ns
from crawler.sync.push import COLUMNS
from crawler.core.queue import PendingQueue
import run

def load_fixtures():
    path = Path(__file__).parent / 'fixtures' / 'new_sources_posts.json'
    if not path.exists():
        return None
    return json.loads(path.read_text())

class NewSourceTests(unittest.TestCase):
    def test_official_samples_keep_identity_links_and_raw_data(self):
        fixtures = load_fixtures()
        if fixtures is None:
            self.skipTest('样例文件不在当前工作区')
        for fixture in fixtures:
            with self.subTest(source=fixture['source'],portal=fixture['portal']):
                post=copy.deepcopy(fixture['post'])
                augmented={**post,'_crawler_id':fixture['job_id']}
                row=ns.parse_post(augmented,fixture['source'],fixture['portal'])
                self.assertEqual(set(row),set(COLUMNS))
                self.assertEqual(row['job_id'],fixture['job_id'])
                self.assertEqual(row['raw_data'],post)
                self.assertIsNone(row['address'])
                self.assertTrue(row['job_url'].startswith('https://'))
                self.assertNotIn('_crawler_id',row['raw_data'])

    def test_no_invention_of_unknown_department_or_address(self):
        row=ns.parse_post({'id':1,'name':'岗位','positionNatureCode':'C001'},'kuaishou','society')
        self.assertEqual(row['business_units'],[])
        self.assertIsNone(row['business_unit'])
        self.assertIsNone(row['address'])

    def test_requested_projects_are_enforced(self):
        for source,post in [('jd',{'publishId':1,'positionName':'岗位','planId':999}),
                            ('kuaishou',{'id':1,'name':'岗位','recruitSubProjectCode':'wrong'})]:
            with self.subTest(source=source),self.assertRaises(ns.SourceError):
                ns.parse_post({**post,'_crawler_id':'1'},source,'campus')

    def test_kuaishou_public_signature_is_canonical_and_time_bound(self):
        params={'pageNum':1,'pageSize':50,'workLocationCode':'domestic','positionNatureCode':'C001','recruitProject':'socialr'}
        self.assertEqual(ns.kuaishou_headers(params,1792764000000),
                         ns.kuaishou_headers(dict(reversed(list(params.items()))),1792764000000))
        self.assertNotEqual(ns.kuaishou_headers(params,1)['sign'],ns.kuaishou_headers(params,2)['sign'])

    def test_baidu_uses_server_accepted_size_and_form_encoding(self):
        client=ns.client('baidu','campus',50)
        self.assertEqual(client.page_size,10)
        client.request=Mock(return_value={'status':'ok','data':{'total':'1','list':[{'postId':'p','name':'岗位'}]}})
        jobs,total=client.fetch(1)
        self.assertEqual((total,jobs[0]['id']),(1,'p'))
        self.assertEqual(client.request.call_args.args[1]['curPage'],1)
        self.assertTrue(client.request.call_args.kwargs['form'])

    def test_jd_page_index_is_zero_based_and_project_is_fixed(self):
        client=ns.client('jd','campus')
        client.request=Mock(return_value={'success':True,'body':{'totalNumber':1,'items':[{'publishId':123,'planId':45}]}})
        jobs,total=client.fetch(1)
        self.assertEqual(client.request.call_args.args[1]['pageIndex'],0)
        self.assertEqual(client.request.call_args.args[1]['parameter']['planIdList'],[45])
        self.assertEqual(jobs[0]['_crawler_id'],'123')

    def test_errors_and_missing_totals_cannot_be_successful_empty_pages(self):
        for response in [{'status':'fail','message':'login'}, {'status':'ok','data':{'list':[]}},
                         {'status':'ok','data':{'list':None,'total':'5'}}]:
            client=ns.client('baidu','society');client.request=Mock(return_value=response)
            with self.assertRaises(ns.SourceError):client.fetch(1)

    def test_repeated_page_ids_are_detected(self):
        client=ns.client('baidu','society')
        client.request=Mock(return_value={'status':'ok','data':{'total':'20','list':[{'postId':'same'}]}})
        client.fetch(1)
        with self.assertRaises(ns.SourceError):client.fetch(2)

    def test_cities_from_public_dictionary_not_english_code(self):
        client=ns.client('kuaishou','society')
        client.request=Mock(side_effect=[{'code':0,'result':{'total':1,'list':[{'id':1,'name':'岗位','positionNatureCode':'C001','workLocationCode':'Beijing'}]}},
                                         {'code':0,'result':{'domestic':[{'code':'Beijing','name':'北京'}]}}])
        jobs,_=client.fetch(1);row=ns.parse_post(jobs[0],'kuaishou','society')
        self.assertEqual(row['city_name'],'北京')
        self.assertNotIn('_crawler_city_names',row['raw_data'])

    def test_new_companies_same_id_are_separate_in_local_database(self):
        with tempfile.TemporaryDirectory() as directory:
            q=PendingQueue(directory+'/q.db')
            for source,post in [('netease',{'workType':'0'}),('kuaishou',{'positionNatureCode':'C001'})]:
                row=ns.parse_post({'id':123,'name':'岗位',**post},source,'society')
                q.enqueue([row],source,'society')
            self.assertEqual(q.pending_count(),2)

    def test_new_cli_continues_after_blocked_channel_without_cloud_calls(self):
        calls=[]
        def fake(source,portals,*args,**kwargs):
            calls.append((source,portals[0]))
            if source=='jd' and portals==['society']:raise ns.SourceError('login')
        with patch.object(run,'crawl_source',side_effect=fake),patch.object(run.sync_cloud,'drain') as push:
            self.assertEqual(run.main(['crawl','--source','new','--full']),1)
            self.assertEqual(len(calls),12)
            self.assertIn(('kuaishou','campus'),calls)
            push.assert_not_called()
