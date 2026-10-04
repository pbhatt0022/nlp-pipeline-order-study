# Decision & Experiment Log
Project: Domain-Specific Text Analysis and Retrieval System (NLP Assessment-1, DATA403)
Deadline: 04.10.2026

Entries are append-only. Changes to earlier decisions are recorded as new, dated amendments, never by editing the original entry.

---

## Decisions

### DEC-000 — Dataset source (29.09.2026)
**Decision.** Use MIRACL English (`miracl/miracl` topics + qrels; passage text from MIRACL corpus or Wikipedia, see EXP-01).
**Rationale.** Human relevance judgments (qrels) give a far more defensible relevance set for Module 6 than self-made judgments; public, versioned, Apache-2.0.
**Alternatives considered.** Other Wikipedia retrieval sets (Natural Questions, HotpotQA, DBpedia-Entity, FEVER, Climate-FEVER): same open-domain problem, sparser judgments. TREC-COVID: better domain fit and deeper judgments; kept as fallback if no MIRACL theme had been eligible.
**Known weaknesses.** Wikipedia is open-domain (addressed by DEC-001); text arrives already clean, so Module 1 "extraction" is parsing + artifact cleaning; judgments cover only ~10 passages per query, so unjudged pairs in our corpus must be judged by us before any retrieval run; MIRACL queries are natural-language questions, so our Boolean/phrase queries are formulations of the same information need.
**Practical note.** `datasets` >= 4.0 no longer runs loading scripts; load raw TSV files via `huggingface_hub` instead.

### DEC-001 — Domain: video games (29.09.2026)
**Decision.** MIRACL English, video games theme, train + dev splits combined (no model training, so no leakage concern).
**Rule used** (agreed before EXP-00 was run): a theme is eligible if usable queries >= 15, usable queries with >= 2 positives >= 10, distinct judged articles >= 50, and >= 20% of queries share a judged article or >= 50% share a content word. Among eligible themes, preference order: video games > neuroscience & mental health > computing & technology > medicine > space.
**Result.** All five themes eligible; video games selected by preference order. EXP-00: 83 usable queries, 72 with >= 2 positives, 474 distinct judged articles, 65.1% of queries share an article, 94.0% share a content word.
**Manual review.** Keyword matching near-perfect for video games (only borderline item: Ash Ketchum voice-actor question, which concerns the anime). Three additional time-sensitive queries excluded: "When does Kingdom Hearts 3 come out?", "Is Prey 2 announced?", "When did the last Pokemon hit the DS?". Roughly 80 usable queries remain.
**Transparency caveat.** Thresholds and preference order were fixed before EXP-00 was run, but after an informal partial scan of training queries, so the rule was not fully blind to the data.
**Alternatives considered.** Computing & technology (runner-up on manual review; 63 usable after cleanup, weaker MONEY/EVENT coverage, stronger optics); neuroscience & mental health (keyword matching poor: Great/Long Depression, WIPO, Kierkegaard matched); a combined "digital technology and gaming" domain. Considered briefly for presentation reasons; team kept video games.

---

## Experiments

### EXP-00 — MIRACL English theme scan (EXPLORATORY) (29.09.2026)
**Purpose.** Choose the domain. No hypotheses tested.
**Script.** `exp00_miracl_theme_scan.py` (keyword-regex theme assignment, multi-label; time-sensitivity regex flag).
**Inputs.** MIRACL English topics + qrels, train and dev.
**Outputs.** `exploration/exp00_theme_summary.csv`, `exploration/exp00_theme_queries.csv`, `exploration/exp00_run_info.json`.
**Key results.**

| Theme | Usable | >= 2 pos | Judged articles | Share article | Share term |
|---|---|---|---|---|---|
| medicine_health | 140 | 106 | 852 | 55.7% | 84.3% |
| video_games | 83 | 72 | 474 | 65.1% | 94.0% |
| computing_tech | 64 | 48 | 386 | 59.4% | 81.2% |
| space_astronomy | 56 | 50 | 366 | 69.6% | 96.4% |
| neuro_mental | 55 | 42 | 341 | 61.8% | 76.4% |

**Limitations.** Keyword themes are crude; the time-sensitivity regex missed at least three queries; overlap percentages computed before manual cleanup.

### EXP-01 — Corpus construction (CONFIRMATORY-but-corrected) (30.09.2026)
**Purpose.** Build the ~50-document corpus by fetching Wikipedia articles whose MIRACL docids appear in the judged pools of our 12 video-game queries.
**Script.** Notebook 1 §1-§2 (`notebook_A1.ipynb` + its A2 copy).
**Inputs.** MIRACL English topics + qrels; Wikipedia page IDs derived from MIRACL docid prefix `X#Y`.
**Outputs.** `03_CORPUS/D01.txt` … `D47.txt`, `03_CORPUS/manifest.csv`, `03_CORPUS/LOCKED_ON.txt`.

**Build-time issues and fixes** (first-day iteration; the final committed notebook is clean, but issues are documented here for the record and because they inform the final design):

1. **Placeholder MIRACL qids.** First version of Notebook 1 §1 used hand-plugged qids (`train:1` … `train:12`) that were meant to be replaced from `exp00_theme_queries.csv` before running. The replacement step was missed on first run and the fetched articles were about American football players and other unrelated topics (because MIRACL covers all topics, not just gaming). **Fix:** §1 now programmatically discovers real video-game qids by rescanning MIRACL topics with the EXP-00 regex, then picks 12 queries balanced across clusters by a deterministic rule. No manual qid mapping is required.
2. **Wikipedia API rate-limiting (HTTP 429).** First fetcher issued one request every 0.1 s with no retry; Wikipedia blocked after ~10 articles. **Fix:** session reuse, `Retry-After` header honoured, pacing at ~2.5 req/s.
3. **Batch extract truncation.** Attempted mitigation (fetch 20 pageids per request) returned mostly empty `extract` fields because MediaWiki's `TextExtracts` extension needs `exlimit=1` for full extracts. **Fix:** reverted to one-article-per-request with `exlimit=1`.
4. **Off-topic hard negatives.** MIRACL's judged pools include documents annotators judged *not* relevant; some are about unrelated topics (sports biographies, etc.). Pulled uncritically they would pollute the corpus. **Fix:** apply a positive video-game keyword filter to the first 3000 characters of each extract; drops are logged.

**Final build.** 47 articles kept, all topically on-domain. Median body length well above 1000 characters.
**Reproducibility note.** None of these issues touched `vgir.py`, the preregistration, or any downstream analysis. The final notebook §2 (as of 30.09.2026) runs cleanly from scratch and should produce the same corpus if rerun.

### EXP-02 — Pipeline A retrieval (CONFIRMATORY) (30.09.2026)
**Purpose.** Build positional inverted index for Pipeline A; run the 12 locked queries; compute retrieval metrics against hand-verified relevance judgments.
**Script.** Notebook 2 §3 (`notebook_A2_retrieval.ipynb`).
**Inputs.** 47 documents in `03_CORPUS/`, 12-query QUERIES table (same auto-picked list as EXP-01, decorated with Boolean/phrase operators in Notebook 2 §1), hand-verified `04_GOLD/relevance.tsv` (see amendment on relevance-verification protocol).
**Outputs.** `10_PIPELINE_A/results_A/inverted_index_A.json`, `10_PIPELINE_A/results_A/retrieval_results_A.csv`.
**Metrics.** Precision, Recall, F1, P@5, P@10, R@5, R@10 per query and macro-averaged; cold and warm (median of 5 repeats) query timings.
**Status.** Pipeline A's retrieval evaluation is complete. Pipeline B's parallel run and the cross-pipeline comparison are pending B1/B2's work.

---

## Amendments

### Amendment to EXP-02 — Two-person relevance-judgment protocol (30.09.2026)
**Change from preregistration.** PREREGISTRATION.md §10 specified a four-teammate hand-verification of `relevance.tsv` before Notebook 2 §3 runs. B1 and B2 were unavailable at the time this step blocked A2's retrieval work. A1 and A2 performed a two-person verification pass on 30.09.2026 instead.

**Protocol used (two-person pass).** Neither A1 nor A2 is a video-game domain expert; relevance judgments were therefore made under a rule-based *topical-aboutness* protocol rather than deep-fact judgments:
1. If the document title contains the query's main entity or topic, mark relevant.
2. Otherwise, if the document is a general reference document for the query's domain (and the query is itself about that reference), mark relevant.
3. Otherwise, if the document preview explicitly mentions the query's main entity, mark relevant.
4. Otherwise, mark non-relevant.

**Edge-case rulings fixed before the pass started.**
- General reference articles (e.g. "History of Nintendo", "Video game development") marked non-relevant unless the query is itself about that reference.
- Franchise umbrella articles marked relevant for queries about specific games in that franchise.

**Workflow.** The seeded `relevance.tsv` (auto-generated from MIRACL positive judgments) was expanded into a review sheet (`relevance_REVIEW.csv`) that joins each (query, document) row with the original query text, the document title, and the first 200 characters of the document body. The review sheet was opened in a shared Google Sheet. A1 verified rows for Q01–Q06; A2 verified Q07–Q12; each spot-checked the other's rulings. The final `final_rel` column was exported back to `relevance.tsv` in TSV format. `04_GOLD/relevance_LOCKED_ON.txt` was created with a note recording this was a two-person pass pending full-team re-verification.

**Known limitations.**
- Judgments capture *topical* relevance ("is the document about the query topic?"), not *answer* relevance ("does the document contain the specific fact the query asks for?").
- Recall will be slightly overestimated for queries whose answer requires specific facts that generic domain articles may or may not contain.
- Two-annotator agreement was not formally measured. Agreement is expected to be moderate (~70%) given the mechanical nature of the protocol.
- Consistent with TREC pooling practice (Voorhees 2000): unjudged (query, document) pairs are treated as non-relevant.

**Next step.** When B1 and B2 are available, a full four-teammate re-verification may be run. If their verification changes `relevance.tsv`, retrieval must be rerun for both pipelines. Pipeline A retrieval numbers produced before any re-verification are labelled "preliminary" in the report.

---

## Grounding audit (29.09.2026)
Each decision mapped to the course plan (CP, lecture numbers), lab sheets and literature. "Extension" = goes beyond what was taught, with a stated justification.

| Decision | Course plan | Lab sheet / slides | Literature | Status |
|---|---|---|---|---|
| DEC-000 MIRACL | Tools: Hugging Face Hub; L1 P#1–2 corpus loader | LAB1 (JSON/TXT loaders) | Zhang et al. 2023 (MIRACL) | Grounded |
| DEC-001 domain rule | PO4 (design of experiments) | — | — (team judgment, documented) | Judgment |
| Hybrid tokenizer | L3 (NLTK/spaCy/regex tokenizers) | Tokenization notebook (MWETokenizer, `add_special_case`/ORTH, token attributes); regex notebook; PPT 2 tokenization issues | Manning et al. 2008, ch. 2 | Grounded |
| BPE: tiktoken + corpus-trained | L3 (BPE, WordPiece) | BPE notebook (tiktoken gpt2); PPT 2 BPE algorithm | Sennrich et al. 2016 | Grounded |
| Stop-word policy (A minimal/none; B standard list) | L2 | — (no lab) | Manning et al. 2008, §2.2.2 (trend from large lists to none; titles made of stop words) | Grounded in literature |
| Stemmers + over/under-stemming measure | L7 (Porter, Snowball) | Porter handout | Porter 1980; Paice 1990 (Lancaster); Paice 1994 (OI, UI, ERRT; implemented in NLTK) | Grounded |
| Lemmatization | L7 (WordNet) | Language Model notebook (spaCy `lemma_`, lemma bigrams) | — | Grounded |
| Custom POS (rule + ML) | L4 (rule vs statistical vs neural) | NLTK POS comparison notebook (RegexpTagger, n-gram backoff, Affix); POS_TAGGING notebook (KNN, features, accuracy) | — | Grounded |
| NER + domain entity rules | L6 (rule vs neural, evaluation); L8 (adding pipeline components) | spaCy pipeline cells (tokenization notebook) | spaCy entity label scheme (verify at implementation) | Grounded |
| N-grams 1–5 | L9 (n-grams, vocabulary growth) | Language Model notebook | — | Grounded |
| Pipelines A/B, order effects | L2 P#4 (compare orders of preprocessing); L8 | — | Manning et al. 2008, ch. 2; Lucene StopFilter position increments | Grounded |
| Positional index, phrase search | — | LAB1 ex. 2 (document-level index only) | Manning et al. 2008, ch. 2; Brin & Page 1998 (hit lists with positions) | Extension (required by phrase search) |
| Ranking for P@K | L9 (TF-IDF); L26 (top-K ranking) | — | Manning et al. 2008, ch. 6–8; Brin & Page 1998 | Grounded |
| P/R/F1, P@K, R@K | L6 (evaluation metrics) | POS_TAGGING notebook (`classification_report`) | Manning et al. 2008, ch. 8 | Grounded |
| EXP-01 via Wikipedia API | — | Regex notebook (Wikipedia API request) | — | Grounded |
| Preregistration, logs | PO4 | — | — | Grounded |
| Relevance protocol (A1+A2 pass) | — (not in course) | — | Voorhees 2000 (TREC pooling) | Documented as amendment |

## References (verified)
- Brin, S. & Page, L. (1998). The Anatomy of a Large-Scale Hypertextual Web Search Engine. WWW7. http://infolab.stanford.edu/~backrub/google.html
- Manning, C. D., Raghavan, P. & Schütze, H. (2008). Introduction to Information Retrieval. Cambridge University Press. (Stop words: §2.2.2.)
- Paice, C. D. (1990). Another stemmer. ACM SIGIR Forum 24(3), 56–61.
- Paice, C. D. (1994). An evaluation method for stemming algorithms. SIGIR '94, pp. 42–50. doi:10.1007/978-1-4471-2099-5_5
- Porter, M. F. (1980). An algorithm for suffix stripping. Program 14(3), 130–137.
- Sennrich, R., Haddow, B. & Birch, A. (2016). Neural Machine Translation of Rare Words with Subword Units. ACL.
- Voorhees, E. M. (2000). Variations in relevance judgments and the measurement of retrieval effectiveness. *Information Processing & Management* 36(5), 697–716.
- Zhang, X. et al. (2023). MIRACL: A Multilingual Retrieval Dataset Covering 18 Diverse Languages. TACL.
- Apache Lucene documentation: `org.apache.lucene.analysis` (token position increments; StopFilter).
- Course textbooks (course plan): Jurafsky & Martin, *Speech and Language Processing*; Bird, Klein & Loper, *Natural Language Processing with Python*.

---

## Open decisions

1. Document unit: single passages / full articles / articles rebuilt from judged passages. **Settled 30.09**: full Wikipedia articles (47 of them), chosen because MIRACL's judged pools point at articles whose text is retrievable in full via the Wikipedia API; passages would be too thin for n-gram and BPE analysis.
2. Final 12–15 queries and their Boolean/phrase formulations. **Settled 30.09**: 12 queries auto-picked by the Notebook 1 §1 cluster-balanced selector, decorated with keyword/phrase/AND/OR/NOT operators in Notebook 2 §1.
3. Pipeline A and Pipeline B definitions. **Settled 29.09** in PREREGISTRATION.md §5.
4. Gold-set sizes (tokenization, POS, NER) and annotation protocol. **POS settled 30.09** by A2 (~200 tokens, Penn Treebank). **NER pending** B2.
5. GUI framework. **Pending** B2 (Day 4).

---

### Amendment — Single-author completion, query reformulation, corrected Module 2 measurements (01.10.2026)


**Context.** From 01.10.2026 the project is completed by one team member (A1). All remaining work (re-runs, comparison, GUI, report) is done in one notebook, `90_SUBMISSION/Domain_Text_Analysis_Retrieval.ipynb`, which uses `vgir.py` unchanged.

**1. Corpus size.** The final corpus has 53 documents (D01–D53), not 47 as written in EXP-01. 53 is inside the preregistered range (40–55, PREREGISTRATION §3). `03_CORPUS/manifest.csv` is authoritative.

**2. Query forms (supersedes the PREREGISTRATION §4 table and the auto-decoration in `notebook_A2_retrieval.ipynb` §1).**
- The §4 table was a template placeholder (placeholder qids `train:1`–`train:12`). Its topics are mostly absent from the corpus and were never judged, so it cannot be evaluated.
- The auto-decoration took the first content words of each MIRACL question and produced forms that do not express the information need (e.g. Q02 `"there Sonic game"`, Q10 `third AND NOT person`).
- The 12 information needs (the MIRACL questions) and `relevance.tsv` are unchanged. New forms were written by hand under this rule: (a) only words from the question; (b) aimed at the question's main entity; (c) query type chosen to fit the question; (d) coverage of 2 keyword, 3 phrase, 3 AND, 2 OR and 2 NOT queries, spanning unigram, bigram and trigram.

| our_qid | MIRACL question | New form | Type |
|---|---|---|---|
| Q01 | How many units has Total War sold? | `Total War` | keyword |
| Q02 | Was there a Sonic game on the Sega Genesis? | `Sonic AND "Sega Genesis"` | AND |
| Q03 | Did Nintendo help make PlayStation? | `Nintendo AND PlayStation` | AND |
| Q04 | Who plays the voice of Ash Ketchum in the English version of Pokemon? | `"Ash Ketchum" AND NOT Japanese` | NOT |
| Q05 | Who are the main villains of Metroid? | `Metroid` | keyword |
| Q06 | Who wrote the Zelda theme song? | `Zelda AND (theme OR song)` | OR |
| Q07 | When was the first Tomb Raider published? | `"Tomb Raider"` | phrase |
| Q08 | Is Cloud in Kingdom Hearts? | `Cloud AND "Kingdom Hearts"` | AND |
| Q09 | When was Guitar Hero Live first released? | `"Guitar Hero Live"` | phrase |
| Q10 | What was the first third person shooter? | `shooter AND NOT "first person"` | NOT |
| Q11 | What was the first video game? | `"first video game"` | phrase |
| Q12 | When was the Super Nintendo Entertainment System first introduced? | `SNES OR "Super Nintendo Entertainment System"` | OR |

**Bias disclosure.** These forms were written after the macro-F1 of both pipelines on the auto-generated forms had been seen (A 0.183, B 0.237). The per-document results of the new forms were not inspected before they were fixed. The auto-form results are kept and reported as EXPLORATORY (reproduction check).

**3. Discarded outputs.**
- `20_PIPELINE_B/results_B/stemming_lemmatization.csv`: the OI/UI values were typed in by hand in `notebook_B1.ipynb`, not computed.
- `20_PIPELINE_B/results_B/ner_results.csv`: it checked only whether the entity text appeared, never the label, and processed only the first 5,000 characters of each body.

Both are replaced by computed versions in the submission notebook.

**4. Paice groups (PREREGISTRATION §6).** The over-stemming trap requires `universe` and `university/universities` to be in different concept groups. `notebook_A1.ipynb` §6 placed them in one group, so over-stemming could not register (OI = 0 for every method). Corrected groups: develop*, release*, play*, game*, {universe}, {university, universities}.

**5. NER evaluation (Exercise 13).**
- Evaluation is corpus-level against `ner_gold.tsv` (51 entities, no document ids), over full documents, classifying each gold entity as correct (text and label), incorrect (text found with another label) or missed.
- A second system adds a spaCy `EntityRuler` built from `domain_lexicon.json`, placed before `ner` (Course Plan L8). It maps platforms and titles to PRODUCT, companies to ORG and events to EVENT. Hideo Kojima is listed under companies in the lexicon, so he is mapped to PERSON.

**6. N-grams and comparison metrics.**
- Identical code for both pipelines, over each document's index-term sequence (title and body).
- The meaningful-bigram rate is computed on the top 20 (PREREGISTRATION §7), using the NLTK stop list for the edge test in both pipelines.
- Domain-term preservation follows §8, using `vgir.domain_term_preservation`.

**7. Relevance judgments.** A four-person re-verification is no longer possible. The two-person pass (amendment to EXP-02) stands, and all retrieval numbers are labelled preliminary.

**8. Known engine behaviour (vgir.py unchanged, reported as limitations).**
- idf = log(N/df) is 0 for a term in every document, so such queries rank by document id.
- Single-term operands also match lexicon MWE components by substring (`QueryEngine.operand`), which broadens recall.

**Unchanged.** Pipelines A and B, metrics, K values, hypotheses H1–H6 and the selection rule (§9).

**Addendum (01.10.2026, recorded after the first full run of the submission notebook; these are observations, not changes to the protocol).**
- *Reproduction.* With the original auto-generated query forms, the notebook reproduces both earlier result files exactly (12/12 queries for A and for B; macro-F1 A 0.1834, B 0.2371), so the pipelines and indexes are unchanged.
- *Result on the amended queries.* A and B retrieve identical document sets for all 12 queries (macro-F1 0.6478 each). Selection rule step 1 cannot fire (delta F1 = 0); step 2 fires: domain-term preservation A 1.000 vs B 0.898 (gap 0.102 >= 0.05), so **Pipeline A is the Final Pipeline**. Under the superseded auto-generated forms, step 1 would have selected B (delta F1 = 0.054, driven by Q02 alone). Both results are reported; the amended set is the confirmatory one.
- *Implementation vs preregistration (Pipeline A step 3).* `vgir.pipeline_A` runs the spaCy tagger and lemmatizer but not the NER component, so NER does not influence A's index terms; multi-word entities are protected by the lexicon MWE merge in the shared tokenizer instead. NER is evaluated separately (Exercise 13).
- *Section 7 measure.* The meaningful-n-gram test uses the NLTK stop list at the edges for both pipelines, which mechanically favours B (A keeps most function words), and it does not treat the possessive clitic `'s` as a stop word (5 of B's top-20 bigrams contain `'s`). Reported as a limitation; it did not decide the selection.
- *H4.* None of the 12 amended queries contains an internal stop word, so H4 is examined with an exploratory 8-phrase probe (`h4_phrase_gap_probe_EXPLORATORY.csv`).

### Amendment — Pre-submission audit (01.10.2026)
An audit against the assignment brief and the preregistration, carried out after the submission notebook first ran end to end.

1. **POS rule tagger corrected (Exercise 12).**
   - *Problem.* The first version of `rule_only` contained closed-class word lists (e.g. *behind, across, until*) chosen after reading `pos_gold.tsv`. That leaks the gold set into the tagger.
   - *Fix.* Replaced with the RegexpTagger patterns from the course's NLTK POS lab, plus three rules not derived from the gold: domain lexicon names map to NNP, capitalised non-initial words map to NNP, and Penn Treebank conventions apply for punctuation and possessive `'s`.
   - *Effect.* Accuracy falls from 0.827 to 0.504; the earlier figure is void. `rule_custom` (lexicon override on NLTK) and `knn_custom` were not affected.
2. **POS gold size.** PREREGISTRATION §10 asks for about 200 tokens across 15–20 sentences. `pos_gold.tsv` has 226 tokens in only 8 sentences. Accepted as is: the accuracy differences between the strong taggers (0.982 vs 0.987) amount to one token and are not interpreted as meaningful, and the KNN result (5-fold cross-validation on 226 tokens) is reported as indicative only.
3. **NER labels.** The domain EntityRuler maps titles and platforms to PRODUCT, following the assignment's 7-type scheme (which has no WORK_OF_ART). This is the same convention the original Notebook 1 §9 used before the gold file existed.
4. **Outputs added to meet the brief.**
   - `unified_corpus.jsonl` (Module 1 "unified corpus").
   - `table_I_retrieval_results.csv` (Table I layout).
   - `tokenizer_domain_terms.csv`, the evidence for choosing the hybrid tokenizer: it keeps 91/91 multi-word lexicon names as one token, against 0/91 for NLTK, spaCy and the regex tokenizer.
5. **Additional EXPLORATORY analysis.** Each MIRACL question was run as an OR of all its words, to see whether the pipeline choice matters for verbose queries containing stop words and inflected verbs. Macro P@5 is 0.533 for both pipelines and macro R@10 is A 0.794 vs B 0.798; differences appear only on single queries (Q07 favours A, Q11 favours B). This supports the confirmatory finding that, on this corpus, the order of normalisation has a negligible effect on retrieval.
6. **Relevance-judgment problems** observed during error analysis. `relevance.tsv` stays locked and unchanged; these are classified as *relevance-judgment* errors (PREREGISTRATION §12):
   - D41 (*Sakura Wars*) is marked relevant to Q01 ("How many units has Total War sold?") but never mentions Total War. The label is inherited from a MIRACL positive.
   - D11 (*Early history of video games*) and D35 (*Pre-rendering*) are marked relevant to Q10 ("first third person shooter"). Neither discusses third-person shooters.
7. **Optimistic retrieval scores.** Every document was fetched from the judged pool of one of the 12 queries, so the collection is query-centred. Absolute retrieval scores are higher than they would be on a natural collection; the A vs B comparison is unaffected because both pipelines face the same collection.
8. **Project layout.**
   - *Canonical folder.* From this entry on, the canonical project is the `Domain_Text_Analysis_Retrieval/` repository: the submission notebook, `vgir.py`, `data/`, `results/`, and `docs/`, which holds this log and the preregistration.
   - *Team-workspace files left out:* the discarded B1 stemming and B2 NER CSVs (amendment of 01.10.2026, item 3), the unrun template `02_Retrieval_and_GUI.ipynb`, and course material that may not be redistributed.
   - *Provenance kept.* The notebooks that built the corpus and produced the earlier runs are kept in `history/`.
9. **Environment.** The submission results were produced with Python 3.14.7, spaCy 3.8.13 (`en_core_web_sm`), NLTK 3.10.3 and scikit-learn 1.8.0 on Windows (`results/environment.json`). The earlier Colab runs are reproduced exactly (12/12 queries per pipeline), apart from timings.

### Amendment — Report production (02.10.2026)
1. **New exploratory analysis.** `mwe_expansion_EXPLORATORY.csv` measures what the query engine's two expansion layers contribute: matching merged names by whole component, and the substring fallback.
   - *Effect.* Turning both off lowers macro recall from 0.805 to 0.764 and raises precision from 0.596 to 0.617. F1 stays within 0.641–0.648, and at most 2 queries change.
   - *Use.* The report presents the expansions as a measured recall-oriented choice.
2. **Error classification.** Every false negative and false positive was classified by hand, using the category list in PREREGISTRATION §12 plus "query formulation". The classification, with the evidence for each special case, is in `docs/error_analysis_classification.csv`.
   - *Result.* 9 FN and 56 FP per pipeline, identical in A and B: 54 passing-mention FPs, 6 query-formulation FNs, 3 FNs and 2 FPs due to relevance judgments, and none due to tokenization, stemming, lemmatization, stop words or NER.
3. **Claims omitted from the report.** Two framing claims supplied for the report are not recorded in any earlier entry, so the report leaves them out:
   - that NFCorpus was among the datasets considered;
   - that video games is the only MIRACL theme yielding all seven NER types.

   The report uses only the alternatives and reasons recorded in DEC-000 and DEC-001.
4. **Claims checked against sources before use.**
   - *Brin & Page (1998).* Stemming listed as future work (§6.1), Table 2's initial vs repeated query times, "fancy hits", and count-weights that taper off: all checked against the paper.
   - *MIRACL.* The English corpus comes from the 2019-02-01 Wikipedia dump: checked against the dataset card.

### Amendment — GUI redesign (02.10.2026)
The GUI was rebuilt to a design brief: diagnostic-instrument styling and one accent colour per pipeline. It adds four views:
- **Pipeline Trace:** streams Pipeline A or B stage by stage, with real per-stage timings.
- **Tokenization Lab:** token chips for each tokenizer.
- **Compare A vs B:** the same query through both pipelines, with a diff region.
- **Index Explorer:** postings with click-to-expand context.

All 15 required functions remain, and no method, result or metric changed.

Two safeguards keep the visualisation honest:
1. **Pause between stages.** The trace waits 0.15 s between stages so each one can be seen. This is labelled as a visualisation pause in the code, the notebook and the report; the time shown per stage is the measured compute time.
2. **Self-check.** The trace re-implements the two pipelines stage by stage, so a self-check asserts that its final terms are identical to `vgir.pipeline_A` / `vgir.pipeline_B`.

Three elements of the brief were not built:
- keyboard-shortcut hints that would not work, because a hint that does nothing misleads the user;
- a dark-mode toggle, because the palette is light only and Gradio's own dark theme is suppressed so it cannot clash;
- cross-row token highlighting, because it would need custom JavaScript.

Gradio 6 is now required (`requirements.txt`), because custom CSS is passed at launch.

### Amendment — GUI motion polish (02.10.2026)
The GUI's motion was reviewed against Emil Kowalski's design-engineering guidelines (`emil-design-eng` skill), and the following were fixed. There is no effect on any method or result.

**Bug fixed.** The streamed Pipeline Trace re-rendered all completed stages on every step, so each one replayed its entry animation. Only the newly finished stage animates now.

**Motion changes:**
- Transitions name the exact properties (`transition: all` removed).
- Hover effects apply only on devices with a fine pointer.
- Buttons scale to 0.97 when pressed.
- Entries use a strong ease-out curve, under 250 ms.
- The shimmer and the scanner sweep run at a constant (linear) speed, and the scanner animates `transform` instead of `left`.
- Tokenizer rows and the two comparison columns enter one after another, 40–60 ms apart.
- With `prefers-reduced-motion`, movement is replaced by simple fades.

### Amendment — Stage-wise evaluation, index description and report rewrite (02.10.2026)
**Trigger.** Guidance given in class asked for:
- a view of the indexer's data structure, with comparison to Lucene/Elasticsearch;
- the role of every component;
- performance measured at each stage with accuracy, precision, recall, F1 and confusion matrices;
- a GUI that works as a searcher.

**Analyses added.** All are descriptive and change no method or earlier result.

| Analysis | Files |
|---|---|
| POS per-tag P/R/F1 and confusion | `pos_per_tag_metrics.csv`, `pos_confusion_errors.csv`, `pos_confusion_matrix_nltk.csv` |
| NER confusion matrices and per-type P/R/F1 | `ner_confusion_default.csv`, `ner_confusion_ruler.csv`, `ner_per_type_metrics.csv` |
| Retrieval confusion matrix with accuracy | `retrieval_confusion_per_query.csv`, `retrieval_confusion_total.csv` |
| Size and shape of the positional index | `index_structure.csv` |

**Main results.**
- **Retrieval, pooled over queries:** TP 48, FP 56, FN 9, TN 523; accuracy 0.898, against 0.910 for a system that retrieves nothing. This is why precision and recall, not accuracy, are the retrieval metrics.
- **NER, mean F1 over types:** 0.563 default, 0.744 with the EntityRuler.
- **POS, mean F1 over tags:** NLTK 0.988, rule + dictionary 0.990.

**Caveat.** NER precision is computed over the gold entity list only, because the gold set has no positions.

**Tokenizer quirk found.** The money rule in `vgir.TOKEN_RX` keeps a trailing comma (e.g. `$1,000,000,`). It is reported as a limitation; `vgir.py` is unchanged.

**Report rewrite.**
- *Structure.* The report is now organised around the system's components rather than assignment modules, with a plain-language and a technical explanation for each. The mapping to the brief's items is in Appendix A.
- *Corpus size.* The class guidance of 10–15 documents is acknowledged. The 53-document corpus is retained (preregistered range 40–55), with the reasons stated in report §3.1.

### Amendment — GUI upload progress (03.10.2026)
Animation plan `plans/001-stream-upload-rebuild-progress.md` was executed. After a document upload, the GUI now streams three stage cards (add documents, rebuild index A, rebuild index B) with their measured times, instead of a silent wait of up to a minute.

- **Code.** `gui_upload` became a generator, and the message component became HTML. No method or result changed.
- **Verification.**
  - The executor's diff matches the plan exactly.
  - Browser feel check: the stages move from waiting to running to done in order; only the newest card plays its entry animation; index A took 24.0 s and index B 2.7 s.
  - The notebook was re-executed and the report's timing numbers re-synced.

### Amendment — Index Explorer context entrance (03.10.2026)
Animation plan `plans/002-settle-postings-context-on-open.md` was executed: two CSS lines and no other change.

- **Effect.** Opening a postings row in the Index Explorer fades its context in with a 4 px settle (180 ms, `cubic-bezier(0.23, 1, 0.32, 1)`). Closing stays instant, and reduced motion gives a 150 ms fade.
- **Verification.**
  - The executor's diff is exactly the two planned lines.
  - In the browser, the animation finishes at 180 ms at full opacity and its final position; rapid toggling never leaves the text half-transparent.
  - The notebook was re-executed and the report's timings re-synced.

### Amendment — GUI layout and on-screen copy (03.10.2026)
A design audit of the GUI, made against `docs/PRODUCT.md` (audience: the grader; tone: precise, calm, explanatory), found four problems:

- **Horizontal scroll on phones.** The container was fixed at 1200 px.
- **Hidden tabs.** At 1280 px, four of the twelve tabs sat behind an overflow menu.
- **Low contrast.** Pipeline-coloured text measured 2.9–4.4:1, and stop-word chips 2.2:1.
- **Unexplained screens.** Labels were generic ("Text", "Show", "Encode") and tables were raw, with no explanation.

Changes (GUI only; no analysis code, result or metric changed):

- **Fewer tabs.** Twelve tabs became nine, in reading order: Search, Compare A vs B, Pipeline trace, Corpus, Tokenization (with BPE), POS & NER, N-grams, Index, Evaluation. All fit on one row at 1280 px.
- **Explained screens.** Every tab opens with a one-line intro saying what it shows and what to notice. Every table has a heading and a one-line note, and column names are plain words.
- **Specific labels.** Buttons say what they do ("Run on both pipelines", "Look up in the index"). Query types are readable ("All words (AND)"), while the internal values are unchanged.
- **Search.** The tab shows an empty state before the first query. For the 12 evaluation queries it adds a "judged relevant" column, and when nothing matches it explains why.
- **Readability.** Darker ink tokens bring pipeline-coloured text and muted chips to WCAG AA (≥ 4.5:1); the bright pipeline colours remain for borders only. A 4 px spacing scale is used throughout, the layout is fluid down to 375 px, and comparison panels wrap.
- **Self-test.** The test now also runs the two merged handlers and checks for the relevance column.
- **Phone rules location.** The phone rules are in the page `<head>` rather than in Gradio's `css=`, because Gradio scopes media queries under `.contain`, so container-level rules there never applied.
- **Re-run.** Figures 2–5 were recaptured at 1280 × 821, the notebook was re-executed, and the report's timings were re-synced.

### Amendment — Report GUI section expanded; Word version (03.10.2026)
- **GUI section (§9).** The section now explains how the GUI is built: layout, handlers, the shared state with the notebook, streaming and the self-test. It adds a two-minute tour, and covers each tab under three headings: what you see, how it works, what to notice. Three screenshots were added (Search, POS & NER, Evaluation), so Figures 2–8 are now GUI screenshots. Every "what to notice" claim was checked against the results files and the report sections it cites.
- **Word version.** `Report.docx` is generated from `Report.md` through Microsoft Word (`tools/report_to_docx.py`), with images embedded and Word heading styles. The PDF was rebuilt from the same Markdown.

### Amendment — Presentation (03.10.2026)
A Beamer deck was added in `presentation/` (`slides.tex`, `slides.pdf`, `references.bib`, `SPEAKER_NOTES.md`).

- **Structure.** It follows the brief's Select → Order → Implement → Compare → Evaluate → Justify sequence.
- **Sources.** Every number is taken from `results/` or the report.
- **Look.** It follows the structure of the supplied template, but uses a self-contained theme instead of Masaryk University's `MU` theme, which is not on CTAN and carries that university's branding.
- **Build.** It was compiled with Tectonic (XeTeX), and every slide was checked visually for overflow.
