from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel
import uvicorn
import hashlib
import unidecode
from mimetypes import guess_type as guess_mimetype
from cv2 import imread, threshold, cvtColor, COLOR_BGR2GRAY, THRESH_OTSU, THRESH_BINARY
from PIL import Image as PILImage
from os import urandom
from os import makedirs, remove as os_remove
from typing import Tuple, Optional
import pypandoc
import pytesseract
import sqlalchemy
import sqlalchemy.orm
import underthesea
#import psycopg2
from sqlalchemy import text
from shutil import copyfileobj
from stopwords import stopwords
from datetime import date
import requests as rq
from fitb_demo import fetch_content_phrase, generate_wh_qs_from_definitions, generate_true_false_qs, generate_fitb
from random import randint
from enum import Enum
server = FastAPI()

# Set up database connection

requests = rq.Session()

SQLALCHEMY_DATABASE_URL = "postgresql://mvlzxjih:hQSOo8VpoyzsfQAEm67BNdQOievQYTKr@satao.db.elephantsql.com/mvlzxjih"
engine = sqlalchemy.create_engine(SQLALCHEMY_DATABASE_URL)
Session = sqlalchemy.orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Language map
LANGUAGE_SHORT2FULL: dict[str, str] = {
    'vie': 'Vietnamese',
    'eng': 'English'
}

DAYS = ['mon','tue','wed','thu','fri','sat','sun']

class LoginForm(BaseModel):
    email: str
    pw: str

class TextUploadForm(LoginForm):
    name: str
    subject: str
    content: str
    lang: str
    keywords: str

class TextQuery(LoginForm):
    name: str
    lang: Optional[str]

class OcrImage(LoginForm):
    pass

class TextContent(BaseModel):
    content: Optional[str]
    summary: list[str]
    definitions_raw: str
    #length: int

class Activity(LoginForm):
    name: str
    accuracy: float

class Goal(LoginForm):
    T2: tuple
    T3: tuple
    T4: tuple
    T5: tuple
    T6: tuple
    T7: tuple
    CN: tuple

# https://levelup.gitconnected.com/python-salting-your-password-hashes-3eb8ccb707f9
def hash_pw(pw: str) -> Tuple[bytes, bytes]:
    salt = urandom(32)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 1000)
    return salt, h

# set up pytesseract by providing path to tesseract executable
pytesseract.pytesseract.tesseract_cmd = './tesseract'

@server.post("/signup/")
async def signup(form: LoginForm):
    with Session() as conn:

        if (len(conn.execute(text(f"SELECT id FROM credentials WHERE id = '{form.email}'")).fetchmany()) > 0):
            raise HTTPException(status_code=400, detail="Tài khoản đã tồn tại")
        else:
            salt, h = hash_pw(form.pw)
            conn.execute(text(f"INSERT INTO credentials(id, pw, salt) VALUES ('{form.email}', '{h.hex()}', '{salt.hex()}')"))
            conn.commit()

            conn.execute(text(f"CREATE TABLE {form.email.split('@')[0]}_texts (name TEXT, subject TEXT, content TEXT, lang TEXT, keywords TEXT)"))
            conn.commit()
            conn.execute(text(f"CREATE TABLE {form.email.split('@')[0]}_activities (text_name TEXT, type TEXT, score FLOAT(2), date TEXT)"))
            conn.commit()
            conn.execute(text(f"CREATE TABLE {form.email.split('@')[0]}_goals (name TEXT, mon TEXT, tue TEXT, wed TEXT, thu TEXT, fri TEXT, sat TEXT, sun TEXT)"))
            conn.commit()
            
            # Generate slots inside user_goals table
            # Target practise count slot
            conn.execute(text(f"INSERT INTO {form.email.split('@')[0]}_goals (name, mon, tue, wed, thu, fri, sat, sun) VALUES ('sum', '0','0','0','0','0','0','0')"))
            conn.commit()
            # Target subject slot
            conn.execute(text(f"INSERT INTO {form.email.split('@')[0]}_goals (name, mon, tue, wed, thu, fri, sat, sun) VALUES ('comp', '','','','','','','')"))
            conn.commit()
            raise HTTPException(status_code=200, detail=True)

def check_credentials(email, pw):
    with Session() as conn:
        _credentials = conn.execute(text(f"SELECT id, pw, salt FROM credentials WHERE id = '{email}'")).fetchall()
        #print(_credentials[0][2])
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
        _fn = f"tmp/{unidecode.unidecode(fi.filename)}"
        _ft = str(guess_mimetype(_fn, False)[0])

        with open(_fn, 'wb') as w:
            copyfileobj(fi.file, w)
        if (not _ft.startswith('image/')):
            try:
                _c = pypandoc.convert_file(_fn, "plain", verify_format=False, extra_args=['--wrap=none']).replace('\r\n\r\n', '\n').replace('\r\n', ' ').removeprefix('\n')
            except:
                _c = "<Không thể chuyển đổi văn bản>"

            os_remove(_fn)
            #print(r"{0}".format(_c))
            return {"text": _c} 
        else:
            _img = imread(f"{_fn}")
            os_remove(_fn)
            _img = cvtColor(_img, COLOR_BGR2GRAY)
            threshold(_img, 0, 255, THRESH_OTSU | THRESH_BINARY, _img)
            _img = PILImage.fromarray(_img)
            return {"text": pytesseract.image_to_string(_img, lang=lang, config=r'--tessdata-dir "./tessdata"',  output_type= pytesseract.Output.STRING)}

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
                conn.execute(text(f"INSERT INTO {t.email.split('@')[0]}_texts (name, subject, content, lang, keywords) VALUES ('{t.name}', '{t.subject}', '{t.content}', '{t.lang}', '{t.keywords}')"))
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

            _texts = conn.execute(text(f"SELECT subject, content, keywords FROM {q.email.split('@')[0]}_texts WHERE name='{q.name}'")).fetchall()
            #print(_texts[0][1])
            return {"subject": _texts[0][0], "content": _texts[0][1], "keywords": _texts[0][2]}

@server.get("/get-user-status/")
async def get_user_status(credentials: LoginForm):
    _c = check_credentials(credentials.email, credentials.pw)
    if _c:
        with Session() as conn:
            if len(conn.execute(text(f"SELECT * FROM {credentials.email.split('@')[0]}_texts")).fetchall()) == 0:
                return {'status': ['no_files', None]}
            else:
                _today_count = len(conn.execute(text(f"SELECT * FROM {credentials.email.split('@')[0]}_activities WHERE date = '{date.today().strftime('%Y-%m-%d')}'")).all())
                _needs_practising = conn.execute(text(f"SELECT text_name, score FROM {credentials.email.split('@')[0]}_activities WHERE score < 65")).all()
                
                # run if there are practises scoring under 65%
                if len(_needs_practising) > 0:
                    return {'status': ['needs_practising', len(_needs_practising)],
                            'extras': [(_name, _acc) for _name, _acc in _needs_practising]}

                else:
                    # retrieve goals of the day from user
                    
                    # check if user has any goals
                    _sum = conn.execute(text(f"SELECT FROM {credentials.email.split('@')[0]}_goals WHERE name='sum'")).fetchall()
                    _comp = conn.execute(text(f"SELECT FROM {credentials.email.split('@')[0]}_goals WHERE name='comp'")).fetchall()
                    _suggested_docs = conn.execute(text(f"SELECT * FROM {credentials.email.split('@')[0]}_texts WHERE subject IN ()")).fetchall()
                    
                    if len(_suggested_docs) > 0:
                        pass

                    else:
                        # run if user have practised during the day
                        if _today_count > 0:
                            return {'status': ['practised', _today_count]}
                        # remind user to practise if they haven't yet
                        else:
                            _total_count = len(conn.execute(text(f"SELECT * FROM {credentials.email.split('@')[0]}_texts")).fetchall())
                            return {'status': ['not_practised', _total_count]}

@server.get("/generate-questionaire/")
async def generate_qs(_t: TextContent):

    _questions: list[tuple(str, any)] = []

    
    # Generate questions from summary
    for sentence in _t.summary:
        print(sentence)

        content_phrases = fetch_content_phrase(sentence)
        if len(content_phrases["content_words"]) != 0:
            if not (content_phrases["content_words"][0][1].isnumeric() and len(content_phrases["content_words"]) <= 2):
                _temp_question = generate_fitb(content_phrases, 3)
                if _temp_question[1]:
                    _questions.append(_temp_question)
        

    return {"questions": tuple(_questions)}

@server.post("/record-activity/")
async def record_activity(_activity: Activity):
    try:
        if check_credentials(_activity.email, _activity.pw):
            with Session() as sql:
                # override record of attempts with accuracy under 65%
                if _activity.accuracy < 65:
                    sql.execute(text(f"DELETE FROM {_activity.email.split('@')[0]}_activities WHERE text_name = '{_activity.name}'"))
                sql.commit()
                sql.execute(text(f"INSERT INTO {_activity.email.split('@')[0]}_activities (text_name, score, date) VALUES ('{_activity.name}', {_activity.accuracy}, '{date.today().strftime('%Y-%m-%d')}')"))
                sql.commit()
            return "success"
    except Exception as e:
        print(e)
        return e
    
@server.post("/save-goals/")
async def save_goals(_goals: Goal):
    with Session() as sql:
        sql.execute(text(f"DELETE FROM {_goals.email.split('@')[0]}_goals"))
        sql.commit()
        _sum_sql_string = ''
        _comp_sql_string = ''
        for goal in (_goals.T2, _goals.T3, _goals.T4, _goals.T5, _goals.T6, _goals.T7, _goals.CN):
            _sum_sql_string += f'{goal[0]}, '
            _comp_sql_string += f"'{goal[1]}', "
        _sum_sql_string = text(f"INSERT INTO {_goals.email.split('@')[0]}_goals (name, mon, tue, wed, thu, fri, sat, sun) VALUES ('sum', {_sum_sql_string.removesuffix(', ')})")
        _comp_sql_string = text(f"INSERT INTO {_goals.email.split('@')[0]}_goals (name, mon, tue, wed, thu, fri, sat, sun) VALUES ('comp', {_comp_sql_string.removesuffix(', ')})")
        sql.execute(_sum_sql_string)
        sql.commit()
        sql.execute(_comp_sql_string)
        sql.commit()
    print(_sum_sql_string)

@server.get('/get-goals/')
async def retrieve_goals(user: LoginForm):
    _c = check_credentials(user.email, user.pw)
    if _c:
        with Session() as sql:
            _sum = sql.execute(text(f"SELECT mon, tue, wed, thu, fri, sat, sun FROM {user.email.split('@')[0]}_goals WHERE name='sum'")).fetchall()
            _comp = sql.execute(text(f"SELECT mon, tue, wed, thu, fri, sat, sun FROM {user.email.split('@')[0]}_goals WHERE name='comp'")).fetchall()
            
            return {'sum': [str(x) for x in _sum[0]], 'comp': [str(x) for x in _comp[0]]}
if __name__ == '__main__':
    uvicorn.run('server:server', reload=False)