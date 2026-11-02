import os,time
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QMimeData,QUrl,QPointF,Qt
from PySide6.QtGui import QDropEvent
from PySide6.QtTest import QTest
from shiftconvert.ui import Window,STYLE
@pytest.fixture(scope='module')
def app():
 a=QApplication.instance() or QApplication([]); a.setStyleSheet(STYLE); return a

def wait(app,w):
 deadline=time.monotonic()+30
 while w.worker.isRunning() and time.monotonic()<deadline: app.processEvents(); QTest.qWait(10)
 app.processEvents(); assert not w.worker.isRunning()

def test_drag_drop_and_batch(app,tmp_path):
 w=Window(); w.show(); app.processEvents()
 p=tmp_path/'a.png'; Image.new('RGB',(300,200),'red').save(p)
 p2=tmp_path/'b.png'; Image.new('RGB',(300,200),'blue').save(p2)
 data=QMimeData(); data.setUrls([QUrl.fromLocalFile(str(p)),QUrl.fromLocalFile(str(p2))])
 event=QDropEvent(QPointF(10,10),Qt.CopyAction,data,Qt.LeftButton,Qt.NoModifier)
 w.drop.dropEvent(event); assert len(w.paths)==2
 w.target.setCurrentText('PDF'); w.limit.setChecked(True); w.size_input.setValue(.05); w.output=tmp_path/'out'
 w.start(); wait(app,w)
 assert w.success_count==1 and w.fail_count==0
 assert len(list(w.output.rglob('*.pdf')))==1
 assert 'Done' in w.table.item(1,2).text()
 w.close()

def test_queue_continues_after_error(app,tmp_path):
 w=Window(); w.show(); app.processEvents()
 bad=tmp_path/'bad.png'; bad.write_bytes(b'invalid')
 good=tmp_path/'good.png'; Image.new('RGB',(50,50),'white').save(good)
 w.add_files([str(bad),str(good)]); w.target.setCurrentText('JPG'); w.output=tmp_path/'out'
 w.start(); wait(app,w)
 assert w.fail_count==1 and w.success_count==1
 assert 'Failed' in w.table.item(0,2).text() and 'Done' in w.table.item(1,2).text()
 assert w.go.isEnabled(); w.close()

def test_incompatible_selection(app,tmp_path):
 w=Window(); p=tmp_path/'x.png'; Image.new('RGB',(10,10)).save(p); c=tmp_path/'x.csv'; c.write_text('a,b\n1,2')
 w.add_files([str(p),str(c)]); assert not w.go.isEnabled() and w.target.count()==0; w.close()

def test_limit_disabled_for_csv(app,tmp_path):
 w=Window(); c=tmp_path/'x.json'; c.write_text('[{"a":1}]'); w.add_files([str(c)]); w.target.setCurrentText('CSV')
 assert not w.limit.isEnabled() and not w.limit.isChecked(); w.close()
