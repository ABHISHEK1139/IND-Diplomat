"""Offline regression for unavailable STIX export support."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from dip.api import rest_api
from dip.engines import stix2_adapter


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unavailable_stix_adapter_preserves_501(monkeypatch):
    store = Mock()
    store.get.return_value = SimpleNamespace(result={"query": "Offline test"})
    monkeypatch.setattr(rest_api, "job_store", store)
    monkeypatch.setattr(stix2_adapter, "create_stix2_adapter", lambda: None)

    with pytest.raises(HTTPException) as caught:
        await rest_api.api_v3_job_stix2("test-job")

    assert caught.value.status_code == 501
    assert "stix2 not installed" in caught.value.detail
