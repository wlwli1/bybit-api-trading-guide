"""Fetch one public Bybit V5 ticker without credentials or order requests."""

import argparse
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class TickerError(Exception):
    """A request failed or returned an unusable ticker."""


def fetch_ticker(market="spot", testnet=False, timeout=10):
    """Return the BTCUSDT ticker from a single unauthenticated GET request."""
    if market not in ("spot", "linear"):
        raise TickerError("Market must be spot or linear.")
    base = "https://api-testnet.bybit.com" if testnet else "https://api.bybit.com"
    query = urlencode({"category": market, "symbol": "BTCUSDT"})
    request = Request(
        f"{base}/v5/market/tickers?{query}",
        headers={"Accept": "application/json", "User-Agent": "CoinPop-Market-Data-Example/1.0"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise TickerError(
            f"HTTP {exc.code}. Check official availability and rate-limit guidance; "
            "do not bypass access restrictions."
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise TickerError("Network request failed or timed out.") from exc
    except (ValueError, UnicodeError) as exc:
        raise TickerError("The API did not return valid JSON.") from exc

    if not isinstance(payload, dict):
        raise TickerError("Unexpected API response structure.")
    if type(payload.get("retCode")) is not int:
        raise TickerError("The API response is missing a valid retCode.")
    if payload["retCode"] != 0:
        raise TickerError(f"Bybit returned retCode {payload['retCode']}. Check the official error codes.")

    result = payload.get("result")
    if not isinstance(result, dict) or result.get("category") != market:
        raise TickerError("The response does not match the requested market.")
    entries = result.get("list")
    if not isinstance(entries, list):
        raise TickerError("The ticker list is missing.")
    ticker = next(
        (entry for entry in entries if isinstance(entry, dict) and entry.get("symbol") == "BTCUSDT"),
        None,
    )
    if ticker is None or not isinstance(ticker.get("lastPrice"), str):
        raise TickerError("No usable BTCUSDT ticker was returned.")
    try:
        price = Decimal(ticker["lastPrice"])
    except InvalidOperation as exc:
        raise TickerError("The returned price is not numeric.") from exc
    if not price.is_finite() or price <= 0:
        raise TickerError("The returned price is not a finite positive number.")
    return {"market": market, "symbol": "BTCUSDT", "last_price": ticker["lastPrice"], "time": payload.get("time")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", choices=("spot", "linear"), default="spot")
    parser.add_argument("--testnet", action="store_true", help="Use the separate Bybit test environment")
    args = parser.parse_args(argv)
    try:
        ticker = fetch_ticker(args.market, args.testnet)
    except TickerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    environment = "testnet" if args.testnet else "mainnet"
    print(f"Market: {ticker['market']} ({environment})")
    print(f"Symbol: {ticker['symbol']}")
    print(f"Last traded price: {ticker['last_price']} USDT per BTC")
    timestamp = ticker["time"]
    if type(timestamp) is int and timestamp > 0:
        try:
            response_time = datetime.fromtimestamp(timestamp / 1000, timezone.utc)
            print(f"API response time (UTC): {response_time.isoformat()}")
        except (ValueError, OverflowError, OSError):
            print("API response timestamp could not be formatted.")
    print("Market snapshot only; not an executable quote or trading signal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
