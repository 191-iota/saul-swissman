#!/usr/bin/env python3
"""
REGISTER helper — (re)build register/locator.tsv, Saul's fast resolver.

This is NOT application code and it interprets no law. It walks the corpus
frontmatter and the `##### **Art. N**` headings and writes one derived file:

  register/locator.tsv   one TAB-separated row per NAMED law (has short_title),
                         carrying file + the article-number RANGES actually
                         present as headings. Saul greps ONE line out of it
                         (file + presence + Stand) instead of Reading the whole
                         165 KB catalog.md or grepping 114 MB. The ranges expose
                         truncation/holes (e.g. OR present 1-361 but with the
                         employment-termination gap 334-336) WITHOUT opening the
                         file — so an absent article is a one-line answer.

locator.tsv is a disposable cache: the corpus is the only source of law. The
verbatim quote Saul prints ALWAYS comes from reading the article block this turn
(Law 2); the ranges here only say which file to open and whether the article's
base number can be there. catalog.md (the human-browsable Markdown map, sorted by
SR) holds the same set and is rebuilt separately from the same frontmatter scan;
this script writes only locator.tsv. Re-run after ./launch.sh clones or pulls
the corpus:

    python3 register/build_index.py

stdlib only.
"""
import datetime
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORPUS = os.path.join(ROOT, "corpus", "ch")
LOCATOR = os.path.join(HERE, "locator.tsv")

# The four codes vendored in the repo (answer offline without ./launch.sh).
SEED = {
    "cc-1999-404.md", "cc-27-317_321_377.md",
    "cc-54-757_781_799.md", "cc-2022-491.md",
}

FM_KEYS = ("short_title", "sr_number", "title", "rank", "applicability_date", "status")

# Same heading grammar as web/serve.py's slicer — keep this pattern byte-identical to it.
# (The suffix subgroups are captured but unused here; we read only group(1), the integer base.)
ORD = r"bis|ter|quater|quinquies|sexies|septies|octies|novies|decies"
HEAD = re.compile(
    rf"^#####\s+\*\*Art\.\s+(\d+)(?:({ORD}|[a-z]))?\*\*(?:\s*\*?({ORD}|[a-z])\*?(?=[\s*\[]|$))?")


def read_frontmatter(path):
    fm = {}
    try:
        with open(path, encoding="utf-8") as fh:
            if fh.readline().strip() != "---":
                return fm
            for line in fh:
                if line.strip() == "---":
                    break
                m = re.match(r'(\w+):\s*"?(.*?)"?\s*$', line)
                if m and m.group(1) in FM_KEYS:
                    fm[m.group(1)] = m.group(2).strip()
    except OSError:
        pass
    return fm


def scan_articles(path):
    """Return (total_headings, set_of_integer_bases).
    `total` counts every '##### **Art. N**' heading, so 269 and 269a count twice
    (this is the catalog's `arts`, the truncation hint). `bases` collapses letter/
    ordinal suffixes onto the integer number, which is what the ranges encode —
    enough to expose holes (e.g. OR 334-336 missing), with the file grepped for the
    exact heading before quoting anyway."""
    total, bases = 0, set()
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("#####"):
                    h = HEAD.match(line)
                    if h:
                        total += 1
                        bases.add(int(h.group(1)))
    except OSError:
        pass
    return total, bases


def compress(nums):
    """{1,2,3,5,6,253} -> '1-3,5-6,253'. Empty -> '-'."""
    if not nums:
        return "-"
    out, s = [], sorted(nums)
    lo = prev = s[0]
    for n in s[1:]:
        if n == prev + 1:
            prev = n
            continue
        out.append(f"{lo}-{prev}" if lo != prev else f"{lo}")
        lo = prev = n
    out.append(f"{lo}-{prev}" if lo != prev else f"{lo}")
    return ",".join(out)


def build():
    today = datetime.date.today().isoformat()

    def better(a, b):
        # prefer in_force, then already-applicable, then latest applicability date
        ka = (a["status"] == "in_force", a["appl"] <= today, a["appl"])
        kb = (b["status"] == "in_force", b["appl"] <= today, b["appl"])
        return ka > kb

    best = {}
    if not os.path.isdir(CORPUS):
        sys.exit(f"no corpus at {CORPUS} — run ./launch.sh first (seed-only is fine).")
    for fn in sorted(os.listdir(CORPUS)):
        if not fn.endswith(".md"):
            continue
        fm = read_frontmatter(os.path.join(CORPUS, fn))
        ab = fm.get("short_title")
        if not ab:
            continue
        total, bases = scan_articles(os.path.join(CORPUS, fn))
        e = {
            "abbrev": ab, "sr": fm.get("sr_number", ""), "file": fn,
            "rank": fm.get("rank", ""), "appl": fm.get("applicability_date", ""),
            "status": fm.get("status", ""), "title": fm.get("title", ""),
            "arts": total, "max": max(bases) if bases else 0,
            "ranges": compress(bases), "seed": fn in SEED,
        }
        key = (ab, e["sr"])
        if key not in best or better(e, best[key]):
            best[key] = e
    return sorted(best.values(), key=lambda e: (e["abbrev"], e["sr"])), today


def write_locator(rows, today):
    cols = ["abbrev", "sr", "file", "rank", "Stand", "status", "seed", "arts", "max", "ranges"]
    out = [
        f"# locator.tsv — Saul's fast resolver. Generated by build_index.py on {today}.",
        "# Look up ONE line: awk -F'\\t' '$1==\"OR\"' register/locator.tsv  (portable exact match; BSD grep",
        "# has no -P). Never Read the whole file. Columns are TAB-separated.",
        "# seed=1 -> file ships in this repo (offline). ranges = article-number BASES present as headings",
        "# (e.g. base 269 covers 269a..). A base absent from ranges = not in this copy: say so and stop",
        "# without reading (no claim/quote made). A base present still needs the file opened to confirm the",
        "# exact article and quote it (Law 2) — every quote comes from a read; not every absence does.",
        "\t".join(cols),
    ]
    for e in rows:
        out.append("\t".join(str(x) for x in (
            e["abbrev"], e["sr"], e["file"], e["rank"], e["appl"], e["status"],
            "1" if e["seed"] else "0", e["arts"], e["max"], e["ranges"])))
    with open(LOCATOR, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    return len(rows)


def main():
    rows, today = build()
    n = write_locator(rows, today)
    print(f"wrote register/locator.tsv ({n} named laws) — generated {today}")
    seed = [e for e in rows if e["seed"]]
    print("seed laws (offline):")
    for e in seed:
        print(f"  {e['abbrev']:<6} SR {e['sr']:<8} arts={e['arts']:<4} max={e['max']:<5} ranges={e['ranges']}")


if __name__ == "__main__":
    main()
