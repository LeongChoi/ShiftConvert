import json
import pytest
from PIL import Image
import pymupdf as fitz
from openpyxl import Workbook,load_workbook
from docx import Document
from shiftconvert.core import convert,Options,ConversionError,_tool,_run
@pytest.fixture
def photo(tmp_path):
 p=tmp_path/'photo.png'; Image.effect_noise((1200,800),60).convert('RGB').save(p); return p
@pytest.mark.parametrize('target',['jpg','png','webp','heic','bmp','tiff'])
def test_image_format(photo,tmp_path,target):
 r=convert([photo],tmp_path/'out',Options(target))
 with Image.open(r.files[0]) as im: assert im.size==(1200,800)
@pytest.mark.parametrize('target',['jpg','png','webp','heic','bmp','tiff'])
def test_strict_cap(photo,tmp_path,target):
 r=convert([photo],tmp_path/'out',Options(target,max_bytes=50_000))
 assert 0<r.files[0].stat().st_size<=50_000
 with Image.open(r.files[0]) as im: im.load()
def test_heic_roundtrip(photo,tmp_path):
 h=convert([photo],tmp_path/'out',Options('heic')).files[0]
 j=convert([h],tmp_path/'out',Options('jpg')).files[0]
 with Image.open(j) as im: assert im.size==(1200,800)
def test_failed_cap_cleanup(photo,tmp_path):
 out=tmp_path/'out'
 with pytest.raises(ConversionError): convert([photo],out,Options('jpg',max_bytes=5))
 assert list(out.iterdir())==[]
def test_no_resize(photo,tmp_path):
 with pytest.raises(ConversionError): convert([photo],tmp_path/'out',Options('png',max_bytes=1000,allow_resize=False))
def test_no_overwrite(photo,tmp_path):
 original=photo.read_bytes(); out=tmp_path/'out'
 a=convert([photo],out,Options('png')); b=convert([photo],out,Options('png'))
 assert a.directory==out and b.directory==out and a.files[0] != b.files[0] and a.files[0].exists() and photo.read_bytes()==original
def test_combined_pdf(photo,tmp_path):
 r=convert([photo,photo],tmp_path/'out',Options('pdf',max_bytes=100_000),True)
 assert r.files[0].stat().st_size<=100_000
 with fitz.open(r.files[0]) as doc: assert len(doc)==2
def make_pdf(tmp_path):
 p=tmp_path/'sample.pdf'
 with fitz.open() as doc:
  for i in range(2): doc.new_page().insert_text((72,72),'Hello world '+str(i))
  doc.save(p)
 return p
@pytest.mark.parametrize('target',['txt','jpg','png','webp','docx','pdf'])
def test_pdf_formats(tmp_path,target):
 r=convert([make_pdf(tmp_path)],tmp_path/'out',Options(target))
 if target=='docx': assert 'Hello world' in '\n'.join(p.text for p in Document(r.files[0]).paragraphs)
 if target=='txt': assert 'Hello world' in r.files[0].read_text()
 if target in {'jpg','png','webp'}: assert len(r.files)==2
def test_pdf_cap_preserves_text(tmp_path):
 r=convert([make_pdf(tmp_path)],tmp_path/'out',Options('pdf',max_bytes=20_000))
 with fitz.open(r.files[0]) as doc: assert 'Hello world' in doc[0].get_text()
def test_pdf_raster_cap(photo,tmp_path):
 p=convert([photo],tmp_path/'out',Options('pdf')).files[0]
 r=convert([p],tmp_path/'out',Options('pdf',max_bytes=20_000,rasterize_pdf=True))
 assert r.files[0].stat().st_size<=20_000 and any('flattened' in n for n in r.notes)
def test_scan_needs_ocr(photo,tmp_path):
 p=convert([photo],tmp_path/'out',Options('pdf')).files[0]
 with pytest.raises(ConversionError,match='OCR'): convert([p],tmp_path/'out',Options('txt'))
def test_protected_pdf(tmp_path):
 p=tmp_path/'protected.pdf'
 with fitz.open() as doc:
  doc.new_page(); doc.save(p,encryption=fitz.PDF_ENCRYPT_AES_256,user_pw='secret',owner_pw='owner')
 with pytest.raises(ConversionError,match='password'): convert([p],tmp_path/'out',Options('txt'))
def test_unicode_excel(tmp_path):
 p=tmp_path/'工作.xlsx'; wb=Workbook(); ws=wb.active; ws.title='People'; ws.append(['Name','Score']); ws.append(['澳門',9]); wb.create_sheet('Other').append(['x']); wb.save(p)
 r=convert([p],tmp_path/'out',Options('csv'))
 assert len(r.files)==2 and '澳門' in r.files[0].read_text(encoding='utf-8-sig')
def test_formula_cache(tmp_path):
 p=tmp_path/'formula.xlsx'; wb=Workbook(); wb.active.append(['=1+1']); wb.save(p)
 with pytest.raises(ConversionError,match='saved result'): convert([p],tmp_path/'out',Options('csv'))
def test_table_roundtrip(tmp_path):
 p=tmp_path/'data.json'; p.write_text(json.dumps([{'name':'Jayden','score':10},{'name':'Kyle','score':9}]))
 c=convert([p],tmp_path/'out',Options('csv')).files[0]
 x=convert([c],tmp_path/'out',Options('xlsx')).files[0]
 wb=load_workbook(x); assert wb.active['A2'].value=='Jayden'; wb.close()
 j=convert([c],tmp_path/'out',Options('json')).files[0]
 assert json.loads(j.read_text())[0]['name']=='Jayden'
def test_duplicate_headers(tmp_path):
 p=tmp_path/'bad.csv'; p.write_text('name,name\na,b\n')
 with pytest.raises(ConversionError,match='unique'): convert([p],tmp_path/'out',Options('json'))
def test_csv_literal_formula(tmp_path):
 p=tmp_path/'cells.csv'; p.write_text('value\n=1+1\n'); x=convert([p],tmp_path/'out',Options('xlsx')).files[0]
 wb=load_workbook(x); assert wb.active['A2'].data_type=='s'; wb.close()
@pytest.mark.parametrize('target',['pdf','docx'])
def test_unicode_text(tmp_path,target):
 p=tmp_path/'text.txt'; p.write_text('Hello world\n澳門測試\n'+'Long text\n'*100,encoding='utf-8')
 out=convert([p],tmp_path/'out',Options(target)).files[0]; assert out.stat().st_size>100
 if target=='pdf':
  with fitz.open(out) as doc: assert len(doc)>1 and '澳門' in ''.join(p.get_text() for p in doc)
def test_orientation(tmp_path):
 p=tmp_path/'rotated.jpg'; im=Image.new('RGB',(100,200),'red'); exif=im.getexif(); exif[274]=6; im.save(p,exif=exif)
 out=convert([p],tmp_path/'out',Options('png')).files[0]
 with Image.open(out) as im: assert im.size==(200,100)
def test_transparency(tmp_path):
 p=tmp_path/'alpha.png'; Image.new('RGBA',(10,10),(0,0,0,0)).save(p)
 out=convert([p],tmp_path/'out',Options('jpg')).files[0]
 with Image.open(out) as im: assert min(im.getpixel((0,0)))>250
def test_media(tmp_path):
 ff=_tool('ffmpeg')
 if not ff: pytest.skip('ffmpeg unavailable')
 p=tmp_path/'clip.mp4'
 _run([ff,'-loglevel','error','-f','lavfi','-i','color=c=blue:s=160x120:d=1','-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-c:a','aac','-shortest',str(p)])
 for target in ['mp3','wav','flac','m4a','ogg','mp4','webm','mkv']:
  out=convert([p],tmp_path/'out',Options(target)).files[0]
  _run([ff,'-v','error','-i',str(out),'-f','null','-'])
def test_ocr(tmp_path):
 if not _tool('tesseract'): pytest.skip('tesseract unavailable')
 from PIL import ImageDraw,ImageFont
 p=tmp_path/'scan.png'; im=Image.new('RGB',(1000,160),'white'); draw=ImageDraw.Draw(im)
 draw.text((20,30),'HELLO WORLD 123',fill='black',font=ImageFont.truetype('DejaVuSans.ttf',60)); im.save(p)
 assert 'HELLO WORLD' in convert([p],tmp_path/'out',Options('txt')).files[0].read_text()
def test_bad_target(photo,tmp_path):
 with pytest.raises(ConversionError,match='not compatible'): convert([photo],tmp_path/'out',Options('csv'))

def test_direct_and_no_overwrite(photo):
 original=photo.read_bytes(); result=convert([photo],photo.parent,Options('png'))
 assert result.files[0].parent == photo.parent and result.files[0].name == 'photo (1).png'
 assert photo.read_bytes()==original

def test_many_pages_save_directly(tmp_path):
 src=make_pdf(tmp_path); dest=tmp_path/'out'; dest.mkdir()
 existing=dest/'sample_page_001.jpg'; existing.write_bytes(b'original')
 result=convert([src],dest,Options('jpg'))
 assert existing.read_bytes()==b'original'
 assert [p.name for p in result.files]==['sample_page_001 (1).jpg','sample_page_002.jpg']
 assert all(p.parent==dest for p in result.files)
