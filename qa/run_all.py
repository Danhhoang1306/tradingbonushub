"""Chạy lại toàn bộ QA chức năng, từ gốc repo:

    $env:QA_WORK = "<thư mục tạm>"
    .venv\\Scripts\\python qa\\run_all.py          # bỏ qua cài đặt sạch
    .venv\\Scripts\\python qa\\run_all.py --full   # thêm s0 (venv mới) và s8 (ảnh so thiết kế, cần mạng cho CDN của design)

Cổng: 8014 (server), 8016 (proxy https), 8015 (design). Kết quả JSON ở qa/results/. Không đụng data/app.db, không gửi email.
"FAIL" trong script là kỳ vọng chưa đạt; phân loại và lý do nằm ở docs/QA_REPORT.md.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
names = ["s3_edge", "s4_security", "s1_admin_first_use", "s2_visitor", "s5_ui", "s6_ops", "s7_probes", "s9_round2", "s10_upgrade_prod", "s11_round3"]
if "--full" in sys.argv:
    names = ["s0_fresh_install"] + names + ["s8_design_compare"]
total = bad = 0
for n in names:
    print(f"\n######## {n}", flush=True)
    subprocess.run([sys.executable, str(HERE / f"{n}.py")], cwd=HERE.parent, env={**os.environ, "PYTHONUTF8": "1"})
    f = HERE / "results" / f"{n}.json"
    if f.exists():
        rows = json.loads(f.read_text(encoding="utf-8"))
        total += len(rows)
        bad += sum(1 for r in rows if not r["ok"])
print(f"\nTỔNG: {total - bad}/{total} đạt, {bad} không đạt")
