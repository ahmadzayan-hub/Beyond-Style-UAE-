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

    backup = sub.add_parser("backup", help="zip var/ (ledger, DB, provenance) and externalize the ledger head hash")
    backup.add_argument("--dest", default="backups", help="destination directory (default: backups/)")

    sub.add_parser("ledger-head", help="print the current ledger chain head hash")

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

    if args.command == "ledger-head":
        from bsos.kernel.ledger import Ledger

        ledger = Ledger(root / "var" / "ledger.jsonl")
        print(ledger._prev_hash)  # noqa: SLF001 — head hash, recovered on open
        return 0

    if args.command == "backup":
        import zipfile
        from datetime import datetime, timezone

        from bsos.kernel.ledger import Ledger

        var = root / "var"
        if not var.exists():
            print("nothing to back up: var/ missing", file=sys.stderr)
            return 1
        ledger = Ledger(var / "ledger.jsonl")
        if not ledger.verify():
            print("REFUSING to back up: ledger chain fails verification", file=sys.stderr)
            return 2
        dest = Path(args.dest)
        dest.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive = dest / f"bsos-var-{stamp}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(var.rglob("*")):
                if path.is_file() and path.name != "api-token.txt":
                    zf.write(path, path.relative_to(root))
        head = ledger._prev_hash  # noqa: SLF001
        head_file = dest / f"ledger-head-{stamp}.txt"
        head_file.write_text(
            f"{head}  seq={ledger._seq}  archived={archive.name}\n", encoding="utf-8"
        )
        ledger.append("backup", actor="owner", outcome="ok",
                      data={"archive": str(archive), "head": head})
        print(f"backed up var/ -> {archive}")
        print(f"ledger head    -> {head_file} ({head[:16]}…)")
        print("store the head file somewhere OFF this machine — it is the tamper anchor")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
