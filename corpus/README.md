# corpus/ — the law

`corpus/ch/` holds Swiss **federal** law as verbatim German Markdown, one file per SR number, sourced from
[legalize-ch](https://github.com/legalize-dev/legalize-ch) (in turn from [Fedlex](https://www.fedlex.admin.ch)).
This is Saul's **only** source of truth. Saul reads it; it never writes here.

Each file opens with a YAML frontmatter block (`short_title`, `sr_number`, `title`, `applicability_date`,
`status`, `source`, …). Articles are anchored as headings — `##### **Art. N**` — with `<sup>N</sup>` marking
each Absatz; lettered articles render split (`##### **Art. 269** d` = Art. 269d).

**Seed (vendored, works offline):** four complete codes —
`cc-1999-404.md` (BV, SR 101), `cc-27-317_321_377.md` (OR, SR 220, to Art. 361),
`cc-54-757_781_799.md` (StGB general part, SR 311.0, to Art. 64), `cc-2022-491.md` (DSG, SR 235.1).

**The rest** is fetched by `./launch.sh` and is git-ignored (114 MB, re-clonable). Coverage is uneven — this
is an early-stage conversion, so several laws are truncated or sparse upstream. That is why Saul verifies that
an article is actually present before it quotes it, and says so when it isn't. The catalog of what's here is
rebuilt by the REGISTER ritual into `register/catalog.md`.
