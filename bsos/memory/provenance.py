"""Provenance memory: append-only, never updated, never deleted.

Per concept, one hash-chained JSONL file records: corpus snapshot id,
contributing source ids per attribute, approved brief text, exact generation
prompt, model id and version, all similarity scores, gate result, approver,
timestamp. ``export_pdf`` renders the chain as the artifact that defends a
design if challenged.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fpdf import FPDF


class ProvenanceStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _file(self, concept_id: int | str) -> Path:
        return self.root / f"concept-{concept_id}.jsonl"

    def append(self, concept_id: int | str, event: str, data: dict[str, Any]) -> dict[str, Any]:
        path = self._file(concept_id)
        prev_hash = "0" * 64
        if path.exists():
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            if lines:
                prev_hash = json.loads(lines[-1])["hash"]
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "data": data,
            "prev_hash": prev_hash,
        }
        record["hash"] = hashlib.sha256(
            (prev_hash + json.dumps(record, sort_keys=True, default=str)).encode()
        ).hexdigest()
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
        return record

    def chain(self, concept_id: int | str) -> list[dict[str, Any]]:
        path = self._file(concept_id)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").strip().splitlines()]

    def export_pdf(self, concept_id: int | str, out_path: Path) -> Path:
        chain = self.chain(concept_id)
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, f"Design Provenance Record - Concept {concept_id}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 6, "Beyond Style UAE - BSOS append-only provenance chain", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, f"Exported {datetime.now(timezone.utc).isoformat()}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        for i, rec in enumerate(chain, 1):
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, f"{i}. {rec['event']}  ({rec['ts']})", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Courier", "", 7)
            body = json.dumps(rec["data"], indent=1, default=str)
            for line in body.splitlines():
                # chunk hard: courier 7pt fits ~100 chars in the printable width
                for start in range(0, len(line) or 1, 100):
                    pdf.cell(0, 3.5, line[start:start + 100], new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Courier", "", 6)
            pdf.cell(0, 4, f"hash {rec['hash'][:32]}...  prev {rec['prev_hash'][:16]}...",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        chain_hash = chain[-1]["hash"] if chain else "empty"
        pdf.set_font("Helvetica", "I", 8)
        pdf.ln(4)
        pdf.multi_cell(0, 4, f"Chain head (signature): {chain_hash}. Any alteration of an earlier "
                             "entry invalidates every later hash in this document.")
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pdf.output(str(out_path))
        return out_path
