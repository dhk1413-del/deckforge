"""M6 合同回归：临时数据、实际 PPTX、无服务/模型调用。"""
import hashlib
import os
import tempfile
import unittest
import json
from pathlib import Path

_SANDBOX = tempfile.TemporaryDirectory(prefix='deckforge-m6-')
os.environ['DECKFORGE_DATA'] = _SANDBOX.name
from PIL import Image
from pptx import Presentation
from fastapi import HTTPException
from server.app import config, db, main, pipeline, slide_versions


class MilestoneSix(unittest.TestCase):
    def setUp(self):
        db.init_db()
        pipeline.JOBS.clear()
        os.makedirs(os.path.join(config.FILES_DIR,'p'), exist_ok=True)
        for table in ('exports', 'slide_versions', 'slides', 'jobs', 'projects', 'usage_log'):
            db.x('DELETE FROM ' + table)
        db.insert('projects', dict(id='p', title='导出测试项目', style_pack_id='tech-deepblue', size='2K'))
        for no, status in ((1, 'done'), (2, 'failed'), (3, 'done')):
            path = os.path.join(config.FILES_DIR, 'p', str(no)+'.png')
            Image.new('RGB', (160, 90), (no*40, 50, 80)).save(path)
            db.insert('slides', dict(id='s'+str(no), project_id='p', page_no=no, display_order=4-no,
                                    title='原文标题', status=status, provider='import', image_path=path))
        slide_versions.backfill()

    def test_scope_versions_freeze_and_history(self):
        preview = main.export_preview('p', {'kind':'image'})
        self.assertEqual([p['page_no'] for p in preview['included']], [3, 1])
        self.assertEqual(preview['excluded'][0]['page_no'], 2)
        self.assertIn('失败', preview['excluded'][0]['reason'])
        first = main.create_export('p', dict(kind='image', snapshot_token=preview['snapshot_token']))
        rec = dict(db.q1('SELECT * FROM exports WHERE id=?', (first['id'],)))
        digest = hashlib.sha256(Path(rec['path']).read_bytes()).hexdigest()
        self.assertEqual(len(Presentation(rec['path']).slides), 2)
        second = main.create_export('p', dict(kind='image', snapshot_token=preview['snapshot_token']))
        self.assertNotEqual(first['file'], second['file'])
        selected = main.export_preview('p', {'kind':'image','page_nos':[1]})
        one = main.create_export('p', dict(kind='image',page_nos=[1],snapshot_token=selected['snapshot_token']))
        self.assertEqual(one['pages'], 1)
        self.assertIn('导出测试项目', one['file'])
        path = os.path.join(config.FILES_DIR, 'p', 'new.png')
        Image.new('RGB', (160, 90), 'red').save(path)
        db.update('slides', 's1', dict(image_path=path))
        conn=db.connect()
        slide_versions.preserve(conn, dict(conn.execute("SELECT * FROM slides WHERE id='s1'").fetchone()))
        with self.assertRaises(HTTPException) as caught:
            main.create_export('p',dict(kind='image',page_nos=[1],snapshot_token=selected['snapshot_token']))
        self.assertEqual(caught.exception.status_code,409)
        slide_versions.select('s1', selected['included'][0]['version_id'])
        db.update('slides','s1',dict(title='修改内容', content_revision=2))
        db.update('projects','p',dict(title='已改名'))
        self.assertEqual(hashlib.sha256(Path(rec['path']).read_bytes()).hexdigest(), digest)
        history=main.export_history('p')['items']
        self.assertEqual(len(history),3)
        self.assertEqual(next(r for r in history if r['id']==first['id'])['snapshot'], first['snapshot'])
        self.assertEqual(db.q1('SELECT COUNT(*) FROM usage_log')[0],0)

    def test_running_and_missing_assets_are_explicit(self):
        job=pipeline.new_job('p','generate',1)
        pipeline._job_update(job['id'],pages_json=json.dumps({'1':{'status':'running'}}))
        os.remove(db.q1("SELECT image_path FROM slides WHERE id='s3'")[0])
        preview=main.export_preview('p',{'kind':'image'})
        self.assertEqual(preview['included'],[])
        reasons={p['page_no']:p['reason'] for p in preview['excluded']}
        self.assertIn('运行中',reasons[1]); self.assertIn('缺失',reasons[3])
        with self.assertRaises(HTTPException):
            main.create_export('p',dict(kind='image',snapshot_token=preview['snapshot_token']))
        self.assertEqual(db.q1('SELECT COUNT(*) FROM exports')[0],0)

    def test_native_export_is_retired(self):
        """可编辑 PPTX 只允许由 editppt 精细重建产出；旧原生场景导出必须拒绝。"""
        with self.assertRaises(HTTPException) as caught:
            main.export_preview('p', {'kind': 'native'})
        self.assertEqual(caught.exception.status_code, 400)
        preview = main.export_preview('p', {'kind': 'image'})
        self.assertEqual([c['kind'] for c in preview['capabilities']], ['image', 'editable_hi'])


if __name__=='__main__':
    unittest.main()
