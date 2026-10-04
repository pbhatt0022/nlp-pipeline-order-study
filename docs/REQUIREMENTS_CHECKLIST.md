# Assignment requirements: where each one is met

Source: *NLP Assessment-1: Domain-Specific Text Analysis and Retrieval System* (deadline 04.10.2026). "NB" is the notebook `Domain_Text_Analysis_Retrieval.ipynb`, and files are in `results/` unless another folder is given. **Report** means the item needs written explanation in `Report.pdf`, built on the files listed.

## Sections 2-3: domain, dataset, pipeline

| Requirement | Where | Status |
|---|---|---|
| Application domain chosen and justified | DECISION_LOG DEC-000, DEC-001 (eligibility rule, EXP-00 scan); Report section 1 | met |
| At least 15 domain documents (15-30 recommended) | `data/D01.txt`-`D53.txt`, 53 documents. More than recommended, needed for phrase/n-gram/BPE statistics and 12 judged queries (DECISION_LOG open decision 1) | met, justified |
| Supported format, IDs D01, D02, ... | TXT, IDs D01-D53, `data/manifest.csv` | met |
| Every pipeline step present, and selection and order justified | NB Modules 1-6; order rationale in PREREGISTRATION section 5 and NB "Pipelines A and B" | met; **Report** expands per process |

## Module 1: collection and extraction

| Requirement | Where | Status |
|---|---|---|
| Load from Drive/local, extract and clean | NB section 0 (Drive or local), `vgir.clean_text`; corpus fetched from the MediaWiki API (`history/notebook_A1_corpus_and_module2.ipynb`, DECISION_LOG EXP-01) | met |
| Unified corpus | `unified_corpus.jsonl` | met |
| Statistics: documents, sentences, tokens, characters, vocabulary, average length | `corpus_summary.csv`, `document_statistics.csv` | met |

## Module 2: Exercises 1-14

| Ex. | Requirement | Where | Status |
|---|---|---|---|
| 1 | Dictionary size vs term-based dictionary | `tokenization_comparison.csv` (unique tokens vs term dictionary, per tokenizer); `preprocessing_results.csv`; `ngram_summary.csv` (unique n-grams) | met |
| 2 | Inspect built-in tokenizer dictionaries, identify improving processes | `tokenization_dictionary_issues.csv` (punctuation types, case variants, possessives, split names, numbers) | met; **Report** maps each issue to a process |
| 3 | At least 5 domain tokenization problems, at least 1 custom rule, NLTK vs spaCy vs Custom vs Hybrid, choice justified | `tokenization_problems.csv` (10 problems); custom rules in `vgir.TOKEN_RX`; evidence for the choice in `tokenizer_domain_terms.csv` (hybrid keeps 91/91 multi-word names, others 0/91) | met |
| 4 | BPE (course tool); compare with NLTK, spaCy, Custom, Hybrid; common, rare and domain words, subwords, vocabulary, token count | `bpe_results.csv` (common/rare/domain words, GPT-2 tiktoken and corpus-trained BPE as in the slides); `bpe_vs_tokenizers.csv` | met |
| 5 | Scenarios where verbs+NPs vs only NPs matter | `np_vs_verbs.csv` (spaCy noun chunks and verbs on a corpus sentence) | met; **Report** discussion |
| 6 | Are dates/numbers needed? Tokenize accordingly | `numbers_dates.csv`; custom regex keeps years, decades, money, %, ordinals, alphanumerics | met |
| 7 | Stop-word removal, justified | `stopword_comparison.csv` (none / 10-word / NLTK); lexicon titles that contain stop words; PREREGISTRATION section 5 | met |
| 8 | Stemming: several algorithms, examples, over- and under-stemming, choice justified | `stemming_lemmatization.csv` (Paice UI/OI/SW), `stem_lemma_examples.csv` | met |
| 9 | Order of stemming vs stop-word removal | `order_effect_stem_stop.csv` (Porter leaks `thi wa ha` when stemming first; Snowball does not) | met |
| 10 | Lemmatization: several algorithms, choice justified | WordNet noun, WordNet verb and spaCy in `stemming_lemmatization.csv` / `stem_lemma_examples.csv`; Pipeline A uses spaCy POS-aware lemmas in context | met |
| 11 | Corpus before vs after preprocessing | `preprocessing_results.csv` (Table A) | met |
| 12 | POS with NLTK/spaCy; at least 5 mis-tagged domain terms; custom rule tagger; custom ML tagger; compare; accuracy | `pos_tagging_results.csv` (5 taggers); `pos_tagging_domain_terms.csv` (Table D); `pos_domain_probe.csv` (32 names in context). Mis-tagged domain terms: PC, Total, Empire, Wars, Islands, Xbox | met (gold set smaller than preregistered, see DECISION_LOG) |
| 13 | NER, 7 types; correct / incorrect / missed / domain-specific | `ner_results.csv` (Table E), `ner_summary.csv`, `ner_by_type.csv`, `ner_domain_entities.csv`; default spaCy vs spaCy + domain EntityRuler | met |
| 14 | 1-5-grams: total, unique, frequency, top 10, meaningful phrases, dictionary size | `unigram_results.csv`, `bigram_results.csv`, `trigram_results.csv`, `ngram_results.csv` (4/5-grams), `ngram_summary.csv`, `bigram_top20_meaningful.csv` | met |

## Module 3: process selection and ordering

| Requirement | Where | Status |
|---|---|---|
| Per process: why, where, dependencies, effect of moving it | PREREGISTRATION section 5; `pipeline_trace_example.csv` (one sentence through both pipelines); `order_effect_stem_stop.csv`; `ablation_EXPLORATORY.csv` (stop lists swapped) | evidence met; **Report** needs the per-process table |
| At least two pipeline orders (A, B) | `vgir.pipeline_A` / `vgir.pipeline_B` | met |
| Compare token count, vocabulary, n-gram quality, domain terms | `pipeline_comparison.csv` (Table H), `domain_term_preservation.csv` | met |
| Select and justify the best pipeline | `final_pipeline_selection.json` (preregistered rule, rule fired, deltas) | met |

## Modules 4-6: retrieval

| Requirement | Where | Status |
|---|---|---|
| Inverted index / posting list | `inverted_index.json` (positional, both pipelines); GUI Terms Dictionary | met |
| Keyword, phrase, AND, OR, NOT search | `vgir.QueryEngine`; demo in NB Module 4 | met |
| 10-15 domain queries; Query, Type, Retrieved Documents, Number of Results | `queries.csv` (12), `retrieval_results.csv`, `table_I_retrieval_results.csv` | met |
| Relevance set | `data/gold/relevance.tsv` (12 x 53, two-person verified; see DECISION_LOG) | met, preliminary |
| P, R, F1, P@K, R@K | `retrieval_results.csv`, `evaluation_results.csv`, `overall_performance.csv` (Table J) | met |

## Required results tables A-J

A `preprocessing_results.csv`; B `tokenization_problems.csv` / `tokenization_comparison.csv`; C `stem_lemma_examples.csv`; D `pos_tagging_domain_terms.csv`; E `ner_results.csv` and `ner_summary.csv`; F `ngram_summary.csv`; G `bpe_results.csv`; H `pipeline_comparison.csv`; I `table_I_retrieval_results.csv`; J `overall_performance.csv`. **All present.**

## Section 6: GUI (15 functions)

The GUI is a Gradio app in the notebook's last section. It was tested in a browser, and the notebook's self-test cell runs every handler and checks that the pipeline trace matches the indexing pipelines.

1. Load/upload: Corpus tab.
2. Statistics: Corpus tab.
3. Tokenization: Tokenization tab.
4. Preprocessing: Pipeline trace tab (streamed stage by stage).
5. POS: POS & NER tab.
6. Custom POS: POS & NER tab.
7. NER: POS & NER tab.
8. N-grams: N-grams tab.
9. BPE: Tokenization tab.
10. Inverted index: Index tab (postings with context, plus the sortable terms dictionary of the sample GUI).
11. Query input: Search tab.
12. Query type selection: Search tab.
13. Retrieval: Search tab.
14. Pipeline comparison: Compare A vs B tab and Evaluation tab.
15. Performance/Evaluation: Evaluation tab.

**All met.**

## Section 11: submission structure

| Item | Where | Status |
|---|---|---|
| `Domain_Text_Analysis_Retrieval.ipynb` | repository root | met |
| `data/` | `data/` (corpus, manifest, lexicon, gold files) | met |
| `results/` with the 14 named files | `document_statistics`, `preprocessing_results`, `tokenization_comparison`, `pos_tagging_results`, `ner_results`, `unigram_results`, `bigram_results`, `trigram_results`, `ngram_results`, `bpe_results`, `inverted_index.json`, `retrieval_results`, `pipeline_comparison`, `evaluation_results` | met |
| `Report.pdf` | repository root (source `Report.md`, built with `tools/report_to_pdf.py`) | met |
