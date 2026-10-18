import sys

import pytest

from flim.gui import macos


def test_app_name_functions_never_raise():
    # cosmetic only: they must not stop the app from starting on any platform
    macos.set_bundle_name("FLIMAnalyzer")
    macos.set_display_name("FLIMAnalyzer")


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_bundle_name_is_set():
    import ctypes

    objc = macos._lib("objc")
    objc.objc_getClass.restype = objc.sel_registerName.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = objc.sel_registerName.argtypes = [ctypes.c_char_p]
    send = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
    p = ctypes.c_void_p
    msg = ctypes.CFUNCTYPE(p, p, p)(send)
    msg1 = ctypes.CFUNCTYPE(p, p, p, p)(send)
    msg_str = ctypes.CFUNCTYPE(p, p, p, ctypes.c_char_p)(send)
    utf8 = ctypes.CFUNCTYPE(ctypes.c_char_p, p, p)(send)
    sel = lambda n: objc.sel_registerName(n.encode())  # noqa: E731
    key = msg_str(objc.objc_getClass(b"NSString"), sel("stringWithUTF8String:"), b"CFBundleName")

    macos.set_bundle_name("FLIMAnalyzer")
    bundle = msg(objc.objc_getClass(b"NSBundle"), sel("mainBundle"))
    value = msg1(bundle, sel("objectForInfoDictionaryKey:"), key)
    assert value and utf8(value, sel("UTF8String")) == b"FLIMAnalyzer"
