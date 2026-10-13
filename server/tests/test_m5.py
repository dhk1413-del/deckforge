"""M5 离线回归：仅临时 DB/文件，不启动服务、不请求供应商。"""
import asyncio
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch

_SANDBOX = tempfile.TemporaryDirectory(prefix='deckforge-m5-')
os.environ['DECKFORGE_DATA'] = _SANDBOX.name
from PIL import Image
from fastapi import HTTPException
from server.app import db, pipeline, main, operations, slide_versions


class MilestoneFive(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        db.init_db()
        for table in ('slide_versions', 'slides', 'jobs', 'projects', 'usage_log', 'operation_submissions', 'operation_quotes'):
            db.x('DELETE FROM '+table)
        pipeline.JOBS.clear()
        pipeline.CANCEL.clear()
        db.insert('projects', dict(id='p', title='真实测试输入', style_pack_id='tech-deepblue', size='2K', status='generating', content_confirmed_at=db.now()))
        for no in (1, 2):
            db.insert('slides', dict(id='s'+str(no), project_id='p', page_no=no, title='原文标题', outline='原文内容', points_json='["原文要点"]', status='pending'))

    async def test_interruption_is_terminal_and_reentrant(self):
        pages = {'1':dict(page=1, status='done'), '2':dict(page=2, status='queued')}
        db.insert('jobs', dict(id='old', project_id='p', kind='generate', status='running', pages_json=json.dumps(pages)))
        for status in ('done', 'failed', 'cancelled'):
            db.insert('jobs', dict(id=status, status=status))
        live = pipeline.new_job('p', 'generate', 1)
        await pipeline.emit(live['id'], dict(type='progress', page=1, status='running'))
        self.assertEqual(pipeline.recover_interrupted_jobs(), 1)
        self.assertEqual(pipeline.recover_interrupted_jobs(), 0)
        snapshot = main.job_detail('old')
        self.assertEqual(snapshot['task_status'], 'interrupted')
        self.assertEqual(snapshot['counts']['interrupted'], 1)
        self.assertEqual(json.loads(snapshot['pages_json'])['1']['status'], 'done')
        self.assertEqual(main._job_terminal_event(snapshot)['type'], 'interrupted')
        self.assertEqual(db.q1("SELECT status FROM slides WHERE id='s2'")[0], 'interrupted')
        self.assertEqual(pipeline.get_job(live['id'])['status'], 'running')
        self.assertEqual(db.q1("SELECT status FROM projects WHERE id='p'")[0], 'generating')
        for status in ('done', 'failed', 'cancelled'):
            self.assertEqual(pipeline.get_job(status)['status'], status)
        with self.assertRaises(HTTPException) as caught:
            await main.cancel_job('old')
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(main.get_project('p')['resume_step'], 5)
        self.assertEqual(main.list_projects()['items'][0]['resume_step'], 5)

    async def test_version_transaction_rolls_back_together(self):
        conn = db.connect()
        db._COLUMNS_CACHE.clear()
        conn.execute('BEGIN IMMEDIATE')
        db.update('slides', 's1', dict(status='done', image_path='/tmp/unused-version.png'))
        slide_versions.preserve(conn, dict(conn.execute("SELECT * FROM slides WHERE id='s1'").fetchone()))
        conn.execute('ROLLBACK')
        self.assertEqual(db.q1("SELECT status FROM slides WHERE id='s1'")[0], 'pending')
        self.assertEqual(db.q1('SELECT COUNT(*) FROM slide_versions')[0], 0)

    async def test_startup_preserves_legacy_version_once(self):
        image_path = os.path.join(_SANDBOX.name, 'legacy.png')
        Image.new('RGB', (160, 90)).save(image_path)
        db.update('slides', 's1', dict(image_path=image_path, status='done'))
        db.insert('jobs', dict(id='legacy', project_id='p', kind='generate', status='queued', pages_json=json.dumps({'2':dict(status='queued')})))
        main._startup()
        main._startup()
        self.assertEqual(pipeline.get_job('legacy')['status'], 'interrupted')
        result = main.slides('p')['items'][0]
        self.assertEqual(len(result['versions']), 1)
        self.assertTrue(result['versions'][0]['current'])
        self.assertEqual(result['status'], 'done')

    async def test_versions_retry_idempotency_stale_and_export(self):
        buf = io.BytesIO()
        Image.new('RGB', (160, 90), 'white').save(buf, format='PNG')
        def image(*args, **kwargs):
            return dict(ok=True, image_bytes=buf.getvalue(), provider='local_render', model='local', cost_cny=0)
        async def settle(jid):
            # Await actual worker tasks, never infer completion from elapsed time.
            workers = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and t.get_coro().__name__ == '_generate_worker']
            await asyncio.gather(*workers)
            return pipeline.get_job(jid)
        async def offline_call(fn, *args, **kwargs):
            return fn(*args, **kwargs)
        with patch.object(pipeline.providers, 'generate_image', side_effect=image), patch('asyncio.to_thread', side_effect=offline_call):
            job = pipeline.new_job('p', 'generate', 2)
            rows = [dict(r) for r in db.q('SELECT * FROM slides ORDER BY page_no')]
            real_verify = pipeline.verify_page
            def verify(content):
                if content['index'] == '02':
                    raise ValueError('离线注入单页失败')
                return real_verify(content)
            with patch.object(pipeline, 'verify_page', side_effect=verify):
                await pipeline._generate_worker(job['id'], dict(db.q1("SELECT * FROM projects WHERE id='p'")), rows, [1,2], {}, 'tech-deepblue', '2K')
            self.assertEqual(pipeline.get_job(job['id'])['task_status'], 'partial_success')
            first = dict(db.q1("SELECT * FROM slides WHERE id='s1'"))
            quote = operations.quote('p', dict(operation='regenerate', page_nos=[2]))
            payload = dict(quote_id=quote['quote_id'], idempotency_key='m5-retry-page-two')
            res = await main.regenerate('p', 2, payload)
            await settle(res['job_id'])
            again = await main.regenerate('p', 2, payload)
            self.assertEqual(res, again)
            self.assertEqual(first['image_path'], db.q1("SELECT * FROM slides WHERE id='s1'")['image_path'])
            self.assertEqual(db.q1("SELECT COUNT(*) FROM usage_log WHERE page_no=2 AND ok=1")[0], 1)
            old = db.q1("SELECT current_version_id FROM slides WHERE id='s1'")[0]
            saved = main.save_content('p', 's1', dict(revision=1, outline='新的原文内容'))
            self.assertEqual(saved['content_revision'], 2)
            self.assertTrue(main.slides('p')['items'][0]['content_stale'])
            main.configure_project('p', dict(confirm_content=True))
            quote = operations.quote('p', dict(operation='regenerate', page_nos=[1]))
            res = await main.regenerate('p', 1, dict(quote_id=quote['quote_id'], idempotency_key='m5-new-content-page-one'))
            await settle(res['job_id'])
            self.assertFalse(main.slides('p')['items'][0]['content_stale'])
            self.assertEqual(len(main.slides('p')['items'][0]['versions']), 2)
            main.restore_slide_version('p', 's1', old)
            restored = main.slides('p')['items'][0]
            self.assertTrue(restored['content_stale'])
            self.assertEqual(restored['current_version_id'], old)
            self.assertEqual(sum(v['current'] for v in restored['versions']), 1)
            slide_versions.backfill()
            self.assertEqual(len(main.slides('p')['items'][0]['versions']), 2)
            self.assertTrue(all(os.path.isfile(json.loads(v['snapshot_json'])['image_path']) for v in db.q('SELECT * FROM slide_versions')))
            db.update('slides', 's2', dict(status='interrupted'))
            result = pipeline.do_export('p', 'image')
            self.assertEqual(result['pages'], 1)
            live = pipeline.new_job('p', 'generate', 1)
            await pipeline.emit(live['id'], dict(type='progress', page=1, status='running'))
            with self.assertRaises(HTTPException) as caught:
                main.restore_slide_version('p', 's1', old)
            self.assertEqual(caught.exception.status_code, 409)
            with self.assertRaises(ValueError):
                pipeline.do_export('p', 'image')


if __name__ == '__main__':
    unittest.main()
