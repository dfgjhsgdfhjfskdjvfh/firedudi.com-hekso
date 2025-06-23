import asyncio
import threading
import time
import logging
from flask import Flask

from telethon import TelegramClient, events
import requests
import re
import json
import os

# --- Config ---
api_id = 1747534
api_hash = '5a2684512006853f2e48aca9652d83ea'
bot_token = '7862725675:AAF4dXAm4vRO-Vhf-hQQO3Ms8g80zGgze_8'
output_channel_id = -1002318245173
session_name = "pump_input_account"
ref_link_prefix = "https://t.me/paris_trojanbot?start=r-choudhary-"  # for pump message
vip_link_fixed = "https://t.me/FireCallsVip"
CA_MAP_FILE = "ca_to_msg_ids.json"

input_channel_ids = [-1002380293749, -1002520621518]

# --- Mapping ---
def load_ca_mapping():
    if os.path.exists(CA_MAP_FILE):
        with open(CA_MAP_FILE, "r") as f:
            return json.load(f)
    return {}

def save_ca_mapping(mapping):
    with open(CA_MAP_FILE, "w") as f:
        json.dump(mapping, f)

# --- Parsers ---
def extract_contract_address(text):
    match = re.search(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}pump\b', text)
    return match.group(0) if match else None

def extract_name(text):
    lines = text.splitlines()
    return lines[0].strip() if lines else "Unknown"

def parse_pump_message(text):
    ca = extract_contract_address(text)
    name = extract_name(text)
    mcap = re.search(r'Cap:\s*([\d\.KMBkmb]+)', text)
    vol = re.search(r'Vol:\s*([\d\.KMBkmb]+)', text)
    dev = re.search(r'Dev:\s*✅', text)
    th = re.search(r'TH:\s*(\d+)', text)
    top10 = re.search(r'Top 10%:\s*([\d\.%]+)', text)
    dex_paid = re.search(r'Dex Paid:\s*(✅|❌)', text)

    return {
        "ca": ca,
        "name": name,
        "cap": mcap.group(1) if mcap else "N/A",
        "vol": vol.group(1) if vol else "N/A",
        "dev": "✅" if dev else "❌",
        "th": th.group(1) if th else "N/A",
        "top10": top10.group(1) if top10 else "N/A",
        "dex_paid": dex_paid.group(1) if dex_paid else "❌"
    }

def format_message(data):
    ref_link = f"{ref_link_prefix}{data['ca']}"
    return f"""🚀 𝗣𝘂𝗺𝗽 𝗔𝗹𝗲𝗿𝘁

┌ 📛 NAME: {data['name']}
├ 💰 Market Cap: {data['cap']}
├ 📊 Volume: {data['vol']}
├ 🧾 Dex Paid: {data['dex_paid']}
├ 👨‍💻 Dev sold : {data['dev']}
├ 🔺 TH: {data['th']} | Top 10%: {data['top10']}
├ 📋 CA: `{data['ca']}`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
└ 🔗 [Quick Buy]({ref_link})"""

# --- Flask keep-alive ---
app = Flask(__name__)

@app.route('/')
def home():
    return "I am alive"

def run_flask():
    try:
        app.run(host='0.0.0.0', port=8085)
    except Exception as e:
        logging.error(f"Error in Flask server: {e}")

def keep_alive():
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()

# --- Telethon bot logic ---
client = TelegramClient(session_name, api_id, api_hash)

@client.on(events.NewMessage(chats=input_channel_ids))
async def handle_message(event):
    text = event.raw_text

    if "pump" in text.lower():
        start_time = time.perf_counter()
        ca = extract_contract_address(text)
        if ca:
            print(f"\n🚨 Pump Detected @ {time.strftime('%X')}")
            print(f"CA Found: {ca}")
            data = parse_pump_message(text)
            print(f"Parsed Data: {data}")
            msg = format_message(data)

            try:
                res = requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    data={
                        "chat_id": output_channel_id,
                        "text": msg,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": True
                    }
                )
                if res.status_code == 200:
                    msg_id = res.json().get("result", {}).get("message_id")
                    print(f"✅ Sent to Channel (msg_id={msg_id})")

                    ca_map = load_ca_mapping()
                    if ca not in ca_map:
                        ca_map[ca] = []
                    ca_map[ca].append((output_channel_id, msg_id))
                    save_ca_mapping(ca_map)
                else:
                    print("❌ Failed to send message:", res.text)
            except Exception as e:
                print("❌ Error sending message:", e)

            end_time = time.perf_counter()
            print(f"⚡ Time Taken: {round(end_time - start_time, 3)}s")

    if re.search(r'(🌕|🌙|📈|🎉)?\s?\d+(\.\d+)?x', text, re.IGNORECASE) and event.is_reply:
        try:
            reply = await event.get_reply_message()
            if reply:
                orig_text = reply.raw_text
                ca_match = re.search(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}pump\b', orig_text)
                if ca_match:
                    ca = ca_match.group(0)
                    print(f"🔗 Matched CA from replied message: {ca}")
                    ca_map = load_ca_mapping()
                    if ca in ca_map:
                        base_perf = re.search(r'(🌕|🌙|📈|🎉)?\s?\d+(\.\d+)?x', text)
                        extra_perf = re.search(r'\(\s*[\d\.]+x\s*from\s*(VIP|vip)\s*\)', text, re.IGNORECASE)

                        perf_reply = base_perf.group(0).strip() if base_perf else ""
                        if extra_perf:
                            vip_part = extra_perf.group(0).strip()
                            vip_link = "[VIP](https://t.me/FireXCalls/2)"
                            vip_formatted = re.sub(r'\bVIP\b', vip_link, vip_part, flags=re.IGNORECASE)
                            perf_reply += f"{vip_formatted}"

                        print(f"📈 Final formatted reply: {perf_reply}")

                        for chat_id, msg_id in ca_map[ca]:
                            print(f"↪️ Replying to msg {msg_id} in {chat_id}")
                            try:
                                requests.post(
                                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                                    data={
                                        "chat_id": chat_id,
                                        "text": perf_reply,
                                        "reply_to_message_id": msg_id,
                                        "parse_mode": "Markdown",
                                        "disable_web_page_preview": True
                                    }
                                )
                            except Exception as e:
                                print("❌ Failed to send performance reply:", e)
        except Exception as e:
            print("❌ Error in performance detection:", e)

# --- Start everything ---
def start_telethon():
    async def main():
        await client.start()
        print("🔥 Bot is live and ultra-fast now...")
        await client.run_until_disconnected()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())

if __name__ == "__main__":
    keep_alive()
    telethon_thread = threading.Thread(target=start_telethon)
    telethon_thread.start()
