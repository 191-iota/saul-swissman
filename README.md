# Saul Swissman

> A Claude Code agent that answers questions on Swiss federal law and quotes the governing statute verbatim for every claim it makes.

![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)

Saul Swissman has no engine of its own. `SAUL.md` is the whole program, and Claude Code is the runtime that reads it. The agent opens the law in `corpus/`, resolves the governing articles through the small index in `register/`, and writes a short legal memo. Every legal proposition carries the article, the law abbreviation, the SR number, and the German wording copied from the statute it opened that turn. When a provision is not in the corpus, the agent says so and points to Fedlex instead of answering from memory.

The corpus is German federal law from the Systematische Rechtssammlung, one Markdown file per SR number. `register/` is a derived map over it (a router, a resolver, and per-topic domain maps), rebuilt from the law itself so that one question costs a few article reads rather than a scan of the whole 114 MB. The optional webview in `web/` is a local viewer. It renders the register, slices the article behind each citation, and streams a headless `claude -p` run. It interprets no law, and deleting it changes nothing.

<p align="center">
  <img src="docs/02-wortlaut.png" alt="Saul names the Rechtsgebiet, then quotes Art. 15 and Art. 16 StGB verbatim, each as a clickable citation with its SR number and Stand." width="640"><br>
  <sub>An answer on self-defence: the governing articles quoted word for word, each citation a chip that opens the statute.</sub>
</p>

## Quickstart

```bash
git clone https://github.com/lambdaf-org/saul-swissman
cd saul-swissman
./launch.sh web                  # the webview at http://127.0.0.1:8788
```

The webview needs only Python 3 (standard library, no pip or Node). Answering a question needs the `claude` CLI on `PATH`, which the server spawns as the engine. Running `./launch.sh` with no argument prints the two ways in and offers to clone the full corpus.

Without the webview, open the folder in a Claude Code session and ask directly. The session reads `SAUL.md` and answers as counsel.

```bash
claude -p "Darf mein Vermieter den Mietzins erhöhen?"
claude -p "register"             # rebuild the index after cloning more of the corpus
```

The seed ships four complete codes (BV and DSG complete, OR to Art. 361, the StGB general part), so questions on contracts, tenancy, data protection, and constitutional rights work offline. `./launch.sh` fetches the rest of Swiss federal law from [legalize-ch](https://github.com/legalize-dev/legalize-ch), about 114 MB, which stays git-ignored and re-clonable.

### Configuration

| Variable | Required | Purpose |
| --- | --- | --- |
| `SAUL_PORT` | No | Port for the webview (default `8788`). |

## Features

- **Citation or nothing**: a legal statement is made only with its article, law abbreviation, SR number, and a verbatim German quote read that turn. A sentence without a receipt does not get written.
- **Verifies presence before quoting**: the agent confirms the article heading exists in the file before citing it, and never reconstructs a missing or truncated article from memory.
- **Names its gaps**: it works only from federal law (SR), so it flags when a question turns on cantonal law, court rulings (BGE), or doctrine. The corpus holds none of those.
- **Clickable statutes**: in the webview, each citation in an answer opens the verbatim article in a side panel, and a law browser lists every named law present in the local corpus.
- **Routed retrieval**: a question resolves to a Rechtsgebiet, then to one law file via `register/`, so a single answer touches a handful of articles instead of scanning the corpus.
- **Derived, rebuildable index**: `register/build_index.py` walks the corpus frontmatter and headings to regenerate the resolver, so coverage tracks what is actually on disk.

## How it works

The agent answers as a short memo with a fixed skeleton: Frage, Einschlägige Bestimmung, Wortlaut, Anwendung, Vorbehalte, Anwalt. It reads `register/index.md` first to route the question, looks up one line in `register/locator.tsv` for the file and the present-article ranges, greps that one file for the article heading, reads the block, and quotes it with its `Stand`. The nine Laws of Saul in `SAUL.md` govern the rest: it never invents a deadline, fine, or threshold; it pinpoints the Absatz only as far as the markers allow; it raises the adjacent provision or deadline the question walks into without predicting an outcome.

```
SAUL.md       the operating manual: the one idea, the nine Laws, the citation format, the two rituals
register/     the map: index.md (router), locator.tsv (resolver), catalog.md (law to file),
              domains/ (topic to articles), build_index.py (rebuilds the locator)
corpus/ch/    the law, verbatim German federal statutes (seed vendored; launch.sh fetches the rest)
web/          the optional webview (serve.py + index.html)
```

The webview's server (`web/serve.py`) does four things and no more. It serves `register/` files read-only, slices one statute article out of `corpus/ch/` verbatim, lists the catalog of laws present, and spawns `claude -p` to stream an answer back. It binds to `127.0.0.1` only, mints a CSRF token per launch, runs one query at a time, and never decides what the law means.

## Contributing

See [lambdaf-org/contributing](https://github.com/lambdaf-org/contributing).

## License

Saul's own files (`SAUL.md`, `register/`, `web/`, the scripts) are MIT, per the `LICENSE` file. The Swiss federal legal texts under `corpus/` are official enactments of the Swiss Confederation and are not protected by copyright under the Swiss Copyright Act (URG, SR 231.1). The authoritative source is [Fedlex](https://www.fedlex.admin.ch).