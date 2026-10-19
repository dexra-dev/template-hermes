import httpx

from conftest import BONK, DEXRA, JUP, dexra_result, make_config
from dexra_trader import tools


def test_unresolved_placeholders_count_as_unset():
    cfg = tools.settings({"DRY_RUN": "${DRY_RUN}", "DEXRA_API_KEY": "${env:DEXRA_API_KEY}", "MAX_TRADE_SOL": "0.02"})
    assert cfg.dry_run_requested and not cfg.live
    assert cfg.dexra_api_key is None and cfg.max_trade_sol == 0.02


def test_check_token_calls_deep_check_with_key(mock):
    route = mock.get(f"{DEXRA}/token_deep_check").mock(
        return_value=httpx.Response(200, json=dexra_result("caution", ["top holders linked"]))
    )
    r = tools.check_token(BONK, make_config(DEXRA_API_KEY="dxr_test"))
    assert (r["verdict"], r["reasons"]) == ("caution", ["top holders linked"])
    req = route.calls.last.request
    assert req.url.params["mint"] == BONK and req.headers["authorization"] == "Bearer dxr_test"


def test_preflight_sends_side_and_amount(mock):
    route = mock.get(f"{DEXRA}/swap_preflight").mock(return_value=httpx.Response(200, json=dexra_result("ok")))
    assert tools.preflight(BONK, "buy", 0.01, make_config())["verdict"] == "ok"
    params = route.calls.last.request.url.params
    assert (params["mint"], params["side"], params["amount"]) == (BONK, "buy", "0.01")


def test_fresh_launches_drops_unset_filters(mock):
    route = mock.get(f"{DEXRA}/new_launches").mock(
        return_value=httpx.Response(200, json={"result": {"launches": [], "verdict": None}})
    )
    assert tools.fresh_launches(minutes=30, limit=5, config=make_config())["launches"] == []
    assert dict(route.calls.last.request.url.params) == {"minutes": "30", "limit": "5"}


def test_buy_blocked_on_avoid_never_quotes(mock):
    mock.get(f"{DEXRA}/token_deep_check").mock(
        return_value=httpx.Response(200, json=dexra_result("avoid", ["mint authority active"]))
    )
    mock.get(f"{DEXRA}/swap_preflight").mock(return_value=httpx.Response(200, json=dexra_result("ok")))
    order = mock.get(f"{JUP}/order")
    r = tools.buy(BONK, 0.01, make_config(JUPITER_API_KEY="jup"))
    assert r["status"] == "blocked" and "token_deep_check: mint authority active" in r["decision"]["reasons"]
    assert order.call_count == 0


def test_buy_without_dexra_key_fails_closed(mock):
    mock.get(f"{DEXRA}/token_deep_check").mock(return_value=httpx.Response(402, json={"error": "payment_required"}))
    mock.get(f"{DEXRA}/swap_preflight").mock(return_value=httpx.Response(402, json={"error": "payment_required"}))
    r = tools.buy(BONK, 0.01, make_config())
    assert r["status"] == "blocked" and "402" in r["message"]


def test_buy_reports_bad_settings_without_calls(mock, monkeypatch):
    monkeypatch.setenv("SLIPPAGE_BPS", "5000")
    r = tools.buy(BONK, 0.01)
    assert (r["status"], r["side"], r["input"]["mint"]) == ("error", "buy", tools.SOL_MINT)
    assert "SLIPPAGE_BPS" in r["message"]
    assert tools.sell(BONK, "100")["input"]["mint"] == BONK
    assert len(mock.calls) == 0


def test_sell_is_allowed_on_avoid_in_dry_run(mock):
    mock.get(f"{DEXRA}/describe_address").mock(
        return_value=httpx.Response(200, json={"result": {"stats": {"decimals": 5}}})
    )
    mock.get(f"{DEXRA}/swap_preflight").mock(return_value=httpx.Response(200, json=dexra_result("avoid")))
    r = tools.sell(BONK, 250000, make_config())
    assert (r["status"], r["decision"]["allowed"], r["decision"]["verdicts"]["preflight"]) == ("dry_run", True, "avoid")
