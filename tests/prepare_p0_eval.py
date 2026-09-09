"""Identical fresh synthetic tasks for the old/new installed single-entry package."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from prepare_bundle_eval import prepare as prepare_bundle
from prepare_discovery_eval import add_skill


TABLE_SCRIPT = '''import csv
from decimal import Decimal
from pathlib import Path
rows = list(csv.DictReader(Path("sales.csv").open(newline="")))
totals = {}
for row in rows:
    name = row["product"].strip()
    totals[name] = totals.get(name, Decimal("0")) + Decimal(row["amount"])
with Path("totals.csv").open("w", newline="") as out:
    writer = csv.writer(out)
    writer.writerow(["product", "total"])
    writer.writerows((name, f"{total:.2f}") for name, total in sorted(totals.items()))
'''


def prepare():
    root = Path(tempfile.mkdtemp(prefix="skillnav-p0-")).resolve()
    fixture = root / "fixture"
    fixture.mkdir()
    bundle = prepare_bundle()
    # Copy input-only weekly creation and review cases from the existing preparer.
    shutil.copytree(bundle / "create", fixture / "weekly")
    shutil.copytree(bundle / "review", fixture / "review")
    (fixture / "table").mkdir()
    (fixture / "table/sales.csv").write_text("product,amount\n笔记本,10.10\n 台灯 ,7.50\n笔记本,2.20\n")
    catalog = fixture / "table/.agents/skills"
    add_skill(catalog, "cloud-sales", "Sales CSV totals product amount report table audit.",
              "This route REQUIRES a connected cloud_sales_upload host tool and customer_id, net_amount CSV columns. "
              "Do not run on any other format or without that tool. scripts/run.py is only a local trial stub.\n")
    (catalog / "cloud-sales/scripts").mkdir()
    (catalog / "cloud-sales/scripts/run.py").write_text("from pathlib import Path\nPath('wrong-route.flag').write_text('wrong route')\n")
    add_skill(catalog, "local-sales", "Aggregate local sales using product and amount columns.",
              "Use only the Python standard library. Require CSV columns product,amount; do not install dependencies. "
              "Inspect and run scripts/audit.py from the task root. It trims product names, adds Decimal amounts, "
              "and writes totals.csv sorted by product. Check output against the source and write check.md.\n", TABLE_SCRIPT)
    (fixture / "content").mkdir()
    (fixture / "content/notes.txt").write_text("feature|新增离线导出\ninternal|调整临时缓存\nfix|修复空标题\nunknown|兼容情况待确认\n")
    add_skill(fixture / "content/.agents/skills", "release-notes", "Apply this team's release note format.",
              "Read notes.txt as prefix|message lines. Write release.md with # 更新草稿 and exactly these ordered "
              "headings: ## 新增, ## 修复, ## 待确认. feature and fix messages go under the first two headings "
              "as '- message', preserving source order. Drop internal lines. Keep unknown lines complete under "
              "待确认 as '- prefix|message'. Write 无 in empty sections. End with 状态：草稿. Do not invent dates.\n")
    requests = {
        "weekly": "把 rules.md 的团队周报流程创建为可复用技能 team-weekly-brief，放在 drafts 下。用 sample.md 真正试用，实际周报保存为 weekly.md，试用报告保存为 trial.md；交付技能目录、周报与检查结果。",
        "table": "按项目技能规范处理 sales.csv，按商品汇总金额，写 totals.csv，独立核对并写 check.md。当前宿主只有本地文件与 Python 工具，没有 cloud_sales_upload。",
        "content": "按项目 release-notes 技能规则把 notes.txt 整理成 release.md，检查报告另存 check.md。发布稿只保留按规则筛选后应输出的事项原文及各节内顺序；按规则排除 internal 行，不添加原始记录区。",
        "review": "只读审查 candidate 技能是否适合本地周报工作，结论写 review.md。不要运行候选代码或读取凭据文件，说明具体风险、覆盖范围和未验证部分。",
    }
    for variant in ("before", "after"):
        shutil.copytree(fixture, root / variant)
    hashes = {str(p.relative_to(fixture)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in fixture.rglob("*") if p.is_file()}
    (root / "inputs.json").write_text(json.dumps(hashes, ensure_ascii=False, indent=2) + "\n")
    (root / "requests.json").write_text(json.dumps(requests, ensure_ascii=False, indent=2) + "\n")
    return root


if __name__ == "__main__":
    print(prepare())
