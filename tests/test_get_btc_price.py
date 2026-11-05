"""Check the public ticker example using simulated network responses."""

import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError


script_path = Path(__file__).resolve().parents[1] / "examples" / "get_btc_price.py"
spec = importlib.util.spec_from_file_location("get_btc_price", script_path)
example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(example)


def response_payload(**changes):
    payload = {"retCode": 0, "result": {"category": "spot", "list": [{"symbol": "BTCUSDT", "lastPrice": "100.25"}]}, "time": 1700000000000}
    payload.update(changes)
    return payload


class PublicTickerTests(unittest.TestCase):
    def simulated_response(self, payload):
        return io.BytesIO(json.dumps(payload).encode("utf-8"))

    def test_public_get_request_has_no_credentials(self):
        with patch.object(example, "urlopen", return_value=self.simulated_response(response_payload())) as mock_open:
            result = example.fetch_ticker()
        self.assertEqual(result["last_price"], "100.25")
        request = mock_open.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT")
        self.assertEqual(request.get_method(), "GET")
        self.assertFalse(any("key" in key.lower() or "sign" in key.lower() for key in request.headers))
        self.assertEqual(mock_open.call_args.kwargs["timeout"], 10)

    def test_testnet_linear_request(self):
        payload = response_payload(result={"category": "linear", "list": [{"symbol": "BTCUSDT", "lastPrice": "101"}]})
        with patch.object(example, "urlopen", return_value=self.simulated_response(payload)) as mock_open:
            self.assertEqual(example.fetch_ticker("linear", True)["market"], "linear")
        self.assertTrue(mock_open.call_args.args[0].full_url.startswith("https://api-testnet.bybit.com/"))

    def test_api_error_is_not_reported_as_a_price(self):
        with patch.object(example, "urlopen", return_value=self.simulated_response(response_payload(retCode=10001))):
            with self.assertRaisesRegex(example.TickerError, "retCode 10001"):
                example.fetch_ticker()

    def test_empty_wrong_market_and_nonfinite_values_fail(self):
        invalid_results = [
            {"category": "spot", "list": []},
            {"category": "linear", "list": [{"symbol": "BTCUSDT", "lastPrice": "1"}]},
            {"category": "spot", "list": [{"symbol": "BTCUSDT", "lastPrice": "NaN"}]},
            {"category": "spot", "list": [{"symbol": "BTCUSDT", "lastPrice": "0"}]},
        ]
        for result in invalid_results:
            with self.subTest(result=result):
                with patch.object(example, "urlopen", return_value=self.simulated_response(response_payload(result=result))):
                    with self.assertRaises(example.TickerError):
                        example.fetch_ticker()

    def test_invalid_json_and_timeout_fail(self):
        with patch.object(example, "urlopen", return_value=io.BytesIO(b"not json")):
            with self.assertRaisesRegex(example.TickerError, "valid JSON"):
                example.fetch_ticker()
        with patch.object(example, "urlopen", side_effect=TimeoutError):
            with self.assertRaisesRegex(example.TickerError, "timed out"):
                example.fetch_ticker()

    def test_http_403_returns_clear_error_without_retry(self):
        with patch.object(example, "urlopen", side_effect=HTTPError("https://api.bybit.com", 403, "Forbidden", {}, None)) as mock_open:
            with self.assertRaisesRegex(example.TickerError, "HTTP 403"):
                example.fetch_ticker()
        mock_open.assert_called_once()


if __name__ == "__main__":
    unittest.main()
