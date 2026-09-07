import pytest
from ui_common import require_auth

def test_require_auth_does_not_block():
    # require_auth should be a pass-through and not stop or raise
    require_auth()
    assert True
