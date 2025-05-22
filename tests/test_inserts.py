import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json
import os
from pathlib import Path


from src.sql_scripts.sql_clans import insert_clan, insert_clans, get_clans_count
from src.sql_scripts.sql_players import insert_player, insert_players, get_players_count


@pytest.mark.asyncio
async def test_insert_single_player(db_pool):
    playertags = ['#P9J292JCL', '#J20Y2QG0Y', '#2VJ9PL9UG']

    for tag in playertags:
        await insert_player(db_pool, tag)

    count = await get_players_count(db_pool)

    assert count == 3

@pytest.mark.asyncio
async def test_insert_multiple_player(db_pool):
    playertags = ['#PYQQ92QJ', '#9YVUQCRUC', '#RY2RG2G8']

    await insert_players(db_pool, playertags)

    count = await get_players_count(db_pool)

    assert count == 3


@pytest.mark.asyncio
async def test_insert_single_clan(db_pool):
    clantags = [{'clantag': '#Q0JRGC22', 'clan_name': 'Afterparty', 'clan_league': 3}, {'clantag': '#PLL0UL0R', 'clan_name': 'addictedfamhero', 'clan_league': 4}, { 'clantag': '#9UP00V8Q', 'clan_name': 'AddictedIII', 'clan_league': 5 }]

    for clan in clantags:
        await insert_clan(db_pool, clan)

    count = await get_clans_count(db_pool)

    assert count == 3

@pytest.mark.asyncio
async def test_insert_multiple_clans(db_pool):
    clantags = [{'clantag': '#P2P2Y880', 'clan_name': 'Shock-13', 'clan_league': 3}, {'clantag': '#L9VRJ', 'clan_name': 'Calalas Espana', 'clan_league': 4}, { 'clantag': '#8UJ2UUJ8', 'clan_name': 'Muukans', 'clan_league': 5 }]

    await insert_clans(db_pool, clantags)

    count = await get_clans_count(db_pool)

    assert count == 3
