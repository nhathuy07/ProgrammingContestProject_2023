from os import path as os_path
from os import remove as os_remove
import os
os.environ['KIVY_GL_BACKEND'] = 'angle_sdl2'

import platform
import requests as rq
import camera4kivy
import plyer
from typing import Literal
from datetime import date
from copy import deepcopy
from kivy.base import EventLoop
from kivy.metrics import dp
from kivy.core.window import Window
from kivy import clock, animation
from kivymd import fonts_path
from kivy import properties
from kivymd import app
from kivymd.uix.behaviors import RectangularRippleBehavior
from kivymd.uix.list import TwoLineListItem, TwoLineAvatarListItem, OneLineAvatarListItem
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRoundFlatButton
from kivymd.uix import widget, screenmanager, screen, snackbar, card, dialog, button, menu, textfield, floatlayout
from kivymd.uix import filemanager
from kivy.uix.screenmanager import CardTransition
from kivy.uix.image import Image as KvImage
from kivymd.uix.recycleview import *
from kivy import utils
from kivy.core import text
from kivy.lang import Builder
from kivy.logger import Logger


if platform.system() != 'Windows':
    from jnius import autoclass
    from android import activity

if utils.platform == "android":
     from android.permissions import request_permissions, Permission
     request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE, Permission.CAMERA, Permission.INTERNET, Permission.POST_NOTIFICATIONS])

if utils.platform == 'android':
    ANDROID_ARGS = os.environ.get('ANDROID_APP_PATH')
    if ANDROID_ARGS == None:
        ANDROID_ARGS = 'data/user/0/io.huyn.reviseapp/files/app'
    print('Android app directory is:', ANDROID_ARGS, os_path.exists(ANDROID_ARGS))

else:
    ANDROID_ARGS = '.'

Builder.load_file(os.path.join(ANDROID_ARGS, "UI/layout.kv"))

import captcha.image
import re
import random
from collections import namedtuple
from string import ascii_lowercase, digits
fonts: list[str] = ["OpenSans"]
captchaGenerator = captcha.image.ImageCaptcha(fonts=[os_path.join(ANDROID_ARGS ,"UI/Fonts/OpenSans-Bold.ttf")])

with open('./http_endpoint.txt', 'r') as fi:
    HTTP_ENDPOINT = f'{fi.readlines()[0]}'
INTERNET_CONN_ERR = "Vui lòng kiểm tra kết nối Internet!"
if platform.system() in ['Windows']:
    Window.size = (720 // 2, 1280 // 2)
FONT_DIR = "UI/Fonts"

KEYRING_PLACEHOLDER = namedtuple('Credentials', ['username','password'])

# Language map
LANGUAGE_SHORT2FULL: dict[str, str] = {
    'vie': 'Vietnamese',
    'eng': 'English'
}

requests = rq.Session()

# Reference: https://kivymd.readthedocs.io/en/0.104.0/components/spinner/index.html
class LoadingScreen(dialog.MDDialog):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = 'Đang tải...'

class CameraFrame(floatlayout.MDFloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = 1.0
        self.size_hint_x = 1.0
        self.camera = camera4kivy.Preview()
        self.ids.camera_slot.add_widget(self.camera)
        self.flash_states = ('on', 'auto', 'off')
        self.default_state = 2
        self.is_open = False
        self.callback = None

    def open(self, camera_id: Literal['front', 'back'], callback):
        self.path = ""
        self.callback = callback
        self.camera.connect_camera(camera_id = camera_id, filepath_callback = callback, enable_video = False)
        self.is_open = True
        print(self.camera.filepath_callback)

    def shot(self, *args):

        user_data_dir = app.MDApp.get_running_app().user_data_dir
        print(user_data_dir)

        self.camera.export_to_png(os.path.join(user_data_dir, 'temp.png'), scale=2)
        self.path = os.path.join(os.path.join(user_data_dir, 'temp.png'))
        self.disconnect()

    def disconnect(self, *args):
        self.camera.disconnect_camera()
        self.is_open = False
        self.callback(self.path)

    
    def flash(self, *args):
        self.default_state += 1
        _f =self.camera.flash(self.flash_states[self.default_state % 3])
        self.ids.flash_btn.text = f'Flash {_f}'

class ScreenMan(screenmanager.MDScreenManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class WelcomeScreen(screen.MDScreen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._loading_anim = LoadingScreen()
        

    def actual_submit(self, user: str, pw: str):
        try:
            _r = requests.post(url=f"{HTTP_ENDPOINT}/signin/", json={"email": user, "pw": pw})
            if (_r.status_code == 200):
                
                plyer.keystore.set_key("recall_keyring", "username", user)
                plyer.keystore.set_key("recall_keyring", "password", pw)
                
                _snackbar = snackbar.Snackbar(text=_r.json()["detail"], bg_color = (0.55, 0.76, 0.29, 1))
                _snackbar.open()
                clock.Clock.schedule_once(lambda _: app.MDApp.get_running_app().reload_screen(2, "right"))
            else:
                _snackbar = snackbar.Snackbar(text=_r.json()["detail"], bg_color = (233/255, 30/255, 99/255, 1))
                _snackbar.open()
        except Exception as e:
            # display alert when no Internet connection is available
            _snackbar = snackbar.Snackbar(text=f'LỖI: {str(e)}', bg_color = (233/255, 30/255, 99/255, 1))
            _snackbar.open()
            
    def submit(self, user: str, pw: str):
        self._loading_anim.open()
        clock.Clock.schedule_once(lambda _: self.actual_submit(user, pw))
        self._loading_anim.dismiss()
        
class SignupForm(screen.MDScreen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loading_anim = LoadingScreen()
        self.valid_captcha_key = ""
        self._c = None
    
    def generate_captcha(self):
        self.valid_captcha_key = "".join(random.choices(ascii_lowercase + digits, k=6))
        self._c = captchaGenerator.generate_image(self.valid_captcha_key)
        self._c.save("./temp.png", "png")
        self.ids.captcha_img.reload()

    def actual_signup(self, user: str, pw: str, pw_repeat: str, captcha: str):
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
        
        try:
            if len(errors) == 0:
                r = requests.post(url=f"{HTTP_ENDPOINT}/signup/", json={"email": str(user), "pw": str(pw)})
                if (r.status_code == 400):
                    errors.append("Tài khoản đã tồn tại")
        except Exception as e:
            # display alert when no Internet connection is available
            _snackbar = snackbar.Snackbar(text=f'LỖI: {str(e)}', bg_color = (233/255, 30/255, 99/255, 1))
            _snackbar.open()
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

            plyer.keystore.set_key('recall_keyring', 'username', user)
            plyer.keystore.set_key('recall_keyring', 'password', pw)
            _snackbar = snackbar.Snackbar(
                text="Đăng kí thành công",
                bg_color = (0.55, 0.76, 0.29, 1)
            )
            _snackbar.open()
            app.MDApp.get_running_app().reload_screen(2)
            return True
        

    def signup(self, user: str, pw: str, pw_repeat: str, captcha: str):
        self.loading_anim.open()
        clock.Clock.schedule_once(lambda _: self.actual_signup(user, pw, pw_repeat, captcha))
        self.loading_anim.dismiss()

class HomePage(screen.MDScreen):
    current_status = properties.DictProperty()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loading_anim = LoadingScreen()
        self.current_status_id = ""
        self.status_bar_state = {
            "no_files": {
                "text": "Hãy thêm tài liệu đầu tiên",
                "secondary_text": "Để bắt đầu ôn tập,",
                "icon": '📃',
                "color": (250/255, 227/255, 173/255),
                "icon_box": (255 / 255, 222 / 255, 129 / 255)
            }, 
            "not_practised": {
                "text": "Bạn hiện có %1 tài liệu",
                "secondary_text": "Cùng ôn tập nào!",
                "icon": '📝',
                "color": (250/255, 227/255, 173/255),
                "icon_box": (255 / 255, 222 / 255, 129 / 255)
            },
            "practised": {
                "text": "%1 lượt",
                "secondary_text": "Số lượt ôn tập (hôm nay)",
                "icon": 'ℹ️',
                "color": (194/255, 239/255, 255/255),
                "icon_box": (155/255, 230/255, 255/255),
            },
            "needs_practising": {
                "text": "%1 mục",
                "secondary_text": "Cần ôn tập thêm (chạm để xem)",
                "icon": '❗',
                "color": (255/255, 182/255, 181/255),
                "icon_box": (255/255, 147/255, 145/255)
            },
            "goal_0": {
                "secondary_text": 'Mục tiêu hôm nay',
                "text": "Làm %1",
                "icon": '🎯',
                "color": (250/255, 227/255, 173/255),
                "icon_box": (255 / 255, 222 / 255, 129 / 255)
            },
            "goal_50": {
                'secondary_text': 'Tiến trình',
                'text': 'Đã làm %1 bài',
                'icon': '📈',
                "color": (194/255, 239/255, 255/255),
                "icon_box": (155/255, 230/255, 255/255),
            },
            "goal_100": {
                'secondary_text': 'Thông báo',
                'text': 'Bạn đã hoàn thành mục tiêu!',
                'icon': '✅',
                "color": (194/255, 255/255, 196/255),
                "icon_box": (173/255, 255/255, 155/255),
            }
        }


    def on_pre_enter(self, *args):
        self.current_filter = "goal"
        self.ids.docslist.refresh_data()
        self._update_status_bar()
        self.switch_filter('goal')
        return super().on_pre_enter(*args)

    def status_bar_clicked(self, *args):
        if self.current_status_id in ('needs_practising'):
            self.dlg = dialog.MDDialog(
                type = 'simple',
                text = 'Lượt ôn tập này sẽ không được tính vào tổng số lượt của bạn.',
                title = 'Cải thiện kết quả',
                
                items = [NeedsImprovementCard(text=_name, tertiary_text=f"độ chính xác: {_acc}%") for _name, _acc in self._r.json()["extras"]],
                on_touch_up = self.dismiss_dlg
            )
            
            #self.dlg.update_height(dp(500))
            self.dlg.open()

    def dismiss_dlg(self, *args):
        self.dlg.dismiss()

    def _reload_greetings(self):
        self.ids.greetings.text = "Xin chào, " + plyer.keystore.get_key('recall_keyring', 'username').split('@')[0]
        
    def _update_status_bar(self):
        self._r = requests.get(f'{HTTP_ENDPOINT}/get-user-status/', json={
            "email": plyer.keystore.get_key('recall_keyring', 'username'),
            "pw": plyer.keystore.get_key('recall_keyring', 'password')
        })

        self.current_status_id = self._r.json()["status"][0]
        self.current_status = deepcopy(self.status_bar_state[self.current_status_id])

        if '%1' in self.current_status["secondary_text"]:
            self.current_status["secondary_text"] = self.current_status["secondary_text"].replace('%1', str(self._r.json()["status"][1]))
        
        if '%1' in self.current_status["text"]:
            self.current_status["text"] = self.current_status["text"].replace('%1', str(self._r.json()["status"][1]))

        self.ids.primary.text = self.current_status["text"]
        self.ids.primary.font_size = "24sp" if len(self.current_status["text"]) < 23 else "20sp"
        self.ids.secondary.text = self.current_status["secondary_text"].upper()
        self.ids.icon.text = self.current_status["icon"]
        self.ids.status_banner.md_bg_color = self.current_status["color"]
        self.ids.icon_box.md_bg_color = self.current_status["icon_box"]

    def on_enter(self, *args):
        self.loading_anim.dismiss()
        return super().on_enter(*args)
    
    def switch_filter(self, f , *args, **kwargs):
        self.current_filter = f
        if f == 'goal':
            self.ids.filter_goal.font_name = 'UI/Fonts/OpenSans-BoldItalic.ttf'
            self.ids.filter_all.font_name = 'UI/Fonts/OpenSans-Italic.ttf'
            
            self.ids.filter_goal.color = (63/255, 81/255, 181/255, 1)
            self.ids.filter_all.color = (100/255, 100/255, 100/255, 1)
        elif f == 'all':
            self.ids.filter_goal.font_name = 'UI/Fonts/OpenSans-Italic.ttf'
            self.ids.filter_all.font_name = 'UI/Fonts/OpenSans-BoldItalic.ttf'
            self.ids.filter_all.color = (63/255, 81/255, 181/255, 1)
            self.ids.filter_goal.color = (100/255, 100/255, 100/255, 1)
        
        clock.Clock.schedule_once(lambda _: self.ids.docslist.refresh_data(f == 'goal'))

class LoginWidgets(widget.MDWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class DocsList(MDRecycleView):
    data = properties.ListProperty([])
    def __init__(self, **kwargs):
        super(DocsList, self).__init__(**kwargs)
        self.loading_anim = LoadingScreen()        
        self.data = []

    def get_data_length(self):
        return len(self.data)
    
    def refresh_data(self, goal_only = False):
        try:
            
            _r = requests.get(f"{HTTP_ENDPOINT}/get-texts-and-goals/", json = {"email": plyer.keystore.get_key('recall_keyring', 'username'), "pw": plyer.keystore.get_key('recall_keyring', 'password')})
            
            #_goals = requests.get(f'{HTTP_ENDPOINT}/get-goals/', json = {"email": plyer.keystore.get_key('recall_keyring', 'username'), "pw": plyer.keystore.get_key('recall_keyring', 'password')})
            _goals = _r.json()['comp'][date.today().weekday()].split('::')
            print("goals", _goals)
            self.loading_anim.dismiss()
            if goal_only:
                self.data = [
                    {"title": f"{name}",
                    "icon": u"📕",
                    "theme": f"Chủ đề: {subject}",
                    "last_accessed": str(None),
                    "on_press": lambda x = name: app.MDApp.get_running_app().go_to_text_browser(x)
                    
                    } for name, subject in _r.json()["texts"] if (subject in _goals)
                ]
            else:
                self.data = [
                    {"title": f"{name}",
                    "icon": u"📕",
                    "theme": f"Chủ đề: {subject}",
                    "last_accessed": str(None),
                    "on_press": lambda x = name: app.MDApp.get_running_app().go_to_text_browser(x)
                    
                    } for name, subject in _r.json()["texts"]
                ]
            self.refresh_from_data(self.data)
        except Exception as e:
            # display alert when no Internet connection is available
            _snackbar = snackbar.Snackbar(text=f'LỖI: {str(e)}', bg_color = (233/255, 30/255, 99/255, 1))
            _snackbar.open()

class NewFile(screen.MDScreen):
    _chosen_lang = properties.StringProperty('vie')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._loading_anim = LoadingScreen()
        self.layout = None
        self.files = []
        # User data
        self.available_subjects = []
        self._chosen_lang = 'vie'
        self._chosen_subject = None

        # file browser based on kivy MDDialog
        self.file_dlg = filemanager.MDFileManager()
        self.file_dlg.preview = False
        self.file_dlg.select_path = self.process_file
        self.file_dlg.exit_manager = lambda _: self.process_file('')
        self.file_dlg.on_touch_up = self.update_filemanager
        #self.file_dlg.icon_selection_button = 'UI/Images/check_blue.png'

        # Is file dialog open?
        self.file_dlg_open = False

        # camera
        self.camera = CameraFrame()
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

    def update_filemanager(self, *args):
        pass
    
    def get_available_subjects(self):
        try:
            _c = app.MDApp.get_running_app().get_credential()
            _r = requests.get(f'{HTTP_ENDPOINT}/user-subjects/', json={'email': _c.username, 'pw': _c.password})
            
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
        except Exception as e:
            # display alert when no Internet connection is available
            _snackbar = snackbar.Snackbar(text=f'LỖI: {str(e)}', bg_color = (233/255, 30/255, 99/255, 1))
            _snackbar.open()
        
    def capture(self):
        if not self.camera.is_open:
            self.camera.open('back', self.process_image)
        self.add_widget(self.camera)
        self.toggle_disable_widget(True)

    def toggle_disable_widget(self, disabled):
        self.ids.upload_btn.disabled = disabled
        #self.ids.upload_btn.opacity = 0
        self.ids.browse_file_btn.disabled = disabled
        self.ids.capture_btn.disabled = disabled
        self.ids.name.disabled = disabled
        self.ids.lang_chooser.disabled = disabled
        self.ids.subject_chooser.disabled = disabled
        self.ids.textfield.disabled = disabled

    def process_image(self, path):
        # if utils.platform == 'win':
        #     self.process_file(path)
        #     self._loading_anim.dismiss()
        #     self.remove_widget(self.camera)
        #     self.toggle_disable_widget(False)
        # elif utils.platform == 'android':
        Logger.debug(f'Removing camera widget')
        self.remove_widget(self.camera)
        Logger.debug(f'Processing image: {path}')
        self.actual_process_file(path)
        Logger.debug(f'Re-enabling widgets')
        self.toggle_disable_widget(False)
        snackbar.Snackbar(text='image processing completed').open()

    def open_from_file(self):
        #plyer.filechooser.open_file(multiple = True, on_selection = self.process_file)
        try:
            self.remove_widget(self.camera)
        except:
            pass
        if utils.platform == 'android':
            self.file_dlg.show('/storage/emulated/0')
        else:
            print(os.path.expanduser("~"))
            plyer.filechooser.open_file(multiple = True, on_selection = self.process_file)
        self.file_dlg_open = True
    
    def actual_process_file(self, fi: str):
        self.file_dlg_open = False
        print(fi)
        self.ids.upload_btn.disabled = False
        self.ids.upload_btn.opacity = 1
        if utils.platform != 'android':
            self._loading_anim.open()
        url = f"{HTTP_ENDPOINT}/image-processing/{self._chosen_lang}/"
        try:
            if not os.path.isdir(fi):
                if fi.endswith('.txt'):
                    with open(fi, 'r', encoding='utf8', errors='ignore') as rf:
                        self.ids.textfield.text += "\n".join(rf.readlines())
                else:
                    _r = requests.get(url, files = {'fi': open(fi, 'rb')})

                    self.ids.textfield.text += f"{_r.json()['text']}\n"
                
                    self.file_dlg.close()
        except:
            pass

        if fi.endswith('.jpg'):
            os.remove(fi)
        self._loading_anim.dismiss()

    def process_file(self, files: str):
        if platform.system() == 'Windows':
            files = files[0]
        self._loading_anim.title = str(files)
        self._loading_anim.open()
        clock.Clock.schedule_once(lambda *_: self.actual_process_file(files))
        self._loading_anim.dismiss()
        
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

    def actual_upload_file(self):
        _name = self.ids.name.text
        _content = self.ids.textfield.text
        _subject = self._chosen_subject
        _status = snackbar.Snackbar()
        _keywords = app.MDApp.get_running_app().fetch_keywords(_content, 8)
        self._loading_anim.open()
        if not _subject or not _name or not _content:
            _status.bg_color = (233/255, 30/255, 99/255, 1)
            _status.text = "Vui lòng điền tên / chủ đề / nội dung"
        else:
            try:
                _r = requests.post(url=f"{HTTP_ENDPOINT}/upload-text/", 
                                json={"email": plyer.keystore.get_key('recall_keyring', 'username'),
                                        "pw": plyer.keystore.get_key('recall_keyring', 'password'),
                                        "name": _name,
                                        "subject": _subject,
                                        "content": _content,
                                        "lang": self._chosen_lang,
                                        "keywords": _keywords})
                if _r.status_code == 200:
                    _status.bg_color = (0.55, 0.76, 0.29, 1)
                else:
                    _status.bg_color = (233/255, 30/255, 99/255, 1)
                _status.text = str(_r.json()['detail'])
                _status.duration = 1
                _status.open()
                self._loading_anim.dismiss()
                if _r.status_code == 200:
                    clock.Clock.schedule_once(lambda _: app.MDApp.get_running_app().reload_screen(2, "right"))
            except Exception as e:
                # display alert when no Internet connection is available
                _snackbar = snackbar.Snackbar(text=f'LỖI: {str(e)}', bg_color = (233/255, 30/255, 99/255, 1))
                _snackbar.open()
        
    def upload_file(self):
        self._loading_anim.title = 'Đang tải'
        self._loading_anim.open()
        clock.Clock.schedule_once(lambda _: self.actual_upload_file())

    def on_pre_leave(self, *args):
        self._loading_anim.title = 'Đang tải'
        self._loading_anim.open()
        return super().on_pre_leave(*args)

    def on_leave(self, *args):
        self._loading_anim.dismiss()
        return super().on_leave(*args)
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
    

class DocsCard(card.MDCard, RectangularRippleBehavior):
    title = properties.StringProperty()
    theme = properties.StringProperty()
    last_accessed = properties.StringProperty()
    icon = properties.StringProperty()
    on_press = properties.Property(None)
    

class TextBrowser(screen.MDScreen):
    text_name = properties.StringProperty()
    _content = properties.StringProperty()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._loading_anim = LoadingScreen()
        self._content = ''
        self.qs_num = 15
    def on_pre_enter(self, *args):
        self._loading_anim.open()
        clock.Clock.schedule_once(lambda _: self.get_text())
        return super().on_pre_enter(*args)
    
    def get_text(self):
        try:
            self._r = requests.get(f"{HTTP_ENDPOINT}/get-text-content/", json=
                            {
                                "email": plyer.keystore.get_key('recall_keyring', 'username'),
                                "pw": plyer.keystore.get_key('recall_keyring', 'password'),
                                "name": self.text_name
                            })
            self._content = str(self._r.json()["content"])

            self.qs_num = 15

            self.ids.subject.text = str(self._r.json()["subject"]).upper()
            self.ids.text_name.text = self.text_name.upper()
            self.ids.content_box.text = str(self._r.json()["content"])
            self.ids.content_box.cursor = (0, 0)
            self.ids.keywordsview.reload_keywords(str(self._r.json()["keywords"]))
            self.ids.qs_num_disp.text = f'Số câu hỏi: {self.qs_num}'
        except Exception as e:
            # display alert when no Internet connection is available
            _snackbar = snackbar.Snackbar(text=f'LỖI: {str(e)}', bg_color = (233/255, 30/255, 99/255, 1))
            _snackbar.open()
        finally:
            self._loading_anim.dismiss()

    def actual_prepare_questionaire(self):
        try:
            self._data = requests.get(
                url=f"{HTTP_ENDPOINT}/generate-questionaire/",
                json={
                    "summary": app.MDApp.get_running_app().fetch_summarization(str(self._r.json()["content"]), self.qs_num),
                    "definitions_raw": str(self._r.json()["keywords"])
                }
            )
            print(self._data.request.body)
            app.MDApp.get_running_app().start_practise(self._data.json()["questions"], self.text_name)
        except Exception as e:
            # display alert when no Internet connection is available
            _snackbar = snackbar.Snackbar(text=f'LỖI: {str(e)}', bg_color = (233/255, 30/255, 99/255, 1))
            _snackbar.open()
        finally:
            self._loading_anim.dismiss()

    def prepare_questionaire(self):
        self._loading_anim.open()
        clock.Clock.schedule_once(lambda _: self.actual_prepare_questionaire())

    def change_qs_num(self, diff: int):
        self.qs_num = max(diff + self.qs_num, 1)
        self.ids.qs_num_disp.text = f'Số câu hỏi: {self.qs_num}'

    def on_pre_leave(self, *args):
        self._loading_anim.open()
        return super().on_pre_leave(*args)
        
    def on_leave(self, *args):
        self._loading_anim.dismiss()
        return super().on_leave(*args)


class GoalSetter(screen.MDScreen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.goal_count = 5
        self.loading_anim = LoadingScreen()
    
    def on_pre_enter(self, *args):
        self.goal_count = 5
        self.prev_dow = ''
        # get user subjects
        try:
            _c = app.MDApp.get_running_app().get_credential()
            self._r = requests.get(f'{HTTP_ENDPOINT}/user-subjects/', json={'email': _c.username, 'pw': _c.password}).json()

            self.current_subjects = [
                {
                    "text": t, 
                    'check': False
                } for t in self._r['subjects']
            ]
            self.goals = {
                'T2': (5, ""),
                'T3': (5, ""),
                'T4': (5, ""),
                'T5': (5, ""),
                'T6': (5, ""),
                'T7': (5, ""),
                'CN': (5, ""),
            }

            self.ids.subjectchooserlist.update_content(self.current_subjects)
        except Exception as e:
            # display alert when no Internet connection is available
            _snackbar = snackbar.Snackbar(text=f'LỖI: {str(e)}', bg_color = (233/255, 30/255, 99/255, 1))
            _snackbar.open()
        return super().on_pre_enter(*args)

    def change_qs_num(self, i):
        self.goal_count = max(int(self.goal_count) + int(i), 1)
        self.ids.goal_count_disp.text = f'{self.goal_count}'
    
    def on_enter(self, *args):
        self.loading_anim.open()
        clock.Clock.schedule_once(lambda _:self._on_enter())
        self.loading_anim.dismiss()
        return super().on_enter(*args)

    def _on_enter(self):
        self.prev_dow = ''
        try:
            _r = requests.get(f"{HTTP_ENDPOINT}/get-goals/", json={'email': plyer.keystore.get_key('recall_keyring', 'username'),
                                                                'pw': plyer.keystore.get_key('recall_keyring', 'password')})
            
            # retrieve goals from the server
            for index, day in enumerate(self.goals.keys()):
                self.goals[day] = (_r.json()['sum'][index], _r.json()['comp'][index])
            print('response: ',self.goals)
            self.get_goals('T2')
        except Exception as e:
            # display alert when no Internet connection is available
            _snackbar = snackbar.Snackbar(text=f'LỖI: {str(e)}', bg_color = (233/255, 30/255, 99/255, 1))
            _snackbar.open()
        finally:
            self.ids.dowview.update_dow_toggle('T2')

    def save_goals(self):
        try:
            print('current D-O-W view value: ', self.ids.dowview.current, self.goal_count, '::'.join(self.ids.subjectchooserlist.retrieve_subjects()))
            self.goals[self.ids.dowview.current] = (self.goal_count, '::'.join(self.ids.subjectchooserlist.chosen_subject))
            
            _json = self.goals
            _json['email'] = plyer.keystore.get_key('recall_keyring', 'username')
            _json['pw'] = plyer.keystore.get_key('recall_keyring', 'password')
            _r = requests.post(f'{HTTP_ENDPOINT}/save-goals/', json=_json)

        except Exception as e:
            # display alert when no Internet connection is available
            _snackbar = snackbar.Snackbar(text=f'LỖI: {str(e)}', bg_color = (233/255, 30/255, 99/255, 1))
            _snackbar.open()
        finally:
            print(self.goals)

    def get_goals(self, s: str):
        if s != self.prev_dow:
            _chosen_subjects = self.goals[s][1].split('::')
            print(_chosen_subjects, 'goal retrieved')
            self.ids.subjectchooserlist.chosen_subject = _chosen_subjects
            self.ids.subjectchooserlist.update_content_from_list()
            self.ids.goal_count_disp.text = f'{self.goals[s][0]}'
            self.goal_count = self.goals[s][0]
            self.prev_dow = s
            
    def on_pre_leave(self, *args):
        self.loading_anim.open()
        return super().on_pre_leave(*args)

    def on_leave(self, *args):
        self.loading_anim.dismiss()
        return super().on_leave(*args)

class DaysOfWeekBtn(MDRoundFlatButton):
    toggle = properties.BooleanProperty(False)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        print(self.text)
        self.line_color = (211/255, 148/255, 0, 1)
        self.text_color = (211/255, 148/255, 0, 1)
        self.toggle_action()

    def on_press(self):
        self.toggle = not self.toggle
        self.toggle_action()

    def force_toggle(self, t):
        self.toggle = t
        self.toggle_action()

    def toggle_action(self):
        if self.toggle:
            self.md_bg_color = (211/255, 148/255, 0, 1)
            self.text_color = (1, 1, 1, 1)

            self.parent.parent.current = self.text

            self.parent.parent.parent.parent.parent.get_goals(self.text)
        else:
            self.md_bg_color = (1, 1, 1, 1)
            self.text_color = (211/255, 148/255, 0, 1)

class SubjectCheckbox(OneLineAvatarListItem):
    check = properties.BooleanProperty(False)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.CHECK_ICON_DIR = "./UI/Images/right_icon.png"
        self.BLANK_DIR = "./UI/Images/blank.png"
        
    def on_press(self):
        self.check = not self.check
        if self.check:
            self.ids.check_icon.source = self.CHECK_ICON_DIR
            print(self.text, 'checked')
            self.parent.parent.add_subject(self.text)
        else:
            self.ids.check_icon.source = self.BLANK_DIR
            self.parent.parent.remove_subject(self.text)
    
    def force_check(self, checked):
        self.check = checked
        if self.check:
            self.ids.check_icon.source = self.CHECK_ICON_DIR

        else:
            self.ids.check_icon.source = self.BLANK_DIR
            print(self.text, 'unchecked')
    
class SubjectChooserList(MDRecycleView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.chosen_subject = []
        self.data = [{
            'text': '122',
            'check': False
        }]

    def add_widget(self, widget, *args, **kwargs):
        return super().add_widget(widget, *args, **kwargs)

    
    def add_subject(self, text):
        self.chosen_subject.append(text)
        self.update_content_from_list()
    
    def remove_subject(self, text):
        self.chosen_subject.remove(text)
        self.update_content_from_list()
    
    def update_content(self, c):
        self.data = c
        self.refresh_from_data()
    
    def update_content_from_list(self):
        print(self.chosen_subject)
        for child in self.ids.recycleLayout.children:
            if child.text in self.chosen_subject:
                child.force_check(True)
            else:
                child.force_check(False)
            
    def retrieve_subjects(self):
        print('retrieved', self.chosen_subject.copy())
        return self.chosen_subject.copy()

class DaysOfWeekView(MDRecycleView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dow = ('T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN')
        self.current = self.dow[0]
        self.data = [
            {
                'text': t,
                'toggle': True if t == 'T2' else False
            } for t in self.dow
        ]
        self.recycleLayout = None
        self.size_hint_x = None
        self.width = dp(10)

    def add_widget(self, widget, *args, **kwargs):
        self.recycleLayout = widget
        return super().add_widget(widget, *args, **kwargs)

    def on_touch_up(self, touch):
        self.update_dow_toggle(self.current)
        return super().on_scroll_stop(touch)
    
    def update_dow_toggle(self, dow: str):
        self.current = dow
        for child in self.recycleLayout.children:
            if child.text != self.current:
                child.force_toggle(False) 
            else:
                child.force_toggle(True)   
        print(self.current)

class KeywordsView(MDRecycleView):
    text_name = properties.StringProperty()
    text_content = properties.StringProperty()
    kw = properties.StringProperty()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = []

    def reload_keywords(self, kw: str):
        self.data = [
            {"text": x.split(':')[0], "font_size": '16sp'}
            for x in kw.split('\n')
        ]
        self.viewclass.font_size = '16sp'
        self.refresh_from_data(self.data)

class BaseQuestionPage(screen.MDScreen):
    prompt = properties.StringProperty()
    problem = properties.StringProperty()
    correct_ans: list[str] = properties.ListProperty()
    color_shifting_anim = animation.Animation()

class MCQPage(BaseQuestionPage):
    options = properties.ListProperty()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class MatchingPage(BaseQuestionPage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.swap_pending = ""

        self.keys_shown = False
        self.CARD_COLORS = (
            (141/255, 101/255, 197/255, 1),
            (0, 116/255, 186/255, 1),
            (0, 159/255, 80/255),
            (201/255, 169/255, 50/255, 1),
            (196/255, 38/255, 37/255, 1)
        )
    
    def on_pre_enter(self, *args):
        self.swapped_answers = self.correct_ans.copy()
        for _ in range(3):
            random.shuffle(self.swapped_answers)
        self.ids.gridlayout.rows = len(self.swapped_answers)
        self.swap_pending = ""
        self.ids.validation_result.text = ""
        self.ids.gridlayout.clear_widgets()
        self.refresh_list()
        return super().on_pre_enter(*args)

    def refresh_list(self):
        self.ids.gridlayout.clear_widgets()
        for i, val in enumerate(self.swapped_answers):
            self.ids.gridlayout.add_widget(
                SwappableCard(
                    size_hint =(1, 0.15), 
                    bgColor = self.CARD_COLORS[i % len(self.CARD_COLORS)],
                    num = str(i),
                    text = (val)
                )
            )

    def swap_items(self, _input: str):
        if not self.swap_pending:
            self.swap_pending= _input
            _from = self.swapped_answers.index(self.swap_pending)
            self.ids.gridlayout.children[-_from-1].toggle()
        else:
            _from = self.swapped_answers.index(self.swap_pending)
            _to = self.swapped_answers.index(_input)
            self.swapped_answers[_from], self.swapped_answers[_to] = self.swapped_answers[_to], self.swapped_answers[_from]
            print(self.swapped_answers)
            self.swap_pending = ""
            self.refresh_list()
    
    def verify_answer(self):
        for index, item in enumerate(self.swapped_answers):
            correct = True
            if not (item[1] == self.correct_ans[index][1]):
                correct = False
                break
            return correct
    
    def submit(self):
        if not self.keys_shown:
            self.keys_shown = True
            if self.verify_answer():
                self.color_shifting_anim = animation.Animation(md_bg_color = (0.55, 0.76, 0.29, 1), duration = 0.25, t = 'in_cubic')
                self.color_shifting_anim.start(self.ids.question_panel)
                self.ids.validation_result.text = "✓ CÂU TRẢ LỜI ĐÚNG"
            else:
                self.color_shifting_anim = animation.Animation(md_bg_color = (233/255, 30/255, 99/255, 1), duration = 0.25, t = 'in_cubic')
                self.color_shifting_anim.start(self.ids.question_panel)
                self.ids.validation_result.text = f"✘ ĐÁP ÁN ĐÚNG: {', '.join([x[1] for x in self.correct_ans])}"
        else:
            self.ids.question_panel.md_bg_color = (0.321, 0.298, 0.431, 1.000)
            app.MDApp.get_running_app().next_quiz((self.verify_answer(), self.problem, self.correct_ans))
            self.keys_shown = False


class ShortAnswerPage(BaseQuestionPage):
    def __init__(self, *args, **kwargs):
        self.keys_shown = False
        super().__init__(*args, **kwargs)

    def on_pre_enter(self, *args):
        self.ids.validation_result.text = ""
        self.ids.ans_input_1.text = ""
        self.ids.ans_input_2.text = ""
        self.ids.ans_input_3.text = ""
        if len(self.correct_ans) == 3:
            self.ids.ans_input_2.opacity = 1
            self.ids.ans_input_3.opacity = 1
        if len(self.correct_ans) <= 2:
            self.ids.ans_input_3.opacity = 0
        if len(self.correct_ans) <= 1:
            self.ids.ans_input_2.opacity = 0
        return super().on_pre_enter(*args)

    def verify_answer(self) -> bool:
        print(self.correct_ans)
        answer_one_match = (self.ids.ans_input_1.text.lower() == self.correct_ans[0][1].lower())
        
        try:
            answer_two_match = (self.ids.ans_input_2.text.lower() == self.correct_ans[1][1].lower())
        except IndexError:
            answer_two_match = True
        
        try:
            answer_three_match = (self.ids.ans_input_3.text.lower() == self.correct_ans[2][1].lower())
        except IndexError:
            answer_three_match = True
        
        if (answer_one_match and answer_two_match and answer_three_match):
            return True
        else:
            return False

    def submit(self):
        if not self.keys_shown:
            self.keys_shown = True
            if self.verify_answer():
                self.color_shifting_anim = animation.Animation(md_bg_color = (0.55, 0.76, 0.29, 1), duration = 0.25, t = 'in_cubic')
                self.color_shifting_anim.start(self.ids.question_panel)
                self.ids.validation_result.text = "✓ CÂU TRẢ LỜI ĐÚNG"
            else:
                self.color_shifting_anim = animation.Animation(md_bg_color = (233/255, 30/255, 99/255, 1), duration = 0.25, t = 'in_cubic')
                self.color_shifting_anim.start(self.ids.question_panel)
                self.ids.validation_result.text = f"✘ ĐÁP ÁN ĐÚNG: {', '.join([x[1] for x in self.correct_ans])}"
        else:
            self.ids.question_panel.md_bg_color = (0.321, 0.298, 0.431, 1.000)
            app.MDApp.get_running_app().next_quiz((self.verify_answer(), self.problem, self.correct_ans))
            self.keys_shown = False

class ResultPage(screen.MDScreen):
    title = properties.StringProperty()
    accuracy = properties.NumericProperty()
    detailed_result = properties.ListProperty()
    r_percentage_gauge = properties.NumericProperty()
    r_gauge_color = properties.ColorProperty()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def on_pre_enter(self, *args):
        self.ids.detailedresultlist.update_list(self.detailed_result)
        self.ids.r_title.text = self.title
        _correct_count = len([x for x in self.detailed_result if x[0]])
        _wrong_count = len(self.detailed_result) - _correct_count
        self.ids.r_metrics.text = f"{len(self.detailed_result)} CÂU · {_correct_count} ✔️ · {_wrong_count} ❌"
        
        try:
            self.accuracy = round(_correct_count / len(self.detailed_result) * 100, 2)
        except ZeroDivisionError:
            self.accuracy = 0

        self.ids.r_percentage.text = f"{self.accuracy}%"
        self.r_gauge_color = (0.55 * 1.25, 0.76 * 1.25, 0.29 * 1.25, 1) if self.accuracy > 65 else (233/255 * 1.25, 30/255 * 1.25, 99/255 * 1.25, 1)
        self.r_percentage_gauge = 360 * self.accuracy / 100
        try:
            _r = requests.post(f"{HTTP_ENDPOINT}/record-activity/",
                            json={
                                "email": plyer.keystore.get_key('recall_keyring', 'username'),
                                "pw": plyer.keystore.get_key('recall_keyring', 'password'),
                                "name": self.title,
                                "accuracy": self.accuracy
                            })
        except Exception as e:
            # display alert when no Internet connection is available
            _snackbar = snackbar.Snackbar(text=f'LỖI: {str(e)}', bg_color = (233/255, 30/255, 99/255, 1))
            _snackbar.open()

        return super().on_pre_enter(*args)

class SwappableCard(card.MDCard):

    bgColor = properties.ColorProperty()
    num = properties.StringProperty()
    text = properties.ListProperty(["", ""])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pending = False
    
    def prepare_swap(self, _input: str):
        # SwappableCard > GridLayout > ScrollView > BoxLayout > self
        self.parent.parent.parent.parent.swap_items(_input)
    
    def toggle(self):
        self.pending = not self.pending
        if self.pending:
            self.line_color = self.bgColor
            self.md_bg_color = (1, 1, 1, 1)
            print(self.children)
            self.children[0].color = self.bgColor
        else:
            self.line_color = (0, 0, 0, 0)
            self.md_bg_color = self.bgColor
            self.children.ids.card_label.color = (1, 1, 1, 1)

class NeedsImprovementCard(TwoLineAvatarListItem):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
    def on_touch_up(self, touch):
        app.MDApp.get_running_app().go_to_text_browser(self.text)
        return super().on_touch_up(touch)

class DetailedResultItem(TwoLineAvatarListItem):
    grade_icon_path = properties.StringProperty()
    text = properties.StringProperty()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class DetailedResultList(MDRecycleView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = []
        
    def update_list(self, _data: list[bool, str]):
        for is_correct, question, answer in _data:
            self.data.append({
                "text": question,
                "tertiary_text": f"đáp án: {', '.join([x for _, x in answer])}",
                "grade_icon_path": f"UI/Images/{'right_icon.png' if is_correct else 'wrong_icon.png'}"
            })
        self.refresh_from_data(self.data)

class Client(app.MDApp):
    def __init__(self, **kwargs):
        self.title = "Test"
        super().__init__(**kwargs)
        self.s = screenmanager.ScreenManager()
        self.ANDROID_ARGS = ANDROID_ARGS
        #self.screens = [WelcomeScreen(name="WelcomeScreen"), SignupForm(name="SignupForm")]
        self.loading = LoadingScreen()
        self.practise_data = {
            "data": None,
            "current": 0,
            "length": 0,
            "swap_pending": "",
            "correct": 0
        }
    
    def build(self):

        self.screens = [WelcomeScreen(name="WelcomeScreen"), SignupForm(name="SignupForm"), HomePage(name="HomePage"), NewFile(name = "NewFile"), TextBrowser(name = "TextBrowser", text_name = ""), GoalSetter(name = "GoalSetter"),  ShortAnswerPage(name = 'ShortAnswerPage'), MatchingPage(name = 'MatchingPage'), ResultPage(name = "ResultPage")]
        for s in self.screens:
            self.s.add_widget(s)
        self.reload_screen(0, "left")
        
        # bind back button / ESC to homescreen / login screen (if not logged in)
        EventLoop.window.bind(on_keyboard=self.hook_keyboard)
        return self.s

    def hook_keyboard(self, window, key, *args):
        clock.Clock.schedule_once(lambda _:self.back_to_homescreen(key))
        return True
    
    def back_to_homescreen(self, key, *args):
        if key == 27:
            if self.s.current in ['WelcomeScreen', 'SignupForm']:
                app.MDApp.get_running_app().reload_screen(0)
            elif self.s.current in ['NewFile']:
                _scr: NewFile = self.s.current_screen
                if _scr.file_dlg_open:
                    if _scr.file_dlg.current_path == r"\\":
                        _scr.file_dlg.exit_manager()
                    _scr.file_dlg.back()
                else: 
                    app.MDApp.get_running_app().reload_screen(2)
            else:
                app.MDApp.get_running_app().reload_screen(2)

    def reload_screen(self, index, d = None):
        self.s.transition = CardTransition(duration=0.23)
        self.s.current = self.screens[index].name
        
    def on_stop(self):
        if os_path.exists("temp.png"):
            os_remove("temp.png")
    
    def get_credential(self):
        _usr = plyer.keystore.get_key('recall_keyring', 'username')
        _pw = plyer.keystore.get_key('recall_keyring', 'password')
        if _usr:
            return KEYRING_PLACEHOLDER(_usr, _pw)
        else:
            return KEYRING_PLACEHOLDER("", "")

    def get_raw_username(self, username: str):
        return username.split('@')[0]

    def get_kivy_texture(self, path):
        return KvImage(source = path).texture

    def go_to_text_browser(self, name):
        self.s.get_screen("TextBrowser").text_name = name
        self.s.transition = CardTransition(duration=0.23)
        self.s.current = "TextBrowser"

    def fetch_keywords(self, _content: str, _keywords_num: str):
        _kw_extraction_prompt = f"""
            Fetch {_keywords_num} shortest keywords from the document. Please use the template below.
        """
        _FORMAT = """
            ---BEGIN FORMAT TEMPLATE---
            {KEYWORD_1}: {DEFINITION_IN_VIETNAMESE}
            {KEYWORD_2}: {DEFINITION_IN_VIETNAMESE}
            ---END FORMAT TEMPLATE
        """
        
        try:
            _r = requests.post(
                url='https://api.openai.com/v1/chat/completions',
                headers= {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer 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'
                },
                json={
                    'model': 'gpt-3.5-turbo',
                    'messages': [
                        {
                            'role': 'system',
                            'content': _kw_extraction_prompt + _FORMAT
                        },
                        {
                            'role': 'user',
                            'content': _content
                        }
                    ],
                    'temperature': 0.7, 
                    'top_p': 1.0,
                    'frequency_penalty': 0.0,
                    'presence_penalty': 1.0,
                    'max_tokens': 256
                }
            )
            _raw: str = _r.json()['choices'][0]['message']['content']
            return _raw
        except Exception as e:
            # display alert when no Internet connection is available
            _snackbar = snackbar.Snackbar(text=f'LỖI: {str(e)}', bg_color = (233/255, 30/255, 99/255, 1))
            _snackbar.open()

    def start_practise(self, data, title):
        self.practise_data["title"] = title
        self.practise_data["data"] = data
        self.practise_data["current"] = 0
        self.practise_data["length"] = len(data)
        self.practise_data["log"] = []
        self.navigate_to_quiz(0)

    def navigate_to_quiz(self, index: int):
        try:
            self.practise_data["swap_pending"] = ""
            self.practise_data["current"] = index
            if self.practise_data["data"][index][0] == 'FITB':
                _scr = self.s.get_screen("ShortAnswerPage")

            elif self.practise_data["data"][index][0] == 'FITB_MCQ':
                _scr = self.s.get_screen("MatchingPage")

            _scr.ids.qs_num.text = (u'#️⃣ ' + f"CÂU {self.practise_data['current'] + 1}/{self.practise_data['length']}")
            _scr.ids.progressbar.value = (self.practise_data['current'] / self.practise_data['length']) * 100
            _scr.problem = self.practise_data["data"][index][1]
            _scr.correct_ans = self.practise_data["data"][index][2]
            _scr.on_pre_enter()
            self.s.transition = CardTransition(duration=0.23)
            
            # navigate to screen
            if self.practise_data["data"][index][0] == 'FITB':
                self.s.current = "ShortAnswerPage"

            elif self.practise_data["data"][index][0] == 'FITB_MCQ':
                self.s.current = "MatchingPage"
        
        except IndexError:
            _scr = self.s.get_screen("ResultPage")
            _scr.title = self.practise_data["title"]
            # _scr.accuracy = round(len([x for x in self.practise_data["log"] if x[0] == True]) / self.practise_data["length"] * 100, 1)
            _scr.detailed_result = self.practise_data["log"]
            self.s.current = "ResultPage"

    def next_quiz(self, status: list[str, str, str]):
        self.practise_data["current"] += 1
        self.practise_data["log"].append(status)
        self.navigate_to_quiz(self.practise_data["current"])

    def show_units_requiring_improvement(self):
        self.dlg = dialog.MDDialog(
                type = 'simple',
                title = 'Ôn tập lại',
                items = [TwoLineListItem(text='aaa', secondary_text='bbb')]
            )
        self.dlg.open()

    def close_error_dlg(self):
        self._err.dismiss()

    def fetch_summarization(self, fullform: str, length: int):
        try:
            _r = requests.post(
                url='https://api.openai.com/v1/chat/completions',
                headers= {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer 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'
                },
                json=
                {
                    "model": "gpt-3.5-turbo",
                    "temperature": 0.35, 
                    "top_p": 1.0,
                    "frequency_penalty": 0.0,
                    "presence_penalty": 0.0,
                    "max_tokens": 2048,
                    "messages": [
                    {
                        "role": "system",
                        "content": "You are a language model that can extract key sentences."
                    },
                    {
                        "role": "user",
                        "content": fullform
                    },
                    {
                        "role": "assistant",
                        "content": f"Sure, here are {length} key sentences in Vietnamese"
                    }
                ]}
            )
            try:
                _raw_responses: list[str] = _r.json()['choices'][0]['message']['content'].split('.')
                return _raw_responses
            except:
                print(_r.json())
        except Exception as e:
            # display alert when no Internet connection is available
            _snackbar = snackbar.Snackbar(text=f'LỖI: {str(e)}', bg_color = (233/255, 30/255, 99/255, 1))
            _snackbar.open()

Client().run()