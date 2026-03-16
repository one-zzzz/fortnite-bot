import os
import json
import requests
import base64
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
GITHUB_TOKEN       = os.getenv("TOKEN")
GITHUB_REPO        = os.getenv("GITHUB_REPOSITORY", "one-zzzz/fortnite-bot")
RAPIDAPI_KEY       = os.getenv("RAPIDAPI_KEY")
TWITTER_USER_ID    = "1181729392755707904"
TWITTER_USERNAME   = "FortniteStatus"
RAPIDAPI_HOST      = "twitter241.p.rapidapi.com"
SEEN_IDS_PATH      = "seen_ids.json"

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

def send_telegram(tweet):
    is_reply  = tweet["text"].startswith("@")
    label     = "💬 Reply" if is_reply else "📢 Tweet"
    tweet_url = f"https://x.com/{TWITTER_USERNAME}/status/{tweet['id']}"
    msg = f"{label} from @{TWITTER_USERNAME}\n\n{tweet['text']}\n\n🔗 {tweet_url}"
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    )
    print(f"[+] Sent: {tweet['text'][:80]}")

def fetch_tweets():
    headers = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": RAPIDAPI_HOST}
    tweets  = []

    for endpoint in ["user-tweets", "user-replies"]:
        try:
            url  = f"https://{RAPIDAPI_HOST}/{endpoint}?user={TWITTER_USER_ID}&count=20"
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                print(f"[!] {endpoint} error: {resp.status_code}")
                continue
            data         = resp.json()
            instructions = data.get("result", {}).get("timeline", {}).get("instructions", [])
            for instruction in instructions:
                for entry in instruction.get("entries", []):
                    # standard tweet
                    try:
                        r = entry["content"]["itemContent"]["tweet_results"]["result"]
                        if "tweet" in r:
                            r = r["tweet"]
                        lg = r["legacy"]
                        if not lg.get("full_text", "").startswith("RT @"):
                            tweets.append({"id": lg["id_str"], "text": lg["full_text"]})
                    except (KeyError, TypeError):
                        pass
                    # thread items
                    for item in entry.get("content", {}).get("items", []):
                        try:
                            r = item["item"]["itemContent"]["tweet_results"]["result"]
                            if "tweet" in r:
                                r = r["tweet"]
                            lg = r["legacy"]
                            if not lg.get("full_text", "").startswith("RT @"):
                                tweets.append({"id": lg["id_str"], "text": lg["full_text"]})
                        except (KeyError, TypeError):
                            pass
        except Exception as e:
            print(f"[!] {endpoint} exception: {e}")

    # deduplicate
    seen, unique = set(), []
    for t in tweets:
        if t["id"] not in seen:
            seen.add(t["id"])
            unique.append(t)
    print(f"[*] Fetched {len(unique)} total tweets/replies")
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
        for t in tweets:
            seen_ids.add(t["id"])
        save_seen_ids(seen_ids, sha)
        print(f"[*] First run — recorded {len(seen_ids)} IDs, won't send.")
        return

    new = [t for t in tweets if t["id"] not in seen_ids]
    if not new:
        print("[~] No new tweets.")
        return

    for t in reversed(new):
        send_telegram(t)
        seen_ids.add(t["id"])

    save_seen_ids(seen_ids, sha)
    print(f"[*] Sent {len(new)} new tweet(s).")

if __name__ == "__main__":
    main()
