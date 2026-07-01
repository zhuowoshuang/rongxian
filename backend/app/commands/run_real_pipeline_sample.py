from __future__ import annotations

import argparse
import json

from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.services.real_pipeline import run_real_pipeline_sample


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the real-calculated sample pipeline.")
    parser.add_argument("--limit", type=int, default=30, help="Number of sample stocks to process.")
    args = parser.parse_args()

    import app.models.refresh_job_run  # noqa: F401

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        result = run_real_pipeline_sample(db, limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    main()
