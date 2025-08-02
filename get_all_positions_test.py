# get_all_positions_test.py
import json
from rest_client import BitgetRESTClient

# config betöltés
with open("config.json") as f:
    cfg = json.load(f)

# hitelesítési adatok
creds = cfg["bitget"]
client = BitgetRESTClient(creds["apiKey"], creds["apiSecret"], creds["passphrase"])

# tesztelt bot neve
bot = cfg["bots"]["grid1"]
product_type = bot["productType"]
margin_coin = bot["marginCoin"]

# callback
def cb(resp):
    print("GET POSITIONS VÁLASZ:")
    print(json.dumps(resp, indent=2))

# kérés elküldése
client.submit_rest_task("get_positions", {
    "productType": product_type,
    "marginCoin": margin_coin
}, callback=cb)

client.task_queue.join()
