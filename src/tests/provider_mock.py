"""Helpers for mocking market data in the Flask API tests.

main_web reaches market data through option_lib's DataProvider factory, which
selects Massive.com or Yahoo Finance depending on whether MASSIVE_API_KEY is
set in the environment.  Patching a concrete backend module (for example
``option_lib.yahoo_data.get_stock_info``) therefore only takes effect when that
backend happens to be the one selected — the same test passes with the key
unset and either fails or silently hits the live API with it set.

Patch ``main_web.get_provider`` instead: it is the single seam every endpoint
goes through, so the mock applies regardless of which provider is configured.
``massive_api_key()`` pins the environment so endpoint tests can assert the
same behaviour under both provider configurations.
"""

import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from option_lib.data_provider import DataProvider


# Both provider configurations, for tests that must behave identically under
# each: True -> Massive.com is selected, False -> Yahoo Finance.
MASSIVE_KEY_STATES = (True, False)


def make_provider(**returns) -> MagicMock:
    """Return a DataProvider mock whose named methods return the given values.

    ``make_provider(get_stock_info={...})`` makes ``provider.get_stock_info()``
    return that dict.  ``spec=DataProvider`` means a misspelt method name raises
    instead of quietly producing a new mock.
    """
    provider = MagicMock(spec=DataProvider)
    # api_stock falls back to this when the snapshot carries no earnings date;
    # a bare mock return value would be neither a date string nor None.
    provider.get_earnings_date.return_value = None
    for name, value in returns.items():
        getattr(provider, name).return_value = value
    return provider


@contextmanager
def mock_provider(**returns):
    """Patch main_web.get_provider for the duration of the block.

    Yields the mock provider so calls to it can be asserted on.
    """
    provider = make_provider(**returns)
    with patch("main_web.get_provider", return_value=provider):
        yield provider


@contextmanager
def massive_api_key(enabled: bool):
    """Run the block with MASSIVE_API_KEY set (*enabled*) or absent.

    The developer environment usually carries a real key, so tests that must
    hold for both providers set this explicitly rather than inheriting whatever
    the shell happens to export.  patch.dict restores the original environment
    on exit, including keys removed inside the block.
    """
    with patch.dict(os.environ, {}, clear=False):
        if enabled:
            os.environ["MASSIVE_API_KEY"] = "test-massive-key"
        else:
            os.environ.pop("MASSIVE_API_KEY", None)
        yield
