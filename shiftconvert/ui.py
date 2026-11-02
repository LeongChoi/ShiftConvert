from pathlib import Path
from threading import Event
import os
import sys
from PySide6.QtCore import Qt, QThread, Signal, QUrl, QSettings, QStandardPaths
from PySide6.QtGui import QDesktopServices, QColor, QFont, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QComboBox, QCheckBox, QDoubleSpinBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QMessageBox,
    QFrame, QFormLayout, QLineEdit, QAbstractItemView, QScrollArea, QSystemTrayIcon, QMenu)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from .core import Options, convert, formats, IMAGES, CAP_TARGETS, capabilities

STYLE='''
QWidget { background:#151a20; color:#edf3f2; font-family:"Segoe UI"; font-size:14px; }
QMainWindow { background:#151a20; }
QLabel#title { font-size:28px; font-weight:700; }
QLabel#muted { color:#a7b5bd; font-size:13px; }
QLabel#badge { color:#85ddbc; background:#203a34; border-radius:10px; padding:6px 12px; font-size:12px; }
QFrame#drop { border:2px dashed #4e7e70; border-radius:14px; background:#1d302c; }
QFrame#drop QLabel { background:transparent; border:none; }
QPushButton { padding:9px 16px; background:#29323a; color:#e8f0ef; border:1px solid #42515a; border-radius:7px; }
QPushButton:hover { border-color:#6ad7ad; background:#31473f; }
QPushButton:disabled { color:#79858c; background:#242b31; }
QPushButton#primary { background:#48c595; color:#102820; border:none; font-weight:700; padding:12px 25px; }
QPushButton#primary:hover { background:#69dcaf; }
QPushButton#primary:disabled { background:#344c42; color:#819c90; }
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox { background:#242c33; color:#edf3f2; border:1px solid #42515a; border-radius:6px; padding:7px; min-height:20px; }
QComboBox QAbstractItemView { background:#242c33; color:#edf3f2; selection-background-color:#356c58; }
QTableWidget { background:#20282e; color:#edf3f2; border:1px solid #3b4850; border-radius:8px; gridline-color:#303d44; }
QTableWidget::item { padding:7px; }
QTableWidget::item:selected { background:#315d4e; color:white; }
QHeaderView::section { background:#273139; border:none; border-bottom:1px solid #3b4850; padding:8px; color:#afc0c4; font-size:12px; }
QCheckBox { spacing:8px; }
QCheckBox::indicator { width:17px; height:17px; }
QProgressBar { border:none; background:#303d3a; height:6px; border-radius:3px; }
QProgressBar::chunk { background:#4ed2a4; border-radius:3px; }
QMenu { background:#242c33; color:#edf3f2; border:1px solid #42515a; }
QMenu::item:selected { background:#356c58; }
''' 


def label(text, kind=None):
    w=QLabel(text)
    if kind: w.setObjectName(kind)
    return w


def human(n):
    return f'{n/1_000_000:.2f} MB' if n>=1_000_000 else f'{n/1000:.1f} KB'


class Worker(QThread):
    status=Signal(int,str)
    done=Signal(int,object)
    failed=Signal(int,str)
    tick=Signal(int,int)
    def __init__(self,paths,output,opt,merge):
        super().__init__(); self.paths=paths; self.output=output; self.opt=opt; self.merge=merge; self.stop=Event()
    def run(self):
        jobs=[self.paths] if self.merge else [[p] for p in self.paths]
        for i,paths in enumerate(jobs):
            if self.stop.is_set():
                for j in range(i,len(jobs)): self.status.emit(j,'Stopped')
                break
            self.status.emit(i,'Converting…')
            try:
                result=convert(paths,self.output,self.opt,self.merge,lambda text:self.status.emit(i,text))
                self.done.emit(i,result)
            except Exception as e: self.failed.emit(i,str(e) or type(e).__name__)
            self.tick.emit(i+1,len(jobs))


class DropZone(QFrame):
    files=Signal(list)
    browse=Signal()
    def __init__(self):
        super().__init__(); self.setObjectName('drop'); self.setAcceptDrops(True)
        layout=QVBoxLayout(self); layout.setContentsMargins(24,20,24,20)
        title=label('Drop your files here'); title.setFont(QFont('Segoe UI',18,QFont.Weight.DemiBold)); title.setAlignment(Qt.AlignCenter)
        sub=label('Images, PDFs, documents, spreadsheets, audio & video','muted'); sub.setAlignment(Qt.AlignCenter)
        row=QHBoxLayout(); b=QPushButton('Choose files'); b.clicked.connect(self.browse); row.addStretch(); row.addWidget(b); row.addStretch()
        layout.addWidget(title); layout.addWidget(sub); layout.addLayout(row)
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls() and all(u.isLocalFile() for u in event.mimeData().urls()): event.acceptProposedAction()
    def dropEvent(self,event):
        self.files.emit([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]); event.acceptProposedAction()


class Window(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('ShiftConvert'); self.resize(900,870); self.setMinimumSize(760,660)
        self.paths=[]; self.worker=None; self.results={}; self.merge_active=False
        self.settings=QSettings('ShiftConvert','ShiftConvert')
        downloads=QStandardPaths.writableLocation(QStandardPaths.DownloadLocation) or str(Path.home()/'Downloads')
        old_default=Path.home()/'Documents'/'ShiftConvert'
        saved=self.settings.value('output',None)
        # Migrate the old app's default while respecting an explicitly chosen folder.
        self.output=Path(downloads if not saved or Path(saved)==old_default else saved)
        self.caps=capabilities()
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame); self.setCentralWidget(scroll)
        root=QWidget(); scroll.setWidget(root); v=QVBoxLayout(root); v.setContentsMargins(28,22,28,22); v.setSpacing(12)
        header=QHBoxLayout(); header.addWidget(label('ShiftConvert','title')); header.addStretch(); header.addWidget(label('●  Runs locally','badge')); v.addLayout(header)
        v.addWidget(label('Your files. A different format.','muted'))
        self.drop=DropZone(); self.drop.browse.connect(self.browse); self.drop.files.connect(self.add_files); v.addWidget(self.drop)
        self.table=QTableWidget(0,3); self.table.setHorizontalHeaderLabels(['FILE','SIZE','STATUS'])
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch)
        self.table.verticalHeader().hide(); self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.table.setMinimumHeight(150); self.table.setMaximumHeight(190)
        self.table.itemDoubleClicked.connect(self.show_details); v.addWidget(self.table)
        row=QHBoxLayout(); self.count=label('No files added','muted'); row.addWidget(self.count); row.addStretch()
        self.remove=QPushButton('Remove selected'); self.remove.clicked.connect(self.remove_selected); row.addWidget(self.remove)
        self.clear=QPushButton('Clear'); self.clear.clicked.connect(self.clear_files); row.addWidget(self.clear); v.addLayout(row)
        self.controls=QWidget(); c=QVBoxLayout(self.controls); c.setContentsMargins(0,0,0,0); c.setSpacing(12)
        row=QHBoxLayout(); row.addWidget(label('Convert to')); self.target=QComboBox(); self.target.setMinimumWidth(130); row.addWidget(self.target); row.addStretch()
        self.merge=QCheckBox('Combine images into one PDF'); self.merge.setChecked(True); row.addWidget(self.merge); c.addLayout(row)
        row=QHBoxLayout(); self.limit=QCheckBox('Maximum file size'); row.addWidget(self.limit)
        self.size_input=QDoubleSpinBox(); self.size_input.setRange(.01,10000); self.size_input.setDecimals(2); self.size_input.setValue(2); self.size_input.setEnabled(False); row.addWidget(self.size_input)
        self.unit=QComboBox(); self.unit.addItems(['MB','KB']); self.unit.setEnabled(False); row.addWidget(self.unit); row.addWidget(label('per output file','muted')); row.addStretch(); c.addLayout(row)
        self.limit.toggled.connect(lambda on:(self.size_input.setEnabled(on),self.unit.setEnabled(on)))
        self.hint=label('Add files to see compatible output formats.','muted'); self.hint.setWordWrap(True); c.addWidget(self.hint)
        self.advanced_button=QPushButton('More options  ▾'); self.advanced_button.setCheckable(True); c.addWidget(self.advanced_button,alignment=Qt.AlignLeft)
        self.advanced=QWidget(); f=QFormLayout(self.advanced); f.setContentsMargins(0,4,0,4)
        self.quality=QSpinBox(); self.quality.setRange(15,100); self.quality.setValue(90); f.addRow('Image quality',self.quality)
        self.resize_check=QCheckBox('Allow smaller image dimensions to meet size limit'); self.resize_check.setChecked(True); f.addRow(self.resize_check)
        self.flatten=QCheckBox('Convert PDF pages to images if needed to meet the limit'); self.flatten.setToolTip('Removes selectable text, links, annotations and forms.'); f.addRow(self.flatten)
        self.dpi=QSpinBox(); self.dpi.setRange(36,600); self.dpi.setValue(150); f.addRow('PDF image resolution (DPI)',self.dpi)
        self.ocr=QCheckBox('Use OCR for scanned PDF pages'); f.addRow(self.ocr)
        self.lang=QComboBox(); self.lang.addItem('English','eng'); self.lang.addItem('English + Traditional Chinese','eng+chi_tra'); self.lang.addItem('English + Simplified Chinese','eng+chi_sim'); f.addRow('OCR language (installed packs)',self.lang)
        self.delimiter=QComboBox(); self.delimiter.addItem('Comma',','); self.delimiter.addItem('Semicolon',';'); self.delimiter.addItem('Tab','\t'); f.addRow('CSV separator',self.delimiter)
        self.bitrate=QComboBox(); [self.bitrate.addItem(f'{n} kbps',n) for n in [96,128,192,256,320]]; self.bitrate.setCurrentIndex(2); f.addRow('Audio bitrate',self.bitrate)
        self.crf=QSpinBox(); self.crf.setRange(15,40); self.crf.setValue(23); f.addRow('Video CRF (lower = higher quality)',self.crf)
        self.startup=QCheckBox('Start quietly in the system tray when I sign in')
        self.startup.setChecked(startup_enabled()); self.startup.toggled.connect(self.set_startup)
        self.startup.setVisible(sys.platform=='win32'); f.addRow(self.startup)
        self.advanced.hide(); self.advanced_button.toggled.connect(self.advanced.setVisible); c.addWidget(self.advanced)
        row=QHBoxLayout(); self.folder=QLineEdit(str(self.output)); self.folder.setReadOnly(True); row.addWidget(self.folder)
        self.folder_button=QPushButton('Save to…'); self.folder_button.clicked.connect(self.choose_folder); row.addWidget(self.folder_button); c.addLayout(row)
        v.addWidget(self.controls)
        self.progress=QProgressBar(); self.progress.setTextVisible(False); self.progress.setRange(0,100); self.progress.setValue(0); v.addWidget(self.progress)
        row=QHBoxLayout(); self.summary=label('Ready when you are.','muted'); self.summary.setWordWrap(True); row.addWidget(self.summary,1)
        self.stop=QPushButton('Stop after current file'); self.stop.setVisible(False); self.stop.clicked.connect(self.stop_work); row.addWidget(self.stop)
        self.go=QPushButton('Convert files'); self.go.setObjectName('primary'); self.go.clicked.connect(self.start); self.go.setEnabled(False); row.addWidget(self.go); v.addLayout(row)
        row=QHBoxLayout(); self.open=QPushButton('Open output folder'); self.open.clicked.connect(lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output)))); row.addWidget(self.open)
        row.addStretch(); help_btn=QPushButton('Formats & setup'); help_btn.clicked.connect(self.show_help); row.addWidget(help_btn); v.addLayout(row)
        footer=label('Files save directly to the selected folder. Existing files are never overwritten.','muted'); footer.setWordWrap(True); v.addWidget(footer); v.addStretch()
        self.target.currentTextChanged.connect(self.update_options)
        self.update_formats()

    def set_startup(self, enabled):
        try: set_startup(enabled)
        except OSError as e:
            self.startup.blockSignals(True); self.startup.setChecked(not enabled); self.startup.blockSignals(False)
            QMessageBox.warning(self,'Startup setting',str(e))

    def browse(self):
        names,_=QFileDialog.getOpenFileNames(self,'Choose files'); self.add_files(names)
    def add_files(self,names):
        if self.worker and self.worker.isRunning(): return
        skipped=[]
        for name in names:
            p=Path(name).resolve()
            if not p.is_file() or not formats(p): skipped.append(p.name); continue
            if p not in self.paths:
                self.paths.append(p); row=self.table.rowCount(); self.table.insertRow(row)
                for col,text in enumerate([p.name,human(p.stat().st_size),'Ready']):
                    item=QTableWidgetItem(text); item.setToolTip(str(p) if col==0 else text); self.table.setItem(row,col,item)
        self.results={}; self.update_formats()
        if skipped: QMessageBox.information(self,'Unsupported files','These files were not added:\n'+'\n'.join(skipped[:15])+'\n\nFolders and .img disk images are not supported.')
    def remove_selected(self):
        for row in sorted({i.row() for i in self.table.selectedIndexes()},reverse=True): self.paths.pop(row); self.table.removeRow(row)
        self.results={}; self.update_formats()
    def clear_files(self):
        self.paths=[]; self.results={}; self.table.setRowCount(0); self.update_formats()
    def update_formats(self):
        old=self.target.currentText().lower(); self.target.blockSignals(True); self.target.clear()
        common=set(formats(self.paths[0])) if self.paths else set()
        for path in self.paths[1:]: common.intersection_update(formats(path))
        order=['jpg','png','webp','heic','pdf','docx','txt','csv','xlsx','json','mp3','wav','mp4','webm','mkv','flac','m4a','ogg','bmp','tiff']
        self.target.addItems([x.upper() for x in order if x in common])
        if old in common: self.target.setCurrentText(old.upper())
        self.target.blockSignals(False); self.count.setText(f'{len(self.paths)} file'+('s' if len(self.paths)!=1 else ''))
        self.go.setEnabled(bool(common)); self.update_options()
    def update_options(self):
        target=self.target.currentText().lower()
        can_merge=target=='pdf' and len(self.paths)>1 and all(p.suffix[1:].lower() in IMAGES for p in self.paths)
        self.merge.setVisible(can_merge)
        can_limit=target in CAP_TARGETS; self.limit.setEnabled(can_limit)
        if not can_limit: self.limit.setChecked(False)
        self.flatten.setEnabled(target=='pdf' and any(p.suffix.lower() not in {'.jpg','.jpeg','.heic','.heif','.png','.webp','.bmp','.gif','.tif','.tiff'} for p in self.paths))
        self.ocr.setEnabled(target in {'txt','docx'} and any(p.suffix.lower()=='.pdf' for p in self.paths))
        if not target: text='Add files to see compatible formats.' if not self.paths else 'These files have no common output format. Convert one category at a time.'
        elif target=='pdf': text='Images become a photo PDF. Size limits may reduce image quality and resolution.'
        elif target in {'csv','json'}: text='XLSX: one file per worksheet. Formulas need saved results; formatting is removed.'
        elif target=='docx': text='Editable Word output. PDF layout recovery is approximate; enable OCR for scans.'
        elif target=='txt': text='Plain text output. Images require OCR; for scanned PDFs, enable OCR under More options.'
        elif target in CAP_TARGETS: text='Size is checked after conversion. Resizing is allowed by default; change this in More options.'
        else: text='Maximum file size is available for images and PDFs. Audio/video quality is under More options.'
        self.hint.setText(text)
    def choose_folder(self):
        value=QFileDialog.getExistingDirectory(self,'Save conversions to',str(self.output))
        if value: self.output=Path(value); self.folder.setText(value); self.settings.setValue('output',value)
    def start(self):
        target=self.target.currentText().lower()
        need_ocr=(target=='txt' and any(p.suffix[1:].lower() in IMAGES for p in self.paths)) or (self.ocr.isEnabled() and self.ocr.isChecked())
        need_office=any(p.suffix.lower() in {'.doc','.odt','.rtf'} or (p.suffix.lower()=='.docx' and target=='pdf') for p in self.paths)
        if (need_ocr and not self.caps['tesseract']) or (need_office and not self.caps['soffice']):
            QMessageBox.information(self,'One-time setup needed',('OCR needs Tesseract.\n' if need_ocr and not self.caps['tesseract'] else '')+('Word/Office conversion needs LibreOffice.\n' if need_office and not self.caps['soffice'] else '')+'Open “Formats & setup” for instructions.'); return
        cap=int(self.size_input.value()*(1_000_000 if self.unit.currentText()=='MB' else 1000)) if self.limit.isChecked() else None
        opt=Options(target=target,quality=self.quality.value(),max_bytes=cap,allow_resize=self.resize_check.isChecked(),rasterize_pdf=self.flatten.isEnabled() and self.flatten.isChecked(),dpi=self.dpi.value(),ocr=need_ocr,ocr_language=self.lang.currentData(),delimiter=self.delimiter.currentData(),audio_kbps=self.bitrate.currentData(),video_crf=self.crf.value())
        self.merge_active=self.merge.isVisible() and self.merge.isChecked()
        self.results={}; self.success_count=0; self.fail_count=0; self.progress.setValue(0)
        for i in range(len(self.paths)): self.set_status(i,'Queued')
        self.worker=Worker(list(self.paths),self.output,opt,self.merge_active)
        self.worker.status.connect(self.on_status); self.worker.done.connect(self.on_done); self.worker.failed.connect(self.on_error)
        self.worker.tick.connect(lambda a,b:self.progress.setValue(int(a/b*100)))
        self.worker.finished.connect(self.finished)
        for w in [self.controls,self.drop,self.remove,self.clear,self.go]: w.setEnabled(False)
        self.stop.show(); self.stop.setEnabled(True); self.summary.setText('Converting locally…'); self.worker.start()
    def affected(self,i): return range(len(self.paths)) if self.merge_active else [i]
    def set_status(self,row,text,color=None):
        item=self.table.item(row,2); item.setText(text); item.setToolTip(text)
        item.setForeground(QColor(color or '#a7b5bd'))
    def on_status(self,i,text):
        for row in self.affected(i): self.set_status(row,text)
    def on_done(self,i,result):
        self.success_count+=1
        detail='Saved to: '+str(result.directory)+'\n\n'+'\n'.join(p.name+' — '+human(p.stat().st_size) for p in result.files)+'\n\n'+'\n'.join(result.notes)
        for row in self.affected(i):
            self.results[row]=detail; self.set_status(row,'Done · '+human(sum(p.stat().st_size for p in result.files)),'#7de0ba')
    def on_error(self,i,text):
        self.fail_count+=1
        for row in self.affected(i): self.results[row]=text; self.set_status(row,'Failed · double-click for details','#ff9b9b')
    def stop_work(self):
        if self.worker: self.worker.stop.set(); self.stop.setEnabled(False); self.summary.setText('Stopping after this file finishes…')
    def finished(self):
        stopped=self.worker.stop.is_set()
        for w in [self.controls,self.drop,self.remove,self.clear,self.go]: w.setEnabled(True)
        self.stop.hide(); self.summary.setText(f'{self.success_count} conversion(s) saved · {self.fail_count} failed'+(' · stopped' if stopped else ''))
        self.update_options()
    def show_details(self,item):
        if item.row() in self.results: QMessageBox.information(self,'Conversion details',self.results[item.row()])
    def show_help(self):
        page=Path(__file__).resolve().parent.parent/'START_HERE.html'
        if page.exists(): QDesktopServices.openUrl(QUrl.fromLocalFile(str(page)))
        else: QMessageBox.information(self,'Setup',str(self.caps))
    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self,'Conversion running','Use “Stop after current file” and wait for it to finish before closing.'); event.ignore()
        elif getattr(self,'tray',None) and self.tray.isVisible() and self.startup.isChecked() and not getattr(self,'quitting',False):
            self.hide(); event.ignore()
        else: event.accept()


def startup_enabled():
    if sys.platform != 'win32': return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
            return bool(winreg.QueryValueEx(key,'ShiftConvert')[0])
    except FileNotFoundError: return False


def set_startup(enabled):
    if sys.platform != 'win32': return
    import winreg
    root=Path(__file__).resolve().parent.parent
    exe=root/'ShiftConvert.exe'
    if enabled and not exe.is_file(): raise OSError('Startup is available after installing ShiftConvert.')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
        if enabled: winreg.SetValueEx(key,'ShiftConvert',0,winreg.REG_SZ,f'"{exe}" --background')
        else:
            try: winreg.DeleteValue(key,'ShiftConvert')
            except FileNotFoundError: pass


def main():
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('ShiftConvert.Desktop')
    app=QApplication(sys.argv); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
    app.setWindowIcon(QIcon(str(Path(__file__).with_name('app.png'))))
    # Reopening a pinned shortcut brings the existing tray instance forward.
    server_name='ShiftConvert-v1-'+str(Path.home())
    import hashlib
    server_name='ShiftConvert-'+hashlib.sha256(server_name.encode()).hexdigest()[:16]
    socket=QLocalSocket(); socket.connectToServer(server_name)
    if socket.waitForConnected(400):
        socket.write(b'show'); socket.flush(); socket.waitForBytesWritten(400); socket.disconnectFromServer(); return
    QLocalServer.removeServer(server_name)
    server=QLocalServer()
    if not server.listen(server_name): server=None
    window=Window(); window.setWindowIcon(app.windowIcon()); window.quitting=False
    def show_window():
        window.showNormal(); window.raise_(); window.activateWindow()
    def on_connection():
        while server.hasPendingConnections():
            conn=server.nextPendingConnection(); conn.readyRead.connect(show_window)
            if conn.bytesAvailable(): show_window()
    if server: server.newConnection.connect(on_connection)
    tray=None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray=QSystemTrayIcon(app.windowIcon(),window); tray.setToolTip('ShiftConvert')
        menu=QMenu(); menu.addAction('Open ShiftConvert',show_window)
        def quit_app():
            if window.worker and window.worker.isRunning():
                show_window(); QMessageBox.information(window,'Conversion running','Stop the conversion before quitting.'); return
            window.quitting=True; tray.hide(); app.quit()
        menu.addAction('Quit',quit_app); tray.setContextMenu(menu); window.tray_menu=menu
        tray.activated.connect(lambda reason: show_window() if reason in (QSystemTrayIcon.Trigger,QSystemTrayIcon.DoubleClick) else None)
        tray.show(); window.tray=tray
    if '--background' not in sys.argv or not tray: window.show()
    app.exec()
