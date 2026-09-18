"""
conftest.py — Global Testing Fixtures for Project Anara.
"""

import os
import sys
from pathlib import Path
import pytest

_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


@pytest.fixture(scope="session", autouse=True)
def hermetic_environment(tmp_path_factory):
    test_home = tmp_path_factory.mktemp("anara_test_home")
    os.environ["ANARA_HOME"] = str(test_home)
    os.environ["ANARA_TESTING"] = "1"
    yield test_home
