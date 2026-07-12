"""D126 -- 1회성 백필: experiments/hook_loop/students/*/round*/ 전체를 personal.db로 적재.

이미 git에 있는 라운드들(현재는 gamma_s1의 4라운드)을 순서대로 sync_round()에 통과시킨다.
새 학생/라운드가 생기면 다시 실행해도 안전(멱등 -- store.py의 upsert들이 라운드별
DELETE+INSERT라 재실행해도 중복 적재되지 않는다).

Usage:
  python3 hookfile/db/migrate_existing.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402
from sync_to_db import sync_round  # noqa: E402

REPO = Path(__file__).resolve().parent.parent.parent
STUDENTS_DIR = REPO / "experiments" / "hook_loop" / "students"


def main():
    conn = store.connect_personal()
    round_dirs = sorted(d for d in STUDENTS_DIR.glob("*/round*") if d.is_dir())
    if not round_dirs:
        print(f"[migrate_existing] no round dirs found under {STUDENTS_DIR}", file=sys.stderr)
        return
    for round_dir in round_dirs:
        sync_round(round_dir, conn)
    conn.close()
    print(f"[migrate_existing] done -- {len(round_dirs)} round dirs processed", file=sys.stderr)


if __name__ == "__main__":
    main()
