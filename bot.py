import tweepy
from nba_api.stats.endpoints import boxscoretraditionalv2, scoreboardv2
from datetime import datetime, timedelta, timezone
import time
from supabase import create_client
import os

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
#  SUPABASE CONNECTION    #
# ======================= #
supabase_url = "https://fjtxowbjnxclzcogostk.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZqdHhvd2JqbnhjbHpjb2dvc3RrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDI2MDE5NTgsImV4cCI6MjA1ODE3Nzk1OH0.LPkFw-UX6io0F3j18Eefd1LmeAGGXnxL4VcCLOR_c1Q"
supabase = create_client(supabase_url, supabase_key)

# ======================= #
#     NBA STATS LOGIC     #
# ======================= #

def get_yesterday_date_str():
    est_now = datetime.now(timezone.utc) - timedelta(hours=4)
    yesterday = est_now - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")  # YYYY-MM-DD for DB use

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
    top_efficiency = {"name": "", "fg_pct": 0.0, "fga": 0, "team": ""}
    top_plus_minus = {"name": "", "plus_minus": -100, "team": ""}
    top_stocks = {"name": "", "stocks": 0, "team": ""}
    triple_double = None

    for game_id in game_ids:
        time.sleep(0.6)
        boxscore = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id)
        players = boxscore.get_normalized_dict()["PlayerStats"]

        for p in players:
            name = p["PLAYER_NAME"]
            team = p["TEAM_ABBREVIATION"]
            fga = p.get("FGA") or 0
            fgm = p.get("FGM") or 0
            fg_pct = fgm / fga if fga >= 15 else 0
            plus_minus = p.get("PLUS_MINUS")
            steals = p.get("STL") or 0
            blocks = p.get("BLK") or 0
            assists = p.get("AST") or 0
            rebounds = p.get("REB") or 0
            points = p.get("PTS") or 0

            if fg_pct > top_efficiency["fg_pct"]:
                top_efficiency = {
                    "name": name,
                    "fg_pct": round(fg_pct * 100, 1),
                    "fga": fga,
                    "team": team
                }

            if plus_minus is not None and plus_minus > top_plus_minus["plus_minus"]:
                top_plus_minus = {
                    "name": name,
                    "plus_minus": plus_minus,
                    "team": team
                }

            stocks = steals + blocks
            if stocks > top_stocks["stocks"]:
                top_stocks = {
                    "name": name,
                    "stocks": stocks,
                    "team": team
                }

            stat_categories = [points, rebounds, assists, steals, blocks]
            double_digits = sum(1 for stat in stat_categories if stat >= 10)
            if double_digits >= 3:
                triple_double = {
                    "name": name,
                    "team": team,
                    "pts": points,
                    "reb": rebounds,
                    "ast": assists
                }

    return top_efficiency, top_plus_minus, top_stocks, triple_double

def compose_tweet(date_str, efficiency, plus_minus, stocks, triple_double):
    formatted_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%m/%d/%Y")

    tweet = f"""📊 Efficiency Kings – {formatted_date}

⚡ Most Efficient Scorer
{efficiency['name']} ({efficiency['team']}): {efficiency['fg_pct']}% FG ({efficiency['fga']} FGA)

📈 Best +/-
{plus_minus['name']} ({plus_minus['team']}): +{plus_minus['plus_minus']}

🛡️ Defensive Beast
{stocks['name']} ({stocks['team']}): {stocks['stocks']} STL+BLK"""

    if triple_double:
        tweet += f"""\n\n👑 Triple-Double Royalty
{triple_double['name']} ({triple_double['team']}): {triple_double['pts']} | {triple_double['reb']} | {triple_double['ast']}"""

    tweet += "\n\n#NBAStats #CourtKingsHQ"
    return tweet

# ============================== #
#   SUPABASE JSON INSERT/UPSERT  #
# ============================== #

def update_efficiency_to_db(date_str, efficiency, plus_minus, stocks, triple_double):
    payload = {
        "date": date_str,
        "data": {
            "efficiency": {
                "player": efficiency["name"],
                "team": efficiency["team"],
                "fg_pct": efficiency["fg_pct"],
                "fga": efficiency["fga"]
            },
            "plus_minus": {
                "player": plus_minus["name"],
                "team": plus_minus["team"],
                "value": plus_minus["plus_minus"]
            },
            "defense": {
                "player": stocks["name"],
                "team": stocks["team"],
                "stocks": stocks["stocks"]
            },
            "triple_double": triple_double  # can be None
        }
    }

    try:
        response = supabase.table("efficiencykings").upsert(payload, on_conflict="date").execute()
        print("✅ Supabase updated:", response)
    except Exception as e:
        print("❌ Supabase write error:", e)

# ======================= #
#         MAIN BOT        #
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

        # Push to Supabase
        update_efficiency_to_db(date_str, efficiency, plus_minus, stocks, triple_double)

    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    run_bot()
