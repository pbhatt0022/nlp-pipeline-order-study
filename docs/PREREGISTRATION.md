# PREREGISTRATION — FROZEN 29.09.2026

**Freeze rule.** No content below this section may be changed after the first confirmatory result is produced. Any subsequent change is recorded only as a dated amendment at the bottom.

Domain: **Video games**, from MIRACL English train + dev.
Source: DEC-000 and DEC-001 in `DECISION_LOG.md`.

---

## 1. Research questions

- **RQ1.** Does an annotate-first, lemma-based pipeline (A) or a normalize-first, stem-based pipeline (B) achieve higher retrieval quality on domain-specific queries about video games?
- **RQ2.** Which specific NLP components (title-preserving tokenization, POS-aware lemmatization, minimal vs standard stop lists) explain any difference?

## 2. Hypotheses (formalized from prior expectations)

| # | Hypothesis | Confidence at freeze |
|---|---|---|
| H1 | Pipeline B produces a **smaller vocabulary and fewer tokens** than Pipeline A. | Near-certain by construction (reported for §11 table only). |
| H2 | Pipeline B has **higher macro-averaged recall** than A on keyword and Boolean queries. | Moderate. |
| H3 | Pipeline A has **higher macro-averaged precision** than B, especially on phrase queries. | Moderate. |
| H4 | Pipeline B produces false phrase matches from position-preserving stop removal (any stop word can bridge the gap). | Moderate; possibly rare. |
| H5 | Pipeline A preserves ≥ 5% more domain-lexicon terms intact than B. | High. |
| H6 | Pipeline A has a higher proportion of meaningful bigrams among the top 20 (by count ≥ 2). | Moderate. |
| — | Macro-F1: **no prediction**. This is the primary open question. |

## 3. Corpus and documents

- ~50 documents (accept 40–55), each a full English Wikipedia article whose passages appear in the MIRACL judged pools of our chosen queries.
- Every doc traceable to a Wikipedia `pageid` via `data/manifest.csv`.
- Documents contain title + body only. Queries are never inside documents.

## 4. Queries (locked; 12 items)

Copied here from Notebook 1 §1. Ties every required query type to a MIRACL question.

| our_qid | Query | Type | Cluster |
|---|---|---|---|
| Q01 | Game Boy | phrase | consoles |
| Q02 | Sega Genesis | phrase | consoles |
| Q03 | SNES OR "Super Nintendo Entertainment System" | OR | consoles |
| Q04 | Xbox AND Microsoft | AND | consoles |
| Q05 | Wolfenstein | keyword | franchises |
| Q06 | Metal Gear Solid | phrase | franchises |
| Q07 | Zelda AND Nintendo | AND | franchises |
| Q08 | Halo AND NOT Wars | NOT | franchises |
| Q09 | "first-person shooter" | phrase | genre |
| Q10 | RPG OR "role-playing game" | OR | genre |
| Q11 | Gears of War 3 | keyword | sales |
| Q12 | Doom | keyword | firsts |

## 5. Pipelines A and B

**Shared components.** Cleaning (Unicode NFKC, diacritic folding, Wikipedia artefact removal, whitespace); hybrid tokenization (custom regex protecting titles, sequel numbers, hyphenated terms, plus MWE merge from `domain_lexicon.json`); positional inverted index; TF-IDF ranking with title-hit boost (Brin & Page 1998); Boolean + phrase query engine; sublinear TF (1 + log tf); queries always pass through the same pipeline as documents; POS tagging and NER always run on cased, full text.

| Step | Pipeline A | Pipeline B |
|---|---|---|
| 1 | Hybrid tokenization | Hybrid tokenization |
| 2 | POS tagging (spaCy on cased text) | Lowercase |
| 3 | NER (spaCy on cased text) | Stop-word removal — standard NLTK list, positions kept |
| 4 | POS-aware lemmatization (proper nouns and MWEs kept) | Snowball (Porter2) stemming |
| 5 | Lowercase | — |
| 6 | Minimal stop list (10 words: a, an, the, of, and, or, to, in, is, was) | — |

**Order justification.** A: lemmatization needs POS; POS needs case and context; so tagging first, stop removal last. B: stemming needs no context; standard IR order is lowercase → stop removal → stem (Manning et al., IIR §2). This satisfies "at least two different pipeline orders" per §2 P#4.

## 6. Metrics and K values

- Set-based: Precision, Recall, F1 over the full ranked list.
- Ranked: P@5, P@10, R@5, R@10.
- Aggregation: macro-averaged across the 12 queries.
- Timing: cold (first) and warm (median of 5 repeats) per query (Brin & Page 1998, Table 2).
- Overstemming/Understemming: Paice OI, UI, SW (SIGIR 1994) on 5 concept groups covering common video-game morphology and one known over-stemming trap (`universe`/`university`/`universities`).

## 7. "Meaningful n-gram" operational definition

An n-gram (n≥2) is *meaningful* if all of: (a) it occurs ≥2 times in the corpus, (b) neither edge word is a stop word or a pure numeric/punctuation token, and (c) at least one token has an alphabetic character. Rate = share of meaningful items among the top 20 by count.

## 8. Domain-term preservation

For each entry in `domain_lexicon.json` (titles, platforms, companies, events), a pipeline "preserves" it iff its output for that entry (in isolation) is exactly one token equal to the case-folded MWE form. Reported as a share.

## 9. Final-pipeline selection rule

1. **Primary:** Pipeline with higher macro-F1 wins if `|ΔF1| ≥ 0.05`.
2. If `|ΔF1| < 0.05`: pick the pipeline with higher domain-term preservation if that gap is `≥ 0.05`.
3. Otherwise: pick the pipeline with higher meaningful-bigram rate.

The "Final Pipeline" column in the assignment's tables is one of {A, B} — no post-hoc mix. If we later report an exploratory mix, it is labeled EXPLORATORY.

## 10. Gold sets (must be built before running the retrieval and evaluation cells)

- `data/pos_gold.tsv`: ~200 tokens across 15–20 sentences drawn from our corpus, Penn Treebank tags. Must include ≥1 occurrence each of Doom, Halo, Destiny, Prey.
- `data/ner_gold.tsv`: ~50 entities across our documents; 7 types: PERSON, ORG, GPE, DATE, MONEY, PRODUCT, EVENT.
- `data/relevance.tsv`: MIRACL-seeded, then hand-completed for every (query × document) pair. Frozen before Notebook 2 §3.

## 11. Confirmatory vs exploratory experiments

**Confirmatory** (tests H1–H6, §3–§5 of Notebook 2, and the Paice/POS/NER tests in Notebook 1 §6, §8, §9 when their gold files are frozen).

**Exploratory** (labeled as such in the report; do not test hypotheses):
- Any pipeline other than A and B (e.g. minimal-stop + snowball).
- BPE fertility across GPT-2 vs corpus-trained.
- Timing across pipelines beyond warm/cold reporting.
- Any post-hoc "Final Pipeline" that mixes components.

## 12. Error-analysis plan

For each of Q01–Q12: list every FN and FP; classify each as tokenization / stemming / lemma / stop / NER / ranking / relevance-judgment. Aggregate counts per pipeline. Include ≥3 representative examples in the report.

## 13. Options from Brin & Page 1998 — decision at freeze

Adopted (built into pipelines):
- Title-hit boost (2.0×) in TF-IDF.
- Sublinear TF (1 + log tf).
- Cold vs warm timing.

Not adopted (out of scope):
- PageRank (no link graph in MIRACL).
- Anchor-text propagation (no link text).
- Full proximity bins in ranking (kept for exploratory only; the phrase-query engine already returns exact phrases as a Boolean primitive).

## Amendments (append-only)

*(none yet)*
