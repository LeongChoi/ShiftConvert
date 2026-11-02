import sys
from pathlib import Path
# Embedded Python uses an explicit search path; keep source modules editable.
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root))
try:
    from shiftconvert.ui import main
    main()
except Exception:
    import traceback, ctypes, os
    log=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'ShiftConvert'/'startup-error.txt'
    log.parent.mkdir(parents=True,exist_ok=True)
    log.write_text(traceback.format_exc(),encoding='utf-8')
    if sys.platform=='win32': ctypes.windll.user32.MessageBoxW(0,'ShiftConvert could not start. Details saved to:\n'+str(log),'ShiftConvert',16)
    else: raise
