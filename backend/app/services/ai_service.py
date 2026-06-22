"""
AI 分析服务 — 基于 DeepSeek 大模型生成投资洞察
使用线程池执行同步 HTTP 调用，避免阻塞 FastAPI 事件循环
"""
import json
import logging
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

# 单线程池，限制并发 AI 调用数
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ai-service")

logger = logging.getLogger(__name__)


def _get_deepseek_config(db) -> Optional[dict]:
    """从数据库读取 DeepSeek 配置"""
    from app.models.api_config import ApiConfig
    from app.core.config import decrypt_api_key

    config = db.query(ApiConfig).filter(ApiConfig.provider == "deepseek").first()
    if not config or not config.is_enabled or not config.api_key:
        return None

    params = {"model": "deepseek-chat", "temperature": 0.7, "max_tokens": 2000}
    if config.config_json:
        try:
            params.update(json.loads(config.config_json))
        except json.JSONDecodeError:
            pass

    return {
        "api_key": decrypt_api_key(config.api_key),
        "base_url": (config.base_url or "https://api.deepseek.com").rstrip("/"),
        **params,
    }


def _call_deepseek(api_key: str, base_url: str, model: str, prompt: str,
                    temperature: float = 0.7, max_tokens: int = 2000) -> Optional[str]:
    """调用 DeepSeek Chat API"""
    url = f"{base_url}/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一位拥有20年经验的A股/港股投资分析师，擅长基本面分析、技术分析和风险管理。请用专业但易懂的中文回答，输出 Markdown 格式。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"DeepSeek API 调用失败: {e}")
        return None


def generate_ai_market_insight(db, market_data: dict) -> str:
    """生成 AI 市场洞察（用于每日报告）"""
    cfg = _get_deepseek_config(db)
    if not cfg:
        return ""

    prompt = f"""请基于以下市场数据，给出专业的投资洞察分析（300-500字）：

## 市场状态
- 市场情绪：{market_data.get('market_status', '未知')}
- 买入/加仓信号：{market_data.get('buy_add', 0)} 个
- 减仓/卖出信号：{market_data.get('reduce_sell', 0)} 个

## Top 买入信号
{json.dumps(market_data.get('top_buys', []), ensure_ascii=False, indent=2)}

## 风险预警
{json.dumps(market_data.get('risk_items', []), ensure_ascii=False, indent=2)}

请从以下角度分析：
1. **市场情绪判断**：当前市场处于什么阶段
2. **机会与风险**：重点关注哪些板块/个股，需要规避什么
3. **仓位建议**：当前应采取什么策略
4. **关键观察点**：接下来需要关注什么"""

    result = _call_deepseek(cfg["api_key"], cfg["base_url"], cfg["model"], prompt, cfg["temperature"], cfg["max_tokens"])
    return result or ""


def generate_ai_stock_analysis(db, stock_data: dict) -> str:
    """生成 AI 个股分析（用于个股报告）"""
    cfg = _get_deepseek_config(db)
    if not cfg:
        return ""

    prompt = f"""请基于以下个股数据，给出深度投资分析（400-600字）：

## 基本信息
- 股票：{stock_data.get('name', '')}（{stock_data.get('symbol', '')}）
- 市场：{stock_data.get('market', '')} | 行业：{stock_data.get('industry', '')}

## 五维评分
- 总分：{stock_data.get('total_score', 0)}/100 | 评级：{stock_data.get('rating', '')}
- 质量：{stock_data.get('quality_score', 0)}/30 | 估值：{stock_data.get('valuation_score', 0)}/20
- 成长：{stock_data.get('growth_score', 0)}/20 | 趋势：{stock_data.get('trend_score', 0)}/20
- 风险：{stock_data.get('risk_score', 0)}/10

## 行情数据
- 收盘价：{stock_data.get('close', 'N/A')} | PE：{stock_data.get('pe', 'N/A')} | PB：{stock_data.get('pb', 'N/A')}
- 市值：{stock_data.get('market_cap', 'N/A')}亿 | 股息率：{stock_data.get('dividend_yield', 'N/A')}%

## 技术指标
- RSI14：{stock_data.get('rsi14', 'N/A')} | MACD：{stock_data.get('macd', 'N/A')}
- MA20：{stock_data.get('ma20', 'N/A')} | MA60：{stock_data.get('ma60', 'N/A')}

## 信号
- 类型：{stock_data.get('signal_type', 'N/A')} | 强度：{stock_data.get('signal_strength', 'N/A')}
- 入场价：{stock_data.get('entry_price', 'N/A')} | 止损价：{stock_data.get('stop_loss', 'N/A')}

## 财务摘要
{json.dumps(stock_data.get('financials', []), ensure_ascii=False, indent=2)}

请从以下角度分析：
1. **核心优势与风险**：这家公司最大的看点和隐患是什么
2. **估值合理性**：当前价格是否值得买入
3. **技术面研判**：趋势如何，支撑位和压力位在哪
4. **操作建议**：具体的买入/持有/卖出策略"""

    result = _call_deepseek(cfg["api_key"], cfg["base_url"], cfg["model"], prompt, cfg["temperature"], cfg["max_tokens"])
    return result or ""


def generate_ai_style_insight(db, style_data: dict) -> str:
    """生成 AI 风格策略洞察（用于风格报告）"""
    cfg = _get_deepseek_config(db)
    if not cfg:
        return ""

    prompt = f"""请基于以下{style_data.get('style_name', '')}投资策略数据，给出专业分析（300-500字）：

## 策略概况
- 风格：{style_data.get('style_name', '')} — {style_data.get('style_desc', '')}
- 精选标的：{style_data.get('pick_count', 0)} 只
- 行业分布：{json.dumps(style_data.get('industry_dist', {}), ensure_ascii=False)}

## Top 标的
{json.dumps(style_data.get('top_picks', [])[:5], ensure_ascii=False, indent=2)}

## 仓位参数
- 单只上限：{style_data.get('max_position', 'N/A')}%
- 总仓位：{style_data.get('total_position', 'N/A')}%

请分析：
1. **策略适配性**：当前市场环境是否适合该策略
2. **标的选择评价**：选出的标的质量如何
3. **风险提示**：该策略在当前环境下的主要风险
4. **优化建议**：如何改进策略执行"""

    result = _call_deepseek(cfg["api_key"], cfg["base_url"], cfg["model"], prompt, cfg["temperature"], cfg["max_tokens"])
    return result or ""
