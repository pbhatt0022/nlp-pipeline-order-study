# Speaker notes

The deck is `slides.pdf`, built from `slides.tex`. It has 27 numbered slides (numbers as in the footer) plus 5 unnumbered roadmap slides, and runs about **15 minutes**. Presenters (alphabetical): Priyanka B, Sachin B, Tiya P, Vaidhav A.

- **To rebuild locally:** `tectonic -X compile slides.tex`.
- **To build on Overleaf:** upload this folder and set the compiler to **XeLaTeX** or **LuaLaTeX**. The Fira fonts need one of these; pdfLaTeX will not work.

**If you are short on time,** skip:

- 6 (BPE);
- 9 (N-grams);
- 11 (why each step sits where it does);
- 14 (the 12 queries).

Mention each of these in one sentence instead.

The thread to keep repeating is the brief's own objective: **Select → Order → Implement → Compare → Evaluate → Justify**. The roadmap slides mark where you are in it.

---

## The Problem (≈2 min)

**1. Title.** One sentence: "We built a complete search engine for video-game articles, and asked whether the *order* of text processing changes what it finds."

**2. What we built.**
- A search engine has two halves: the indexer, built ahead of time, and the searcher, used at question time.
- Everything between raw text and the index decides which "words" exist. That is the decision our two pipelines disagree on.
- Point at the diagram: the query goes through the *same* pipeline as the documents.

**3. Domain and data.**
- Video games are hard for generic tools: names with hyphens and numbers, names made of ordinary words, spelling variants.
- The corpus comes from MIRACL, a public retrieval benchmark: 12 real questions and the Wikipedia articles judged for them.
- Those articles include *hard negatives*: on-topic articles judged not relevant, which make retrieval harder.
- **Why 53 documents, not 15:**
  - each question needs several relevant documents and some negatives, otherwise recall can only ever be 0 or 1;
  - the 53 documents were fixed in the preregistration.

**4. Gold standards.**
- Every stage that makes a decision has an answer key.
- Stress the process:
  - hypotheses and the selection rule were written down **before** any result;
  - every later change is a dated amendment in the decision log.
- The relevance labels come from two reviewers, so search numbers are called *preliminary*. Say this up front: it builds trust.

## Select (≈3.5 min)

**5. Tokenization.**
- This is the most important slide of the talk.
- General tokenizers keep **0 of 91** multi-word names intact; the hybrid keeps **91 of 91**.
- Read the Counter-Strike example aloud: spaCy produces six pieces, the hybrid one token.
- The hybrid tokenizer is used in both pipelines. Its limit: it only knows the names in the lexicon.

**6. BPE.**
- BPE never meets an unknown word and keeps the vocabulary tiny: 3,242 types.
- But *met | roid* is not something a user types.
- So BPE was analysed but not used for the index.
- Nice detail: the corpus-trained model learned *nintendo* as one piece; GPT-2 splits it into *n | intendo*.

**7. Stemming and lemmatization.**
- We planted a trap: *universe* vs *university*. Every stemmer falls into it; lemmatizers never over-merge.
- **Order matters:** Porter run before stop-word removal leaks *thi*, *wa*, *ha* into the index. That is why B removes stop words first and uses Snowball.

**8. POS and NER.**
- spaCy calls *Prey*, *Doom* and *Halo* people. A lexicon-driven EntityRuler fixes this: 29 → 37 of 51 entities correct.
- Be honest about POS: the dictionary tagger's gain over NLTK is **one token** out of 226, which is within noise.

**9. N-grams.**
- Almost every long sequence is unique, which is why a "phrase" must occur at least twice.
- A's top bigrams are grammar (*it be*); B's are content (*lara croft*).
- The meaningful-bigram test is biased toward B, because it checks against the stop list B has already removed. We report that bias ourselves.

## Order (≈2.5 min)

**10. The two pipelines.**
- **A** is the linguist: tag while the capitals are still there, then reduce words to dictionary forms. Bet: careful analysis keeps names intact.
- **B** is the IR engineer: lowercase, drop all stop words, stem. Bet: aggressive merging gives more matches and a smaller index.

**11. Why each step sits where it does.**
- This answers the brief's mandatory questions: why each process, where it sits, what it depends on, what breaks if it moves.
- Pick two rows to say aloud:
  - tagging before lowercasing (otherwise *Halo* gets lemmatized);
  - stop words before stemming (otherwise *thi* and *wa* leak into the index).

**12. One sentence through both.**
- A keeps real words (*release*, *praise*); B keeps stems (*releas*, *prais*).
- Both keep names identical, because the tokenizer merged them first. This foreshadows the result.

## Implement (≈1.5 min)

**13. Inverted index.**
- Term → document → positions. Positions are what make phrase search possible.
- More than half of all terms occur in one document only. Terms found in every document get an idf of 0, which is the formal version of a stop word.

**14. Searcher.**
- Boolean logic decides *which* documents match: AND intersects, OR unites, NOT subtracts. Phrases are checked by position.
- Ranking decides *in what order*: TF-IDF with title matches counting double.
- The 12 queries cover keyword, phrase, AND, OR and NOT.

## Compare & Evaluate (≈3 min)

**15. Hypotheses.**
- Six predictions, written before running anything.
- Three held: B is smaller (H1), B makes false phrase matches (H4), A keeps names (H5).
- Three did not: no recall difference (H2), no precision difference (H3), and the bigram test went the other way (H6).
- Say it plainly: **reporting the failed predictions is part of the result.**

**16. Table H.**
- B's index is 29% smaller. A keeps all 128 names; B breaks 13 of them (*Civilization* → *civil*).
- Search results are identical on all 12 queries.

**17. Retrieval.**
- AND and phrase queries do best; NOT does worst.
- The accuracy point: our searcher scores 0.898, but returning *nothing* scores 0.910. That is why accuracy is useless for search, and why we report precision and recall.

**18. Errors.**
- Every error was classified:
  - 54 of the 56 false hits are passing mentions;
  - 6 misses come from query logic;
  - 3 misses come from labels that look wrong.
- **Zero** errors come from any preprocessing step. That is exactly why A and B tie.

## Justify (≈2 min)

**19. Final pipeline.**
- The rule was fixed in advance. F1 ties (0.648 each), so the tie-breaker decides: name preservation 1.000 vs 0.898, which **selects A**.
- Key line: "A is not chosen because it searches better; it doesn't. It's chosen because, at equal search quality, its index represents the domain faithfully."
- Mention the costs: a larger index and slower indexing.

**20. The earlier run chose B.**
- This is your strongest reasoning slide; take your time.
- An automatically worded query, `"there Sonic game"`, decided the whole comparison: B dropped *there*, A did not.
- We reproduced that run exactly. Then we rewrote the queries under a stated rule *before* seeing new results, and reported both runs.
- The finding: pipeline differences come from **query wording**, not from domain content.

**21. Design lesson.**
- On an entity-heavy domain, the tokenizer and lexicon decide more than stemming vs lemmatization does.
- Label this as exploratory: we did not run a pipeline without name merging.

## Demonstration and close (≈1.5 min + demo)

**22. GUI.**
- Nine tabs cover all 15 required functions, and every button runs the real pipelines.
- If there is time, demo live:
  1. Search with Q03;
  2. Compare A vs B on Q02;
  3. Pipeline trace on the default sentence;
  4. Index lookup for *Game Boy*, then open D08.

**23. Limitations.**
- Name them before you are asked:
  - preliminary relevance labels;
  - only 12 queries;
  - a corpus built around its queries;
  - lexicon coverage.

**24. Conclusion.**
- Read the five points.
- Close with: "All search results are preliminary until the relevance labels are re-judged."

---

## Likely questions

**"If both pipelines score the same, isn't the choice arbitrary?"**
No. The rule and its tie-breaker were fixed before any result. Name preservation is a real property of the index: it is what a person sees in the term dictionary, the postings and the n-grams. The rule only falls through to it because search quality ties.

**"You rewrote the queries after seeing results. Isn't that p-hacking?"**
- The rewrite followed a stated rule: words from the question only, aimed at its main entity, every query type covered.
- It was made before any result for the new wording existed, and the automatic queries did not express their questions at all (`units`, `wrote`).
- Both runs are reported, and the earlier run is reproduced exactly (12 of 12 queries).
- The reversal is reported as a finding, not hidden.

**"Why not index with BPE?"**
Users search with words and names. Sub-word pieces such as *met | roid* would match unrelated words that share the piece, and they make postings unreadable. BPE was analysed as the brief asks, not used for retrieval.

**"Why is accuracy 0.898 bad if it's high?"**
Only 57 of the 636 pairs are relevant, so labelling everything "not relevant" already scores 0.910. Precision and recall look only at what matters: the relevant documents.

**"Why 53 documents?"**
With 15 documents, most questions would have one relevant document, so recall can only be 0 or 1. Each question needed several relevant articles plus hard negatives, and the relevance judgments were made for these 53 documents.

**"Why TF-IDF rather than BM25?"**
TF-IDF is the ranking taught in the course (L9 and L26), and ranking is not what the pipeline comparison tests. BM25, Lucene's default, is listed as a next step.

**"What would make A and B differ?"**
Queries that contain stop words or inflected forms: wordy questions, and phrases with stop words inside (H4). Also more queries, and a one-component-at-a-time ablation.
