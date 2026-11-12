"""macOS integration that wxPython does not provide.

Started as a script, the GUI is the Python executable to macOS, so the Dock and
the menu bar show the executable's name (e.g. "python3.12"). The functions here
replace that name; they do nothing on other platforms, and they log errors (debug
level) instead of raising them.
"""

import ctypes
import ctypes.util
import logging
import sys
from typing import Optional

logger = logging.getLogger(__name__)

_UTF8 = 0x08000100  # kCFStringEncodingUTF8


def _lib(name: str) -> ctypes.CDLL:
    """Load a system library by its short name, e.g. `objc`."""
    return ctypes.cdll.LoadLibrary(ctypes.util.find_library(name))


def set_bundle_name(name: str) -> None:
    """Set the name that the macOS menu bar shows for the GUI.

    Call it before the `wx.App` is created. It sets `CFBundleName` in the main
    bundle's info dictionary.

    Args:
        name: The name to show.
    """
    if sys.platform != "darwin":
        return
    try:
        objc = _lib("objc")
        _lib("Foundation")
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        send = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
        p = ctypes.c_void_p
        msg = ctypes.CFUNCTYPE(p, p, p)(send)
        msg_str = ctypes.CFUNCTYPE(p, p, p, ctypes.c_char_p)(send)
        msg_set = ctypes.CFUNCTYPE(None, p, p, p, p)(send)

        def sel(n: str) -> Optional[int]:
            return objc.sel_registerName(n.encode())

        def nsstring(s: str) -> Optional[int]:
            return msg_str(objc.objc_getClass(b"NSString"), sel("stringWithUTF8String:"), s.encode())

        bundle = msg(objc.objc_getClass(b"NSBundle"), sel("mainBundle"))
        info = msg(bundle, sel("infoDictionary"))
        if info:
            msg_set(info, sel("setObject:forKey:"), nsstring(name), nsstring("CFBundleName"))
    except Exception as e:
        logger.debug(f"Could not set the macOS bundle name: {e!r}")


def set_display_name(name: str) -> None:
    """Set the name that the macOS Dock shows for the GUI.

    Call it after the `wx.App` is created. It uses the private LaunchServices call
    that Chromium uses for the same purpose.

    Args:
        name: The name to show.
    """
    if sys.platform != "darwin":
        return
    try:
        cf = _lib("CoreFoundation")
        ls = _lib("CoreServices")
        cf.CFStringCreateWithCString.restype = ctypes.c_void_p
        cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
        cf.CFRelease.argtypes = [ctypes.c_void_p]
        ls._LSGetCurrentApplicationASN.restype = ctypes.c_void_p
        ls._LSSetApplicationInformationItem.restype = ctypes.c_int32
        ls._LSSetApplicationInformationItem.argtypes = [ctypes.c_int] + [ctypes.c_void_p] * 4
        asn = ls._LSGetCurrentApplicationASN()
        if not asn:
            return
        key = ctypes.c_void_p.in_dll(ls, "_kLSDisplayNameKey").value
        value = cf.CFStringCreateWithCString(None, name.encode(), _UTF8)
        try:
            ls._LSSetApplicationInformationItem(-2, asn, key, value, None)  # -2: current session
        finally:
            cf.CFRelease(value)
    except Exception as e:
        logger.debug(f"Could not set the macOS display name: {e!r}")
