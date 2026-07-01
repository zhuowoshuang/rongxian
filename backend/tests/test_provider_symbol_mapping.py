from app.services.provider_symbols import normalize_stock_symbol_for_provider


def test_normalize_symbol_for_major_providers():
    assert normalize_stock_symbol_for_provider("600519", "tencent") == "sh600519"
    assert normalize_stock_symbol_for_provider("000001", "tencent") == "sz000001"
    assert normalize_stock_symbol_for_provider("600519", "eastmoney") == "1.600519"
    assert normalize_stock_symbol_for_provider("000001", "eastmoney") == "0.000001"
    assert normalize_stock_symbol_for_provider("600519", "baostock") == "sh.600519"
    assert normalize_stock_symbol_for_provider("000001", "baostock") == "sz.000001"
    assert normalize_stock_symbol_for_provider("600519", "xueqiu") == "SH600519"
    assert normalize_stock_symbol_for_provider("000001", "xueqiu") == "SZ000001"
    assert normalize_stock_symbol_for_provider("600519", "yahoo") == "600519.SS"
    assert normalize_stock_symbol_for_provider("000001", "yahoo") == "000001.SZ"


def test_normalize_symbol_for_hk():
    assert normalize_stock_symbol_for_provider("00700", "tencent") == "hk00700"
    assert normalize_stock_symbol_for_provider("00700", "eastmoney") == "116.00700"
    assert normalize_stock_symbol_for_provider("00700", "xueqiu") == "00700"
    assert normalize_stock_symbol_for_provider("00700", "yahoo") == "0700.HK"
