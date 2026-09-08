"""Synthetic acceptance fixture: produce actual checked reports."""
import argparse
import csv
from decimal import Decimal
import html
import json
from pathlib import Path


def report(source, target, format="markdown"):
    if Path(source).resolve() == Path(target).resolve() or Path(target).exists():
        raise ValueError("Use a new output path")
    with open(source, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["item", "quantity", "unit_price", "line_total"]:
            raise ValueError("Normalize the input first")
        rows = list(reader)
    total = Decimal(0)
    for row in rows:
        expected = Decimal(row["unit_price"]) * int(row["quantity"])
        if expected != Decimal(row["line_total"]):
            raise ValueError("Line total mismatch")
        total += expected
    result = {"kind": "synthetic-test", "rows": rows, "item_count": len(rows), "total": f"{total:.2f}"}
    if format == "json":
        content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    elif format == "html":
        body = "".join("<tr>" + "".join(f"<td>{html.escape(str(row[k]))}</td>" for k in row) + "</tr>" for row in rows)
        content = f'<!doctype html><html lang="en"><meta charset="utf-8"><title>Synthetic report</title><h1>Synthetic report</h1><table><thead><tr><th>Item</th><th>Quantity</th><th>Unit price</th><th>Line total</th></tr></thead><tbody>{body}</tbody></table><p>Items: {len(rows)}</p><p>Total: {total:.2f}</p></html>\n'
    else:
        lines = ["# Synthetic report", "", "| Item | Quantity | Unit price | Line total |", "| --- | ---: | ---: | ---: |"]
        for row in rows:
            escaped = [str(v).replace("|", "\\|").replace("\n", " ").replace("\r", " ") for v in row.values()]
            lines.append("| " + " | ".join(escaped) + " |")
        content = "\n".join(lines) + f"\n\nItems: {len(rows)}\n\nTotal: {total:.2f}\n"
    with open(target, "x", encoding="utf-8") as f:
        f.write(content)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("source")
    p.add_argument("target")
    p.add_argument("--format", choices=["markdown", "html", "json"], default="markdown")
    a = p.parse_args()
    print(json.dumps(report(a.source, a.target, a.format), ensure_ascii=False))
