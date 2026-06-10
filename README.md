# Saul Swissman

> Swiss federal law counsel that quotes the statute for every word it says. No citation, no claim.

![Markdown](https://img.shields.io/badge/built%20on-Markdown-083fa1)
![Claude Code](https://img.shields.io/badge/engine-Claude%20Code-d97757)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

Saul answers questions on Swiss federal law and backs every statement with the statute: the article, the SR number, the verbatim German wording, and the consolidation date (`Stand`). There is no application code. `SAUL.md` is the whole program; Claude Code is the engine. It reads the law in `corpus/`, routes to the right article through the `register/` index, and quotes it. When the corpus lacks a provision, it says so and points to [Fedlex](https://www.fedlex.admin.ch).

## Quickstart

```bash
git clone https://github.com/lambdaf-org/saul-swissman.git
cd saul-swissman

# The webview: a white reading room, no terminal to manage.
./launch.sh web                  # open http://127.0.0.1:8788
#   ask a question; every citation opens the verbatim statute next to the answer.

# Or a Claude Code session in this folder, the engine itself:
./launch.sh                      # git-inits register/, offers to clone the full corpus
#   then ask, e.g.  "Darf mein Vermieter den Mietzins erhöhen?"
#   after cloning more law, say  "register"  to re-map it
```

The seed ships four codes (BV and DSG complete, OR to Art. 361, StGB general part to Art. 64), so questions on contracts, tenancy, data protection, and constitutional rights work offline. `./launch.sh` fetches the rest of Swiss federal law (5789 files, 114 MB) from [legalize-ch](https://github.com/legalize-dev/legalize-ch).

## Features

- **Receipt-backed answers.** Every legal statement carries `Art. N <ABBREV> (SR number)`, a verbatim German quote, and the `Stand`. A sentence without that citation does not get made.
- **Quotes only what it read this turn.** The wording is copied from a statute file opened during the answer, so training memory is never the source of statute text.
- **Names the gaps.** It works from federal law (SR) only, so it flags where a question turns on cantonal law, court rulings (BGE), or doctrine, none of which the corpus holds.
- **Invents no numbers.** Every Frist, Busse, threshold, or sum is quoted from the article, and "the statute is silent here" is a valid answer.
- **Verifies presence first.** Before citing, it confirms the article heading exists in the file; a truncated or missing article is reported, with a pointer to Fedlex.
- **Routes to one file.** The `register/` index resolves a question to a single law file, so a question costs a few article reads against the 114 MB corpus.
- **Flags the adjacent thing.** It raises the related deadline, exception, or provision you did not ask about, each named with its own citation.
- **Clickable webview.** A local viewer where every claim is a citation that opens the statute behind it.

## How it works

`SAUL.md` defines Saul's behavior: the one idea (the citation is the product), the nine Laws of Saul, the fixed citation format, and the ADVISE and REGISTER rituals. Claude Code reads it and acts as counsel.

```
SAUL.md       how Saul works, the whole program
register/     the map: index.md (router, read first every turn), locator.tsv (law -> file ->
              present articles), catalog.md (law -> file), domains/ (8 topic maps), build_index.py
corpus/ch/    the law, verbatim German federal statutes (seed vendored; launch.sh fetches the rest)
web/          the webview (serve.py + index.html)
```

An ADVISE answer follows one skeleton: **Frage -> Einschlägige Bestimmung -> Wortlaut -> Anwendung -> Vorbehalte -> Anwalt.** The corpus is the only source of truth. `register/` is a derived index, rebuilt from the law itself by the REGISTER ritual (`python3 register/build_index.py`), so it routes and the heading in the file proves. Deleting `web/` changes nothing about the law.

## What an answer looks like

A single exchange in the webview: someone asks whether they may defend themselves with their fists against an attacker who draws a weapon on a train. Saul names the area of law, quotes the governing articles word for word, applies them to the facts, and marks where the corpus runs out.

![The question, and Saul beginning to read the statutes.](docs/01-frage.png)

![Saul names the Rechtsgebiet, then the governing provisions and their wording: Notwehr in Art. 15 StGB and its excess in Art. 16, each with the SR number and the Stand.](docs/02-wortlaut.png)

![The articles applied to the facts: when the defence is justified, and where the line of proportionality runs.](docs/03-anwendung.png)

![The reservations and the disclaimer: what the words leave open, what is not in the local corpus, and the pointer to a lawyer.](docs/04-vorbehalte.png)

## Limits

This is statute-grounded information for orientation. It does not constitute legal advice and does not replace a licensed lawyer. It rests on federal law (SR) at the consolidation date shown with each quote, which does not rule out a later amendment, and it covers no cantonal law, court practice, or doctrine. The corpus is an early conversion and several laws are incomplete: the Civil Code holds a fraction of its articles, the seed Criminal Code is the general part only, and the OR seed ends at Art. 361 with internal gaps such as the ordinary-termination articles 334-336. Saul names these edges when it reaches them. For anything binding, contested, or time-bound, consult a licensed Anwältin or Anwalt.

## Contributing

Lambdaforge is open source and contributions are welcome. Start with the [contributor guide](https://github.com/lambdaf-org/contributing), and see the org-wide [CONTRIBUTING](https://github.com/lambdaf-org/.github/blob/main/CONTRIBUTING.md) and [Code of Conduct](https://github.com/lambdaf-org/.github/blob/main/CODE_OF_CONDUCT.md).

## License

Saul's own files are MIT. See [LICENSE](./LICENSE). The Swiss federal legal texts in `corpus/` are official enactments and are not protected by copyright under the Swiss Copyright Act (URG, SR 231.1). The authoritative source is [Fedlex](https://www.fedlex.admin.ch).
