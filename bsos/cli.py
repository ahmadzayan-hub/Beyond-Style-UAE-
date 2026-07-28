"""BSOS CLI.

`bsos audit <concept_id>` replays a concept's full provenance chain to
stdout. `bsos verify-ledger` recomputes the audit ledger's hash chain.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bsos")
    parser.add_argument("--root", default=".", help="BSOS data root")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="replay a concept's provenance chain")
    audit.add_argument("concept_id")

    sub.add_parser("verify-ledger", help="verify the audit ledger hash chain")

    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    if args.command == "audit":
        from bsos.memory.provenance import ProvenanceStore

        store = ProvenanceStore(root / "var" / "provenance")
        chain = store.chain(args.concept_id)
        if not chain:
            print(f"no provenance recorded for concept {args.concept_id}", file=sys.stderr)
            return 1
        for i, record in enumerate(chain, 1):
            print(f"── {i}. {record['event']}  {record['ts']}")
            print(json.dumps(record["data"], indent=2, ensure_ascii=False, default=str))
            print(f"   hash {record['hash']}")
        print(f"\nchain length {len(chain)}, head {chain[-1]['hash']}")
        return 0

    if args.command == "verify-ledger":
        from bsos.kernel.ledger import Ledger

        ledger = Ledger(root / "var" / "ledger.jsonl")
        ok = ledger.verify()
        print("ledger chain VERIFIED" if ok else "ledger chain BROKEN")
        return 0 if ok else 2

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
