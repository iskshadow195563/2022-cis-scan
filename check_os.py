import os
import sys
sys.path.insert(0, os.getcwd())
from core.os_detection import is_os_supported, get_server_family, get_windows_edition

from core.language_manager import tr

detected = get_server_family() or get_windows_edition() or tr("unknown")
if not is_os_supported():
    print(tr("server_console_warning", detected))
    sys.exit(1)
