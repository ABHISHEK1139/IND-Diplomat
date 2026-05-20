import pytest


pytestmark = pytest.mark.skip(reason="Legacy MoltBotFetcher was removed from the codebase.")


def test_moltbot_fetcher_legacy_removed() -> None:
    assert True
