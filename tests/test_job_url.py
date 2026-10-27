import json
import sqlite3
import tempfile
import unittest
from crawler.core.model import normalize_job_location
from crawler.core.queue import PendingQueue, fingerprint

class JobURLTests(unittest.TestCase):
    def test_byte_channels_preserve_office(self):
        for portal, channel in [('society','experienced'),('campus','campus')]:
            row=normalize_job_location(dict(source='bytedance',job_id='123',recruitment_type=portal,address='望京'))
            self.assertEqual(row['job_url'],f'https://jobs.bytedance.com/{channel}/position/123/detail')
            self.assertEqual(row['address'],'望京')
            self.assertEqual(normalize_job_location(row),row)

    def test_legacy_links_moved_without_city_guess(self):
        for source in ['alibaba','tencent']:
            row=normalize_job_location(dict(source=source,address='https://example.org/job/1',city_name='杭州'))
            self.assertEqual(row['job_url'],'https://example.org/job/1')
            self.assertIsNone(row['address'])

    def test_v4_migration_updates_fingerprint_and_receipt_once(self):
        with tempfile.TemporaryDirectory() as d:
            path=d+'/q.db'; q=PendingQueue(path)
            old=dict(source='bytedance',job_id='123',recruitment_type='society',address='望京')
            q.enqueue([old],'bytedance','society'); receipt=q.dequeue(1)
            with sqlite3.connect(path) as c:c.execute('PRAGMA user_version=4')
            q=PendingQueue(path); row=q.dequeue(1)[0]
            self.assertTrue(row['job_url'].endswith('/123/detail'))
            self.assertEqual(q.mark_pushed(receipt),0)
            with sqlite3.connect(path) as c:
                self.assertEqual(c.execute('select fingerprint from job_fingerprints').fetchone()[0],fingerprint(row))
            version=row.receipt
            self.assertEqual(PendingQueue(path).dequeue(1)[0].receipt,version)
