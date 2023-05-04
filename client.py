import platform
import requests
# fix blurry UI on Windows
if platform.system() == 'Windows':
    from ctypes import windll
    windll.user32.SetProcessDpiAwarenessContext(-4)

import mimetypes
import plyer
from kivy.base import EventLoop
from kivy.core.window import Window
from kivymd import fonts_path
from kivy import properties
from kivymd import app
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix import widget, screenmanager, screen, snackbar, card, dialog, button, menu, textfield
from kivymd.uix.list import ThreeLineListItem, IRightBodyTouch, OneLineAvatarListItem
from kivy.uix.screenmanager import CardTransition
from kivy.uix.image import Image as KvImage
from kivy.uix import camera
from kivymd.uix.recycleview import *
from kivy.core import text
from kivy.lang import Builder
from os import path as os_path
from os import remove as os_remove

# import tkinter filedialog (linux only)
if platform.system() == 'Linux':
    from tkinter import filedialog

import keyring
import captcha.image
import re
import random
from collections import namedtuple
from string import ascii_lowercase, digits
fonts: list[str] = ["OpenSans"]
captchaGenerator = captcha.image.ImageCaptcha(fonts=['UI/Fonts/OpenSans-Bold.ttf'])

HTTP_ENDPOINT = 'http://127.0.0.1:8000'

if platform.system() in ['Windows', 'Linux']:
    Window.size = (720 // 2, 1280 // 2)
FONT_DIR = "./UI/Fonts"

KEYRING_PLACEHOLDER = namedtuple('Credentials', ['username','password'])

class Item(OneLineAvatarListItem):
    divider = None
    source = properties.StringProperty()

class ScreenMan(screenmanager.MDScreenManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class WelcomeScreen(screen.MDScreen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        

    def submit(self, user: str, pw: str):
        _r = requests.post(url=f"{HTTP_ENDPOINT}/signin", json={"email": user, "pw": pw})
        print(_r.status_code)
        if (_r.status_code == 200):
            if keyring.get_credential('system', None):
                keyring.delete_password('system', keyring.get_credential('system', None).username)
            keyring.set_password("system", user, pw)
            _snackbar = snackbar.Snackbar(text=_r.json()["detail"], bg_color = (0.55, 0.76, 0.29, 1))
            _snackbar.open()
            return True
        elif (_r.status_code == 400):
            _snackbar = snackbar.Snackbar(text=_r.json()["detail"], bg_color = (233/255, 30/255, 99/255, 1))
            _snackbar.open()

class SignupForm(screen.MDScreen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.valid_captcha_key = ""
        self._c = None
    
    def generate_captcha(self):
        self.valid_captcha_key = "".join(random.choices(ascii_lowercase + digits, k=6))
        self._c = captchaGenerator.generate_image(self.valid_captcha_key)
        self._c.save("./temp.png", "png")
        self.ids.captcha_img.reload()

    def signup(self, user: str, pw: str, pw_repeat: str, captcha: str):
        errors = []
        # Check if email and password are valid
        if (re.fullmatch(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', str(user)) == None):
            errors.append("Email không hợp lệ")
        if (len(str(pw)) < 6):
            errors.append("Mật khẩu phải có ít nhất 6 chữ số")
        if (str(pw) != str(pw_repeat)):
            errors.append("Mật khẩu nhập lại không trùng khớp")
        
        # Check if CAPTCHA key is valid
        if (str(captcha).lower() != self.valid_captcha_key.lower()):
            errors.append("Mã CAPTCHA không chính xác")

        # Submit username and password to server if input values are valid
        if len(errors) == 0:
            r = requests.post(url=f"{HTTP_ENDPOINT}/signup", json={"email": str(user), "pw": str(pw)})
            if (r.status_code == 400):
                errors.append("Tài khoản đã tồn tại")
        # Display errors (if any)
        if len(errors) > 0:
            _alert = snackbar.Snackbar(
                text = errors[0], # displays the first error
                bg_color = (233/255, 30/255, 99/255, 1)
            )
            _alert.open()
            self.generate_captcha()
        # Progress to the next step (if there's no errors)
        else:
            if keyring.get_credential('system', None):
                keyring.delete_password('system', keyring.get_credential('system', None).username)
            keyring.set_password("system", user, pw)
            _snackbar = snackbar.Snackbar(
                text="Đăng kí thành công",
                bg_color = (0.55, 0.76, 0.29, 1)
            )
            _snackbar.open()
            return True

class HomePage(screen.MDScreen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    def _reload_greetings(self):
        self.ids.greetings.text = "Xin chào, " + keyring.get_credential('system', None).username.split('@')[0]
        self.status_bar_state = {
            "no_files": {
                "text": "Hãy thêm tài liệu đầu tiên",
                "secondary_text": "Để bắt đầu ôn tập",
                "icon": '✨',
                "color": (250/255, 227/255, 173/255),
                "icon_box": (255 / 255, 222 / 255, 129 / 255)
            }, 
            "not_practised": {
                "text": "Hãy cùng ôn tập nào!",
                "secondary_text": "Bạn hiện đang có %1 tài liệu",
                "icon": '📝',
                "color": (250/255, 227/255, 173/255),
                "icon_box": (255 / 255, 222 / 255, 129 / 255)
            }
        }
        self.current_filter = "all"
    def _update_status_bar(self):
        _r = requests.get(f'{HTTP_ENDPOINT}/get-user-status/', json={
            "email": keyring.get_credential("system", None).username,
            "pw": keyring.get_credential("system", None).password
        })
        current_status = self.status_bar_state[_r.json()["status"][0]]

        if '%1' in current_status["secondary_text"]:
            current_status["secondary_text"] = current_status["secondary_text"].replace('%1', str(_r.json()["status"][1]))
        
        if '%1' in current_status["text"]:
            current_status["text"] = current_status["text"].replace('%1', str(_r.json()["status"][1]))

        self.ids.primary.text = current_status["text"]
        self.ids.secondary.text = current_status["secondary_text"]
        self.ids.icon.text = current_status["icon"]
        self.ids.status_banner.md_bg_color = current_status["color"]
        self.ids.icon_box.md_bg_color = current_status["icon_box"]
    
    def on_enter(self, *args):
        self._update_status_bar()
        return super().on_enter(*args)
    
    def switch_filter(self, f , *args, **kwargs):
        self.current_filter = f
        if f == 'goal':
            self.ids.filter_goal.bold = True
            self.ids.filter_all.bold = False
            
            self.ids.filter_goal.color = (63/255, 81/255, 181/255, 1)
            self.ids.filter_all.color = (100/255, 100/255, 100/255, 1)
        elif f == 'all':
            self.ids.filter_goal.bold = False
            self.ids.filter_all.bold = True
            self.ids.filter_all.color = (63/255, 81/255, 181/255, 1)
            self.ids.filter_goal.color = (100/255, 100/255, 100/255, 1)

class LoginWidgets(widget.MDWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class DocsList(MDRecycleView):
    data = properties.ListProperty([])
    def __init__(self, **kwargs):
        super(DocsList, self).__init__(**kwargs)
        
        self.data = []

    def get_data_length(self):
        return len(self.data)
    
    def refresh_data(self):
        _r = requests.get(f"{HTTP_ENDPOINT}/get-texts", json = {"email": keyring.get_credential("system", None).username, "pw": keyring.get_credential("system", None).password})
        print(_r.json())
        self.data = [
            {"title": f"{name}",
             "icon": u"📕",
             "theme": f"Chủ đề: {subject}",
             "last_accessed": str(None),
             "on_press": lambda x = name: app.MDApp.get_running_app().go_to_text_browser(x)
             
            } for name, subject in _r.json()["texts"]
        ]
        self.refresh_from_data(self.data)

class NewFile(screen.MDScreen):
    _chosen_lang = properties.StringProperty('vie')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.camera = None
        self.layout = None
        self.files = []
        # User data
        self.available_subjects = []
        self._chosen_lang = 'vie'
        self._chosen_subject = None

        # Reference: https://kivymd.readthedocs.io/en/1.1.1/components/menu/index.html
        self.langs = [
            {
                "text": f"{l}",
                "viewclass": "OneLineListItem",
                "on_release": lambda x=l.split(' - '): self.change_lang(x),
            } for l in ['Tiếng Việt - vie', 'English - eng']
        ]
        self.lang_menu = menu.MDDropdownMenu(
            items=self.langs,
            width_mult=4,
            caller = self.ids.lang_chooser
        )
        self.subject_menu = menu.MDDropdownMenu(
            items = self.available_subjects,
            width_mult = 4,
            caller = self.ids.subject_chooser
        )
        self.add_subject_dlg = dialog.MDDialog(
            title=" ",
            type="custom",
            content_cls = AddSubjectDialog(),
            buttons = [
                button.MDFillRoundFlatButton(text = 'Ok', md_bg_color = (0.321, 0.298, 0.431, 1.000), on_release = self._add_subject)
            ]
        )

        EventLoop.window.bind(on_keyboard=self.hook_keyboard)
    
    def get_available_subjects(self):
        _c = keyring.get_credential('system', None)
        _r = requests.get(f'{HTTP_ENDPOINT}/user-subjects', json={'email': _c.username, 'pw': _c.password})
        
        self.available_subjects = [
            {
                "text": f"{subject}",
                "viewclass": "OneLineListItem",
                "on_release": lambda x=subject: self.change_subject(x),
            }
            for subject in _r.json()['subjects']
        ]
        self.subject_menu.items = self.available_subjects
        self.subject_menu.items.append(
            {
                "text": "Thêm chủ đề...",
                "viewclass": "OneLineListItem",
                "on_release": self.add_subject_dlg.open,
            }
        )
        
    def capture(self):
        if platform.system() == 'Windows':
            self.open_from_file()
        else:
            plyer.camera.take_picture("img.png", self.process_file)

    def open_from_file(self):
        if platform.system() in ['Windows', 'Java']:
            plyer.filechooser.open_file(multiple = True, on_selection = self.process_file)
        elif platform.system() == "Linux":
            _f = filedialog.askopenfilenames()
            self.process_file(_f)
    
    def process_file(self, files: list[str]):
        url = f"{HTTP_ENDPOINT}/image-processing/{self._chosen_lang}"
        if files != None:
            for fi in files:
                if files != '':
                    if fi.endswith('.txt'):
                        with open(fi, 'r', encoding='utf16', errors='ignore') as rf:
                            self.ids.textfield.text += "\n".join(rf.readlines())
                    else:
                        print(mimetypes.guess_type(fi, strict=False))
                        _r = requests.get(url, files = {'fi': open(fi, 'rb')})
                        print(_r.url)
                        self.ids.textfield.text += f"\n{_r.json()['text']}"

    def hook_keyboard(self, window, key, *args):
        if key == 27:
            app.MDApp.get_running_app().reload_screen(2)
            return True
        
    def change_lang(self, l):
        self._chosen_lang = l[1]
        self.ids.lang_chooser.text = l[0]
        self.lang_menu.dismiss()
    
    def change_subject(self, s):
        self._chosen_subject = s
        self.ids.subject_chooser.text = s
        self.subject_menu.dismiss()

    def _t(self, *args):
        print(args)

    def _add_subject(self, *args):
        self.add_subject_dlg.dismiss()
        self.change_subject(self.add_subject_dlg.content_cls._t.text)

    def upload_file(self):
        _name = self.ids.name.text
        _content = self.ids.textfield.text
        _subject = self._chosen_subject
        _status = snackbar.Snackbar()
        if not _subject or not _name or not _content:
            _status.bg_color = (233/255, 30/255, 99/255, 1)
            _status.text = "Vui lòng điền tên / chủ đề / nội dung"
        else:
            _r = requests.post(url=f"{HTTP_ENDPOINT}/upload-text/", 
                               json={"email": keyring.get_credential('system', None).username,
                                     "pw": keyring.get_credential('system', None).password,
                                     "name": _name,
                                     "subject": _subject,
                                     "content": _content,
                                     "lang": self._chosen_lang})
            print(_r.json()['detail'])
            if _r.status_code == 200:
                _status.bg_color = (0.55, 0.76, 0.29, 1)
            else:
                _status.bg_color = (233/255, 30/255, 99/255, 1)
            _status.text = str(_r.json())
            _status.duration = 1
            _status.open()
            if _r.status_code == 200:
                app.MDApp.get_running_app().reload_screen(2)


class AddSubjectDialog(MDBoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.height=200
        self.spacing=10
        self.padding=(0, 0, 0, 0)
        self.orientation = 'horizontal'
        self._t = textfield.MDTextField(
            hint_text='Thêm chủ đề...',
            size_hint = (0.7, 1),
            line_color_focus = (0.321, 0.298, 0.431, 1.000),
            text_color_focus = (0.321, 0.298, 0.431, 1.000),
            on_focus = self.submit
        )
        
        self.add_widget(self._t)
    def submit(self, instance):
        self.parent.parent.result = self._t.text
    

class DelBtn(IRightBodyTouch, MDBoxLayout):
    """"""

class CustomListItem(ThreeLineListItem):
    data = properties.StringProperty()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class DocsCard(card.MDCard):
    title = properties.StringProperty()
    theme = properties.StringProperty()
    last_accessed = properties.StringProperty()
    icon = properties.StringProperty()
    on_press = properties.Property(None)
    

class TextBrowser(screen.MDScreen):
    text_name = properties.StringProperty()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def on_enter(self, *args):
        self.get_text()
        return super().on_enter(*args)
    
    def get_text(self):
        _r = requests.get(f"{HTTP_ENDPOINT}/get-text-content", json=
                          {
                            "email": keyring.get_credential('system', None).username,
                            "pw": keyring.get_credential('system', None).password,
                            "name": self.text_name
                          })
        self.ids.subject.text = str(_r.json()["subject"]).upper()
        self.ids.text_name.text = self.text_name.upper()
        self.ids.content_box.text = str(_r.json()["content"])
        self.ids.content_box.cursor = (0, 0)

class GoalSetter(screen.MDScreen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class KeywordsView(MDRecycleView):
    text_name = properties.StringProperty()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = [
        ]

    def reload_keywords(self):
        _r = requests.get(f"{HTTP_ENDPOINT}/get-keywords", json=
                          {
                            "email": keyring.get_credential('system', None).username,
                            "pw": keyring.get_credential('system', None).password,
                            "name": self.text_name
                          })
        self.data = [
            {"text": x, "font_size": 14}
            for x, _ in _r.json()["keywords"]
        ]
        self.refresh_from_data(self.data)


class Client(app.MDApp):
    def __init__(self, **kwargs):
        self.title = "Test"
        super().__init__(**kwargs)
        self.s = screenmanager.ScreenManager()
        #self.screens = [WelcomeScreen(name="WelcomeScreen"), SignupForm(name="SignupForm")]
    
    def build(self):
        self.root = Builder.load_file("UI/layout.kv")
        self.screens = [WelcomeScreen(name="WelcomeScreen"), SignupForm(name="SignupForm"), HomePage(name="HomePage"), NewFile(name = "NewFile"), TextBrowser(name = "TextBrowser", text_name = ""), GoalSetter(name = "GoalSetter")]
        for s in self.screens:
            self.s.add_widget(s)
        self.reload_screen(0, "left")
        return self.s
    
    def reload_screen(self, index, d = None):
        self.s.transition = CardTransition(duration=0.23)

        self.s.current = self.screens[index].name
        
    def on_stop(self):
        if os_path.exists("temp.png"):
            os_remove("temp.png")
    
    def get_credential(self):
        _c: keyring.core.credentials.Credential = keyring.get_credential("system", None)
        if _c:
            return _c
        else:
            return KEYRING_PLACEHOLDER("", "")

    def get_raw_username(self, username: str):
        return username.split('@')[0]

    def get_kivy_texture(self, path):
        return KvImage(source = path).texture

    def go_to_text_browser(self, name):
        self.s.get_screen("TextBrowser").text_name = name
        self.s.current = "TextBrowser"


text.LabelBase.register("MDIconFont", os_path.join(fonts_path, "materialdesignicons-webfont.ttf"))
text.LabelBase.register("seguiemj", "UI/Fonts/seguiemj.ttf")
for f in fonts:
    text.LabelBase.register(f, f"{FONT_DIR}/{f}-Regular.ttf", f"{FONT_DIR}/{f}-Italic.ttf", f"{FONT_DIR}/{f}-Bold.ttf", f"{FONT_DIR}/{f}-BoldItalic.ttf")

Client().run()