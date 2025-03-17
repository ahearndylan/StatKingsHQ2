import tweepy
from nba_api.stats.endpoints import boxscoretraditionalv2, scoreboardv2
from datetime import datetime, timedelta, timezone
import time

# ======================= #
# TWITTER AUTHENTICATION  #
# ======================= #
bearer_token = "AAAAAAAAAAAAAAAAAAAAAPztzwEAAAAAvBGCjApPNyqj9c%2BG7740SkkTShs%3DTCpOQ0DMncSMhaW0OA4UTPZrPRx3BHjIxFPzRyeoyMs2KHk6hM"
api_key = "uKyGoDr5LQbLvu9i7pgFrAnBr"
api_secret = "KGBVtj1BUmAEsyoTmZhz67953ItQ8TIDcChSpodXV8uGMPXsoH"
access_token = "1901441558596988929-WMdEPOtNDj7QTJgLHVylxnylI9ObgD"
access_token_secret = "9sf83R8A0MBdijPdns6nWaG7HF47htcWo6oONPmMS7o98"

client = tweepy.Client(
    bearer_token=bearer_token,
    consumer_key=api_key,
    consumer_secret=api_secret,
    access_token=access_token,
    access_token_secret=access_token_secret
)

# ======================= #
#     NBA STATS LOGIC     #
# ======================= #

def get_yesterday_date_str():
    est_now = datetime.now(timezone.utc) - timedelta(hours=5)
    yesterday = est_now - timedelta(days=1)
    return yesterday.strftime("%m/%d/%Y")

def get_game_ids_for_date(date_str, max_retries=3):
    for attempt in range(max_retries):
        try:
            scoreboard = scoreboardv2.ScoreboardV2(game_date=date_str)
            games = scoreboard.get_normalized_dict()["GameHeader"]
            return [game["GAME_ID"] for game in games]
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(2)
    raise Exception("Failed to fetch game IDs after multiple attempts.")

def get_efficiency_stats(game_ids):
    top_efficiency = {"name": "", "fg_pct": 0.0, "fga": 0}
    top_plus_minus = {"name": "", "plus_minus": -100}
    top_stocks = {"name": "", "stocks": 0}
    triple_double = None

    for game_id in game_ids:
        time.sleep(0.6)
        boxscore = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id)
        players = boxscore.get_normalized_dict()["PlayerStats"]

        for p in players:
            name = p["PLAYER_NAME"]
            fga = p.get("FGA") or 0
            fgm = p.get("FGM") or 0
            fg_pct = fgm / fga if fga >= 15 else 0
            plus_minus = p.get("PLUS_MINUS")
            steals = p.get("STL") or 0
            blocks = p.get("BLK") or 0
            assists = p.get("AST") or 0
            rebounds = p.get("REB") or 0
            points = p.get("PTS") or 0

            # Most efficient scorer (min 15 FGA)
            if fg_pct > top_efficiency["fg_pct"]:
                top_efficiency = {"name": name, "fg_pct": round(fg_pct * 100, 1), "fga": fga}

            # Best plus-minus
            if plus_minus is not None and plus_minus > top_plus_minus["plus_minus"]:
                top_plus_minus = {"name": name, "plus_minus": plus_minus}

            # Most combined steals and blocks
            stocks = steals + blocks
            if stocks > top_stocks["stocks"]:
                top_stocks = {"name": name, "stocks": stocks}

            # Triple-double check
            stat_categories = [points, rebounds, assists, steals, blocks]
            double_digits = sum(1 for stat in stat_categories if stat >= 10)
            if double_digits >= 3:
                triple_double = name

    return top_efficiency, top_plus_minus, top_stocks, triple_double

def compose_tweet(date_str, efficiency, plus_minus, stocks, triple_double):
    tweet = f"""📊 Efficiency Kings – {date_str}

⚡ Most Efficient Scorer
{efficiency['name']}: {efficiency['fg_pct']}% FG ({efficiency['fga']} FGA)

📈 Best Plus-Minus
{plus_minus['name']}: +{plus_minus['plus_minus']}

🛡️ Defensive Beast
{stocks['name']}: {stocks['stocks']} STL+BLK"""

    if triple_double:
        tweet += f"\n\n👑 Triple-Double Alert!\n{triple_double} did it all last night."

    tweet += "\n\n#NBA #EfficiencyKings #StatKingsHQ"
    return tweet

# ======================= #
#        MAIN BOT         #
# ======================= #

def run_bot():
    date_str = get_yesterday_date_str()
    try:
        game_ids = get_game_ids_for_date(date_str)
        if not game_ids:
            print("No games found for", date_str)
            return

        efficiency, plus_minus, stocks, triple_double = get_efficiency_stats(game_ids)
        tweet = compose_tweet(date_str, efficiency, plus_minus, stocks, triple_double)
        print("Tweeting:\n", tweet)
        client.create_tweet(text=tweet)

    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    run_bot()
