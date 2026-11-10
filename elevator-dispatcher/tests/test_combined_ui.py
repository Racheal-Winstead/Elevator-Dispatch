"""Exercise the single-console assignment/message/reply/handover path."""
import os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from streamlit.testing.v1 import AppTest
from state.audit import report

class CombinedConsoleTest(unittest.TestCase):
    def test_complete_shared_ui_flow_and_reload(self):
        with tempfile.TemporaryDirectory() as d:
            previous=os.environ.get('WORKBENCH_DB'); os.environ['WORKBENCH_DB']=str(Path(d)/'shared.db')
            try:
                path=str(Path(__file__).resolve().parents[1]/'app.py')
                app=AppTest.from_file(path).run(timeout=30)
                self.assertFalse(app.exception); self.assertEqual(len(app.tabs),6)
                next(c for c in app.checkbox if c.label=='I reviewed this complete crew and time window').check().run()
                next(b for b in app.button if b.label=='Confirm complete crew assignment').click().run()
                self.assertFalse(app.exception); self.assertEqual(app.metric[1].value,'1')
                next(b for b in app.button if b.label=='Save simulated message').click().run()
                self.assertFalse(app.exception)
                messages=app.session_state.store.messages(); self.assertEqual(len(messages),1)
                mid=messages[0]['message_id']; self.assertEqual(messages[0]['ticket_id'],'ED-001')
                app.checkbox(key='reply_apply_'+mid).check().run()
                next(b for b in app.button if b.label=='Record simulated reply').click().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.session_state.store.progress()['ED-001']['status'],'ACKNOWLEDGED')
                row=report(app.session_state.tickets,app.session_state.store)[0]
                self.assertEqual(row['last_reply'],'ACKNOWLEDGED'); self.assertEqual(row['messages_sent'],1)
                next(b for b in app.button if b.label=='Refresh synthetic source').click().run()
                self.assertFalse(app.exception); self.assertEqual(len(app.session_state.store.messages()),1)
                reopened=AppTest.from_file(path).run(timeout=30)
                self.assertFalse(reopened.exception)
                self.assertEqual(reopened.session_state.store.messages()[0]['response'],'ACKNOWLEDGED')
                self.assertEqual(reopened.session_state.store.progress()['ED-001']['status'],'ACKNOWLEDGED')
            finally:
                if previous is None: os.environ.pop('WORKBENCH_DB',None)
                else: os.environ['WORKBENCH_DB']=previous
