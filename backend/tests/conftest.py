import pytest

from providers import open_meteo, stadia


@pytest.fixture(autouse=True)
def no_live_providers(monkeypatch):
    """Tests never call the network (AGENTS.md): a provider a test did not replace fails it."""

    def live(*args, **kwargs):
        raise AssertionError("This test reached a live provider; replay a recording instead.")

    monkeypatch.setattr(stadia, "default", live)
    monkeypatch.setattr(open_meteo, "default", live)
