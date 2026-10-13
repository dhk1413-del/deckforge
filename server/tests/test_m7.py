"""M7 验收证据：隔离数据库中的列表阶段一致性与内容确认闸。"""
import os
import tempfile
import unittest

_SANDBOX = tempfile.TemporaryDirectory(prefix='deckforge-m7-')
os.environ['DECKFORGE_DATA'] = _SANDBOX.name
from fastapi import HTTPException
from server.app import db, main


class MilestoneSeven(unittest.TestCase):
    def setUp(self):
        db.init_db()
        self.pid = main.create_project(dict(title='验收原稿', intake_mode='doc'))['id']

    def assert_stage(self, expected):
        detail = main.get_project(self.pid)
        listed = next(p for p in main.list_projects()['items'] if p['id'] == self.pid)
        self.assertEqual(detail['resume_step'], expected)
        self.assertEqual(listed['resume_step'], expected)
        self.assertEqual(listed['status'], detail['status'])
        self.assertEqual(listed['title'], detail['title'])
        return listed

    def test_list_detail_stage_and_configuration_agree(self):
        self.assert_stage(1)
        db.update('projects', self.pid, dict(parsed_text='原稿文字'))
        self.assert_stage(2)
        db.insert('slides', dict(id=self.pid+'-s', project_id=self.pid, page_no=1,
                                title='原稿标题', outline='原稿正文', status='pending'))
        db.update('projects', self.pid, dict(pages_confirmed_at=db.now()))
        self.assert_stage(3)
        main.configure_project(self.pid, dict(confirm_content=True, title='保存后的项目名称', size='4K'))
        listed = self.assert_stage(4)
        self.assertEqual(listed['size'], '4K')
        self.assertEqual(listed['page_count'], 1)
        db.update('slides', self.pid+'-s', dict(status='interrupted', error='隔离测试中断原因'))
        db.update('projects', self.pid, dict(status='interrupted'))
        self.assert_stage(5)
        slide = main.slides(self.pid)['items'][0]
        self.assertEqual(slide['slide_id'], self.pid+'-s')
        self.assertEqual(slide['error'], '隔离测试中断原因')

    def test_content_revision_conflict_and_confirmation_gate(self):
        sid = self.pid+'-s'
        db.insert('slides', dict(id=sid, project_id=self.pid, page_no=1,
                                title='原稿标题', outline='收入 12 万元；待统计', status='pending'))
        db.update('projects', self.pid, dict(pages_confirmed_at=db.now()))
        saved = main.save_content(self.pid, sid, dict(revision=1, modules=[
            dict(type='table', unit='万元', cells=[['收入', '12'], ['待统计', None]])]))
        self.assertEqual(saved['content_revision'], 2)
        self.assertIsNone(saved['modules'][0]['cells'][1][1])
        self.assertEqual(saved['modules'][0]['cells'][0][1], '12')
        self.assertEqual(saved['source_content']['outline'], '收入 12 万元；待统计')
        with self.assertRaises(HTTPException) as caught:
            main.save_content(self.pid, sid, dict(revision=1, title='旧窗口内容'))
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(main.slides(self.pid)['items'][0]['title'], '原稿标题')
        main.configure_project(self.pid, dict(confirm_content=True))
        self.assert_stage(4)
        main.save_content(self.pid, sid, dict(revision=2, title='', outline='', points=[], modules=[]))
        self.assert_stage(3)
        self.assertFalse(main.slides(self.pid)['items'][0]['content_ready'])
        with self.assertRaises(HTTPException) as caught:
            main.configure_project(self.pid, dict(confirm_content=True))
        self.assertEqual(caught.exception.status_code, 400)


if __name__ == '__main__':
    unittest.main()
