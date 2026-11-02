"""Standard-library-only query tool for approved agent packets, not raw reports."""

import argparse
import json
from pathlib import Path
import sys


class PacketError(ValueError):
    pass


class QuietParser(argparse.ArgumentParser):
    def error(self, message):
        raise PacketError("invalid_arguments")


def select(packet, *, table=None, student=None, standard=None, offset=0, limit=20):
    if packet.get("format") != "datagoblin.agent.v1" or not isinstance(packet.get("tables"), dict):
        raise PacketError("unsupported_packet")
    if offset < 0 or not 1 <= limit <= 1000:
        raise PacketError("invalid_page")
    context = {key: packet[key] for key in ("format", "method", "assessment_key", "population_key", "snapshot_key", "provenance_ref", "standards_scope_key") if key in packet}
    if table is None:
        context["tables"] = {name: {"columns": value["columns"], "row_count": len(value["rows"])} for name, value in packet["tables"].items()}
        return context
    if table not in packet["tables"]:
        raise PacketError("table_unavailable")
    source = packet["tables"][table]
    columns, rows = source["columns"], source["rows"]
    if student is not None:
        if table != "students":
            raise PacketError("student_filter_requires_students")
        rows = [row for row in rows if row[0] == student]
    if standard is not None:
        if table == "students":
            label = "std:" + standard
            if label not in columns:
                raise PacketError("standard_unavailable")
            indices = [0, columns.index(label)]
            columns = [columns[i] for i in indices]
            rows = [[row[i] for i in indices] for row in rows]
        else:
            index = columns.index("standard_code")
            rows = [row for row in rows if row[index] == standard]
    context.update({"table": table, "columns": columns, "matching_rows": len(rows), "offset": offset,
                    "rows": rows[offset:offset + limit], "next_offset": offset + limit if offset + limit < len(rows) else None})
    return context


def main(argv=None):
    try:
        parser = QuietParser(description="Describe/query a reviewed DataGoblin packet without reading raw reports.")
        parser.add_argument("--packet", type=Path, required=True, help="Packet directory or data.json file.")
        parser.add_argument("--table", choices=("students", "standard_summary", "group_items"))
        parser.add_argument("--student")
        parser.add_argument("--standard")
        parser.add_argument("--offset", type=int, default=0)
        parser.add_argument("--limit", type=int, default=20)
        args = parser.parse_args(argv)
        path = args.packet / "data.json" if args.packet.is_dir() else args.packet
        packet = json.loads(path.read_text(encoding="utf-8"))
        result = select(packet, table=args.table, student=args.student, standard=args.standard, offset=args.offset, limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
        return 0
    except PacketError as error:
        print(f"Packet read stopped: {error}", file=sys.stderr)
    except Exception:
        print("Packet read stopped: invalid_or_unreadable_packet", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
