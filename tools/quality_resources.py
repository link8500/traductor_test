"""Keep native QA inference from exhausting the Windows host's memory."""
import ctypes
import json
import os
import time


def available_memory_bytes():
    if os.name != 'nt':
        return None

    class MemoryStatus(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                    ('total_physical', ctypes.c_ulonglong), ('available_physical', ctypes.c_ulonglong),
                    ('total_pagefile', ctypes.c_ulonglong), ('available_pagefile', ctypes.c_ulonglong),
                    ('total_virtual', ctypes.c_ulonglong), ('available_virtual', ctypes.c_ulonglong),
                    ('available_extended_virtual', ctypes.c_ulonglong)]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ctypes.WinError()
    return status.available_physical


def wait_for_inference_memory(minimum_free_bytes=3 * 1024**3):
    """Wait before a new job; preserve existing reports and user programs."""
    while True:
        free = available_memory_bytes()
        if free is None or free >= minimum_free_bytes:
            return
        print(json.dumps(dict(state='waiting_for_host_memory', free_bytes=free,
                              minimum_free_bytes=minimum_free_bytes)), flush=True)
        time.sleep(20)
