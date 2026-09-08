"""Synthetic acceptance fixture: strict CSV normalization, not a production ledger."""
import csv
from decimal import Decimal
from pathlib import Path
import sys


def normalize(source, target):
    if Path(source).resolve() == Path(target).resolve() or Path(target).exists():
        raise ValueError("Use a new output path")
    with open(source, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["item", "quantity", "unit_price"]:
            raise ValueError("Unexpected columns")
        rows = []
        for row in reader:
            quantity = int(row["quantity"].strip())
            price = Decimal(row["unit_price"].strip())
            item = row["item"].strip()
            if not item or quantity <= 0 or not price.is_finite() or price < 0 or price != price.quantize(Decimal(".01")):
                raise ValueError("Invalid item, quantity or price")
            rows.append(dict(item=item, quantity=quantity, unit_price=f"{price:.2f}", line_total=f"{quantity * price:.2f}"))
    with open(target, "x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["item", "quantity", "unit_price", "line_total"])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    print(normalize(*sys.argv[1:]))
