#!/usr/bin/env python3
"""Normalize browser-extracted Xiaohongshu favorite records into stable JSON."""

import argparse
import sys
from datetime import datetime

from common import dump_json, load_json, normalize_records, records_from_payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="浏览器提取的 JSON 文件")
    parser.add_argument("-o", "--output", help="输出 JSON；省略则打印到标准输出")
    parser.add_argument("--collected-at", default=datetime.now().astimezone().isoformat(timespec="seconds"))
    args = parser.parse_args()
    try:
        result = {"items": normalize_records(records_from_payload(load_json(args.input)), args.collected_at)}
        text = dump_json(result)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as handle:
                handle.write(text)
        else:
            sys.stdout.write(text)
        return 0
    except (OSError, ValueError) as error:
        print(f"错误：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
