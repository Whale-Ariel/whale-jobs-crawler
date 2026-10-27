"""批次隔离的职位队列、内容指纹、组织关系和只读接口缓存。"""
import hashlib
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from crawler import paths


class QueueRow(dict):
    pass


def fingerprint(row):
    stable = dict(row)
    raw = dict(stable.get('raw_data') or {})
    raw.pop('trackId',None)
    if raw.get('positionUrl'):
        raw['positionUrl'] = raw['positionUrl'].split('&track_id=')[0]
    if 'raw_data' in stable:
        stable['raw_data'] = raw
    return hashlib.sha256(json.dumps(stable,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


class PendingQueue:
    def __init__(self, db_path=None):
        self.db_path = db_path or paths.queue_db_path()
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)),exist_ok=True)
        with self._connect() as c:
            c.execute('BEGIN IMMEDIATE')
            renamed = []
            for table in ['pending_jobs','job_fingerprints','job_organizations']:
                columns = {r[1] for r in c.execute('PRAGMA table_info('+table+')')}
                if columns and 'source_site' not in columns:
                    c.execute('ALTER TABLE '+table+' RENAME TO '+table+'_old')
                    renamed.append(table)
            c.execute("""CREATE TABLE IF NOT EXISTS pending_jobs (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,source TEXT NOT NULL,portal TEXT NOT NULL,
                batch_id TEXT NOT NULL DEFAULT '',source_site TEXT NOT NULL DEFAULT '',job_id TEXT NOT NULL,
                payload TEXT NOT NULL,enqueued_at TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,
                UNIQUE(source,portal,batch_id,source_site,job_id))""")
            c.execute("""CREATE TABLE IF NOT EXISTS job_fingerprints (
                source TEXT,portal TEXT,batch_id TEXT NOT NULL DEFAULT '',source_site TEXT NOT NULL DEFAULT '',
                job_id TEXT,fingerprint TEXT,last_seen_at TEXT,
                PRIMARY KEY(source,portal,batch_id,source_site,job_id))""")
            c.execute("""CREATE TABLE IF NOT EXISTS job_organizations (
                source TEXT,portal TEXT,batch_id TEXT,source_site TEXT,job_id TEXT,circle_code TEXT,
                department_code TEXT,business_unit TEXT,department_name TEXT,work_cities TEXT,
                PRIMARY KEY(source,portal,batch_id,source_site,job_id,circle_code,department_code))""")
            c.execute('CREATE TABLE IF NOT EXISTS api_cache(cache_key TEXT PRIMARY KEY,version TEXT,payload TEXT,stored_at REAL)')
            c.execute('CREATE TABLE IF NOT EXISTS recruitment_batches(source TEXT,batch_id TEXT,recruitment_type TEXT,name TEXT,metadata TEXT,PRIMARY KEY(source,batch_id))')
            if 'pending_jobs' in renamed:
                from crawler.core.model import normalize_row
                for source,portal,jid,payload,when in c.execute('SELECT source,portal,job_id,payload,enqueued_at FROM pending_jobs_old ORDER BY seq').fetchall():
                    row = json.loads(payload)
                    if source in {'bytedance','tencent','alibaba'}:
                        row = normalize_row(row)
                        portal = row['recruitment_type']
                    key = (source,portal,str(row.get('batch_id') or ''),row.get('source_site') or '',jid)
                    existing = c.execute('SELECT payload FROM pending_jobs WHERE source=? AND portal=? AND batch_id=? AND source_site=? AND job_id=?',key).fetchone()
                    if existing:
                        row['program_tags'] = sorted(set(row.get('program_tags') or []) | set(json.loads(existing[0]).get('program_tags') or []))
                    c.execute("""INSERT INTO pending_jobs(source,portal,batch_id,source_site,job_id,payload,enqueued_at)
                        VALUES(?,?,?,?,?,?,?) ON CONFLICT(source,portal,batch_id,source_site,job_id) DO UPDATE SET
                        payload=excluded.payload,enqueued_at=excluded.enqueued_at,version=pending_jobs.version+1""",
                        (*key,json.dumps(row,ensure_ascii=False,sort_keys=True),when))
                    c.execute('INSERT OR REPLACE INTO job_fingerprints VALUES(?,?,?,?,?,?,?)',(*key,fingerprint(row),when))
                c.execute('UPDATE pending_jobs SET version=version+1000000000')
            if 'job_fingerprints' in renamed:
                cols=[r[1] for r in c.execute('PRAGMA table_info(job_fingerprints_old)')]
                for values in c.execute('SELECT * FROM job_fingerprints_old').fetchall():
                    old=dict(zip(cols,values))
                    if old['source']=='alibaba' and old['portal']!='society' and 'batch_id' not in old:
                        continue
                    site='taotian' if old['source']=='alibaba' and old['portal']=='society' else ''
                    c.execute('INSERT OR IGNORE INTO job_fingerprints VALUES(?,?,?,?,?,?,?)',
                              (old['source'],old['portal'],old.get('batch_id',''),site,old['job_id'],old['fingerprint'],old['last_seen_at']))
            if 'job_organizations' in renamed:
                c.execute("""INSERT OR REPLACE INTO job_organizations
                    SELECT source,portal,batch_id,CASE WHEN source='alibaba' AND portal='society' THEN 'taotian' ELSE '' END,
                           job_id,circle_code,department_code,business_unit,department_name,work_cities
                    FROM job_organizations_old""")
            for table in renamed:
                c.execute('DROP TABLE '+table+'_old')
            if c.execute('PRAGMA user_version').fetchone()[0] < 5:
                from crawler.core.model import normalize_job_location
                records = c.execute('SELECT seq,source,portal,batch_id,source_site,job_id,payload FROM pending_jobs').fetchall()
                for seq,source,portal,bid,site,jid,payload in records:
                    row = normalize_job_location(json.loads(payload))
                    c.execute('UPDATE pending_jobs SET payload=?,version=version+1 WHERE seq=?',
                              (json.dumps(row,ensure_ascii=False,sort_keys=True),seq))
                    c.execute('UPDATE job_fingerprints SET fingerprint=? WHERE source=? AND portal=? AND batch_id=? AND source_site=? AND job_id=?',
                              (fingerprint(row),source,portal,bid,site,jid))
            c.execute('PRAGMA user_version=5')

    @contextmanager
    def _connect(self):
        c = sqlite3.connect(self.db_path,timeout=30)
        try:
            c.execute('PRAGMA journal_mode=WAL')
            with c:
                yield c
        finally:
            c.close()

    def enqueue(self, rows, source, portal):
        now = datetime.now().astimezone().isoformat()
        changed = 0
        with self._connect() as c:
            for row in rows:
                jid = str(row['job_id'])
                if not jid:
                    raise ValueError('job_id不得为空')
                bid = str(row.get('batch_id') or '')
                key = (source,portal,bid,row.get('source_site') or '',jid)
                digest = fingerprint(row)
                old = c.execute('SELECT fingerprint FROM job_fingerprints WHERE source=? AND portal=? AND batch_id=? AND source_site=? AND job_id=?',key).fetchone()
                c.execute('''INSERT INTO job_fingerprints VALUES(?,?,?,?,?,?,?)
                    ON CONFLICT(source,portal,batch_id,source_site,job_id) DO UPDATE SET
                    fingerprint=excluded.fingerprint,last_seen_at=excluded.last_seen_at''',(*key,digest,now))
                if old and old[0] == digest:
                    continue
                c.execute('''INSERT INTO pending_jobs(source,portal,batch_id,source_site,job_id,payload,enqueued_at)
                    VALUES(?,?,?,?,?,?,?) ON CONFLICT(source,portal,batch_id,source_site,job_id) DO UPDATE SET
                    payload=excluded.payload,enqueued_at=excluded.enqueued_at,version=pending_jobs.version+1''',
                    (*key,json.dumps(row,ensure_ascii=False,sort_keys=True),now))
                if 'organization_assignments' in row:
                    c.execute('DELETE FROM job_organizations WHERE source=? AND portal=? AND batch_id=? AND source_site=? AND job_id=?',key)
                    for group in row['organization_assignments']:
                        for dept in group.get('departments') or [{}]:
                            c.execute('INSERT OR REPLACE INTO job_organizations VALUES(?,?,?,?,?,?,?,?,?,?)',
                                (*key,group['circle_code'],dept.get('department_code',''),group['business_unit'],
                                 dept.get('department_name'),json.dumps(dept.get('work_cities') or [],ensure_ascii=False)))
                changed += 1
        return changed

    def contains(self, source, portal, job_id, batch_id='', source_site=''):
        with self._connect() as c:
            return c.execute('SELECT 1 FROM job_fingerprints WHERE source=? AND portal=? AND batch_id=? AND source_site=? AND job_id=?',
                             (source,portal,str(batch_id or ''),source_site or '',str(job_id))).fetchone() is not None

    def dequeue(self, limit, source=None):
        if limit < 1:
            raise ValueError('limit必须大于零')
        with self._connect() as c:
            sql = 'SELECT seq,version,payload FROM pending_jobs'
            args = []
            if source:
                sql += ' WHERE source=?';args.append(source)
            args.append(limit)
            records = c.execute(sql+' ORDER BY seq LIMIT ?',args).fetchall()
        result = []
        for seq,version,payload in records:
            row = QueueRow(json.loads(payload));row.receipt = (seq,version);result.append(row)
        return result

    def mark_pushed(self, rows):
        removed = 0
        with self._connect() as c:
            for row in rows:
                receipt = getattr(row,'receipt',None)
                if receipt is None:
                    raise ValueError('确认必须使用dequeue返回的记录及版本凭证')
                removed += c.execute('DELETE FROM pending_jobs WHERE seq=? AND version=?',receipt).rowcount
        return removed

    def pending_count(self, source=None):
        with self._connect() as c:
            if source:
                return c.execute('SELECT COUNT(*) FROM pending_jobs WHERE source=?',(source,)).fetchone()[0]
            return c.execute('SELECT COUNT(*) FROM pending_jobs').fetchone()[0]

    def cache_get(self, key, version, max_age=86400):
        with self._connect() as c:
            record = c.execute('SELECT version,payload,stored_at FROM api_cache WHERE cache_key=?',(key,)).fetchone()
        if record and record[0] == str(version) and time.time()-record[2] < max_age:
            return json.loads(record[1])
        return None

    def cache_put(self, key, version, value):
        with self._connect() as c:
            c.execute('INSERT OR REPLACE INTO api_cache VALUES(?,?,?,?)',
                      (key,str(version),json.dumps(value,ensure_ascii=False),time.time()))

    def save_batches(self, batches):
        with self._connect() as c:
            c.execute("DELETE FROM recruitment_batches WHERE source='alibaba'")
            for batch in batches:
                c.execute('INSERT OR REPLACE INTO recruitment_batches VALUES(?,?,?,?,?)',
                          ('alibaba',batch.id,batch.portal,batch.name,json.dumps(batch.metadata,ensure_ascii=False)))


_default_queue = None

def default_queue():
    global _default_queue
    if _default_queue is None:
        _default_queue = PendingQueue()
    return _default_queue
