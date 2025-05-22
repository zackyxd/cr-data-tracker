-- Create all tables for the database

CREATE TABLE players(
    playertag TEXT PRIMARY KEY,
    player_name TEXT,
    last_checked TIMESTAMPTZ DEFAULT NULL,
    is_tracked BOOLEAN DEFAULT False, -- If True, means they have been in 3k+ war clan
    has_been_scanned BOOLEAN DEFAULT FALSE, -- If True, means they havent had matches tracked yet.
    -- When FALSE, mark matches as void because it's not the most updated decks.
    day1_battles SMALLINT DEFAULT 0,
    day2_battles SMALLINT DEFAULT 0,
    day3_battles SMALLINT DEFAULT 0,
    day4_battles SMALLINT DEFAULT 0
);

CREATE TABLE decks(
    deck_id SERIAL PRIMARY KEY,
    deck_count INT DEFAULT 0,
    deck_wins INT DEFAULT 0,
    deck_losses INT DEFAULT 0,
    deck_ties INT DEFAULT 0,
    deck_throws INT DEFAULT 0
);

CREATE TABLE deck_signatures (
    deck_id INT REFERENCES decks(deck_id) ON DELETE CASCADE,
    cards TEXT[] NOT NULL,
    evolutions TEXT[] DEFAULT '{}'::TEXT[],
    UNIQUE (cards, evolutions)
);

CREATE TABLE clans(
   clantag TEXT PRIMARY KEY,
   clan_name TEXT NOT NULL,
   clan_trophy SMALLINT NOT NULL,
   clan_league SMALLINT NOT NULL,
   last_checked TIMESTAMPTZ DEFAULT NULL
);


-- Create this ENUM once
CREATE TYPE match_result_enum AS ENUM ('win', 'loss', 'tie', 'throw', 'unknown');
CREATE TABLE matches(
    match_id SERIAL PRIMARY KEY,
    clantag TEXT REFERENCES clans(clantag),
    player_name TEXT,
    opponent_player_name TEXT,
    playertag TEXT REFERENCES players(playertag) ON DELETE CASCADE,
    opponent_playertag TEXT REFERENCES players(playertag),
    player_deck_id INT REFERENCES decks(deck_id),
    opponent_deck_id INT REFERENCES decks(deck_id),
    player_card_levels SMALLINT[8] NOT NULL,
    opponent_card_levels SMALLINT[8] NOT NULL,
    battle_type TEXT NOT NULL,
    duel_round SMALLINT DEFAULT NULL,
    match_result match_result_enum NOT NULL,
    clan_league SMALLINT NOT NULL,
    elixir_leaked DECIMAL(6,2) NOT NULL,
    battle_time TIMESTAMPTZ NOT NULL,
    season SMALLINT DEFAULT NULL,
    week SMALLINT DEFAULT NULL,
    current_day SMALLINT NOT NULL,
    is_void BOOLEAN DEFAULT NULL, -- If True, means first time searching the player
    CONSTRAINT unique_player_battle UNIQUE (playertag, battle_time, duel_round)
);

CREATE TABLE logs(
    id SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL, -- e.g., 'sync', 'match_insert', 'api_error'
    status_code SMALLINT DEFAULT 200,
    message TEXT, -- human readable
    success BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    context TEXT -- optional JSON or text (e.g., playertag, match_id)
);


CREATE TABLE clan_war_stats(
    clantag TEXT NOT NULL REFERENCES clans(clantag) ON DELETE CASCADE,
    clan_name TEXT NOT NULL,
    season SMALLINT NOT NULL,
    week SMALLINT NOT NULL,
    clan_league SMALLINT NOT NULL,
    placement SMALLINT NOT NULL DEFAULT -1,
    clan_fame INT NOT NULL DEFAULT 0,
    wins SMALLINT NOT NULL DEFAULT 0,
    losses SMALLINT NOT NULL DEFAULT 0,
    throws SMALLINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    participants TEXT[] NOT NULL,
    UNIQUE(clantag, season, week)
);

CREATE TABLE player_weekly_fame(
    season SMALLINT DEFAULT NULL,
    week SMALLINT DEFAULT NULL,
    playertag TEXT NOT NULL REFERENCES players(playertag) ON DELETE CASCADE,
    clantag TEXT NOT NULL REFERENCES clans(clantag) ON DELETE CASCADE,
    clan_league SMALLINT NOT NULL,
    player_fame SMALLINT DEFAULT 0,
    decks_used SMALLINT DEFAULT 0,
    throws SMALLINT DEFAULT 0, -- decks_used + throws = total attacls. Throw fame isnt added originally
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (playertag, clantag, clan_league, season, week)
);

CREATE TABLE player_weekly_stats(
	player_name TEXT,
    playertag TEXT references players(playertag) ON DELETE CASCADE,
    season SMALLINT NOT NULL,
    week SMALLINT NOT NULL,
    exp_level SMALLINT NOT NULL,
    acc_wins INT NOT NULL,
    acc_losses INT NOT NULL,
    trophy_road_trophies SMALLINT NOT NULL,
    classic_wins SMALLINT NOT NULL,
    grand_wins SMALLINT NOT NULL,
    clan_war_wins SMALLINT NOT NULL,
    current_UC_medals SMALLINT,
    last_UC_medals SMALLINT,
    last_UC_rank SMALLINT,
    best_UC_medals SMALLINT,
    best_UC_rank SMALLINT,
    important_badges JSONB,
    fetched_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (playertag, season, week)
);

CREATE TABLE api_calls_count(
 id SERIAL PRIMARY KEY,
 group_id TEXT NOT NULL DEFAULT 'default',
 called_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for checking if match exists or not.
CREATE INDEX idx_matches_playertag_battle_time
ON matches(playertag, battle_time);
