import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="tcgen_")
os.environ["APPDATA"] = _tmp
os.environ["HOME"] = _tmp