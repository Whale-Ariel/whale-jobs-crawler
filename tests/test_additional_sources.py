import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import crawler.sources as a
from crawler.core.text import date, split_duty
from crawler.sources.didi.moka import decode_moka
from crawler.core.queue import PendingQueue
from crawler.sync.push import COLUMNS
import run

def load_samples():
    path = Path(__file__).parent / 'fixtures' / 'additional_sources_posts.json'
    if not path.exists():
        return None
    return json.loads(path.read_text())

class AdditionalSourcesTests(unittest.TestCase):
    def test_official_samples_cover_all_nineteen_scopes(self):
        samples = load_samples()
        if samples is None:
            self.skipTest('样例文件不在当前工作区')
        self.assertEqual({(x['source'],x['portal']) for x in samples},
                         {(s,p) for s,ps in a.EXTRA_PORTALS.items() for p in ps})
        for sample in samples:
            with self.subTest(source=sample['source'],portal=sample['portal']):
                job=copy.deepcopy(sample['job']);original=copy.deepcopy(job)
                row=a.parse_post(job,sample['source'],sample['portal'])
                self.assertEqual(set(row),set(COLUMNS))
                self.assertEqual(job,original)
                self.assertEqual(row['job_id'],job['_crawler_id'])
                self.assertTrue(row['job_url'].startswith('https://'))
                raw=row['raw_data']
                self.assertEqual(raw['list'] if job.get('_crawler_detail') else raw,job['_crawler_raw'])

    def test_bili_campus_retention_intern_does_not_become_graduate(self):
        row=a.parse_post({'_crawler_id':'7','_crawler_raw':{'recruitType':1,'positionTypeName':'留用实习','positionName':'实习岗位'}},'bilibili','internship')
        self.assertEqual(row['recruitment_type'],'internship')
        with self.assertRaises(a.SourceError):
            a.parse_post({'_crawler_id':'7','_crawler_raw':{'recruitType':1,'positionTypeName':'全职','positionName':'岗位'}},'bilibili','internship')

    def test_mihoyo_project_mismatch_cannot_be_stored(self):
        samples = load_samples()
        if samples is None:
            self.skipTest('样例文件不在当前工作区')
        job=next(copy.deepcopy(s['job']) for s in samples if s['source']=='mihoyo' and s['portal']=='campus')
        job['_crawler_detail']['projectId']='4'
        with self.assertRaises(a.SourceError):a.parse_post(job,'mihoyo','campus')

    def test_detail_calls_are_skipped_for_known_jobs_before_request(self):
        with tempfile.TemporaryDirectory() as d:
            q=PendingQueue(d+'/q.db');q.enqueue([{'job_id':'7','batch_id':'13'}],'mihoyo','campus')
            c=a.client('mihoyo','campus',queue=q);c.request=Mock()
            job={'_crawler_id':'7','_crawler_raw':{}}
            self.assertIs(c.hydrate(job),job);c.request.assert_not_called()

    def test_detail_id_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            c=a.client('mihoyo','society',queue=PendingQueue(d+'/q.db'))
            c.request=Mock(return_value={'code':0,'data':{'id':'other'}})
            with self.assertRaises(a.SourceError):c.hydrate({'_crawler_id':'7','_crawler_raw':{}})

    def test_xhs_discovers_regular_and_intern_categories_not_ace(self):
        values=[{'code':'c','extMap':{'category':'regular'}},{'code':'a','extMap':{'category':'ace'}},
                {'code':'i','extMap':{'category':'intern'}}]
        for portal,expected in [('campus',['c']),('internship',['i'])]:
            with tempfile.TemporaryDirectory() as d:
                c=a.client('xiaohongshu',portal,queue=PendingQueue(d+'/q.db'))
                c.request=Mock(return_value={'statusCode':200,'data':{'PositionProjectEnum':values}})
                c.initialize();self.assertEqual(c.xhs_projects,expected)
                self.assertEqual(c.request.call_args.args[1],['PositionProjectEnum'])

    def test_xhs_snapshot_needs_unique_coverage_and_is_reusable_on_resume(self):
        with tempfile.TemporaryDirectory() as d:
            c=a.client('xiaohongshu','campus',2,PendingQueue(d+'/q.db'))
            c.xhs_page=Mock(side_effect=[([{'positionId':1},{'positionId':1}],2),
                                        ([{'positionId':1},{'positionId':2}],2)])
            data=c.xhs_consistent_snapshot(1)
            self.assertEqual(data['passes'],2)
            self.assertEqual(data['unique_positions'],2)
            self.assertEqual([j['positionId'] for j in data['jobs']],[1,2])
            c.xhs_page.reset_mock();self.assertEqual(c.xhs_consistent_snapshot(2),data)
            c.xhs_page.assert_not_called()

    def test_xhs_incomplete_snapshot_never_reports_success(self):
        with tempfile.TemporaryDirectory() as d:
            c=a.client('xiaohongshu','campus',2,PendingQueue(d+'/q.db'))
            c.xhs_page=Mock(return_value=([{'positionId':1},{'positionId':1}],2))
            with self.assertRaises(a.SourceError):c.xhs_consistent_snapshot(1)

    def test_oppo_dynamic_projects_restrict_graduate(self):
        with tempfile.TemporaryDirectory() as d:
            c=a.client('oppo','campus',queue=PendingQueue(d+'/q.db'))
            c.request=Mock(return_value={'code':0,'data':[{'idRecruitProject':30,'recruitmentType':'Graduate'},
                                                        {'idRecruitProject':29,'recruitmentType':'Intern'}]})
            c.initialize();self.assertEqual([p['projectId'] for p in c.oppo_projects],[30])

    def test_iflytek_uses_selected_fields_from_page_configuration(self):
        with tempfile.TemporaryDirectory() as d:
            c=a.client('iflytek','society',queue=PendingQueue(d+'/q.db'))
            c.landing=Mock(return_value='BSGlobal = '+json.dumps({'PortalId':'P','Pages':[
                {'BusinessType':'1','PageType':2,'ConfigAddress':'https://example.org/config'}]})+';')
            c.request=Mock(return_value={'ListItems':[{'Key':'LocId','Select':True},{'Key':'Salary','Select':False}]})
            c.initialize();self.assertEqual(c.display_fields,['LocId'])
            self.assertEqual(c.portal_id,'P')

    def test_net_seven_digit_fraction_and_sentinel_date(self):
        self.assertEqual(date('2026-09-15T09:40:05.9845514'),'2026-09-15T09:40:05.984551+08:00')
        self.assertIsNone(date('0001-01-01T00:00:00'))

    def test_pdd_server_page_limit_and_requirement_field(self):
        with tempfile.TemporaryDirectory() as d:
            c=a.client('pdd','campus',50,PendingQueue(d+'/q.db'))
            self.assertEqual(c.page_size,10)
            row=a.parse_post({'_crawler_id':'p','_crawler_raw':{'id':'p','name':'岗位','code':'A'},
                              '_crawler_detail':{'id':'p','serveRequirement':'要求'}},'pdd','campus')
            self.assertEqual(row['requirement'],'要求');self.assertEqual(row['job_code'],'A')

    def test_plain_text_and_combined_duty_are_not_html_or_discarded(self):
        duty,requirement=split_duty('<p>职责</p><p>工作要求：\n本科</p>')
        self.assertEqual(duty,'职责');self.assertEqual(requirement,'本科')

    def test_moka_response_error_and_invalid_cipher_fail_explicitly(self):
        with self.assertRaises(a.SourceError):decode_moka({'code':400,'msg':'error'},'')
        with self.assertRaises(a.SourceError):decode_moka({'data':'not base64','necromancer':'x'},'bad')
        self.assertEqual(decode_moka({'code':0,'data':{'jobs':[]}},''),{'jobs':[]})

    def test_extra_cli_dispatch_is_local_and_does_not_include_original_sources(self):
        calls=[]
        with patch.object(run,'crawl_source',side_effect=lambda s,ps,*args,**kw:calls.extend((s,p) for p in ps)), \
             patch.object(run.pending_queue,'default_queue') as q,patch.object(run.sync_cloud,'drain') as cloud:
            q.return_value.pending_count.return_value=0
            self.assertEqual(run.main(['crawl','--source','extra','--full']),0)
        self.assertEqual(calls,[(s,p) for s,ps in a.EXTRA_PORTALS.items() for p in ps]);cloud.assert_not_called()
