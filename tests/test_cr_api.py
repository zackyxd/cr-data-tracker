import pytest
from src.api_calls.cr_api import fetch_player, fetch_members_in_clan, fetch_participants_in_clan
from unittest.mock import AsyncMock, patch, MagicMock
from src.api_calls.cr_api import fetch_clan
import json
from pathlib import Path

def load_mock_clan_data(fileName):
    path = Path(__file__).parent / "mock_data" / f"{fileName}.json"
    with open(path, "r", encoding='utf-8') as f:
        return json.load(f)

@pytest.mark.asyncio
async def test_fetch_player(pool):
    playertag = "2VJ9PL9UG"
    data = await fetch_player(pool, playertag)
    # print(data)
    assert data is not None

@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_fetch_clan_success(mock_client_session):
    mock_json_data = load_mock_clan_data('clandata')

    # Setup mock aiohttp response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = mock_json_data

    # Setup the mock session and get() context
    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_client_session.return_value.__aenter__.return_value = mock_session

    # Mock DB pool and internal helpers
    fake_pool = AsyncMock()
    with patch("src.api_calls.cr_api.wait_and_record_api_call", return_value=True), \
         patch("src.api_calls.cr_api.is_under_maintenance", return_value=False), \
         patch("src.api_calls.cr_api.log_api_event", return_value=None):

        result = await fetch_clan(fake_pool, "#9U82JJ0Y")
        assert result['name'] == 'TheAddictedOnes'

@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_fetch_clan_fail(mock_client_session):
    mock_json_data = load_mock_clan_data('clandatafail')

    # Setup mock aiohttp response
    mock_response = AsyncMock()
    mock_response.status = 404
    mock_response.json.return_value = mock_json_data

    # Setup the mock session and get() context
    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_client_session.return_value.__aenter__.return_value = mock_session

    # Mock DB pool and internal helpers
    fake_pool = AsyncMock()
    with patch("src.api_calls.cr_api.wait_and_record_api_call", return_value=True), \
         patch("src.api_calls.cr_api.is_under_maintenance", return_value=False), \
         patch("src.api_calls.cr_api.log_api_event", return_value=None):

        result = await fetch_clan(fake_pool, "#FAKETAG")
        print(result)
        assert result.get('status') == 404
        assert result.get('success') is False

@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_fetch_clan_maintenance(mock_client_session):
    mock_json_data = load_mock_clan_data('clandatafail')

    # Setup mock aiohttp response
    mock_response = AsyncMock()
    mock_response.status = 503
    mock_response.json.return_value = mock_json_data

    # Setup the mock session and get() context
    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_client_session.return_value.__aenter__.return_value = mock_session

    # Mock DB pool and internal helpers
    fake_pool = AsyncMock()
    with patch("src.api_calls.cr_api.wait_and_record_api_call", return_value=True), \
         patch("src.api_calls.cr_api.is_under_maintenance", return_value=False), \
         patch("src.api_calls.cr_api.log_api_event", return_value=None):

        result = await fetch_clan(fake_pool, "#FAKETAG")
        assert result.get('status') == 503
        assert result.get('reason') == 'Maintenance Break'
        assert result.get('success') == False

@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_fetch_clan_unexpected_status(mock_client_session):
    mock_json_data = load_mock_clan_data('clandata')

    # Setup mock aiohttp response
    mock_response = AsyncMock()
    mock_response.status = 69420
    mock_response.json.return_value = mock_json_data

    # Setup the mock session and get() context
    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_client_session.return_value.__aenter__.return_value = mock_session

    # Mock DB pool and internal helpers
    fake_pool = AsyncMock()
    with patch("src.api_calls.cr_api.wait_and_record_api_call", return_value=True), \
         patch("src.api_calls.cr_api.is_under_maintenance", return_value=False), \
         patch("src.api_calls.cr_api.log_api_event", return_value=None):

        result = await fetch_clan(fake_pool, "#9U82JJ0Y")
        assert result.get('status') is not 200 and result.get('status') is not 503 and result.get('status') is not 404
        assert result.get('reason') == 'Unexpected Status'
        assert result.get('success') == False

@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_fetch_clan_triggers_maintenance(mock_client_session):
    # Simulate a 503 response
    mock_response = AsyncMock()
    mock_response.status = 503
    mock_response.json.return_value = {}

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_client_session.return_value.__aenter__.return_value = mock_session

    fake_pool = AsyncMock()

    with patch("src.api_calls.cr_api.wait_and_record_api_call", return_value=True), \
         patch("src.api_calls.cr_api.is_under_maintenance", return_value=False), \
         patch("src.api_calls.cr_api.set_maintenance", return_value=True) as mock_set_maintenance, \
         patch("src.api_calls.cr_api.log_api_event", return_value=None) as mock_log:

        result = await fetch_clan(fake_pool, "#ABC123")
        print(result)
        # ✅ Assert it returned None due to maintenance
        assert result['status'] == 503
        assert result['reason'] == 'Maintenance Break'
        assert result['success'] == False

        # ✅ Assert set_maintenance was triggered
        mock_set_maintenance.assert_called_once_with(20)

        # ✅ Optionally check log_api_event details
        mock_log.assert_called_once()
        args, kwargs = mock_log.call_args
        print (args, kwargs)
        assert kwargs['status_code'] == 503
        assert kwargs['message'] == 'Maintenance Break'


# Player

@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_fetch_player_success(mock_client_session):
    mock_json_data = load_mock_clan_data('playerdata')

    # Setup mock aiohttp response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = mock_json_data

    # Setup the mock session and get() context
    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_client_session.return_value.__aenter__.return_value = mock_session

    # Mock DB pool and internal helpers
    fake_pool = AsyncMock()
    with patch("src.api_calls.cr_api.wait_and_record_api_call", return_value=True), \
         patch("src.api_calls.cr_api.is_under_maintenance", return_value=False), \
         patch("src.api_calls.cr_api.log_api_event", return_value=None):

        result = await fetch_player(fake_pool, "#P9J292JCL")
        assert result['tag'] == '#P9J292JCL'

@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_fetch_player_fail(mock_client_session):
    mock_json_data = {}

    # Setup mock aiohttp response
    mock_response = AsyncMock()
    mock_response.status = 404
    mock_response.json.return_value = mock_json_data

    # Setup the mock session and get() context
    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_client_session.return_value.__aenter__.return_value = mock_session

    # Mock DB pool and internal helpers
    fake_pool = AsyncMock()
    with patch("src.api_calls.cr_api.wait_and_record_api_call", return_value=True), \
         patch("src.api_calls.cr_api.is_under_maintenance", return_value=False), \
         patch("src.api_calls.cr_api.log_api_event", return_value=None):

        result = await fetch_player(fake_pool, "#FAKETAG")
        assert result['success'] is False
        assert result['status'] == 404

@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_fetch_members_in_clan(mock_client_session):
    mock_json_data = load_mock_clan_data('clandata')

    # Setup mock aiohttp response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = mock_json_data

    # Setup the mock session and get() context
    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_client_session.return_value.__aenter__.return_value = mock_session

    # Mock DB pool and internal helpers
    fake_pool = AsyncMock()
    with patch("src.api_calls.cr_api.wait_and_record_api_call", return_value=True), \
         patch("src.api_calls.cr_api.is_under_maintenance", return_value=False), \
         patch("src.api_calls.cr_api.log_api_event", return_value=None):

        result = await fetch_members_in_clan(fake_pool, "#9U82JJ0Y")
        assert len(result) == 43

@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_fetch_participants_in_clan(mock_client_session):
    mock_json_data = load_mock_clan_data('currentriverrace')

    # Setup mock aiohttp response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = mock_json_data

    # Setup the mock session and get() context
    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_client_session.return_value.__aenter__.return_value = mock_session

    # Mock DB pool and internal helpers
    fake_pool = AsyncMock()
    with patch("src.api_calls.cr_api.wait_and_record_api_call", return_value=True), \
         patch("src.api_calls.cr_api.is_under_maintenance", return_value=False), \
         patch("src.api_calls.cr_api.log_api_event", return_value=None):

        result = await fetch_participants_in_clan(fake_pool, "#9U82JJ0Y")
        assert len(result) == 109

# Test API Rate Limit Hit
@patch("src.api_calls.cr_api.wait_and_record_api_call", return_value=False)
@patch("src.api_calls.cr_api.is_under_maintenance", return_value=False)
@pytest.mark.asyncio
async def test_fetch_clan_rate_limited(mock_maintenance, mock_wait):
    fake_pool = AsyncMock()
    result = await fetch_clan(fake_pool, "#ANYTAG")

    assert result["status"] == 429
    assert result["reason"] == "Rate Limit Hit"
    assert result["success"] is False

