from __future__ import annotations
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable
from PIL import Image, ImageOps
import pymupdf as fitz
from pillow_heif import register_heif_opener
register_heif_opener()

IMAGES = {'jpg','jpeg','png','webp','heic','heif','bmp','tif','tiff','gif'}
IMAGE_OUT = ['jpg','png','webp','heic','bmp','tiff']
AUDIO = {'mp3','wav','flac','m4a','aac','ogg'}
VIDEO = {'mp4','mov','mkv','avi','webm'}
CAP_TARGETS = set(IMAGE_OUT + ['pdf'])

class ConversionError(Exception):
    pass

@dataclass(frozen=True)
class Options:
    target: str
    quality: int = 90
    max_bytes: int | None = None
    allow_resize: bool = True
    rasterize_pdf: bool = False
    dpi: int = 150
    ocr: bool = False
    ocr_language: str = 'eng'
    delimiter: str = ','
    audio_kbps: int = 192
    video_crf: int = 23

@dataclass
class Result:
    directory: Path
    files: list[Path]
    notes: list[str]


def formats(path: Path) -> list[str]:
    ext = path.suffix.lower().lstrip('.')
    if ext in IMAGES: return IMAGE_OUT + ['pdf','txt']
    if ext == 'pdf': return ['docx','txt','jpg','png','webp','pdf']
    if ext in {'docx','doc','odt','rtf'}: return ['pdf','txt']
    if ext == 'txt': return ['pdf','docx']
    if ext in {'xlsx','csv','json'}: return [x for x in ['xlsx','csv','json'] if x != ext]
    if ext in VIDEO: return ['mp4','webm','mkv','mp3','wav','flac','m4a','ogg']
    if ext in AUDIO: return ['mp3','wav','flac','m4a','ogg']
    return []


def safe_name(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', value).strip(' .')[:100] or 'file'
    if value.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
        value = '_' + value
    return value


def _tool(name: str) -> str | None:
    exe = name + ('.exe' if os.name == 'nt' else '')
    root = Path(__file__).resolve().parent.parent
    bundled = root / 'tools' / name / exe
    if bundled.is_file(): return str(bundled)
    found = shutil.which(name)
    if found: return found
    if name == 'ffmpeg':
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception: return None
    candidates = {'soffice': ['LibreOffice/program/soffice.exe'], 'tesseract': ['Tesseract-OCR/tesseract.exe']}
    for base in [os.environ.get('ProgramFiles',''), os.environ.get('ProgramFiles(x86)',''), os.environ.get('LOCALAPPDATA','')]:
        if not base: continue
        for tail in candidates.get(name, []):
            p = Path(base) / tail
            if p.is_file(): return str(p)
    return None


def capabilities() -> dict[str, bool]:
    return {name: bool(_tool(name)) for name in ['ffmpeg','soffice','tesseract']}


def _run(args: list[str], timeout: int = 1800) -> str:
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, creationflags=flags, timeout=timeout, text=True,
            encoding='utf-8', errors='replace')
    except subprocess.TimeoutExpired as e:
        raise ConversionError('Conversion timed out. Try a smaller file.') from e
    if result.returncode:
        raise ConversionError((result.stderr or result.stdout or 'Conversion failed.')[-2500:])
    return result.stdout


def load_image(path: Path, notes: list[str]) -> Image.Image:
    with Image.open(path) as src:
        if getattr(src, 'n_frames', 1) > 1:
            notes.append(f'{path.name}: only the first / primary image was converted.')
        im = ImageOps.exif_transpose(src)
        if im.mode not in ('RGB','RGBA'): im = im.convert('RGBA' if 'transparency' in src.info else 'RGB')
        return im.copy()


def rgb(im: Image.Image) -> Image.Image:
    if im.mode == 'RGBA':
        bg = Image.new('RGB', im.size, 'white'); bg.paste(im, mask=im.getchannel('A')); return bg
    return im.convert('RGB')


def encode_image(im: Image.Image, target: str, quality: int) -> bytes:
    buf = io.BytesIO()
    fmt = {'jpg':'JPEG','png':'PNG','webp':'WEBP','heic':'HEIF','bmp':'BMP','tiff':'TIFF'}[target]
    kw = {}
    if target in {'jpg','heic'}: im = rgb(im)
    if target in {'jpg','webp','heic'}: kw['quality'] = quality
    if target == 'jpg': kw.update(optimize=True)
    if target == 'png': kw.update(optimize=True, compress_level=9)
    if target == 'tiff': kw['compression'] = 'tiff_deflate'
    im.save(buf, format=fmt, **kw)
    return buf.getvalue()


def sized_image(im: Image.Image, opt: Options) -> tuple[bytes, str]:
    original = im.size
    for _ in range(24):
        full = encode_image(im, opt.target, opt.quality)
        if opt.max_bytes is None or len(full) <= opt.max_bytes:
            return full, f'{im.width} × {im.height}, quality {opt.quality}'
        if opt.target in {'jpg','webp','heic'}:
            low_data = encode_image(im, opt.target, 15)
            if len(low_data) <= opt.max_bytes:
                best, best_q, lo, hi = low_data, 15, 16, opt.quality - 1
                while lo <= hi:
                    q = (lo + hi) // 2
                    data = encode_image(im, opt.target, q)
                    if len(data) <= opt.max_bytes: best, best_q, lo = data, q, q + 1
                    else: hi = q - 1
                return best, f'{im.width} × {im.height}, quality {best_q}'
        if not opt.allow_resize or max(im.size) <= 32: break
        im = im.resize((max(1,int(im.width*.8)), max(1,int(im.height*.8))), Image.Resampling.LANCZOS)
    raise ConversionError(f'Cannot fit {original[0]} × {original[1]} image within the size limit. Increase the limit or enable resizing.')


def pdf_bytes(doc: fitz.Document) -> bytes:
    return doc.tobytes(garbage=4, deflate=True, use_objstms=1)


def pdf_from_images(images: list[Image.Image], quality: int, scale: float = 1.0) -> bytes:
    with fitz.open() as doc:
        for image in images:
            im = image
            if scale != 1:
                im = im.resize((max(1,int(im.width*scale)),max(1,int(im.height*scale))), Image.Resampling.LANCZOS)
            page = doc.new_page(width=max(1,image.width*72/150), height=max(1,image.height*72/150))
            page.insert_image(page.rect, stream=encode_image(im,'jpg',quality))
        return pdf_bytes(doc)


def capped_photo_pdf(images: list[Image.Image], opt: Options) -> bytes:
    for scale in ([1,.8,.6,.45,.3,.2,.12,.08,.04] if opt.allow_resize else [1]):
        for q in list(dict.fromkeys([opt.quality,min(opt.quality,75),min(opt.quality,50),min(opt.quality,30),15])):
            data = pdf_from_images(images, q, scale)
            if opt.max_bytes is None or len(data) <= opt.max_bytes: return data
    raise ConversionError('Cannot fit all pages within the PDF size limit. Increase the limit or enable resizing.')


def fit_pdf(path: Path, opt: Options, notes: list[str]):
    with fitz.open(path) as doc:
        data = pdf_bytes(doc)
        if opt.max_bytes and len(data) > opt.max_bytes:
            if not opt.rasterize_pdf:
                raise ConversionError('PDF is above the size limit after lossless compression. Enable “Convert PDF pages to images” or increase the limit.')
            for dpi in [opt.dpi,100,72,50,36]:
                if dpi > opt.dpi: continue
                for quality in [opt.quality,60,35,15]:
                    if quality > opt.quality: continue
                    with fitz.open() as out:
                        for page in doc:
                            pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
                            im = Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
                            p = out.new_page(width=page.rect.width,height=page.rect.height)
                            p.insert_image(p.rect, stream=encode_image(im,'jpg',quality))
                        data = pdf_bytes(out)
                    if len(data) <= opt.max_bytes:
                        notes.append(f'PDF pages flattened to images at {dpi} DPI; selectable text, links and forms removed.')
                        path.write_bytes(data); return
            raise ConversionError('PDF cannot fit the requested size limit. No output was saved.')
    path.write_bytes(data)


def ocr_image(im: Image.Image, work: Path, opt: Options) -> str:
    tool = _tool('tesseract')
    if not tool: raise ConversionError('OCR needs Tesseract. Install it, then restart ShiftConvert. See START_HERE.html.')
    p = work / '_ocr_input.png'
    rgb(im).save(p)
    try: return _run([tool,str(p),'stdout','-l',opt.ocr_language], timeout=300)
    finally: p.unlink(missing_ok=True)


def text_doc(text: str, target: Path):
    from docx import Document
    doc = Document()
    for line in text.splitlines(): doc.add_paragraph(line)
    doc.save(target)


def text_pdf(text: str, target: Path):
    # Story uses MuPDF's bundled fonts, including CJK fallback, and automatic pagination.
    import html
    story = fitz.Story(html='<html><body style="font-size:11pt; font-family:sans-serif"><div style="white-space:pre-wrap">'+html.escape(text).replace('\n','<br>')+'</div></body></html>')
    writer = fitz.DocumentWriter(str(target))
    rect = fitz.paper_rect('a4'); content = rect + (40,40,-40,-40)
    try:
        more = True
        while more:
            dev = writer.begin_page(rect)
            more, _ = story.place(content)
            story.draw(dev); writer.end_page()
    finally: writer.close()


def office_convert(src: Path, work: Path, target: str):
    tool = _tool('soffice')
    if not tool: raise ConversionError('This conversion needs LibreOffice. Install LibreOffice, then restart ShiftConvert. See START_HERE.html.')
    with tempfile.TemporaryDirectory(prefix='shift-office-') as profile:
        _run([tool, '-env:UserInstallation='+Path(profile).as_uri(), '--headless', '--convert-to', target, '--outdir',str(work),str(src)])
    p = work / (src.stem+'.'+target)
    if not p.is_file(): raise ConversionError('LibreOffice did not produce an output file.')
    return p


def cell_value(v):
    if v is None: return ''
    if isinstance(v,(date,datetime)): return v.isoformat()
    if isinstance(v,(list,dict)): return json.dumps(v,ensure_ascii=False)
    return v


def table_convert(src: Path, work: Path, opt: Options, notes: list[str]):
    from openpyxl import load_workbook, Workbook
    ext = src.suffix.lower()
    tables = []
    if ext == '.xlsx':
        with_values = load_workbook(src,read_only=True,data_only=True)
        with_formulas = load_workbook(src,read_only=True,data_only=False)
        try:
            for sheet in with_values:
                rows = []
                for values, formulas in zip(sheet.iter_rows(), with_formulas[sheet.title].iter_rows()):
                    row = []
                    for value, formula in zip(values,formulas):
                        if formula.data_type == 'f' and value.value is None:
                            raise ConversionError(f'{sheet.title}!{formula.coordinate}: formula has no saved result. Open and save this workbook in Excel or LibreOffice first.')
                        row.append(cell_value(value.value))
                    rows.append(row)
                tables.append((sheet.title,rows))
            notes.append('One output per worksheet. Formatting, formulas and workbook features are not retained.')
        finally: with_values.close(); with_formulas.close()
    elif ext == '.csv':
        with src.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.reader(f,delimiter=opt.delimiter))
        tables=[(src.stem,rows)]
    else:
        value=json.loads(src.read_text(encoding='utf-8-sig'))
        if not isinstance(value,list) or not all(isinstance(x,dict) for x in value):
            raise ConversionError('JSON must be a list of objects, e.g. [{"name":"Jayden","score":8}].')
        keys=list(dict.fromkeys(k for row in value for k in row))
        tables=[(src.stem,[keys]+[[cell_value(row.get(k)) for k in keys] for row in value])]
        notes.append('Nested JSON values are stored as JSON text in cells; spreadsheet type inference may differ.')
    for i,(name,rows) in enumerate(tables):
        out=work/(f'{i+1:02d}_{safe_name(name)}.{opt.target}')
        if opt.target=='csv':
            with out.open('w',encoding='utf-8-sig',newline='') as f: csv.writer(f,delimiter=opt.delimiter).writerows(rows)
        elif opt.target=='json':
            headers=[str(v) for v in rows[0]] if rows else []
            if len(set(headers))!=len(headers) or any(not h.strip() for h in headers):
                raise ConversionError(f'{name}: JSON conversion needs non-empty, unique column headers.')
            if any(len(row)>len(headers) for row in rows[1:]):
                raise ConversionError('A row has more values than the header. Fix the table before converting.')
            values=[dict(zip(headers,row+['']*(len(headers)-len(row)))) for row in rows[1:]]
            out.write_text(json.dumps(values,ensure_ascii=False,indent=2),encoding='utf-8')
        else:
            wb=Workbook(); ws=wb.active; ws.title='Data'
            for row in rows:
                ws.append(row)
                for cell in ws[ws.max_row]:
                    if isinstance(cell.value,str): cell.data_type='s'
            wb.save(out); wb.close()


def convert_one(src: Path, work: Path, opt: Options, notes: list[str], progress: Callable[[str],None]):
    ext=src.suffix.lower().lstrip('.')
    target=opt.target; out=work/(safe_name(src.stem)+'.'+target)
    if ext in IMAGES:
        im=load_image(src,notes)
        if target in IMAGE_OUT:
            data,description=sized_image(im,opt); out.write_bytes(data); notes.append(description)
        elif target=='pdf':
            out.write_bytes(capped_photo_pdf([im],opt)); notes.append('Image PDF; photos encoded as JPEG, transparency flattened to white.')
        elif target=='txt': out.write_text(ocr_image(im,work,opt),encoding='utf-8')
        if target!='txt': notes.append('Image metadata removed; HDR/extra frames are not retained.')
    elif ext=='pdf':
        with fitz.open(src) as doc:
            if doc.needs_pass: raise ConversionError('This PDF is password-protected. Unlock a copy before converting.')
            if not doc.is_pdf or doc.page_count==0: raise ConversionError('No readable PDF pages.')
            if target=='pdf': out.write_bytes(pdf_bytes(doc))
            elif target in IMAGE_OUT:
                for i,page in enumerate(doc):
                    progress(f'Rendering page {i+1} of {len(doc)}')
                    pix=page.get_pixmap(dpi=opt.dpi,colorspace=fitz.csRGB,alpha=False)
                    data,_=sized_image(Image.frombytes('RGB',(pix.width,pix.height),pix.samples),opt)
                    (work/f'{safe_name(src.stem)}_page_{i+1:03d}.{target}').write_bytes(data)
            elif target in {'txt','docx'}:
                if opt.ocr:
                    parts=[]
                    for i,page in enumerate(doc):
                        progress(f'Reading page {i+1} of {len(doc)}')
                        pix=page.get_pixmap(dpi=200,colorspace=fitz.csRGB,alpha=False)
                        parts.append(ocr_image(Image.frombytes('RGB',(pix.width,pix.height),pix.samples),work,opt))
                    text='\n\n'.join(parts)
                    if target=='txt': out.write_text(text,encoding='utf-8')
                    else: text_doc(text,out)
                    notes.append('OCR output is editable plain text; check recognition and reading order.')
                else:
                    page_text=[p.get_text(sort=True) for p in doc]
                    if any(not t.strip() for t in page_text):
                        raise ConversionError('At least one PDF page has no text. Enable OCR to include scanned/image pages.')
                    if target=='txt': out.write_text('\n\n'.join(page_text),encoding='utf-8')
                    else:
                        from pdf2docx import Converter
                        cv=Converter(str(src))
                        try: cv.convert(str(out),multi_processing=False)
                        finally: cv.close()
                        notes.append('PDF → Word is best-effort; check layout, tables and reading order.')
    elif ext in {'docx','doc','odt','rtf'}:
        if ext=='docx' and target=='txt':
            from docx import Document
            doc=Document(src)
            from docx.table import Table
            parts=[]
            for block in doc.iter_inner_content():
                if isinstance(block,Table): parts.extend('\t'.join(cell.text for cell in row.cells) for row in block.rows)
                else: parts.append(block.text)
            out.write_text('\n'.join(parts),encoding='utf-8')
            notes.append('Main body text and tables extracted; headers, footers and text boxes are omitted.')
        else: out=office_convert(src,work,target)
    elif ext=='txt':
        text=src.read_text(encoding='utf-8-sig')
        text_doc(text,out) if target=='docx' else text_pdf(text,out)
    elif ext in {'xlsx','csv','json'}: table_convert(src,work,opt,notes)
    elif ext in AUDIO | VIDEO:
        ffmpeg=_tool('ffmpeg')
        if not ffmpeg: raise ConversionError('FFmpeg is unavailable. Reinstall ShiftConvert.')
        cmd=[ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-y','-i',str(src)]
        if target in {'mp3','wav','flac','m4a','ogg'}:
            cmd+=['-map','0:a:0','-vn']
            codec={'mp3':'libmp3lame','wav':'pcm_s16le','flac':'flac','m4a':'aac','ogg':'libvorbis'}[target]
            cmd+=['-c:a',codec]
            if target in {'mp3','m4a','ogg'}: cmd+=['-b:a',f'{opt.audio_kbps}k']
        else:
            cmd+=['-map','0:v:0','-map','0:a:0?']
            if target=='webm': cmd+=['-c:v','libvpx-vp9','-crf',str(opt.video_crf),'-b:v','0','-c:a','libopus']
            else: cmd+=['-c:v','libx264','-crf',str(opt.video_crf),'-preset','medium','-c:a','aac','-pix_fmt','yuv420p','-vf','pad=ceil(iw/2)*2:ceil(ih/2)*2']
            if target=='mp4': cmd+=['-movflags','+faststart']
        _run(cmd+['-map_metadata','-1',str(out)],timeout=6*3600)
        notes.append('First audio/video streams converted; subtitles, extra tracks and metadata omitted.')
    if target=='pdf': fit_pdf(out,opt,notes)


def convert(paths: list[Path], output: Path, opt: Options, merge_pdf: bool=False,
            progress: Callable[[str],None]=lambda _:None) -> Result:
    paths=[Path(p).resolve() for p in paths]
    if not paths: raise ConversionError('Add at least one file.')
    if not 15 <= opt.quality <= 100: raise ConversionError('Quality must be between 15 and 100.')
    if opt.max_bytes is not None and (opt.max_bytes<=0 or opt.target not in CAP_TARGETS):
        raise ConversionError('Maximum file size is supported for image and PDF output only.')
    if any(not p.is_file() for p in paths): raise ConversionError('A source file is missing.')
    if any(opt.target not in formats(p) for p in paths): raise ConversionError('This output format is not compatible with every selected file.')
    if len(paths)>1 and not (merge_pdf and opt.target=='pdf' and all(p.suffix[1:].lower() in IMAGES for p in paths)):
        raise ConversionError('Multiple inputs in one job are supported only when combining images into a PDF.')
    output=Path(output).resolve(); output.mkdir(parents=True,exist_ok=True)
    notes=[]
    with tempfile.TemporaryDirectory(prefix='.shiftconvert-',dir=output) as temp:
        work=Path(temp)
        if merge_pdf and len(paths)>1:
            images=[load_image(p,notes) for p in paths]
            (work/'Combined.pdf').write_bytes(capped_photo_pdf(images,opt))
            notes.append('Images combined in queue order; metadata and extra frames omitted.')
        else: convert_one(paths[0],work,opt,notes,progress)
        files=sorted(work.iterdir())
        if not files or any(not p.is_file() or p.stat().st_size==0 for p in files):
            raise ConversionError('No usable output was produced.')
        if opt.max_bytes and any(p.stat().st_size>opt.max_bytes for p in files):
            raise ConversionError('Output exceeds the size limit. No output was saved.')
        published=[]
        try:
            for source in files:
                count=0
                while True:
                    suffix=f' ({count})' if count else ''
                    dest=output/(source.stem+suffix+source.suffix)
                    try:
                        with dest.open('xb') as target, source.open('rb') as origin:
                            published.append(dest)
                            shutil.copyfileobj(origin,target)
                        break
                    except FileExistsError: count+=1
        except Exception:
            for p in published: p.unlink(missing_ok=True)
            raise
    return Result(output,published,notes)
