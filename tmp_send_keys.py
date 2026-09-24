import ctypes
import time

user32 = ctypes.windll.user32

def find_opencode():
    hwnds = []
    def enum_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                val = buf.value
                if "opencode" in val.lower():
                    hwnds.append((hwnd, val))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    return hwnds

windows = find_opencode()
print("Found windows:", windows)

if not windows:
    print("OpenCode window not found!")
else:
    hwnd, title = windows[0]
    print(f"Activating hwnd={hwnd}, title='{title}'")
    user32.ShowWindow(hwnd, 9) # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)
    
    # VK_P = 0x50, VK_RETURN = 0x0D
    KEYEVENTF_KEYUP = 0x0002
    VK_P = 0x50
    VK_RETURN = 0x0D
    
    # Send 'p'
    user32.keybd_event(VK_P, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_P, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.1)
    
    # Send Enter
    user32.keybd_event(VK_RETURN, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)
    print("Sent 'p' and Enter successfully.")
