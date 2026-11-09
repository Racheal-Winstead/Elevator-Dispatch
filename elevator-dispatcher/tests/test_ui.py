"""Streamlit interaction acceptance against a disposable local database."""
import os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from streamlit.testing.v1 import AppTest

class ConsoleTests(unittest.TestCase):
    def test_review_commit_manual_rejection_and_remove(self):
        with tempfile.TemporaryDirectory() as folder:
            old=os.environ.get('WORKBENCH_DB')
            os.environ['WORKBENCH_DB']=str(Path(folder)/'ui.sqlite3')
            try:
                app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
                self.assertFalse(app.exception)
                self.assertEqual(len(app.tabs),5)
                # Default ticket has a complete synthetic recommendation.
                confirm=next(b for b in app.button if b.label=='Confirm complete crew assignment')
                confirm.click().run()
                self.assertFalse(app.exception)
                self.assertTrue(any('No assignment was saved' in e.value for e in app.error))
                next(c for c in app.checkbox if c.label=='I reviewed this complete crew and time window').check().run()
                next(b for b in app.button if b.label=='Confirm complete crew assignment').click().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.metric[1].value,'1')
                self.assertEqual(app.session_state.store.assignments()[0]['scheduler_source'],'DESHAWN_PINNED_ENGINE')
                history_size=len(app.session_state.store.history())
                next(b for b in app.button if b.label=='Refresh synthetic source').click().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.metric[1].value,'1')
                self.assertGreater(len(app.session_state.store.history()),history_size)
                app.selectbox(key='progress_ticket').set_value('ED-001').run()
                self.assertNotIn('UNASSIGNED',app.selectbox(key='new_status_ED-001').options)
                next(b for b in app.button if b.label=='Validate and commit manual proposal').click().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.metric[1].value,'1')
                self.assertTrue(any('Assignment rejected' in e.value for e in app.error))
                next(b for b in app.button if b.label=='Remove selected complete crew').click().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.metric[1].value,'0')
            finally:
                if old is None: os.environ.pop('WORKBENCH_DB',None)
                else: os.environ['WORKBENCH_DB']=old
