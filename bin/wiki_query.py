#!/usr/bin/env python3
"""Query the latest cumulative wiki snapshot without reading raw corpus text."""

import argparse
import json
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY = os.path.join(ROOT, "data", "wiki_history.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("domain", nargs="?", help="domain id; omit to list domains")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    with open(HISTORY, encoding="utf-8") as fh:
        latest = json.load(fh)["snapshots"][-1]
    domains = latest["domains"]
    if not args.domain:
        for domain, metrics in sorted(domains.items(), key=lambda item: -item[1]["n"]):
            print(f"{domain:24s} {metrics['n']:5d}  {metrics['share_pct']:6.2f}%")
        return 0
    if args.domain not in domains:
        print(f"unknown domain: {args.domain}", file=sys.stderr)
        return 2
    result = {
        "date": latest["date"],
        "revision": latest.get("revision", 1),
        "policy": latest["policy"],
        "domain": args.domain,
        **domains[args.domain],
    }
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['name_zh']} ({args.domain})")
        print(f"  neutral n={result['n']} ({result['share_pct']}%)")
        print(f"  production={result['production_pct']}%")
        print(f"  evidence={result['date']} r{result['revision']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
