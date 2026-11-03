import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """모든 테스트는 실제 Documents\\SoneFM 대신 임시 폴더를 쓴다."""
    home = tmp_path / "SoneFM"
    monkeypatch.setenv("SONEFM_HOME", str(home))
    return home
