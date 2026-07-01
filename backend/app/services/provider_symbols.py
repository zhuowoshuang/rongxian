from __future__ import annotations


def infer_exchange_from_symbol(stock_code: str, exchange: str | None = None) -> str | None:
    if exchange:
        return exchange.upper()
    if not stock_code:
        return None
    if len(stock_code) == 5 and stock_code.isdigit():
        return "HK"
    if stock_code.startswith(("6", "5", "9")):
        return "SH"
    if stock_code.startswith(("0", "1", "2", "3")):
        return "SZ"
    return None


def normalize_stock_symbol_for_provider(
    stock_code: str,
    provider: str,
    market: str | None = None,
    exchange: str | None = None,
) -> str:
    code = (stock_code or "").strip().upper()
    provider_key = (provider or "").strip().lower()
    inferred_exchange = infer_exchange_from_symbol(code, exchange)
    inferred_market = (market or ("HK" if inferred_exchange == "HK" else "A_SHARE")).upper()

    if provider_key in {"tencent", "eastmoney_tencent"}:
        if inferred_market == "HK":
            return f"hk{code}"
        return f"{'sh' if inferred_exchange == 'SH' else 'sz'}{code}"

    if provider_key in {"eastmoney", "eastmoney_secid"}:
        if inferred_market == "HK":
            return f"116.{code}"
        return f"{'1' if inferred_exchange == 'SH' else '0'}.{code}"

    if provider_key == "baostock":
        if inferred_market == "HK":
            return code
        return f"{'sh' if inferred_exchange == 'SH' else 'sz'}.{code}"

    if provider_key == "xueqiu":
        if inferred_market == "HK":
            return code
        return f"{'SH' if inferred_exchange == 'SH' else 'SZ'}{code}"

    if provider_key == "yahoo":
        if inferred_market == "HK":
            return f"{int(code):04d}.HK"
        return f"{code}.SS" if inferred_exchange == "SH" else f"{code}.SZ"

    return code
