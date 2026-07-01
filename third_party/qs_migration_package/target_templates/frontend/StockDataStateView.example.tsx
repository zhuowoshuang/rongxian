/**
 * 清数智算前端 — 四种 DataStatus 渲染示例
 *
 * 展示如何根据 dataStatus 渲染不同的 UI 状态。
 * 此文件仅为示例模式，不绑定具体项目结构。
 */

import React from 'react';
import type { StockQuote, StockDataBundle } from './stockData';

// ==================== OK 状态 ====================
function QuoteCardOK({ quote }: { quote: StockQuote }) {
  return (
    <div className="quote-card">
      <div className="price">{quote.price}</div>
      <div className={`change ${quote.changePct && quote.changePct > 0 ? 'up' : 'down'}`}>
        {quote.changePct}%
      </div>
      <div className="source">实时行情</div>
    </div>
  );
}

// ==================== PARTIAL 状态 ====================
function QuoteCardPartial({ quote }: { quote: StockQuote }) {
  return (
    <div className="quote-card partial">
      <div className="banner">
        {!quote.isRealtime && '⚠️ 延迟行情（非交易时段）'}
        {quote.quoteStatusReason && ` — ${quote.quoteStatusReason}`}
      </div>
      <div className="price">{quote.price ?? '--'}</div>
      <div className="source">{quote.source}</div>
      {quote.missingFields.length > 0 && (
        <div className="missing-fields">
          缺失字段: {quote.missingFields.join(', ')}
        </div>
      )}
    </div>
  );
}

// ==================== EMPTY 状态 ====================
function QuoteCardEmpty({ quote }: { quote: StockQuote }) {
  return (
    <div className="quote-card empty">
      <div className="icon">📭</div>
      <p>暂无行情数据</p>
      {quote.errorMessage && <p className="error">{quote.errorMessage}</p>}
      {/* 不显示假数据 */}
    </div>
  );
}

// ==================== ERROR 状态 ====================
function QuoteCardError({ quote, onRetry }: { quote: StockQuote; onRetry: () => void }) {
  return (
    <div className="quote-card error">
      <div className="icon">❌</div>
      <p>数据加载失败</p>
      {quote.errorMessage && <p className="error-msg">{quote.errorMessage}</p>}
      <button onClick={onRetry}>重试</button>
    </div>
  );
}

// ==================== 统一渲染入口 ====================
export function StockQuoteCard({
  quote,
  onRetry,
}: {
  quote: StockQuote;
  onRetry: () => void;
}) {
  switch (quote.dataStatus) {
    case 'OK':
      return <QuoteCardOK quote={quote} />;
    case 'PARTIAL':
      return <QuoteCardPartial quote={quote} />;
    case 'EMPTY':
      return <QuoteCardEmpty quote={quote} />;
    case 'ERROR':
      return <QuoteCardError quote={quote} onRetry={onRetry} />;
  }
}

// ==================== 评分模块（Demo） ====================
export function DemoScoreBadge() {
  return (
    <div className="score-badge demo">
      <span>⭐ 演示评分</span>
      <small>正式评分待接入</small>
    </div>
  );
}
