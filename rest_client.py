# rest_client.py
import time
import hmac
import hashlib
import base64
import json
import requests
import threading
import queue
from urllib.parse import urlencode

class BitgetRESTClient:
    _instance = None
    _lock = threading.Lock()

    BASE_URL = "https://api.bitget.com"

    def __new__(cls, api_key, api_secret, passphrase):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init(api_key, api_secret, passphrase)
            return cls._instance

    def _init(self, api_key, api_secret, passphrase):
        self.api_key = api_key
        self.api_secret = api_secret.encode()
        self.passphrase = passphrase
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "locale": "en-US"
        })
        self.task_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def _get_timestamp(self):
        return str(int(time.time() * 1000))

    def _sign(self, timestamp, method, request_path, body=""):
        msg = f"{timestamp}{method.upper()}{request_path}{body}"
        mac = hmac.new(self.api_secret, msg.encode(), hashlib.sha256)
        return base64.b64encode(mac.digest()).decode()

    def _headers(self, method, path, params=None, body=""):
        timestamp = self._get_timestamp()
        query = f"?{urlencode(params)}" if params else ""
        sign = self._sign(timestamp, method, path + query, body)
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": sign,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
            "locale": "en-US"
        }

    def _request(self, method, path, params=None, data=None):
        url = self.BASE_URL + path
        body = json.dumps(data) if data else ""

        # KÜLDÖTT REQUEST LOG
        if method.upper() == "POST":
            print(f"[REST REQUEST] {method} {url}")
            print(f"[REST BODY] {body}")

        headers = self._headers(method, path, params, body)
        try:
            resp = self.session.request(method, url, headers=headers, params=params, data=body, timeout=10)
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                json_resp = resp.json()
                if resp.status_code >= 400 or json_resp.get("code") != "00000":
                    print(f"[REST ERROR] HTTP {resp.status_code}: {json.dumps(json_resp, indent=2)}")
                return json_resp
            else:
                resp.raise_for_status()
                return {"raw": resp.text}
        except requests.exceptions.RequestException as e:
            try:
                error_json = resp.json()
                print(f"[REST ERROR] Exception: {str(e)} - {json.dumps(error_json, indent=2)}")
            except Exception:
                print(f"[REST ERROR] Exception: {str(e)} - No JSON in response")
            return None

    def _worker_loop(self):
        while True:
            task = self.task_queue.get()
            if task is None:
                break
            try:
                self._handle_task(task)
            except Exception as e:
                print(f"[TASK ERROR] {e}")
            self.task_queue.task_done()

    def _handle_task(self, task):
        action = task.get("action")
        data = task.get("data", {})
        if action == "place_order":
            result = self.place_order(data)
        elif action == "cancel_order":
            result = self.cancel_order(data)
        elif action == "get_positions":
            result = self.get_positions(data["productType"], data["marginCoin"])
        elif action == "get_account":
            result = self.get_account(data["symbol"], data["productType"], data["marginCoin"])
        elif action == "get_pending_orders":
            result = self.get_pending_orders(data["productType"], data.get("symbol"))
        elif action == "flash_close_position":
            result = self.flash_close_position(data)
        elif action == "transfer_to_spot":
            result = self.transfer_futures_to_spot(
                amount=float(data["amount"]),
                coin=data.get("coin", "USDT"),
                from_type=data.get("fromType", "usdt_futures"),
                to_type=data.get("toType", "spot"),
                client_oid=data.get("clientOid")
            )
        elif action == "change_margin_mode":
            result = self.change_margin_mode(
                symbol=data["symbol"],
                product_type=data["productType"],
                margin_coin=data["marginCoin"],
                margin_mode=data["marginMode"]
            )
        elif action == "set_leverage":
            result = self.set_leverage(
                symbol=data["symbol"],
                product_type=data["productType"],
                margin_coin=data["marginCoin"],
                leverage=data["leverage"],
                hold_side=data.get("holdSide")
            )
        elif action == "set_auto_margin":
            result = self.set_auto_margin(
                symbol=data["symbol"],
                margin_coin=data["marginCoin"],
                hold_side=data["holdSide"],
                enabled=data["enabled"]
            )
        elif action == "set_position_mode":
            result = self.set_position_mode(
                symbol=data["symbol"],
                product_type=data["productType"],
                margin_coin=data["marginCoin"],
                hold_mode=data["holdMode"]
            )
        else:
            print(f"[UNKNOWN TASK] {action}")
            return
        if task.get("callback"):
            task["callback"](result)

    def submit_rest_task(self, action, data, callback=None):
        self.task_queue.put({"action": action, "data": data, "callback": callback})

    # direct methods
    def place_order(self, order_data):
        """
        Teljes értékű Bitget order placement.
        Elvárt mezők:
          - symbol
          - productType
          - marginMode
          - marginCoin
          - size (str)
          - price (str) → csak limitnél
          - side ("buy"/"sell")
          - tradeSide ("open"/"close")
          - orderType ("limit"/"market")
          - force ("gtc"/"ioc"/"fok")
          - clientOid (str)
        """
        required_fields = [
            "symbol", "productType", "marginMode", "marginCoin", "size",
            "side", "tradeSide", "orderType", "force", "clientOid"
        ]

        for field in required_fields:
            if field not in order_data:
                raise ValueError(f"Missing required order field: {field}")

        # Csak akkor legyen kötelező a price mező, ha nem market order
        if order_data["orderType"].lower() != "market":
            if "price" not in order_data:
                raise ValueError("Missing required order field: price")

        # Market ordernél ne küldjünk price mezőt
        if order_data["orderType"].lower() == "market":
            order_data = {k: v for k, v in order_data.items() if k != "price"}

        return self._request("POST", "/api/v2/mix/order/place-order", data=order_data)


    def place_bulk_orders(self, symbol: str, product_type: str, margin_coin: str, margin_mode: str, order_list: list[dict]):
        path = "/api/v2/mix/order/batch-place-order"
        max_chunk = 50
        responses = []

        for i in range(0, len(order_list), max_chunk):
            chunk = order_list[i:i+max_chunk]
            data = {
                "symbol": symbol,
                "productType": product_type,
                "marginCoin": margin_coin,
                "marginMode": margin_mode,
                "orderList": chunk
            }
            resp = self._request("POST", path, data=data)
            responses.append(resp)
            time.sleep(0.2)  # minimális várakozás chunkek közt

        return responses





    def cancel_order(self, cancel_data):
        """
        Cancel order a clientOid alapján.
        Kötelező mezők:
          - symbol
          - productType
          - marginCoin
          - clientOid
        """
        required_fields = ["symbol", "productType", "marginCoin", "clientOid"]
        for field in required_fields:
            if field not in cancel_data:
                raise ValueError(f"Missing cancel_order field: {field}")
        return self._request("POST", "/api/v2/mix/order/cancel-order", data=cancel_data)


    def get_positions(self, product_type, margin_coin):
        return self._request("GET", "/api/v2/mix/position/all-position", params={
            "productType": product_type,
            "marginCoin": margin_coin
        })

    def set_auto_margin(self, symbol: str, margin_coin: str, hold_side: str, enabled: bool = True):
        """
        Enable or disable auto margin for isolated position.
        """
        payload = {
            "symbol": symbol,
            "autoMargin": "on" if enabled else "off",
            "marginCoin": margin_coin.upper(),
            "holdSide": hold_side
        }

        #log kimenet kikapcsolva
        #print("[REST REQUEST] POST https://api.bitget.com/api/v2/mix/account/set-auto-margin")
        #print("[REST BODY]", json.dumps(payload))

        return self._request(
            method="POST",
            path="/api/v2/mix/account/set-auto-margin",
            data=payload  # használjuk a helyes kulcsot: data
        )


    def get_account(self, symbol, product_type, margin_coin):
        symbol = symbol.lower()
        return self._request("GET", "/api/v2/mix/account/account", params={
            "symbol": symbol,
            "productType": product_type,
            "marginCoin": margin_coin
        })

    def get_pending_orders(self, product_type, symbol=None):
        params = {"productType": product_type}
        if symbol:
            params["symbol"] = symbol.lower()
        return self._request("GET", "/api/v2/mix/order/orders-pending", params=params)


    def get_all_pending_orders(self, product_type, symbol=None):
        """
        Az összes élő (live) pending order lekérdezése, lapozással.
        Csak a 'live' státuszú (teljesen nyitott) megbízásokat kérdezi le.
        """
        all_orders = []
        id_less_than = None

        while True:
            params = {"productType": product_type, "status": "live"}
            if symbol:
                params["symbol"] = symbol.lower()
            if id_less_than:
                params["idLessThan"] = id_less_than

            resp = self._request("GET", "/api/v2/mix/order/orders-pending", params=params)
            if not resp or resp.get("code") != "00000":
                break

            orders = resp.get("data", {}).get("entrustedList", [])
            all_orders.extend(orders)

            if len(orders) < 100:
                break

            id_less_than = resp.get("data", {}).get("endId")
            if not id_less_than:
                break

        return all_orders



    def flash_close_position(self, close_data):
        """
        Azonnali pozíciózárás (market close).
        Kötelező mezők:
          - symbol (opcionális hedge módban, de mi adjuk)
          - productType (pl. USDT-FUTURES)
          - holdSide: "long" vagy "short"
        """
        required_fields = ["productType", "holdSide"]
        for field in required_fields:
            if field not in close_data:
                raise ValueError(f"Missing flash_close_position field: {field}")
        return self._request("POST", "/api/v2/mix/order/close-positions", data=close_data)


    def cancel_all_orders(self, symbol: str, product_type: str, margin_coin: str):
        """
        Az adott symbol-hoz tartozó összes aktív order törlése (limit: 100+ is működik).
        """
        body = {
            "symbol": symbol,
            "productType": product_type,
            "marginCoin": margin_coin.upper()
        }
        return self._request("POST", "/api/v2/mix/order/cancel-all-orders", data=body)

    def transfer_futures_to_spot(self, amount: float, coin: str = "USDT", from_type: str = "usdt_futures",
                                 to_type: str = "spot", client_oid: str = None):
        """
        Transfer funds between accounts (e.g. from futures to spot).
        Example: USDT from USDT-M futures to spot.
        """
        path = "/api/v2/spot/wallet/transfer"
        payload = {
            "fromType": from_type,
            "toType": to_type,
            "amount": str(amount),
            "coin": coin
        }
        if client_oid:
            payload["clientOid"] = client_oid

        return self._request("POST", path, data=payload)

    def get_contract_config(self, product_type: str, symbol: str):
        """
        Visszaadja a szimbólumhoz tartozó kereskedési konfigurációs adatokat.
        Keresés az összes elérhető szerződés között.
        """
        path = "/api/v2/mix/market/contracts"
        params = {"productType": product_type}
        response = self._request("GET", path, params=params)
        if not response or response.get("code") != "00000":
            raise Exception("Failed to fetch contract config")

        for item in response.get("data", []):
            if item.get("symbol", "").upper() == symbol.upper():
                return item

        raise ValueError(f"Symbol '{symbol}' not found in contract config list")

    def change_leverage(self, symbol: str, product_type: str, margin_coin: str, leverage: int, hold_side: str = None):
        body = {
            "symbol": symbol,
            "productType": product_type,
            "marginCoin": margin_coin,
            "leverage": str(leverage)
        }
        if hold_side:
            body["holdSide"] = hold_side
        return self._signed_post("/api/v2/mix/account/set-leverage", body)

    def change_margin_mode(self, symbol: str, product_type: str, margin_coin: str, margin_mode: str):
        body = {
            "symbol": symbol,
            "productType": product_type,
            "marginCoin": margin_coin,
            "marginMode": margin_mode
        }
        return self._signed_post("/api/v2/mix/account/set-margin-mode", body)

    def change_position_mode(self, product_type: str, pos_mode: str):
        body = {
            "productType": product_type,
            "posMode": pos_mode
        }
        return self._signed_post("/api/v2/mix/account/set-position-mode", body)

    def _signed_post(self, path, body):
        """
        Aláírt POST kérés a védett Bitget endpointokhoz.
        """
        return self._request("POST", path, data=body)



# ---- direct run for test ----
if __name__ == "__main__":
    import sys
    from pathlib import Path

    config_path = Path(__file__).resolve().parent / "config.json"
    with open(config_path) as f:
        cfg = json.load(f)

    creds = cfg["bitget"]
    client = BitgetRESTClient(creds["apiKey"], creds["apiSecret"], creds["passphrase"])

    def print_result(result):
        print(json.dumps(result, indent=2))

    client.submit_rest_task("get_account", {
        "symbol": "btcusdt",
        "productType": "USDT-FUTURES",
        "marginCoin": "USDT"
    }, callback=print_result)

    client.task_queue.join()
