# Domain-Specific Text Analysis and Retrieval: Video Games

A classical NLP and information-retrieval system for a video-game corpus. It runs a full preprocessing stack (tokenization, BPE, stop words, stemming, lemmatization, POS, NER, n-grams). It builds a positional inverted index with Boolean and phrase search, compares two preprocessing pipelines under a preregistered protocol, and ships a Gradio GUI.

**Authors:** Priyanka B, Sachin B, Tiya P, Vaidhav A.

## Results at a glance

| | Pipeline A (annotate-first, lemma) | Pipeline B (normalize-first, stem) |
|---|---|---|
| Index tokens / vocabulary | 176,387 / 13,165 | 137,253 / 11,247 |
| Macro precision / recall / F1 (12 queries) | 0.596 / 0.805 / 0.648 | 0.596 / 0.805 / 0.648 |
| Domain-term preservation | 1.000 | 0.898 |
| Meaningful-bigram rate (top 20) | 0.30 | 1.00 |

**Final pipeline: A.** The preregistered selection rule applies three steps in order. Step 1 (macro-F1 gap of at least 0.05) does not fire because both pipelines retrieve identical documents for all 12 queries. Step 2 (domain-term preservation gap of at least 0.05) fires.

Two caveats are part of the result:
- **Preliminary relevance judgments.** They come from a two-person, topical-relevance pass.
- **Rewritten queries.** The query wording was rewritten after an earlier run in which B won on a single query.

Both points are recorded in `docs/DECISION_LOG.md`, and the notebook reproduces the earlier run exactly so the two can be compared. All numbers come from `results/`.

## Layout

```
Domain_Text_Analysis_Retrieval.ipynb   the submission notebook (Modules 1-6, comparison, GUI), executed
vgir.py                                shared library: cleaning, tokenizers, Pipelines A/B, positional index,
                                       Boolean/phrase query engine, TF-IDF ranking, metrics, n-grams, BPE
data/
  D01.txt ... D53.txt                  corpus: full English Wikipedia articles (first line = title)
  manifest.csv                         doc id -> Wikipedia page id, title, source MIRACL query, judged role
  domain_lexicon.json                  titles, platforms, companies, events, spelling variants (frozen 29.09.2026)
  gold/relevance.tsv                   relevance judgments, 12 queries x 53 documents
  gold/relevance_REVIEW.csv            review sheet behind relevance.tsv (query text, preview, seeded vs final label)
  gold/pos_gold.tsv, gold/ner_gold.tsv POS gold (226 tokens, Penn Treebank) and NER gold (51 entities, 7 types)
  previous_runs/                       the earlier retrieval runs (auto-generated query forms), used for a reproduction check
results/                               every table the notebook writes (corpus stats, every stage's evaluation, retrieval runs)
docs/PREREGISTRATION.md                hypotheses, pipelines, metrics, selection rule (frozen 29.09.2026)
docs/DECISION_LOG.md                   every decision, experiment and dated amendment
docs/REQUIREMENTS_CHECKLIST.md         requirement -> where it is satisfied
docs/error_analysis_classification.csv manual classification of every retrieval error, with evidence
Report.md / .pdf / .docx              the report (PDF: tools/report_to_pdf.py, needs `pip install markdown`; Word: tools/report_to_docx.py, needs Word + pywin32)
tools/build_notebook.py                source of the notebook (edit here, regenerate, re-run)
history/                               the original team notebooks that built the corpus and produced the earlier runs
```

## Running it

**Locally** (Python 3.10+):

```bash
pip install -r requirements.txt
```

```bash
python -m spacy download en_core_web_sm
```

Then open `Domain_Text_Analysis_Retrieval.ipynb` from this folder and run all cells (about 10 minutes, mostly spaCy). The GUI cell starts Gradio on a local URL. To run headless, set `NO_GUI_LAUNCH=1`.

**Google Colab.** Put this folder in Google Drive as `MyDrive/Domain_Text_Analysis_Retrieval`, open the notebook in Colab and run all cells. The first cell mounts Drive and installs the requirements, and the GUI opens through a public Gradio link.

**Changing the notebook.** Edit `tools/build_notebook.py`, then run `python tools/build_notebook.py` and re-run the notebook.

## Method in brief

- **Corpus.** The corpus has 53 full Wikipedia articles from the judged pools of 12 video-game questions in MIRACL English (train + dev). They were fetched through the MediaWiki API and filtered for video-game content. Construction issues and fixes are in DECISION_LOG EXP-01.
- **Pipeline A:** hybrid tokenization, then spaCy POS tagging on cased text, POS-aware lemmatization (proper nouns, numbers and multi-word names kept), lowercase, and a 10-word stop list.
- **Pipeline B:** hybrid tokenization, then lowercase, the NLTK stop list (positions kept), and Snowball stemming.
- **Shared components:** both pipelines use the same hybrid tokenizer, which merges lexicon multi-word names such as `Game Boy` into `game_boy`. They also share the positional index, TF-IDF ranking with sublinear tf and a title boost, and the query engine. Queries go through the same pipeline as documents.
- **Evaluation:**
  - **Queries:** 12 queries, 2 keyword, 3 phrase, 3 AND, 2 OR and 2 NOT, each a hand-written form of one MIRACL question.
  - **Relevance:** judged for every query-document pair.
  - **Metrics:** P, R, F1, P@5/10 and R@5/10, macro-averaged, plus cold and warm query time.
- **Exploratory analyses.** All are labelled EXPLORATORY in `results/`:
  - an exact reproduction of the earlier runs;
  - stop-list swaps between the pipelines;
  - full questions run as OR queries;
  - a probe of false phrase matches;
  - a leave-one-query-out check.

## Data sources and licences

- **Article text** in `data/D*.txt` is from English Wikipedia and is licensed CC BY-SA 4.0. Each file can be traced to its Wikipedia page through `wikipedia_pageid` in `data/manifest.csv`.
- **Queries and seed judgments** come from MIRACL (Zhang et al., 2023, TACL), released under Apache-2.0.
- **Gold files** (`data/gold/`) were made by the project team.

## References

Manning, Raghavan & Schütze (2008), *Introduction to Information Retrieval*. Brin & Page (1998), *The Anatomy of a Large-Scale Hypertextual Web Search Engine*. Porter (1980). Paice (1994), *An evaluation method for stemming algorithms*. Sennrich, Haddow & Birch (2016). Voorhees (2000). Zhang et al. (2023), *MIRACL*. The full list is in `docs/DECISION_LOG.md`.
