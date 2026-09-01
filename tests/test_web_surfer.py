import pytest
from dip.pipeline.collection.research.retrieval.web_surfer import web_surfer

@pytest.mark.asyncio
async def test_web_surfer_search_cascade():
    results = await web_surfer.search("Taiwan Strait military exercises", country_code="TWN", max_results=3)
    assert results is not None
    assert len(results) > 0
    assert results[0].content != ""
    assert results[0].source_id != ""
