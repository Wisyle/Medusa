# ws_client.py

import json
import hmac
import time
import base64
import asyncio
import hashlib
import websockets

WS_URL = "wss://ws.bitget.com/mix/v1/stream"


def generate_login_args(api_key, api_secret, passphrase):
    timestamp = str(int(time.time() * 1000))
    msg = timestamp + "GET" + "/user/verify"
    sign = base64.b64encode(hmac.new(
        api_secret.encode(), msg.encode(), hashlib.sha256
    ).digest()).decode()
    return {
        "op": "login",
        "args": [{
            "apiKey": api_key,
            "passphrase": passphrase,
            "timestamp": timestamp,
            "sign": sign
        }]
    }


async def _websocket_loop(dispatcher, config):
    pong_time = time.time()

    async with websockets.connect(WS_URL, ping_interval=None) as ws:
        print("[WS] kapcsolat létrejött")

        creds = config["bitget"]
        login_msg = generate_login_args(creds["apiKey"], creds["apiSecret"], creds["passphrase"])
        print(f"[WS] küldés: login → {login_msg}")
        await ws.send(json.dumps(login_msg))
        await asyncio.sleep(1)

        for name, bot_cfg in config["bots"].items():
            if not bot_cfg.get("enabled"):
                continue
            symbol = bot_cfg["symbol"].upper()
            product_type = bot_cfg["productType"].upper()

            inst_type = "mc" if product_type == "USDT-FUTURES" else "umcbl"
            sub_msgs = [
                {"instType": inst_type, "channel": "ticker", "instId": symbol},
                {"instType": "umcbl", "channel": "orders", "instId": "default"},
                {"instType": "umcbl", "channel": "positions", "instId": "default"},
            ]
            subscribe_msg = {"op": "subscribe", "args": sub_msgs}
            print(f"[WS] küldés: subscribe → {json.dumps(subscribe_msg)}")
            await ws.send(json.dumps(subscribe_msg))

        async def ping_loop():
            nonlocal pong_time
            while True:
                await asyncio.sleep(30)
                try:
                    await ws.send("ping")
                except:
                    raise Exception("[WS] Ping küldés sikertelen")
                if time.time() - pong_time > 60:
                    raise Exception("[WS] Nem érkezett pong 60 mp-en belül → reconnect")

        asyncio.create_task(ping_loop())

        async for msg in ws:
            if msg == "pong":
                pong_time = time.time()
                continue
            try:
                data = json.loads(msg)
                if "event" in data:
                    print(f"[WS] EVENT ACK {data['event']} → {data.get('arg', '')}")
                    continue
                dispatcher.dispatch(data)
            except Exception as e:
                print(f"[WS] HIBA: {e}")
                raise


async def run_ws_loop(dispatcher, config):
    while True:
        try:
            await _websocket_loop(dispatcher, config)
        except Exception as e:
            print(f"[WS] kapcsolat megszakadt: {e}")
            print("[WS] újracsatlakozás 3 mp múlva...")
            await asyncio.sleep(3)
