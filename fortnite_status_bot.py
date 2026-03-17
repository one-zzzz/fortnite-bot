import os
import json
import requests
import base64
from datetime import datetime

TELEGRAM_BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
GITHUB_TOKEN        = os.getenv("TOKEN")
GITHUB_REPO         = os.getenv("GITHUB_REPOSITORY", "one-zzzz/fortnite-bot")
RAPIDAPI_KEY        = os.getenv("RAPIDAPI_KEY")
TWITTER_USER_ID     = "1181729392755707904"
TWITTER_USERNAME    = "FortniteStatus"
RAPIDAPI_HOST       = "twitter241.p.rapidapi.com"
SEEN_IDS_PATH       = "seen_ids.json"

def load_seen_ids():
    url     = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{SEEN_IDS_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    resp    = requests.get(url, headers=headers)
    if resp.status_code == 200:
        content = base64.b64decode(resp.json()["content"]).decode()
        return set(json.loads(content)), resp.json()["sha"]
    return set(), None

def save_seen_ids(seen_ids, sha=None):
    url     = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{SEEN_IDS_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    content = base64.b64encode(json.dumps(list(seen_ids)).encode()).decode()
    payload = {"message": "update seen_ids", "content": content}
    if sha:
        payload["sha"] = sha
    requests.put(url, headers=headers, json=payload)

def get_original_tweet(tweet_id):
    try:
        headers = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": RAPIDAPI_HOST}
        url  = f"https://{RAPIDAPI_HOST}/tweet-detail?id={tweet_id}"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        instructions = resp.json().get("result", {}).get("timeline", {}).get("instructions", [])
        for instruction in instructions:
            for entry in instruction.get("entries", []):
                for item in [entry] + entry.get("content", {}).get("items", []):
                    try:
                        ic = item.get("content", item.get("item", {}).get("itemContent", {}))
                        if "itemContent" in ic:
                            ic = ic["itemContent"]
                        r  = ic.get("tweet_results", {}).get("result", {})
                        if "tweet" in r:
                            r = r["tweet"]
                        lg   = r.get("legacy", {})
                        user = r.get("core", {}).get("user_results", {}).get("result", {}).get("core", {}).get("screen_name", "")
                        tid  = lg.get("id_str", "")
                        text = lg.get("full_text", "")
                        if tid == tweet_id and text and user:
                            return {"text": text, "user": user}
                    except (KeyError, TypeError):
                        pass
    except Exception as e:
        print(f"[!] Original tweet fetch error: {e}")
    return None

def send_telegram(tweet):
    is_reply  = bool(tweet.get("reply_to"))
    tweet_url = f"https://x.com/{TWITTER_USERNAME}/status/{tweet['id']}"

    if is_reply and tweet.get("original"):
        # Format exactly like X — original message first, then reply below
        orig = tweet["original"]
        msg  = (
            f"@{orig['user']}:\n"
            f"{orig['text']}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"↩️ @{TWITTER_USERNAME} replied:\n"
            f"{tweet['text']}\n\n"
            f"🔗 {tweet_url}"
        )
    else:
        msg = (
            f"📢 @{TWITTER_USERNAME}:\n\n"
            f"{tweet['text']}\n\n"
            f"🔗 {tweet_url}"
        )

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    )
    print(f"[+] Telegram sent")

def send_discord(tweet):
    if not DISCORD_WEBHOOK_URL:
        return
    is_reply  = bool(tweet.get("reply_to"))
    tweet_url = f"https://x.com/{TWITTER_USERNAME}/status/{tweet['id']}"

    if is_reply and tweet.get("original"):
        orig  = tweet["original"]
        color = 0x657786
        desc  = (
            f"> **@{orig['user']}:** {orig['text']}\n\n"
            f"↩️ **@{TWITTER_USERNAME} replied:**\n"
            f"{tweet['text']}"
        )
    else:
        color = 0x1DA1F2
        desc  = tweet["text"]

    embed = {"embeds": [{
        "author": {
            "name":     f"@{TWITTER_USERNAME}",
            "url":      f"https://x.com/{TWITTER_USERNAME}",
            "icon_url": "https://pbs.twimg.com/profile_images/1182784466240135170/tTYzHFoe_normal.jpg"
        },
        "description": desc,
        "color": color,
        "footer": {"text": "🎮 Fortnite Status" + (" • Reply" if is_reply else " • Tweet")},
        "url": tweet_url
    }]}
    requests.post(DISCORD_WEBHOOK_URL, json=embed)
    print(f"[+] Discord sent")

def fetch_tweets():
    headers = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": RAPIDAPI_HOST}
    tweets  = []
    for endpoint in ["user-tweets", "user-replies"]:
        try:
            url  = f"https://{RAPIDAPI_HOST}/{endpoint}?user={TWITTER_USER_ID}&count=20"
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                print(f"[!] {endpoint}: {resp.status_code}")
                continue
            instructions = resp.json().get("result", {}).get("timeline", {}).get("instructions", [])
            for instruction in instructions:
                for entry in instruction.get("entries", []):
                    try:
                        r = entry["content"]["itemContent"]["tweet_results"]["result"]
                        if "tweet" in r: r = r["tweet"]
                        lg = r["legacy"]
                        if not lg.get("full_text","").startswith("RT @"):
                            tweets.append({"id": lg["id_str"], "text": lg["full_text"], "reply_to": lg.get("in_reply_to_status_id_str")})
                    except (KeyError, TypeError): pass
                    for item in entry.get("content", {}).get("items", []):
                        try:
                            r = item["item"]["itemContent"]["tweet_results"]["result"]
                            if "tweet" in r: r = r["tweet"]
                            lg = r["legacy"]
                            if not lg.get("full_text","").startswith("RT @"):
                                tweets.append({"id": lg["id_str"], "text": lg["full_text"], "reply_to": lg.get("in_reply_to_status_id_str")})
                        except (KeyError, TypeError): pass
        except Exception as e:
            print(f"[!] {endpoint}: {e}")
    seen, unique = set(), []
    for t in tweets:
        if t["id"] not in seen:
            seen.add(t["id"])
            unique.append(t)
    print(f"[*] Fetched {len(unique)} tweets/replies")
    return unique

def main():
    print(f"[*] Check at {datetime.utcnow().strftime('%H:%M:%S')} UTC")
    seen_ids, sha = load_seen_ids()
    print(f"[*] Loaded {len(seen_ids)} seen IDs")
    tweets = fetch_tweets()
    if not tweets:
        print("[!] No tweets fetched.")
        return
    if not seen_ids:
        for t in tweets: seen_ids.add(t["id"])
        save_seen_ids(seen_ids, sha)
        print(f"[*] First run — recorded {len(seen_ids)} IDs.")
        return
    new = [t for t in tweets if t["id"] not in seen_ids]
    if not new:
        print("[~] No new tweets.")
        return
    for t in reversed(new):
        if t.get("reply_to"):
            original = get_original_tweet(t["reply_to"])
            if original:
                t["original"] = original
        send_telegram(t)
        send_discord(t)
        seen_ids.add(t["id"])
    save_seen_ids(seen_ids, sha)
    print(f"[*] Sent {len(new)} tweet(s).")

if __name__ == "__main__":
    main()
