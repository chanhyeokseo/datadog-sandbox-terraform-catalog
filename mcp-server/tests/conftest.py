import json
import pytest
from unittest.mock import AsyncMock

from dogstac_client import DogSTACClient


class MockDogSTACClient(DogSTACClient):
    def __init__(self):
        super().__init__(base_url="http://mock:8000")
        self.get = AsyncMock()
        self.put = AsyncMock()
        self.post = AsyncMock()
        self.stream_get = AsyncMock()
        self.stream_post = AsyncMock()


@pytest.fixture
def mock_client():
    return MockDogSTACClient()
