import json
from rest_client import BitgetRESTClient

# Config betöltése
with open("config.json") as f:
    config = json.load(f)

creds = config["bitget"]

# REST kliens példányosítása
client = BitgetRESTClient(
    creds["apiKey"],
    creds["apiSecret"],
    creds["passphrase"]
)

# Teszt paraméterek (első engedélyezett grid alapján)
for name, bot_cfg in config["bots"].items():
    if bot_cfg.get("enabled"):
        symbol = bot_cfg["symbol"]
        product_type = bot_cfg["productType"]
        margin_coin = bot_cfg["marginCoin"]
        break
else:
    raise Exception("Nincs engedélyezett grid a config.json fájlban")

# Callback függvény
def print_account(resp):
    print(f"[GET ACCOUNT] válasz:")
    print(json.dumps(resp, indent=2))

# REST hívás
client.submit_rest_task("get_account", {
    "symbol": symbol,
    "productType": product_type,
    "marginCoin": margin_coin
}, callback=print_account)

client.task_queue.join()
