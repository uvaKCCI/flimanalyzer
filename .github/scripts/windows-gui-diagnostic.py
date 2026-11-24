"""TEMPORARY diagnostic for the Windows GUI tests (2026-11-23): why does
`AppFrame.SetIcons(app_icons())` fail with "invalid icon" in CI when 0.7.0 starts on
users' Windows machines? Reports only; never fails the job.

1. The PNG image handler before and after `wx.App()` (the .ico stores every size as PNG).
2. `app_icons()` as the app loads it, and each size of the .ico on its own.
3. The real program: `flimanalyzer` started for up to 120 s; is its main window there,
   and does it have an icon (WM_GETICON)?
"""

import ctypes
import glob
import os
import platform
import subprocess
import sys
import tempfile
import time
import traceback
from importlib.resources import files


def section(title):
    print(f"\n===== {title} =====", flush=True)


def try_(label, fn):
    try:
        print(f"{label}: {fn()}", flush=True)
    except BaseException as error:  # noqa: BLE001 (report everything)
        print(f"{label}: {type(error).__name__}: {error}", flush=True)


section("platform")
print(platform.platform(), "Python", sys.version.split()[0])

import wx  # noqa: E402

print("wxPython", wx.version())
try_("PNG handler before wx.App", lambda: wx.Image.FindHandler(wx.BITMAP_TYPE_PNG) is not None)
app = wx.App(False)
try_("PNG handler after wx.App", lambda: wx.Image.FindHandler(wx.BITMAP_TYPE_PNG) is not None)
try_("ICO handler", lambda: wx.Image.FindHandler(wx.BITMAP_TYPE_ICO) is not None)
try_("display size", lambda: wx.GetDisplaySize())
try_("assert mode", lambda: app.GetAssertMode())

import flim.resources  # noqa: E402

ico = str(files(flim.resources).joinpath("flimanalyzer.ico"))
print("icon file", ico, os.path.getsize(ico), "bytes")

section("app_icons() as the app loads it")


def load_bundle():
    from flim.gui.app import app_icons

    bundle = app_icons()
    return [(bundle.GetIconByIndex(i).GetSize(), bundle.GetIconByIndex(i).IsOk())
            for i in range(bundle.GetIconCount())]


try_("app_icons()", load_bundle)
try_("IconBundle(ico) directly", lambda: wx.IconBundle(ico, wx.BITMAP_TYPE_ICO).GetIconCount())

section("each size of the .ico")
for size in (16, 32, 48, 64, 128, 256):
    try_(f"wx.Icon {size}", lambda s=size: wx.Icon(ico, wx.BITMAP_TYPE_ICO, s, s).IsOk())

section("a frame with the icons (as the tests' AppFrame)")


def frame_with_icons():
    from flim.gui.app import app_icons

    frame = wx.Frame(None, title="diagnostic")
    frame.SetIcons(app_icons())
    frame.Destroy()
    return "ok"


try_("Frame.SetIcons(app_icons())", frame_with_icons)
app.Destroy()

section("the real program: flimanalyzer")
user32 = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)


def windows_of(pid):
    found = []

    def callback(hwnd, _):
        owner = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title, 256)
            if title.value:
                big = user32.SendMessageW(hwnd, 0x7F, 1, 0)  # WM_GETICON, ICON_BIG
                small = user32.SendMessageW(hwnd, 0x7F, 0, 0)  # ICON_SMALL
                found.append((title.value, bool(big), bool(small)))
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return found


start_dir = tempfile.mkdtemp()
exe = os.path.join(os.path.dirname(sys.executable), "flimanalyzer.exe")
proc = subprocess.Popen([exe], cwd=start_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
seen = []
for second in range(120):
    time.sleep(1)
    if proc.poll() is not None:
        print(f"exited after {second + 1} s with code {proc.returncode}")
        break
    seen = windows_of(proc.pid)
    if any(title.startswith("FLIMAnalyzer") for title, *_ in seen):
        print(f"main window after {second + 1} s")
        break
print("windows (title, big icon, small icon):", seen or "none")
if proc.poll() is None:
    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
try:
    output = proc.communicate(timeout=30)[0].decode(errors="replace")
except Exception:  # noqa: BLE001
    output = traceback.format_exc()
print("--- output (last 40 lines) ---")
print("\n".join(output.splitlines()[-40:]))
for log in glob.glob(os.path.join(start_dir, "**", "*.log"), recursive=True):
    print(f"--- {log} (last 40 lines) ---")
    with open(log, encoding="utf-8", errors="replace") as f:
        print("".join(f.readlines()[-40:]))
