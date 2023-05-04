from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel
import hashlib
import unidecode
from mimetypes import guess_type as guess_mimetype
from cv2 import imread, threshold, cvtColor, COLOR_BGR2GRAY, THRESH_OTSU, THRESH_BINARY
from PIL import Image as PILImage
from os import urandom
from os import makedirs, remove as os_remove
import os
from typing import Tuple
import pypandoc
import pytesseract
import sqlalchemy
import sqlalchemy.orm
import psycopg2
from sqlalchemy import text
from shutil import copyfileobj
from yake import yake
from stopwords import stopwords
from datetime import date
server = FastAPI()

# Set up database connection

SQLALCHEMY_DATABASE_URL = "postgresql://isrxnzde:AE-sx6wF20aLCUEjkAJt31z9P0J2bTie@tiny.db.elephantsql.com/isrxnzde"
engine = sqlalchemy.create_engine(SQLALCHEMY_DATABASE_URL)
Session = sqlalchemy.orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)


class LoginForm(BaseModel):
    email: str
    pw: str

class TextUploadForm(LoginForm):
    name: str
    subject: str
    content: str
    lang: str

class TextQuery(LoginForm):
    name: str

class OcrImage(LoginForm):
    pass

# https://levelup.gitconnected.com/python-salting-your-password-hashes-3eb8ccb707f9
def hash_pw(pw: str) -> Tuple[bytes, bytes]:
    salt = urandom(32)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 1000)
    return salt, h

# set up pytesseract by providing path to tesseract executable
pytesseract.pytesseract.tesseract_cmd = './Tesseract-OCR/tesseract.exe'

@server.post("/signup/")
async def signup(form: LoginForm):
    with Session() as conn:

        if (len(conn.execute(text(f"SELECT id FROM credentials WHERE id = '{form.email}'")).fetchmany()) > 0):
            raise HTTPException(status_code=400, detail="Tài khoản đã tồn tại")
        else:
            salt, h = hash_pw(form.pw)
            conn.execute(text(f"INSERT INTO credentials(id, pw, salt) VALUES ('{form.email}', '{h.hex()}', '{salt.hex()}')"))
            conn.commit()

            conn.execute(text(f"CREATE TABLE {form.email.split('@')[0]}_texts (name TEXT, subject TEXT, content TEXT, last_accessed TEXT, lang TEXT)"))
            conn.commit()
            conn.execute(text(f"CREATE TABLE {form.email.split('@')[0]}_activities (text_name TEXT, type TEXT, score FLOAT(2), date TEXT)"))
            conn.commit()
            conn.execute(text(f"CREATE TABLE {form.email.split('@')[0]}_goals (mon TEXT, tue TEXT, wed TEXT, thu TEXT, fri TEXT, sat TEXT, sun TEXT)"))
            conn.commit()
            raise HTTPException(status_code=200, detail=True)

def check_credentials(email, pw):
    with Session() as conn:
        _credentials = conn.execute(text(f"SELECT id, pw, salt FROM credentials WHERE id = '{email}'")).fetchall()
        print(_credentials[0][2])
        if _credentials:
            _hashed_pw_input = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytearray.fromhex(_credentials[0][2]), 1000)

            if _hashed_pw_input.hex() == _credentials[0][1]:
                return True
            else:
                return False
        else:
            return False

@server.post("/signin/")
async def signin(form: LoginForm):
    _c = check_credentials(form.email, form.pw)
    if _c:
        raise HTTPException(status_code = 200, detail= "Đăng nhập thành công")
    else:
        raise HTTPException(status_code = 400, detail= "Email hoặc mật khẩu không chính xác")
    
@server.get("/image-processing/{lang}")
async def ocr(lang: str, fi: UploadFile = File(...)):
    #_c = check_credentials(form.email, form.pw)
    _c = True
    if not _c:
        raise HTTPException(status_code=400, detail= "Invalid credentials")
    else:
        _fn = unidecode.unidecode(fi.filename)
        _ft = guess_mimetype(fi.filename, False)[0]
        with open(_fn, 'wb') as w:
            copyfileobj(fi.file, w)
        if (not _ft.startswith('image/')):
            try:
                _c = pypandoc.convert_file(_fn, "plain", verify_format=False).replace('\r\n\r\n', '\n').replace('\r\n', ' ')
            except:
                _c = "<Cannot fetch text from file>"
            finally:
                os_remove(_fn)
            return {"text": _c} 
        else:
            _img = imread(f"./{_fn}")
            os_remove(_fn)
            _img = cvtColor(_img, COLOR_BGR2GRAY)
            threshold(_img, 0, 255, THRESH_OTSU | THRESH_BINARY, _img)
            _img = PILImage.fromarray(_img)
            return {"text": pytesseract.image_to_string(_img, lang=lang, output_type= pytesseract.Output.STRING)}

@server.get("/user-subjects/")
async def get_subjects(form: LoginForm):
    _c = check_credentials(form.email, form.pw)
    _subjects = []
    with Session() as conn:
        if _c:

            _subjects = conn.execute(text(f"SELECT DISTINCT subject FROM {form.email.split('@')[0]}_texts")).fetchall()
            _l = []
            for s in _subjects:
                _l.append(s[0])

        return {'subjects': _l}

@server.post("/upload-text/")
async def upload_text(t: TextUploadForm):
    _c = check_credentials(t.email, t.pw)
    with Session() as conn:
        if _c:
            _existing_names = conn.execute(text(f"SELECT name FROM {t.email.split('@')[0]}_texts WHERE name='{t.name}'")).fetchall()
            if len(_existing_names) == 0:
                conn.execute(text(f"INSERT INTO {t.email.split('@')[0]}_texts (name, subject, content, lang) VALUES ('{t.name}', '{t.subject}', '{t.content}', '{t.lang}')"))
                conn.commit()
                raise HTTPException(200, "Thêm tài liệu thành công!")
            else:
                raise HTTPException(400, "Mục mang tên này đã tồn tại")

@server.get("/get-texts/")
async def get_texts(form: LoginForm):
    _c = check_credentials(form.email, form.pw)
    if _c:
        with Session() as conn:
            _texts = conn.execute(text(f"SELECT name, subject FROM {form.email.split('@')[0]}_texts")).fetchall()
            _l = []
            for name, subject in _texts:
                _l.append((name, subject))
            return {"texts": _l}

@server.get("/get-text-content/")
async def get_content(q: TextQuery):
    _c = check_credentials(q.email, q.pw)
    if _c:
        with Session() as conn:

            _texts = conn.execute(text(f"SELECT subject, content FROM {q.email.split('@')[0]}_texts WHERE name='{q.name}'")).fetchall()
            return {"subject": _texts[0][0], "content": _texts[0][1]}

#reference: https://blog.luyencode.net/trich-rut-tu-khoa-tu-dong-voi-hoc-khong-giam-sat/
@server.get("/get-keywords/")
async def get_keywords(q: TextQuery):
    _c = check_credentials(q.email, q.pw)
    if _c:

        with Session() as conn:
            _sql = conn.execute(text(f"SELECT content, lang FROM {q.email.split('@')[0]}_texts WHERE name='{q.name}'")).fetchone()
            _extractor = yake.KeywordExtractor(lan = _sql[1][:2], n = 3, stopwords=stopwords)
            _text: str = _sql[0].replace("\n", ". ")
            
        return {"keywords": _extractor.extract_keywords(_text)}
    
@server.get("/get-user-status/")
async def get_user_status(credentials: LoginForm):
    _c = check_credentials(credentials.email, credentials.pw)
    if _c:
        
        with Session() as conn:
            if len(conn.execute(text(f"SELECT * FROM {credentials.email.split('@')[0]}_texts")).fetchall()) == 0:
                return {'status': ['no_files', None]}
            else:
                _today_count = len(conn.execute(text(f"SELECT * FROM {credentials.email.split('@')[0]}_activities WHERE date = '{date.today()}'")).all())
                _needs_practising = len(conn.execute(text(f"SELECT * FROM {credentials.email.split('@')[0]}_activities WHERE score < 65")).all())
                if _needs_practising > 0:
                    return {'status': ['needs_practising', _needs_practising]}
                else:
                    if _today_count > 0:
                        return {'status': ['practised', _today_count]}
                    else:
                        _total_count = len(conn.execute(text(f"SELECT * FROM {credentials.email.split('@')[0]}_texts")).fetchall())
                        return {'status': ['not_practised', _total_count]}