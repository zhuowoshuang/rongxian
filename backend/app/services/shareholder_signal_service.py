from datetime import datetime

from sqlalchemy.orm import Session

from app.models.watchlist import ShareholderStructure


def get_shareholder_signal(db: Session, stock_code: str) -> dict:
    rows = db.query(ShareholderStructure).filter(ShareholderStructure.stock_code == stock_code).all()
    if not rows:
        return {
            "status": "not_connected",
            "signal": "unknown",
            "summary": "股东结构数据暂未接入或暂缺",
            "sources": [],
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "non_natural_shareholder_count": 0,
            "non_natural_shareholder_ratio": None,
            "state_background_institution_count": 0,
            "has_state_background_support": False,
        }

    non_natural = [row for row in rows if row.shareholder_type != "natural_person"]
    state_rows = [row for row in rows if str(row.is_state_background).lower() in {"1", "true", "yes"}]
    signal = "positive" if len(non_natural) >= 4 and len(state_rows) >= 1 else "neutral"
    summary = (
        "机构股东参与度较高，且存在国家背景投资机构，需结合持股比例和变动方向进一步确认。"
        if signal == "positive"
        else "机构股东参与度较高，但暂未识别国家背景投资机构。"
    )
    return {
        "status": "connected",
        "signal": signal,
        "summary": summary,
        "sources": sorted({row.source for row in rows if row.source}),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "non_natural_shareholder_count": len(non_natural),
        "non_natural_shareholder_ratio": None,
        "state_background_institution_count": len(state_rows),
        "has_state_background_support": bool(state_rows),
    }
