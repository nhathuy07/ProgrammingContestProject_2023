import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {
    "include_files": ['UI/'],
    "excludes": ["tkinter", "unittest"],
    "zip_include_packages": ["kivymd", "kivy", "copy", "datetime", "typing", "plyer", "requests", "camera4kivy", "platform"]
}

# base="Win32GUI" should be used only for Windows GUI app
base = None

setup(
    name="ReviseNow",
    version="0.0.2",
    options={"build_exe": build_exe_options},
    executables=[Executable("main.py", base=base)],
)