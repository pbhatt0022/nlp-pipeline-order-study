"""Source of Domain_Text_Analysis_Retrieval.ipynb (the submission notebook).
Edit cells here, then regenerate:  python tools/build_notebook.py   (needs nbformat).
The generated notebook has no outputs; run it to produce results/."""
import os
import nbformat as nbf

cells = []
def md(s): cells.append(nbf.v4.new_markdown_cell(s.strip()))
def code(s): cells.append(nbf.v4.new_code_cell(s.strip()))

md(r"""
# Domain-Specific Text Analysis and Retrieval System: Video Games
NLP Assessment-1 (DATA403). Single notebook covering Modules 1-6, the Pipeline A vs B experiment, final-pipeline selection and the GUI.

**Governing documents.** `docs/PREREGISTRATION.md` (hypotheses, pipelines, metrics, selection rule, frozen 29.09.2026) and `docs/DECISION_LOG.md` (decisions, experiments, dated amendments). The query reformulation, corrected Paice groups and corrected NER evaluation used below are recorded in the amendment dated 01.10.2026.

**Shared library.** All tokenizers, both pipelines, the positional index, the query engine and the metrics come from `vgir.py` (unchanged since the pipelines were frozen). This notebook only orchestrates, measures and reports.

**Run order.** Top to bottom from the project folder (locally) or from the project folder on Google Drive (Colab; the first cell mounts Drive and installs `requirements.txt`). Runtime is about 10 minutes, mostly spaCy over the corpus (Pipeline A index, NER).
""")

code(r"""
# 0. Setup: works in Colab (Drive) and locally (current folder or PROJECT_ROOT).
import os, sys, subprocess, json, re, time, math, statistics, shutil
from collections import Counter, defaultdict

IN_COLAB = 'google.colab' in sys.modules
if IN_COLAB:
    from google.colab import drive
    drive.mount('/content/drive')
    ROOT = '/content/drive/MyDrive/Domain_Text_Analysis_Retrieval'   # the folder that holds this notebook
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-r', f'{ROOT}/requirements.txt'], check=True)
    subprocess.run([sys.executable, '-m', 'spacy', 'download', 'en_core_web_sm', '-q'], check=True)
else:
    ROOT = os.environ.get('PROJECT_ROOT', os.getcwd())
assert os.path.isfile(f'{ROOT}/vgir.py'), f'vgir.py not found in {ROOT}; set ROOT to the project folder'

DATA, GOLD, RES = f'{ROOT}/data', f'{ROOT}/data/gold', f'{ROOT}/results'
os.makedirs(RES, exist_ok=True)
sys.path.insert(0, ROOT)
import vgir
# vgir looks for the lexicon under <base>/01_FROZEN/; in this layout it lives in data/. Redirect that one path
# (vgir.py itself stays unchanged).
_vgir_P = vgir.P
vgir.P = lambda *parts: f'{DATA}/domain_lexicon.json' if parts and parts[-1] == 'domain_lexicon.json' else _vgir_P(*parts)
import pandas as pd
pd.set_option('display.max_colwidth', 120)
vgir.ensure_nltk()
from nltk.corpus import stopwords
STOP_NLTK = vgir.stop_nltk()

def save(df, name):
    # Every result table is written to results/ (assignment section 11 structure).
    df.to_csv(f'{RES}/{name}', index=False)
    return df

import platform, nltk, sklearn, spacy
ENV = {'python': platform.python_version(), 'platform': platform.platform(), 'nltk': nltk.__version__,
       'spacy': spacy.__version__, 'scikit-learn': sklearn.__version__, 'pandas': pd.__version__}
json.dump(ENV, open(f'{RES}/environment.json', 'w'), indent=2)
print(ENV)
print('ROOT:', ROOT)
print('lexicon entries:', len(vgir.lexicon_entries()))
""")

# ------------------------------------------------------------------ Module 1
md(r"""
## Module 1: Document collection and extraction
Source: MIRACL English (train + dev), video-games theme (DEC-000, DEC-001). For each of 12 MIRACL questions, up to 4 positive and 2 negative judged Wikipedia articles were fetched as full articles through the MediaWiki API, filtered for video-game content, and saved as `D01.txt`-`D53.txt` (first line = title). Build-time issues and fixes are documented in DECISION_LOG EXP-01. Cleaning (shared by both pipelines): NFKC normalisation, diacritic folding, quote normalisation, citation markers, section headings to sentences, whitespace (`vgir.clean_text`).
""")

code(r"""
docs = vgir.load_corpus(DATA)                       # applies vgir.clean_text to title and body
manifest = pd.read_csv(f'{DATA}/manifest.csv')
assert set(docs) == set(manifest.doc_id), 'corpus files and manifest disagree'
TITLE = {d: docs[d]['title'] for d in docs}
TEXT = {d: vgir.full_text(docs[d]) for d in docs}
HYB = {d: vgir.tok_hybrid(TEXT[d]) for d in docs}  # hybrid tokens, cached (used many times)

from nltk.tokenize import sent_tokenize
rows = []
for d in docs:
    toks = HYB[d]
    rows.append({'doc_id': d, 'title': TITLE[d], 'characters': len(TEXT[d]),
                 'sentences': len(sent_tokenize(TEXT[d])), 'tokens': len(toks),
                 'word_tokens': sum(not vgir.is_punct(t) for t in toks),
                 'unique_tokens': len(set(toks))})
doc_stats = save(pd.DataFrame(rows), 'document_statistics.csv')
with open(f'{RES}/unified_corpus.jsonl', 'w', encoding='utf-8') as f:     # the unified, cleaned corpus
    for d in docs:
        f.write(json.dumps({'doc_id': d, 'title': TITLE[d], 'text': docs[d]['body']}, ensure_ascii=False) + '\n')

corpus_vocab = len({t.lower() for d in docs for t in HYB[d] if not vgir.is_punct(t)})
corpus_summary = pd.DataFrame([
    ('Number of documents', len(docs)),
    ('Number of sentences', int(doc_stats.sentences.sum())),
    ('Number of tokens (hybrid, incl. punctuation)', int(doc_stats.tokens.sum())),
    ('Number of word tokens (no punctuation)', int(doc_stats.word_tokens.sum())),
    ('Number of characters', int(doc_stats.characters.sum())),
    ('Vocabulary size (case-folded word types)', corpus_vocab),
    ('Average document length (tokens)', round(doc_stats.tokens.mean(), 1)),
    ('Average document length (characters)', round(doc_stats.characters.mean(), 1)),
    ('Shortest / longest document (tokens)', f'{doc_stats.tokens.min()} / {doc_stats.tokens.max()}'),
], columns=['statistic', 'value'])
save(corpus_summary, 'corpus_summary.csv')
display(corpus_summary)
doc_stats.head()
""")

# ------------------------------------------------------------------ Module 2
md(r"""
## Module 2: Preprocessing exercises 1-14
### Exercises 1-3: built-in vs custom vs hybrid tokenization
The **custom** tokenizer is `vgir.TOKEN_RX`: rules for dotted acronyms, money, ordinals, alphanumerics (3D, PS4, 1990s), numbers with separators, possessive `'s` split, and hyphen/apostrophe compounds kept whole. The **hybrid** tokenizer adds lexicon spelling variants (Gameboy -> Game Boy, SNES -> Super Nintendo Entertainment System), splits lower-case hyphen compounds (first-person -> first person) and merges multi-word expressions from `domain_lexicon.json` (Game Boy -> `Game_Boy`), in the spirit of NLTK `MWETokenizer` and spaCy `add_special_case` from the tokenization lab.
""")

code(r"""
TOK_NAMES = ['nltk', 'spacy', 'custom', 'hybrid']
TOKS, TOK_MS = {}, {}
for name in TOK_NAMES:
    fn = vgir.TOKENIZERS[name]
    t0 = time.perf_counter()
    TOKS[name] = {d: (HYB[d] if name == 'hybrid' else fn(TEXT[d])) for d in docs}
    TOK_MS[name] = (time.perf_counter() - t0) * 1000
t0 = time.perf_counter(); [vgir.tok_hybrid(TEXT[d]) for d in docs]; TOK_MS['hybrid'] = (time.perf_counter() - t0) * 1000

def all_toks(name): return [t for d in docs for t in TOKS[name][d]]

# Exercise 1: dictionary size (raw token dictionary) vs term-based dictionary (case-folded, no punctuation)
rows = []
for name in TOK_NAMES:
    toks = all_toks(name)
    terms = [t.lower() for t in toks if not vgir.is_punct(t)]
    rows.append({'tokenizer': name, 'total_tokens': len(toks), 'unique_tokens': len(set(toks)),
                 'term_tokens': len(terms), 'term_dictionary_size': len(set(terms)),
                 'shrink_pct': round(100 * (1 - len(set(terms)) / len(set(toks))), 1),
                 'ms': round(TOK_MS[name], 1)})
tok_cmp = save(pd.DataFrame(rows), 'tokenization_comparison.csv')
tok_cmp
""")

code(r"""
# Exercise 2: what is wrong in the built-in tokenizers' dictionaries, and which process fixes it
def issues(name):
    toks = all_toks(name); types = set(toks)
    low = Counter(t.lower() for t in types)
    seq = ' '.join(toks)
    return {'tokenizer': name,
            'punctuation_types': sum(vgir.is_punct(t) for t in types),
            'case_variant_groups': sum(c > 1 for c in low.values()),
            'possessive_tokens': sum(t in ("'s", "'S", "’s") for t in toks),
            'hyphen_split_counter_strike': seq.count('Counter - Strike'),
            'game_boy_split': seq.count('Game Boy'),
            'numeric_types': sum(bool(re.fullmatch(r'[\d.,%$]+', t)) for t in types),
            'example_case_variants': ', '.join(sorted(g for g, c in low.items() if c > 1 and g.isalpha())[:6])}
builtin_issues = save(pd.DataFrame([issues(n) for n in TOK_NAMES]), 'tokenization_dictionary_issues.csv')
builtin_issues
""")

code(r"""
# Exercise 3: >= 5 domain-specific tokenization problems, four tokenizers side by side
PROBLEMS = ['Counter-Strike: Global Offensive', 'Metal Gear Solid 4: Guns of the Patriots', 'Destiny 2',
            'Game Boy vs. Gameboy', "Assassin's Creed", 'Pokémon Sun and Moon', 'PlayStation 3 and Wii U',
            'It sold $8.5 million copies in the 1990s', 'a first-person shooter (FPS) with DLC', 'SNES vs. Super NES']
rows = []
for p in PROBLEMS:
    c = vgir.clean_text(p)          # same cleaning the corpus gets before any tokenizer (folds é -> e)
    row = {'input': p}
    for name in TOK_NAMES:
        row[name] = ' | '.join(vgir.TOKENIZERS[name](c))
    rows.append(row)
tok_problems = save(pd.DataFrame(rows), 'tokenization_problems.csv')
display(tok_problems)

# Selection evidence: share of multi-word lexicon names each tokenizer keeps as ONE token
multi = [e for e in vgir.lexicon_entries() if len(vgir.tok_custom(e)) > 1]
tok_dom = pd.DataFrame([{'tokenizer': n, 'multiword_lexicon_entries': len(multi),
                         'kept_as_one_token': sum(len(vgir.TOKENIZERS[n](vgir.clean_text(e))) == 1 for e in multi)}
                        for n in TOK_NAMES])
tok_dom['share'] = (tok_dom.kept_as_one_token / tok_dom.multiword_lexicon_entries).round(3)
save(tok_dom, 'tokenizer_domain_terms.csv')
""")

md(r"""
### Exercise 4: BPE
Two BPE variants, as covered in the course: GPT-2 byte-level BPE via `tiktoken` (BPE lab) and BPE trained on our corpus with the merge algorithm from the lecture slides (`vgir.train_bpe`, characters + `</w>`, most frequent pair merged repeatedly; Sennrich et al. 2016). The corpus BPE is applied to the custom tokenizer's word tokens; non-alphabetic tokens pass through unchanged.
""")

code(r"""
word_freq = Counter(t.lower() for d in docs for t in TOKS['custom'][d] if t.isalpha())
t0 = time.perf_counter()
MERGES = vgir.train_bpe(word_freq, num_merges=1000, min_freq=2)
print(f'corpus BPE: {len(MERGES)} merges learned in {time.perf_counter()-t0:.1f}s')

_bpe_cache = {}
def corpus_bpe(w):
    if w not in _bpe_cache: _bpe_cache[w] = vgir.bpe_encode(w, MERGES)
    return _bpe_cache[w]

try:
    import tiktoken
    ENC = tiktoken.get_encoding('gpt2')
except Exception as e:
    ENC = None; print('tiktoken unavailable:', e)

def gpt2_pieces(w):
    return [ENC.decode_single_token_bytes(i).decode('utf-8', 'replace') for i in ENC.encode(w)] if ENC else ['[unavailable]']

# corpus-level token count / vocabulary for BPE, next to the word tokenizers
bpe_tokens = [p for d in docs for t in TOKS['custom'][d] for p in (corpus_bpe(t.lower()) if t.isalpha() else [t])]
rows = [{'method': n, 'total_tokens': int(tok_cmp.set_index('tokenizer').loc[n, 'total_tokens']),
         'vocabulary': int(tok_cmp.set_index('tokenizer').loc[n, 'unique_tokens'])} for n in TOK_NAMES]
rows.append({'method': 'bpe_corpus (1000 merges)', 'total_tokens': len(bpe_tokens), 'vocabulary': len(set(bpe_tokens))})
if ENC:
    ids = [i for d in docs for i in ENC.encode(TEXT[d])]
    rows.append({'method': 'bpe_gpt2 (tiktoken)', 'total_tokens': len(ids), 'vocabulary': len(set(ids))})
bpe_corpus_cmp = save(pd.DataFrame(rows), 'bpe_vs_tokenizers.csv')
display(bpe_corpus_cmp)

common = [w for w, _ in word_freq.most_common(200) if len(w) >= 4][:4]
rare = sorted((w for w, c in word_freq.items() if c == 1 and len(w) >= 9), key=lambda w: (-len(w), w))[:4]
domain = ['nintendo', 'playstation', 'metroid', 'zelda', 'pokemon', 'gameboy', 'multiplayer', 'gameplay']
rows = []
for cat, words in (('common', common), ('rare', rare), ('domain', domain)):
    for w in words:
        g, c = gpt2_pieces(w), corpus_bpe(w)
        rows.append({'Word': w, 'category': cat, 'corpus_freq': word_freq.get(w, 0),
                     'gpt2_tokens': ' | '.join(g), 'gpt2_n': len(g),
                     'corpus_bpe_tokens': ' | '.join(c), 'corpus_bpe_n': len(c),
                     'nltk': ' | '.join(vgir.tok_nltk(w)), 'hybrid': ' | '.join(vgir.tok_hybrid(w))})
bpe = pd.DataFrame(rows); bpe.insert(0, 'S.No.', range(1, len(bpe) + 1))
save(bpe, 'bpe_results.csv')
""")

md(r"""
### Exercise 5: where verbs and noun phrases matter
Demonstrated with spaCy noun chunks and verbs on a corpus sentence. Discussion of the two scenarios is in the report.
""")

code(r"""
NLP = vgir.spacy_model()
sent = next((s for s in sent_tokenize(TEXT['D28']) if 'released' in s), sent_tokenize(TEXT['D28'])[1])
sp = NLP(sent)
ex5 = pd.DataFrame([
    {'view': 'sentence', 'items': sent},
    {'view': 'noun phrases (spaCy noun_chunks)', 'items': ' | '.join(c.text for c in sp.noun_chunks)},
    {'view': 'verbs (POS=VERB)', 'items': ' | '.join(f'{t.text}->{t.lemma_}' for t in sp if t.pos_ == 'VERB')},
    {'view': 'scenario i: verbs + NPs useful', 'items': 'release-date / who-developed / who-voiced questions (e.g. Q04, Q07, Q09, Q12): the verb (released, voiced, published) selects the relation'},
    {'view': 'scenario ii: only NPs useful', 'items': 'index terms and entity lookup (catalogue of titles, platforms, companies): Game Boy, Nintendo, Tomb Raider carry the topic; verbs add little'},
])
save(ex5, 'np_vs_verbs.csv')
""")

md(r"""
### Exercise 6: dates and numbers
The domain needs numbers: sequel numbers (Destiny 2), platform names (Nintendo 64, PlayStation 3), release years and sales (units, $). Several of our questions ask *when* or *how many*. The custom tokenizer therefore keeps years, decades, money, percentages, ordinals and alphanumerics as single tokens.
""")

code(r"""
CATS = [('money', r'[$£€₹]\d[\d,]*(?:\.\d+)?'), ('decade', r'\d{4}s'), ('year', r'(?:19|20)\d{2}'),
        ('percent', r'\d[\d,.]*%'), ('ordinal', r'\d+(?:st|nd|rd|th)'),
        ('alphanumeric', r'(?:\d+[A-Za-z]+\w*|[A-Za-z]+\d+[A-Za-z\d]*)'), ('number', r'\d[\d,]*(?:\.\d+)?')]
cnt, ex = Counter(), defaultdict(Counter)
for t in all_toks('custom'):
    for cat, rx in CATS:
        if re.fullmatch(rx, t):
            cnt[cat] += 1; ex[cat][t] += 1; break
numbers = save(pd.DataFrame([{'category': c, 'tokens': cnt[c], 'distinct': len(ex[c]),
                              'examples': ', '.join(w for w, _ in ex[c].most_common(8))} for c, _ in CATS]),
               'numbers_dates.csv')
numbers
""")

md(r"""
### Exercise 7: stop-word removal
Pipeline A uses a 10-word minimal list, applied last; Pipeline B uses the standard NLTK English list (its size in the installed NLTK version is printed below) with positions kept (PREREGISTRATION section 5; Manning et al. 2008, section 2.2.2 on the move from large lists towards none, and titles made of stop words). Below: effect of none / minimal / NLTK on hybrid tokens, and lexicon titles that contain stop words (protected only because the hybrid tokenizer merges them into one MWE token before stop removal).
""")

code(r"""
words = [t.lower() for t in all_toks('hybrid') if not vgir.is_punct(t)]
rows = []
for name, stops in (('none', set()), ('minimal (A, 10 words)', vgir.STOP_MINIMAL), ('nltk (B, %d words)' % len(STOP_NLTK), STOP_NLTK)):
    kept = [w for w in words if w not in stops]
    rows.append({'stop_list': name, 'tokens_kept': len(kept), 'pct_removed': round(100 * (1 - len(kept) / len(words)), 1),
                 'vocabulary': len(set(kept))})
stop_cmp = save(pd.DataFrame(rows), 'stopword_comparison.csv')
display(stop_cmp)
titles_with_stops = [e for e in vgir.lexicon_entries() if any(w.lower() in STOP_NLTK for w in e.split())]
print(f'{len(titles_with_stops)} lexicon entries contain NLTK stop words, e.g.:', titles_with_stops[:8])
print('most frequent removed NLTK stop words:', Counter(w for w in words if w in STOP_NLTK).most_common(12))
""")

md(r"""
### Exercises 8-10: stemming, order effect, lemmatization
Over-/under-stemming are measured with Paice's (1994) OI and UI over concept groups (PREREGISTRATION section 6). Correction (amendment 01.10.2026): `universe` and `university/universities` are now separate groups, so a stemmer that conflates them is penalised as over-stemming. In the earlier run they shared a group, which made over-stemming impossible to register.
""")

code(r"""
from nltk.stem import PorterStemmer, SnowballStemmer, LancasterStemmer, WordNetLemmatizer
WNL = WordNetLemmatizer()
GROUPS = [['develop', 'developer', 'developers', 'developing', 'development', 'developed'],
          ['release', 'releases', 'released', 'releasing'],
          ['play', 'plays', 'played', 'playing', 'player', 'players'],
          ['game', 'games', 'gaming', 'gamer', 'gamers'],
          ['universe'], ['university', 'universities']]

def spacy_lemma(w): return NLP(w)[0].lemma_.lower()
METHODS = {'porter': PorterStemmer().stem, 'snowball': SnowballStemmer('english').stem,
           'lancaster': LancasterStemmer().stem,
           'wordnet_noun': lambda w: WNL.lemmatize(w, 'n'), 'wordnet_verb': lambda w: WNL.lemmatize(w, 'v'),
           'spacy_lemma': spacy_lemma}

def paice(fn, groups):
    # UI: share of same-group pairs NOT conflated; OI: share of different-group pairs conflated (Paice 1994)
    s = {w: fn(w) for g in groups for w in g}
    U = Um = O = Om = 0
    for i, g in enumerate(groups):
        for a in range(len(g)):
            for b in range(a + 1, len(g)):
                Um += 1; U += s[g[a]] != s[g[b]]
        for h in groups[i + 1:]:
            for a in g:
                for b in h:
                    Om += 1; O += s[a] == s[b]
    UI, OI = U / Um, O / Om
    return {'UI': round(UI, 3), 'OI': round(OI, 4), 'SW': round(OI / UI, 4) if UI else None,
            'universe==university': s['universe'] == s['university']}

stem_lemma = save(pd.DataFrame([{'method': m, **paice(f, GROUPS)} for m, f in METHODS.items()]),
                  'stemming_lemmatization.csv')
display(stem_lemma)

EXAMPLES = ['released', 'releasing', 'games', 'gaming', 'developers', 'development', 'playable', 'characters',
            'universe', 'university', 'universities', 'studies', 'better', 'consoles', 'was', 'has', 'this']
stem_examples = save(pd.DataFrame([{'word': w, **{m: f(w) for m, f in METHODS.items()}} for w in EXAMPLES]),
                     'stem_lemma_examples.csv')
stem_examples
""")

code(r"""
# Exercise 9: order of stemming and stop-word removal
SAMPLE = 'This was released and it has been played by many gamers'.split()
rows = []
for sname, st in (('porter', PorterStemmer()), ('snowball', SnowballStemmer('english'))):
    stop_first = [st.stem(w.lower()) for w in SAMPLE if w.lower() not in STOP_NLTK]
    stem_first = [(w, st.stem(w.lower())) for w in SAMPLE]
    stem_then_stop = [(w, s) for w, s in stem_first if s not in STOP_NLTK]
    leaked = [s for w, s in stem_then_stop if w.lower() in STOP_NLTK]   # stems of stop words that escaped the list
    rows.append({'stemmer': sname, 'order': 'stop_then_stem', 'output': ' '.join(stop_first), 'leaked_stopword_stems': ''})
    rows.append({'stemmer': sname, 'order': 'stem_then_stop', 'output': ' '.join(s for _, s in stem_then_stop),
                 'leaked_stopword_stems': ' '.join(leaked)})
order_effect = save(pd.DataFrame(rows), 'order_effect_stem_stop.csv')
order_effect
""")

md(r"""
### Exercise 12: POS tagging and custom POS taggers
Gold: `data/gold/pos_gold.tsv` (sentences from our corpus, Penn Treebank tags, includes Doom, Halo, Destiny, Prey). Taggers:
- **nltk_default**: averaged perceptron (`nltk.pos_tag`).
- **spacy_default**: `en_core_web_sm` tagger on the gold tokens.
- **rule_only**: no statistical model. The NLTK POS lab's RegexpTagger patterns, plus a domain dictionary (lexicon names -> NNP), capitalisation (non-initial capitalised word -> NNP), and Penn Treebank conventions for punctuation and possessive 's.
- **rule_custom**: domain dictionary layered over nltk_default: a capitalised, non-sentence-initial token from `domain_lexicon.json` is forced to NNP; digits to CD.
- **knn_custom**: KNN on one-hot word/context/affix features (POS_TAGGING lab), 5-fold cross-validated predictions on the gold set.
""")

code(r"""
import nltk
from spacy.tokens import Doc
gold_sents = []
with open(f'{GOLD}/pos_gold.tsv', encoding='utf-8') as f:
    for line in f:
        s = [tuple(wt.rsplit('|', 1)) for wt in line.split() if '|' in wt]
        if s: gold_sents.append(s)
gold = [wt for s in gold_sents for wt in s]
words = [w for w, _ in gold]; y = [t for _, t in gold]
starts = set(); i = 0
for s in gold_sents: starts.add(i); i += len(s)
print(f'gold: {len(gold)} tokens in {len(gold_sents)} sentences')

def tag_nltk(ws): return [t for _, t in nltk.pos_tag(ws)]
def tag_spacy(ws):
    doc = Doc(NLP.vocab, words=ws)
    for name, proc in NLP.pipeline:
        if name in ('tok2vec', 'tagger', 'attribute_ruler'): doc = proc(doc)
    return [t.tag_ for t in doc]

LEX_TOKENS = {w for e in vgir.lexicon_entries() for w in vgir.tok_custom(e) if w[:1].isupper() or w.isdigit()}
# The RegexpTagger patterns exactly as in the NLTK POS lab, preceded by Penn Treebank punctuation/possessive
# conventions and two domain rules (lexicon names and capitalised non-initial words -> NNP).
# Nothing here is derived from the gold sentences.
LAB_PATTERNS = [(r'^-?[0-9]+(\.[0-9]+)?$', 'CD'), (r'.*ing$', 'VBG'), (r'.*ed$', 'VBD'), (r'.*ly$', 'RB'),
                (r'.*ous$', 'JJ'), (r'.*able$', 'JJ'), (r'.*ness$', 'NN'), (r'.*s$', 'NNS'), (r'.*', 'NN')]
LAB_TAGGER = nltk.RegexpTagger(LAB_PATTERNS)
def tag_rule_only(ws, start_idx=frozenset({0})):
    base = [t for _, t in LAB_TAGGER.tag(ws)]
    out = []
    for i, (w, t) in enumerate(zip(ws, base)):
        if re.fullmatch(r'[^\w]+', w): out.append('.' if w in '.!?' else (',' if w == ',' else ':'))
        elif w == "'s": out.append('POS')
        elif w in LEX_TOKENS and not w.isdigit(): out.append('NNP')
        elif w[:1].isupper() and i not in start_idx: out.append('NNP')
        else: out.append(t)
    return out
def tag_rule_custom(ws, start_idx=frozenset({0})):
    base = tag_nltk(ws)
    return ['NNP' if (w in LEX_TOKENS and i not in start_idx and not w.isdigit()) else
            ('CD' if re.fullmatch(r'\d[\d,.]*', w) else t) for i, (w, t) in enumerate(zip(ws, base))]

from sklearn.pipeline import Pipeline as SkPipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import cross_val_predict, KFold
def knn_feats(ws):
    return [[w, w.lower(), ws[i - 1] if i else '<S>', ws[i + 1] if i < len(ws) - 1 else '</S>',
             w[-3:], w[:1].isupper(), w.isdigit(), str(min(len(w), 10))] for i, w in enumerate(ws)]
KNN = SkPipeline([('oh', OneHotEncoder(handle_unknown='ignore')), ('knn', KNeighborsClassifier(n_neighbors=3))])
knn_pred = cross_val_predict(KNN, knn_feats(words), y, cv=KFold(5, shuffle=True, random_state=vgir.SEED)).tolist()
KNN.fit(knn_feats(words), y)          # full-gold model, used later by the GUI

PRED = {'nltk_default': tag_nltk(words), 'spacy_default': tag_spacy(words),
        'rule_only': tag_rule_only(words, frozenset(starts)), 'rule_custom': tag_rule_custom(words, frozenset(starts)),
        'knn_custom': knn_pred}
acc = lambda p: round(sum(a == b for a, b in zip(p, y)) / len(y), 3)
pos_acc = save(pd.DataFrame([{'tagger': n, 'accuracy': acc(p), 'correct': sum(a == b for a, b in zip(p, y)),
                              'tokens': len(y)} for n, p in PRED.items()]), 'pos_tagging_results.csv')
display(pos_acc)

# Table D: domain terms (lexicon tokens and other proper nouns in the gold) - default vs custom
rows = []
for i, (w, g) in enumerate(gold):
    if w in LEX_TOKENS or g == 'NNP':
        rows.append({'word': w, 'gold': g, 'default_nltk': PRED['nltk_default'][i], 'default_spacy': PRED['spacy_default'][i],
                     'custom_rule': PRED['rule_custom'][i], 'custom_knn': PRED['knn_custom'][i],
                     'default_nltk_correct': PRED['nltk_default'][i] == g, 'custom_rule_correct': PRED['rule_custom'][i] == g})
pos_domain = save(pd.DataFrame(rows), 'pos_tagging_domain_terms.csv')
pos_domain
""")

code(r"""
# Domain-term probe beyond the small gold set: every single-word lexicon name (title / platform / company), tagged in
# its first corpus sentence. Used as a name it should be NNP; this lists the ones default taggers get wrong.
# (Heuristic: no gold here, and a few names can be used generically in their first sentence.)
single = sorted({e for e in vgir.lexicon_entries(('titles', 'platforms', 'companies')) if re.fullmatch(r"[A-Za-z][A-Za-z0-9\-]*", e)})
SENTS = [(d, s) for d in docs for s in sent_tokenize(TEXT[d])]
rows = []
for term in single:
    rx = re.compile(r'(?<![\w-])' + re.escape(term) + r'(?![\w-])')
    hit = next(((d, s) for d, s in SENTS if rx.search(s)), None)
    if not hit: continue
    d, s = hit
    ws = vgir.tok_nltk(s)
    if term not in ws: continue
    i = ws.index(term)
    rows.append({'term': term, 'doc_id': d, 'context': s[:160], 'nltk_default': tag_nltk(ws)[i],
                 'spacy_default': tag_spacy(ws)[i], 'custom_rule': tag_rule_custom(ws)[i]})
pos_probe = pd.DataFrame(rows)
for c in ('nltk_default', 'spacy_default', 'custom_rule'):
    pos_probe[c + '_is_NNP'] = pos_probe[c].isin(['NNP', 'NNPS'])
save(pos_probe, 'pos_domain_probe.csv')
print(f"{len(pos_probe)} domain names found in the corpus; tagged as proper noun by nltk {pos_probe.nltk_default_is_NNP.sum()}, "
      f"spaCy {pos_probe.spacy_default_is_NNP.sum()}, custom rule {pos_probe.custom_rule_is_NNP.sum()}")
pos_probe[~pos_probe.nltk_default_is_NNP | ~pos_probe.spacy_default_is_NNP]
""")

code(r"""
# Stage evaluation, POS: per-tag precision / recall / F1 and where taggers confuse tags (gold vs predicted)
from sklearn.metrics import precision_recall_fscore_support
rows = []
labels = sorted(set(y))
for name in ('nltk_default', 'spacy_default', 'rule_custom', 'knn_custom'):
    p_, r_, f_, n_ = precision_recall_fscore_support(y, PRED[name], labels=labels, zero_division=0)
    for t, a, b, c, n in zip(labels, p_, r_, f_, n_):
        rows.append({'tagger': name, 'tag': t, 'precision': round(a, 3), 'recall': round(b, 3), 'f1': round(c, 3), 'support': int(n)})
pos_tags = save(pd.DataFrame(rows), 'pos_per_tag_metrics.csv')
display(pos_tags.groupby('tagger')[['precision', 'recall', 'f1']].mean().round(3))
conf = []
for name in ('nltk_default', 'spacy_default', 'rule_custom'):
    for (g, pr), c in Counter(zip(y, PRED[name])).items():
        if g != pr: conf.append({'tagger': name, 'gold_tag': g, 'predicted_tag': pr, 'count': c})
pos_conf = save(pd.DataFrame(conf).sort_values(['tagger', 'count'], ascending=[True, False]), 'pos_confusion_errors.csv')
cm = pd.crosstab(pd.Series(y, name='gold'), pd.Series(PRED['nltk_default'], name='nltk_default'))
save(cm.reset_index(), 'pos_confusion_matrix_nltk.csv')
pos_conf
""")


md(r"""
### Exercise 13: Named entity recognition
Gold: `data/gold/ner_gold.tsv`, 51 entities over the 7 required types, taken from our documents (no document ids, so evaluation is corpus-level). Every document is processed in full. For each gold entity: **correct** = spaCy predicts that text with the gold label somewhere in the corpus; **incorrect** (mislabelled) = the text is predicted only with other labels; **missed** = the text is never predicted as an entity. Two systems: default `en_core_web_sm`, and the same model with an `EntityRuler` built from the domain lexicon placed before `ner` (Course Plan L8, adding pipeline components): platforms and titles -> PRODUCT, companies -> ORG, events -> EVENT. This replaces the earlier string-match check, which never compared labels (amendment 01.10.2026).
""")

code(r"""
import spacy
ner_gold = pd.read_csv(f'{GOLD}/ner_gold.tsv', sep='\t')
NLP_RULER = spacy.load('en_core_web_sm')
ruler = NLP_RULER.add_pipe('entity_ruler', before='ner')
LX = vgir.lexicon()
PERSON_IN_COMPANIES = {'Hideo Kojima'}          # lexicon lists him under companies; he is a PERSON
patterns = ([{'label': 'PRODUCT', 'pattern': e} for e in LX['platforms'] + LX['titles']] +
            [{'label': 'ORG', 'pattern': e} for e in LX['companies'] if e not in PERSON_IN_COMPANIES] +
            [{'label': 'PERSON', 'pattern': e} for e in PERSON_IN_COMPANIES] +
            [{'label': 'EVENT', 'pattern': e} for e in LX['events']])
ruler.add_patterns(patterns)

def corpus_entities(nlp):
    found = defaultdict(Counter)
    for doc in nlp.pipe((TEXT[d] for d in docs), batch_size=4):
        for e in doc.ents:
            found[e.text.lower()][e.label_] += 1
    return found
t0 = time.perf_counter()
ENTS = {'default': corpus_entities(NLP), 'ruler': corpus_entities(NLP_RULER)}
print(f'NER over {len(docs)} full documents x 2 systems: {time.perf_counter()-t0:.0f}s')

def judge(found, text, label):
    labs = found.get(text.lower())
    if not labs: return 'MISSING', 'missed'
    if label in labs: return label, 'correct'
    return labs.most_common(1)[0][0], 'incorrect'
rows = []
for _, r in ner_gold.iterrows():
    p0, s0 = judge(ENTS['default'], r.Word, r.Entity_Type)
    p1, s1 = judge(ENTS['ruler'], r.Word, r.Entity_Type)
    rows.append({'Entity': r.Word, 'Gold Type': r.Entity_Type, 'Predicted Type': p0, 'Correct?': s0 == 'correct',
                 'status_default': s0, 'Predicted Type (ruler)': p1, 'status_ruler': s1})
ner = save(pd.DataFrame(rows), 'ner_results.csv')
ner_summary = pd.DataFrame([{'system': sysname, 'total': len(ner), **ner[col].value_counts().reindex(['correct', 'incorrect', 'missed'], fill_value=0).to_dict()}
                            for sysname, col in (('spaCy default', 'status_default'), ('spaCy + EntityRuler', 'status_ruler'))])
ner_by_type = ner.groupby('Gold Type').agg(total=('Entity', 'size'), correct_default=('status_default', lambda s: (s == 'correct').sum()),
                                            correct_ruler=('status_ruler', lambda s: (s == 'correct').sum())).reset_index()
save(ner_summary, 'ner_summary.csv'); save(ner_by_type, 'ner_by_type.csv')
display(ner_summary, ner_by_type)

# domain-specific entities: how does default spaCy label lexicon entries that occur in the corpus?
rows = []
for cat in ('titles', 'platforms', 'companies', 'events'):
    for e in LX[cat]:
        labs, rlabs = ENTS['default'].get(e.lower()), ENTS['ruler'].get(e.lower())
        if labs:
            rows.append({'lexicon_entry': e, 'lexicon_category': cat, 'default_label': labs.most_common(1)[0][0],
                         'default_label_counts': dict(labs), 'ruler_label': rlabs.most_common(1)[0][0] if rlabs else '-'})
ner_domain = save(pd.DataFrame(rows), 'ner_domain_entities.csv')
ner_domain.default_label.value_counts()
""")

code(r"""
# Stage evaluation, NER: confusion matrix gold type x predicted type (MISSING = not recognised) and per-type P / R / F1.
# Precision is computed over the gold entity list (a prediction counts when it was made for a gold entity); spurious
# entities outside the gold list are not counted, a limitation of a gold set without document offsets.
ner_rows, ner_cm = [], {}
for sysname, col in (('default', 'Predicted Type'), ('ruler', 'Predicted Type (ruler)')):
    cm = pd.crosstab(ner['Gold Type'], ner[col]); ner_cm[sysname] = cm
    save(cm.reset_index(), f'ner_confusion_{sysname}.csv')
    for t in sorted(ner['Gold Type'].unique()):
        tp = int(((ner['Gold Type'] == t) & (ner[col] == t)).sum())
        pred = int((ner[col] == t).sum()); gold_n = int((ner['Gold Type'] == t).sum())
        P_ = tp / pred if pred else 0.0; R_ = tp / gold_n; F_ = 2 * P_ * R_ / (P_ + R_) if P_ + R_ else 0.0
        ner_rows.append({'system': sysname, 'type': t, 'gold': gold_n, 'predicted_as_type': pred, 'correct': tp,
                         'precision': round(P_, 3), 'recall': round(R_, 3), 'f1': round(F_, 3)})
ner_prf = save(pd.DataFrame(ner_rows), 'ner_per_type_metrics.csv')
display(ner_cm['default'])
ner_prf.groupby('system')[['precision', 'recall', 'f1']].mean().round(3)
""")


md(r"""
### Pipelines A and B (Module 3 definitions), needed for Exercises 11 and 14
| Step | Pipeline A (annotate-first, lemma-based) | Pipeline B (normalize-first, stem-based) |
|---|---|---|
| 1 | Hybrid tokenization | Hybrid tokenization |
| 2 | POS tagging (spaCy, cased, full context) | Lowercase |
| 3 | POS-aware lemmatization (proper nouns, numbers, MWEs kept) | Stop-word removal, NLTK list, positions kept |
| 4 | Lowercase | Snowball (Porter2) stemming (MWEs kept) |
| 5 | Minimal stop list (10 words) | - |

Order rationale (PREREGISTRATION section 5): in A, lemmatization needs POS and POS needs case and context, so tagging runs first and stop removal last. In B, stemming needs no context, so the classic IR order lowercase -> stop -> stem applies (Manning et al. 2008, ch. 2). NER is run in A's annotation stage in the preregistered design; in `vgir.pipeline_A` the tagger is used for lemmatization and NER results are reported separately (Exercise 13). Queries always pass through the same pipeline as documents.
""")

code(r"""
t0 = time.perf_counter()
IX = {'A': vgir.PositionalIndex(vgir.pipeline_A, 'A').build(docs),
      'B': vgir.PositionalIndex(vgir.pipeline_B, 'B').build(docs)}
print(f'indexes built in {time.perf_counter()-t0:.0f}s')

# trace one sentence through both pipelines (what each step does)
TRACE = "The Legend of Zelda: Majora's Mask was released for the Nintendo 64 in 2000 and players were praising it."
hyb = vgir.tok_hybrid(TRACE)
tags = vgir.spacy_tag_tokens(hyb)
trace = pd.DataFrame({'hybrid_token': hyb, 'spacy_tag': [t for t, _, _ in tags], 'spacy_lemma': [l for _, _, l in tags]})
termsA = dict((p, t) for t, p in vgir.pipeline_A(TRACE)); termsB = dict((p, t) for t, p in vgir.pipeline_B(TRACE))
trace['pipeline_A_term'] = [termsA.get(i, '(removed)') for i in range(len(hyb))]
trace['pipeline_B_term'] = [termsB.get(i, '(removed)') for i in range(len(hyb))]
save(trace, 'pipeline_trace_example.csv')
""")

md(r"""
### Exercise 11: corpus before and after preprocessing (Table A)
"Before" = hybrid tokens of the cleaned text (punctuation included, case kept). "After" = index terms of each pipeline.
""")

code(r"""
raw = all_toks('hybrid')
def after(p): return IX[p].token_count(), IX[p].vocab_size()
tableA = pd.DataFrame([
    {'Measure': 'Documents', 'Before Processing': len(docs), 'After (Pipeline A)': len(docs), 'After (Pipeline B)': len(docs)},
    {'Measure': 'Tokens', 'Before Processing': len(raw), 'After (Pipeline A)': after('A')[0], 'After (Pipeline B)': after('B')[0]},
    {'Measure': 'Unique Tokens (case-sensitive)', 'Before Processing': len(set(raw)), 'After (Pipeline A)': after('A')[1], 'After (Pipeline B)': after('B')[1]},
    {'Measure': 'Vocabulary Size (case-folded terms)', 'Before Processing': corpus_vocab, 'After (Pipeline A)': after('A')[1], 'After (Pipeline B)': after('B')[1]},
])
save(tableA, 'preprocessing_results.csv')
""")

md(r"""
### Exercise 14: n-grams (1-5) for both pipelines
Same code for both pipelines: n-grams over each document's index-term sequence (title + body, never crossing documents). "Meaningful" follows PREREGISTRATION section 7: count >= 2, no NLTK stop word or pure number at either edge, at least one alphabetic token; the rate is the share of meaningful items in the top 20.
""")

code(r"""
NG_NAME = {1: 'unigram', 2: 'bigram', 3: 'trigram', 4: '4-gram', 5: '5-gram'}
NGRAMS, summary_rows, top_rows = {}, [], []
for p in ('A', 'B'):
    seqs = [IX[p].doc_terms[d] for d in docs]
    for n in range(1, 6):
        s = vgir.ngram_stats(seqs, n, top=10)
        NGRAMS[(p, n)] = s['counter']
        rate = vgir.meaningful_rate(s['counter'], STOP_NLTK, top=20) if n >= 2 else None
        summary_rows.append({'pipeline': p, 'n_gram': NG_NAME[n], 'total': s['total'], 'unique': s['unique'],
                             'unique_ratio': round(s['unique'] / s['total'], 3),
                             'meaningful_rate_top20': None if rate is None else round(rate, 2),
                             'top_10': ' ; '.join(f"{' '.join(g)} ({c})" for g, c in s['top'])})
        for rank, (g, c) in enumerate(s['top'], 1):
            top_rows.append({'pipeline': p, 'n': n, 'n_gram': NG_NAME[n], 'rank': rank, 'gram': ' '.join(g), 'count': c,
                             'frequency': round(c / s['total'], 5),
                             'meaningful': (vgir.is_meaningful(g, STOP_NLTK) and c >= 2) if n >= 2 else None})
ng_summary = save(pd.DataFrame(summary_rows), 'ngram_summary.csv')
top = pd.DataFrame(top_rows)
save(top[top.n == 1], 'unigram_results.csv'); save(top[top.n == 2], 'bigram_results.csv')
save(top[top.n == 3], 'trigram_results.csv'); save(top[top.n >= 4], 'ngram_results.csv')
display(ng_summary[['pipeline', 'n_gram', 'total', 'unique', 'unique_ratio', 'meaningful_rate_top20']])

# The 20 bigrams behind the section 7 rate, with the verdict per item (so the measure can be inspected)
rows = []
for p in ('A', 'B'):
    items = [(g, c) for g, c in NGRAMS[(p, 2)].most_common() if c >= 2][:20]
    for r, (g, c) in enumerate(items, 1):
        rows.append({'pipeline': p, 'rank': r, 'bigram': ' '.join(g), 'count': c,
                     'meaningful_s7': vgir.is_meaningful(g, STOP_NLTK), 'contains_possessive_s': "'s" in g})
big20 = save(pd.DataFrame(rows), 'bigram_top20_meaningful.csv')
big20.pivot(index='rank', columns='pipeline', values=['bigram', 'meaningful_s7'])
""")

# ------------------------------------------------------------------ Module 3 comparison
md(r"""
## Module 3: Pipeline A vs Pipeline B (structural comparison)
Token count, vocabulary size, n-gram quality (meaningful-bigram rate, section 7) and domain terms (domain-term preservation, section 8: an entry is preserved iff the pipeline outputs exactly one token equal to its case-folded MWE form). Retrieval quality is added in Module 6.
""")

code(r"""
PRES = {p: vgir.domain_term_preservation(vgir.PIPELINES[p]) for p in ('A', 'B')}
pres_rows = pd.DataFrame([{**r, 'pipeline': p} for p in ('A', 'B') for r in PRES[p][1]])
save(pres_rows, 'domain_term_preservation.csv')
STRUCT = {p: {'Token Count': IX[p].token_count(), 'Vocabulary Size': IX[p].vocab_size(),
              'Meaningful bigram rate (top 20)': vgir.meaningful_rate(NGRAMS[(p, 2)], STOP_NLTK, 20),
              'Meaningful trigram rate (top 20)': vgir.meaningful_rate(NGRAMS[(p, 3)], STOP_NLTK, 20),
              'Domain-term preservation': PRES[p][0]} for p in ('A', 'B')}
pd.DataFrame(STRUCT)
""")

code(r"""
# Lexicon entries the two pipelines treat differently
lost =pres_rows[pres_rows.preserved == False].pivot_table(index='entry', columns='pipeline', values='output', aggfunc='first')
lost
""")

# ------------------------------------------------------------------ Module 4
md(r"""
## Module 4: Inverted index and Boolean / phrase retrieval
Positional inverted index (term -> {doc: [positions]}), required for phrase search (Manning et al. 2008, ch. 2; Brin & Page 1998 hit lists). Ranking: TF-IDF cosine with sublinear tf (1 + log tf) and a 2.0x title-hit boost (Brin & Page 1998). Query engine: keyword, "phrase", AND, OR, NOT, parentheses; queries pass through the same pipeline as documents. Both indexes are saved in one file.
""")

code(r"""
with open(f'{RES}/inverted_index.json', 'w', encoding='utf-8') as f:
    json.dump({p: IX[p].to_json() for p in ('A', 'B')}, f)
print('inverted_index.json:', round(os.path.getsize(f'{RES}/inverted_index.json') / 1e6, 1), 'MB')

for term in ('nintendo', 'game_boy', 'tomb_raider'):
    for p in ('A', 'B'):
        post = IX[p].post.get(term, {})
        print(f'{p}: {term} -> {", ".join(sorted(post))[:150]}  (df={len(post)})')

QE = {p: vgir.QueryEngine(IX[p]) for p in ('A', 'B')}
for q in ('Zelda', '"Game Boy"', 'Sonic AND Sega', 'Halo OR Doom', 'Metroid AND NOT Zelda'):
    r, _ = QE['A'].search(q)
    print(f'{q:28} -> {len(r):2} docs: {" ".join(r[:8])}')
""")

code(r"""
# What the index looks like: size and shape of each positional inverted index, plus real entries
rows = []
for p in ('A', 'B'):
    post = IX[p].post
    dfs = [len(v) for v in post.values()]
    rows.append({'pipeline': p, 'terms (dictionary size)': len(post), 'postings (term-document pairs)': sum(dfs),
                 'positions stored': sum(len(x) for v in post.values() for x in v.values()),
                 'mean documents per term': round(statistics.mean(dfs), 2), 'median documents per term': statistics.median(dfs),
                 'terms in only 1 document': sum(d == 1 for d in dfs), 'terms in all 53 documents': sum(d == len(docs) for d in dfs),
                 'most widespread terms': ', '.join(t for t, _ in sorted(post.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:6])})
index_structure = save(pd.DataFrame(rows), 'index_structure.csv')
display(index_structure.T)
example = {t: {d: IX['A'].post[t][d][:6] for d in sorted(IX['A'].post[t])[:4]} for t in ('game_boy', 'metroid')}
print(json.dumps(example, indent=1))
""")


# ------------------------------------------------------------------ Module 5
md(r"""
## Module 5: The 12 domain-specific queries
The information needs are the 12 MIRACL questions that the corpus and `relevance.tsv` were built from. Their Boolean/phrase forms were rewritten by hand (amendment 01.10.2026) because the earlier auto-generated forms did not express the needs (e.g. `"there Sonic game"`). Rule used: only words from the question, aimed at its main entity, with the query type chosen to fit the question; coverage = 2 keyword, 3 phrase, 3 AND, 2 OR, 2 NOT, spanning unigram, bigram and trigram. The earlier forms are re-run in Module 6 as an exploratory reproduction check.
""")

code(r"""
REVIEW = pd.read_csv(f'{GOLD}/relevance_REVIEW.csv')
QUESTION = REVIEW.drop_duplicates('our_qid').set_index('our_qid')['query'].to_dict()
MIRACL_QID = manifest.drop_duplicates('source_our_qid').set_index('source_our_qid')['source_qid'].to_dict()
QUERIES = [  # our_qid, query, type, n-gram class, cluster
    ('Q01', 'Total War', 'keyword', 'bigram (MWE)', 'sales'),
    ('Q02', 'Sonic AND "Sega Genesis"', 'and', 'boolean', 'consoles'),
    ('Q03', 'Nintendo AND PlayStation', 'and', 'boolean', 'consoles'),
    ('Q04', '"Ash Ketchum" AND NOT Japanese', 'not', 'boolean', 'franchises'),
    ('Q05', 'Metroid', 'keyword', 'unigram', 'franchises'),
    ('Q06', 'Zelda AND (theme OR song)', 'or', 'boolean', 'franchises'),
    ('Q07', '"Tomb Raider"', 'phrase', 'bigram (MWE)', 'firsts'),
    ('Q08', 'Cloud AND "Kingdom Hearts"', 'and', 'boolean', 'franchises'),
    ('Q09', '"Guitar Hero Live"', 'phrase', 'trigram (MWE)', 'firsts'),
    ('Q10', 'shooter AND NOT "first person"', 'not', 'boolean', 'genre'),
    ('Q11', '"first video game"', 'phrase', 'trigram', 'firsts'),
    ('Q12', 'SNES OR "Super Nintendo Entertainment System"', 'or', 'boolean', 'consoles'),
]
qtable = pd.DataFrame([{'our_qid': q, 'miracl_qid': MIRACL_QID.get(q), 'question': QUESTION[q], 'query': f,
                        'type': t, 'ngram_class': c, 'cluster': cl} for q, f, t, c, cl in QUERIES])
save(qtable, 'queries.csv')
""")

# ------------------------------------------------------------------ Module 6
md(r"""
## Module 6: Retrieval evaluation
Relevance: `data/gold/relevance.tsv`, MIRACL-seeded and hand-verified by two annotators under a topical-aboutness protocol (DECISION_LOG amendment to EXP-02); unjudged pairs count as non-relevant (Voorhees 2000). Results are therefore **preliminary**. Metrics (PREREGISTRATION section 6): set-based P, R, F1 over the full result list; P@5, P@10, R@5, R@10 on the ranking; macro-averaged over the 12 queries; cold (first) and warm (median of 5 repeats) query time.
""")

code(r"""
rel = pd.read_csv(f'{GOLD}/relevance.tsv', sep='\t')
RELEVANT = {q: set(g.doc_id[g.rel > 0]) for q, g in rel.groupby('our_qid')}
assert set(RELEVANT) == {q for q, *_ in QUERIES}

def evaluate(p, queries, label=None):
    rows = []
    for q, form, qtype, ngc, cluster in queries:
        ranked, _, cold, warm = QE[p].timed_search(form, repeats=5)
        gold_q = RELEVANT[q]
        P_, R_, F_ = vgir.set_metrics(ranked, gold_q)
        rows.append({'pipeline': label or p, 'our_qid': q, 'query': form, 'type': qtype, 'ngram_class': ngc,
                     'n_retrieved': len(ranked), 'n_relevant': len(gold_q), 'TP': len(set(ranked) & gold_q),
                     'P': P_, 'R': R_, 'F1': F_,
                     'P@5': vgir.p_at_k(ranked, gold_q, 5), 'P@10': vgir.p_at_k(ranked, gold_q, 10),
                     'R@5': vgir.r_at_k(ranked, gold_q, 5), 'R@10': vgir.r_at_k(ranked, gold_q, 10),
                     'cold_ms': cold, 'warm_ms': warm,
                     'retrieved_top10': ' '.join(ranked[:10]), 'retrieved_all': ' '.join(ranked)})
    return pd.DataFrame(rows)

RUN = {p: evaluate(p, QUERIES) for p in ('A', 'B')}
retrieval = pd.concat([RUN['A'], RUN['B']], ignore_index=True)
METRICS = ['P', 'R', 'F1', 'P@5', 'P@10', 'R@5', 'R@10']
save(retrieval.round({m: 3 for m in METRICS} | {'cold_ms': 2, 'warm_ms': 2}), 'retrieval_results.csv')
retrieval.pivot(index='our_qid', columns='pipeline', values=['n_retrieved', 'P', 'R', 'F1']).round(3)
""")

code(r"""
# Sanity checks: metrics in range, timings positive, not everything empty
assert retrieval[METRICS].ge(0).all().all() and retrieval[METRICS].le(1).all().all(), 'metric out of [0,1]'
assert (retrieval[['cold_ms', 'warm_ms']] > 0).all().all(), 'non-positive timing'
assert (retrieval.n_retrieved > 0).any(), 'every query returned nothing'
empty = retrieval[retrieval.n_retrieved == 0][['pipeline', 'our_qid', 'query']]
print('queries with no results:', 'none' if empty.empty else empty.to_dict('records'))
""")

code(r"""
# Stage evaluation, retrieval: per-query confusion matrix over all 53 documents (TP, FP, FN, TN) and accuracy
rows = []
for p in ('A', 'B'):
    for r in RUN[p].itertuples():
        got = set(r.retrieved_all.split()) if r.retrieved_all else set(); g = RELEVANT[r.our_qid]
        tp, fp, fn = len(got & g), len(got - g), len(g - got); tn = len(docs) - tp - fp - fn
        rows.append({'pipeline': p, 'our_qid': r.our_qid, 'query': r.query, 'TP': tp, 'FP': fp, 'FN': fn, 'TN': tn,
                     'accuracy': round((tp + tn) / len(docs), 3), 'precision': round(r.P, 3), 'recall': round(r.R, 3), 'f1': round(r.F1, 3)})
ret_cm = save(pd.DataFrame(rows), 'retrieval_confusion_per_query.csv')
tot = ret_cm.groupby('pipeline')[['TP', 'FP', 'FN', 'TN']].sum().reset_index()
tot['accuracy (micro)'] = ((tot.TP + tot.TN) / (tot.TP + tot.FP + tot.FN + tot.TN)).round(3)
tot['precision (micro)'] = (tot.TP / (tot.TP + tot.FP)).round(3); tot['recall (micro)'] = (tot.TP / (tot.TP + tot.FN)).round(3)
tot['f1 (micro)'] = (2 * tot['precision (micro)'] * tot['recall (micro)'] / (tot['precision (micro)'] + tot['recall (micro)'])).round(3)
tot['accuracy of retrieving nothing'] = round(1 - sum(len(v) for v in RELEVANT.values()) / (len(docs) * len(RELEVANT)), 3)
save(tot, 'retrieval_confusion_total.csv')
tot
""")


md(r"""
### Final-pipeline selection (PREREGISTRATION section 9, applied in order)
1. Higher macro-F1 wins if |delta F1| >= 0.05.
2. Otherwise higher domain-term preservation, if that gap >= 0.05.
3. Otherwise higher meaningful-bigram rate.
""")

code(r"""
MACRO = {p: RUN[p][METRICS + ['warm_ms', 'cold_ms']].mean() for p in ('A', 'B')}
dF1 = MACRO['A']['F1'] - MACRO['B']['F1']
dPres = STRUCT['A']['Domain-term preservation'] - STRUCT['B']['Domain-term preservation']
dBig = STRUCT['A']['Meaningful bigram rate (top 20)'] - STRUCT['B']['Meaningful bigram rate (top 20)']
if abs(dF1) >= 0.05:
    FINAL, RULE = ('A' if dF1 > 0 else 'B'), f'Rule 1: |delta macro-F1| = {abs(dF1):.4f} >= 0.05'
elif abs(dPres) >= 0.05:
    FINAL, RULE = ('A' if dPres > 0 else 'B'), f'Rule 2: |delta F1| = {abs(dF1):.4f} < 0.05; domain-term preservation gap = {abs(dPres):.4f} >= 0.05'
else:
    FINAL, RULE = ('A' if dBig > 0 else 'B'), f'Rule 3: |delta F1| = {abs(dF1):.4f} < 0.05 and preservation gap = {abs(dPres):.4f} < 0.05; meaningful-bigram rate decides (gap {dBig:+.2f})'
print(f'macro-F1  A = {MACRO["A"]["F1"]:.4f}   B = {MACRO["B"]["F1"]:.4f}   delta (A-B) = {dF1:+.4f}')
print(f'FINAL PIPELINE: {FINAL}   ({RULE})')
json.dump({'final_pipeline': FINAL, 'rule_fired': RULE, 'macro_F1_A': MACRO['A']['F1'], 'macro_F1_B': MACRO['B']['F1'],
           'delta_F1_A_minus_B': dF1, 'delta_preservation_A_minus_B': dPres, 'delta_bigram_rate_A_minus_B': dBig},
          open(f'{RES}/final_pipeline_selection.json', 'w'), indent=2)
""")

code(r"""
# Table H: pipeline comparison (Measure | Pipeline A | Pipeline B | Final Pipeline)
def col(p):
    s = STRUCT[p]; m = MACRO[p]
    return {'Token Count': s['Token Count'], 'Vocabulary Size': s['Vocabulary Size'],
            'Meaningful N-Grams (bigram rate, top 20)': round(s['Meaningful bigram rate (top 20)'], 2),
            'Meaningful trigram rate (top 20)': round(s['Meaningful trigram rate (top 20)'], 2),
            'Domain-term preservation': round(s['Domain-term preservation'], 3),
            'Precision (macro)': round(m['P'], 3), 'Recall (macro)': round(m['R'], 3), 'F1-score (macro)': round(m['F1'], 3),
            'P@5': round(m['P@5'], 3), 'P@10': round(m['P@10'], 3), 'R@5': round(m['R@5'], 3), 'R@10': round(m['R@10'], 3),
            'Warm query time (ms, mean of medians)': round(m['warm_ms'], 2), 'Cold query time (ms, mean)': round(m['cold_ms'], 2)}
cA, cB = col('A'), col('B')
tableH = pd.DataFrame({'Measure': list(cA), 'Pipeline A': list(cA.values()), 'Pipeline B': list(cB.values()),
                       'Final Pipeline': list((cA if FINAL == 'A' else cB).values())})
tableH.loc[len(tableH)] = ['Selection', '', '', f'{FINAL} ({RULE})']
save(tableH, 'pipeline_comparison.csv')
""")

code(r"""
# evaluation_results.csv: per-query table of the final pipeline, marked Final; Table I (by query type); Table J (overall)
ev = RUN[FINAL].copy(); ev.insert(0, 'final', f'Final (Pipeline {FINAL})')
macro_row = {'final': f'Final (Pipeline {FINAL})', 'pipeline': FINAL, 'our_qid': 'MACRO', **MACRO[FINAL].to_dict()}
ev = pd.concat([ev, pd.DataFrame([macro_row])], ignore_index=True)
save(ev.drop(columns=['retrieved_all']).round(3), 'evaluation_results.csv')

tableI = retrieval.groupby(['pipeline', 'type'])[['n_retrieved', 'P', 'R', 'F1', 'warm_ms']].mean().round(3).reset_index()
save(tableI, 'retrieval_by_query_type.csv')
# Table I in the assignment's layout: Query Type | Retrieved Documents | # Results | Time (one row per query)
BOOL = {'and': 'Boolean AND', 'or': 'Boolean OR', 'not': 'Boolean NOT'}
tableI_fmt = pd.DataFrame([{'pipeline': r.pipeline, 'our_qid': r.our_qid,
                            'Query Type': BOOL.get(r.type, f'{r.ngram_class[0].upper()}{r.ngram_class[1:]}, {r.type}'),
                            'Query': r.query, 'Retrieved Documents': r.retrieved_all, '# Results': r.n_retrieved,
                            'Time (warm ms)': round(r.warm_ms, 2), 'Time (cold ms)': round(r.cold_ms, 2)}
                           for r in retrieval.itertuples()])
save(tableI_fmt, 'table_I_retrieval_results.csv')
tableJ = pd.DataFrame([{'Method/Pipeline': n, 'Precision': round(MACRO[p]['P'], 3), 'Recall': round(MACRO[p]['R'], 3),
                        'F1-score': round(MACRO[p]['F1'], 3), 'Time (warm ms)': round(MACRO[p]['warm_ms'], 2)}
                       for n, p in (('Pipeline A', 'A'), ('Pipeline B', 'B'), (f'Final Pipeline ({FINAL})', FINAL))])
save(tableJ, 'overall_performance.csv')
display(tableJ, tableI)
""")

code(r"""
# Per-query A vs B, and robustness: does the decision depend on any single query? (EXPLORATORY)
pq = RUN['A'][['our_qid', 'query', 'type', 'F1']].merge(RUN['B'][['our_qid', 'F1']], on='our_qid', suffixes=('_A', '_B'))
pq['delta_F1_A_minus_B'] = pq.F1_A - pq.F1_B
pq['better'] = pq.delta_F1_A_minus_B.map(lambda d: 'A' if d > 1e-9 else ('B' if d < -1e-9 else 'tie'))
save(pq.round(3), 'per_query_A_vs_B.csv')
display(pq.round(3))
loo = pd.DataFrame([{'left_out': q, 'delta_macro_F1_A_minus_B': round(pq[pq.our_qid != q].delta_F1_A_minus_B.mean(), 4)} for q in pq.our_qid])
loo['rule1_winner'] = loo.delta_macro_F1_A_minus_B.map(lambda d: ('A' if d > 0 else 'B') if abs(d) >= 0.05 else 'no rule-1 winner')
save(loo, 'leave_one_query_out_EXPLORATORY.csv')
loo
""")

code(r"""
# Error analysis input (PREREGISTRATION section 12): every false negative and false positive, per query and pipeline
rows = []
for p in ('A', 'B'):
    for _, r in RUN[p].iterrows():
        got = set(r.retrieved_all.split()) if r.retrieved_all else set()
        for d in sorted(RELEVANT[r.our_qid] - got):
            rows.append({'pipeline': p, 'our_qid': r.our_qid, 'query': r.query, 'error': 'FN', 'doc_id': d, 'title': TITLE[d]})
        for d in sorted(got - RELEVANT[r.our_qid]):
            rows.append({'pipeline': p, 'our_qid': r.our_qid, 'query': r.query, 'error': 'FP', 'doc_id': d, 'title': TITLE[d]})
errors = save(pd.DataFrame(rows), 'error_analysis.csv')
errors.groupby(['pipeline', 'error']).size().unstack()
""")

code(r"""
# EXPLORATORY 1: reproduce the earlier runs (auto-generated query forms) with this notebook's indexes.
old = {p: pd.read_csv(f'{DATA}/previous_runs/retrieval_results_{p}_autoforms.csv') for p in ('A', 'B')}
rows = []
for p in ('A', 'B'):
    oq = [(r.our_qid, r.query, r.type, '', r.cluster) for r in old[p].itertuples()]
    new = evaluate(p, oq, label=f'{p} (auto forms)')
    m = new.merge(old[p], on='our_qid', suffixes=('', '_old'))
    same = (m.n_retrieved == m.n_retrieved_old) & ((m.F1.round(3) - m.F1_old).abs() < 1e-9) & \
           (m.retrieved_top10.fillna('') == m.retrieved_top10_old.fillna(''))
    print(f'Pipeline {p}: {same.sum()}/12 queries reproduce the earlier CSV exactly; macro-F1 = {new.F1.mean():.4f}')
    rows.append(new)
auto = save(pd.concat(rows).drop(columns=['retrieved_all']).round(3), 'retrieval_autoforms_EXPLORATORY.csv')
""")

code(r"""
# EXPLORATORY 2 (RQ2): swap the stop lists between the two normalisations to separate their effects.
ABL = {'minimal stop + snowball': vgir.make_pipeline('minimal', 'snowball'),
       'nltk stop + lemma': vgir.make_pipeline('nltk', 'lemma')}
rows = []
for name, fn in ABL.items():
    ix = vgir.PositionalIndex(fn, name).build(docs)
    QE[name] = vgir.QueryEngine(ix)
    r = evaluate(name, QUERIES)
    rows.append({'pipeline': name, 'tokens': ix.token_count(), 'vocabulary': ix.vocab_size(),
                 'domain_term_preservation': round(vgir.domain_term_preservation(fn)[0], 3),
                 **r[METRICS].mean().round(3).to_dict()})
for p in ('A', 'B'):
    rows.append({'pipeline': f'{p} (preregistered)', 'tokens': STRUCT[p]['Token Count'], 'vocabulary': STRUCT[p]['Vocabulary Size'],
                 'domain_term_preservation': round(STRUCT[p]['Domain-term preservation'], 3), **MACRO[p][METRICS].round(3).to_dict()})
ablation = save(pd.DataFrame(rows), 'ablation_EXPLORATORY.csv')
ablation
""")

code(r"""
# EXPLORATORY 4: does the pipeline matter for verbose queries? Each MIRACL question as an OR of all its words
# (stop words and inflected verbs kept; each pipeline analyses them its own way). With OR almost every document
# matches, so the ranked metrics (P@5, P@10, R@10) carry the comparison.
QQ = [(q, ' OR '.join(re.findall(r'[A-Za-z0-9]+', QUESTION[q])), 'or', 'question as OR', c) for q, _, _, _, c in QUERIES]
verbose = pd.concat([evaluate(p, QQ) for p in ('A', 'B')], ignore_index=True)
save(verbose.drop(columns=['retrieved_all']).round(3), 'retrieval_question_OR_EXPLORATORY.csv')
display(verbose.groupby('pipeline')[METRICS].mean().round(3))
verbose.pivot(index='our_qid', columns='pipeline', values=['P@5', 'P@10', 'R@10']).round(2)
""")

code(r"""
# EXPLORATORY 5: what do the query engine's MWE expansions contribute? vgir's single-term operand returns
#   (1) direct postings of the term, plus (2) postings of lexicon MWEs that contain the term as a component
#   ('zelda' -> 'the_legend_of_zelda'), plus (3) a substring fallback: any MWE part (>= 3 chars) containing the
#   term or contained in it ('war' -> 'warcraft'). Variants below switch (3), then (2)+(3), off.
class ComponentOnlyQE(vgir.QueryEngine):
    def operand(self, text):
        terms = self.analyze(text.strip('"'))
        if not terms: return None, []
        if len(terms) > 1: return self.phrase(terms), terms
        t = terms[0][0]; q = t.split('_'); hits = set(self.ix.post.get(t, {}))
        for k, posts in self.ix.post.items():
            if k != t and '_' in k:
                parts = k.split('_')
                if any(parts[i:i + len(q)] == q for i in range(len(parts) - len(q) + 1)): hits |= set(posts)
        return hits, terms
class DirectOnlyQE(vgir.QueryEngine):
    def operand(self, text):
        terms = self.analyze(text.strip('"'))
        if not terms: return None, []
        return (set(self.ix.post.get(terms[0][0], {})) if len(terms) == 1 else self.phrase(terms)), terms
rows = []
for p in ('A', 'B'):
    for variant, cls in (('full (vgir)', vgir.QueryEngine), ('no substring fallback', ComponentOnlyQE), ('direct postings only', DirectOnlyQE)):
        key = f'{p} | {variant}'; QE[key] = cls(IX[p])
        r = evaluate(key, QUERIES)
        rows.append({'pipeline': p, 'operand_matching': variant, 'docs_retrieved_total': int(r.n_retrieved.sum()),
                     **r[['P', 'R', 'F1']].mean().round(3).to_dict(),
                     'queries_changed_vs_full': int((r.retrieved_all.values != RUN[p].retrieved_all.values).sum())})
mwe_expansion = save(pd.DataFrame(rows), 'mwe_expansion_EXPLORATORY.csv')
mwe_expansion
""")

code(r"""
# EXPLORATORY 3 (H4 probe): phrase queries with internal stop words. Both pipelines keep original positions when they
# drop stop words, so a dropped word leaves a gap that ANY token can fill. Truth = exact phrase in the cleaned text.
PROBE = ['Breath of the Wild', 'Ocarina of Time', 'developed by Nintendo', 'published by Sega',
         'released for the Wii', 'released in North America', 'one of the best', 'based on the']
def exact_docs(ph):
    rx = re.compile(r'(?<!\w)' + r'\s+'.join(map(re.escape, ph.split())) + r'(?!\w)', re.I)
    return {d for d in docs if rx.search(TEXT[d])}
rows = []
for ph in PROBE:
    truth = exact_docs(ph)
    row = {'phrase': ph, 'exact_docs': len(truth)}
    for p in ('A', 'B'):
        got = set(QE[p].search(f'"{ph}"')[0])
        row[f'{p}_query_terms'] = ' '.join(f'{t}@{i}' for t, i in IX[p].pipe(ph))
        row[f'{p}_docs'] = len(got)
        row[f'{p}_false_matches'] = ' '.join(sorted(got - truth))
        row[f'{p}_missed'] = ' '.join(sorted(truth - got))
    rows.append(row)
h4 = save(pd.DataFrame(rows), 'h4_phrase_gap_probe_EXPLORATORY.csv')
h4
""")

md(r"""
### Hypotheses H1-H6 (PREREGISTRATION section 2), computed from the results above
H1-H3, H5 and H6 are confirmatory on the amended 12-query set. H4 cannot be tested on that set because none of its phrase queries contains an internal stop word, so its verdict comes from the exploratory probe above.
""")

code(r"""
KB = ['keyword', 'and', 'or', 'not']
recKB = {p: RUN[p][RUN[p].type.isin(KB)].R.mean() for p in ('A', 'B')}
precAll = {p: RUN[p].P.mean() for p in ('A', 'B')}
precPh = {p: RUN[p][RUN[p].type == 'phrase'].P.mean() for p in ('A', 'B')}
nfalse = {p: sum(len(x.split()) for x in h4[f'{p}_false_matches']) for p in ('A', 'B')}
def verdict(cond, equal=False): return 'not supported (no difference)' if equal else ('supported' if cond else 'not supported')
S = STRUCT
hyp = pd.DataFrame([
    ('H1', 'B has a smaller vocabulary and fewer tokens than A',
     f"tokens A {S['A']['Token Count']:,} / B {S['B']['Token Count']:,}; vocabulary A {S['A']['Vocabulary Size']:,} / B {S['B']['Vocabulary Size']:,}",
     verdict(S['B']['Token Count'] < S['A']['Token Count'] and S['B']['Vocabulary Size'] < S['A']['Vocabulary Size'])),
    ('H2', 'B has higher macro recall than A on keyword and Boolean queries',
     f"macro R (keyword+AND+OR+NOT, n={int(RUN['A'].type.isin(KB).sum())}) A {recKB['A']:.3f} / B {recKB['B']:.3f}",
     verdict(recKB['B'] > recKB['A'], abs(recKB['B'] - recKB['A']) < 1e-12)),
    ('H3', 'A has higher macro precision than B, especially on phrase queries',
     f"macro P A {precAll['A']:.3f} / B {precAll['B']:.3f}; phrase P A {precPh['A']:.3f} / B {precPh['B']:.3f}",
     verdict(precAll['A'] > precAll['B'], abs(precAll['A'] - precAll['B']) < 1e-12)),
    ('H4', 'B produces false phrase matches from position-preserving stop removal',
     f"not testable on the 12 queries; probe ({len(h4)} phrases with internal stop words): false-match documents A {nfalse['A']} / B {nfalse['B']}",
     'exploratory: ' + ('B produces false matches' if nfalse['B'] > 0 else 'no false matches observed')),
    ('H5', 'A preserves >= 5 percentage points more domain-lexicon terms than B',
     f"preservation A {S['A']['Domain-term preservation']:.3f} / B {S['B']['Domain-term preservation']:.3f}",
     verdict(S['A']['Domain-term preservation'] - S['B']['Domain-term preservation'] >= 0.05)),
    ('H6', 'A has a higher meaningful-bigram rate (top 20) than B',
     f"rate A {S['A']['Meaningful bigram rate (top 20)']:.2f} / B {S['B']['Meaningful bigram rate (top 20)']:.2f}",
     verdict(S['A']['Meaningful bigram rate (top 20)'] > S['B']['Meaningful bigram rate (top 20)'])),
], columns=['hypothesis', 'statement', 'evidence', 'verdict'])
save(hyp, 'hypotheses.csv')
""")

# ------------------------------------------------------------------ GUI
md(r"""
## GUI (assignment section 6): the 15 functions
A Gradio `Blocks` app styled as a diagnostic instrument (design tokens, faint dot grid, one accent per pipeline: A terracotta, B slate, Final ink).

| # | Function | Tab |
|---|---|---|
| 1-2 | Load/upload documents; statistics | Documents |
| 3 | Tokenization | Tokenization Lab (token chips: NLTK, spaCy, custom, hybrid, BPE) |
| 4 | Preprocessing | Pipeline Trace (each stage of A or B streamed live, with real per-stage timings) |
| 5-6 | POS tagging; custom POS | POS Tagging; Custom POS |
| 7 | NER | NER |
| 8-9 | N-grams; BPE | N-Grams; BPE |
| 10 | Inverted index | Index Explorer (sortable terms dictionary as in the sample GUI; postings with click-to-expand context) |
| 11-13 | Query input, query type, retrieval | Search |
| 14 | Pipeline comparison | Compare A vs B (same query side by side, diff region); Statistics |
| 15 | Performance / evaluation | Statistics |

The Pipeline Trace pauses 0.15 s between stages so each stage is visible. That pause is a UI-only visualisation delay, not pipeline latency: the badge on each stage shows the measured compute time.
""")

code(r"""
import gradio as gr, html as _html, tempfile
PIPE_CHOICES = [(f'Final ({FINAL})', 'Final'), ('A: lemmas', 'A'), ('B: stems', 'B')]   # (label shown, value used)
def pick(p): return FINAL if p == 'Final' else p
EVAL_FORMS = {f: q for q, f, *_ in QUERIES}
SAMPLE_TEXT = "Super Mario Bros. was released for the Nintendo Entertainment System in 1985 and sold 40 million copies."
QTYPES = [('Use operators as typed', 'As typed'), ('Single word or name', 'Keyword'), ('Exact phrase', 'Phrase'),
          ('All words (AND)', 'Boolean AND'), ('Any word (OR)', 'Boolean OR'), ('First word, without the others (NOT)', 'Boolean NOT')]

# ---------------------------------------------------------------- design system (tokens defined once)
GUI_CSS = '''
:root, .dark {
  --bg: #f7f6f3; --surface: #ffffff; --surface-sunken: #ededea; --border: #e0ddd6; --dot: rgba(0,0,0,0.08);
  --text: #1a1917; --text-muted: #5f5e59; --text-faint: #807e77;
  --pipeline-a: #d97757; --pipeline-b: #4a7a8c; --pipeline-final: #1a1917;
  /* text-safe versions of the pipeline colours (>= 4.5:1 on page and card backgrounds); the bright ones stay for lines and fills */
  --pipeline-a-ink: #a64b2c; --pipeline-b-ink: #3a6676;
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px; --space-5: 24px; --space-6: 32px; --space-7: 48px;
  --accent-active: #d97757; --accent-success: #5a8a5e; --accent-warning: #c9a452; --accent-error: #b55a4a;
  --font-sans: 'Inter', -apple-system, system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace;
  --ease-out: cubic-bezier(0.23, 1, 0.32, 1);   /* strong ease-out for entering / responding UI */
  /* map Gradio's own accent variables onto the palette (tab underline, radios, focus) */
  --color-accent: var(--accent-active); --color-accent-soft: rgba(217,119,87,0.10);
  --checkbox-background-color-selected: var(--pipeline-final); --checkbox-border-color-selected: var(--pipeline-final);
  --checkbox-border-color-focus: var(--accent-active); --input-border-color-focus: var(--accent-active);
  --layout-gap: var(--space-3); --block-label-text-color: var(--text-muted);
}
button[role="tab"][aria-selected="true"] { color: var(--text) !important; }
body, gradio-app, .gradio-container {
  background-color: var(--bg) !important;
  background-image: radial-gradient(circle, var(--dot) 1px, transparent 1px) !important;
  background-size: 24px 24px !important;
  font-family: var(--font-sans); color: var(--text); font-variant-numeric: tabular-nums;
}
.gradio-container { width: 100% !important; min-width: 0 !important; max-width: 1200px !important; margin: 0 auto !important;
  padding: var(--space-6) var(--space-6) var(--space-7) !important; }
.gradio-container .main, .gradio-container .wrap, .gradio-container main.contain, .gradio-container .column,
.gradio-container .row, .gradio-container .form, .gradio-container .block { min-width: 0 !important; }

.gradio-container table { font-family: var(--font-mono); font-size: 12.5px; line-height: 1.4; }
button { border-radius: 4px !important; box-shadow: none !important;
  transition: border-color 150ms ease, transform 160ms var(--ease-out) !important; }
button:active { transform: scale(0.97); }
@media (hover: hover) and (pointer: fine) { button:hover { border-color: var(--accent-active) !important; } }
button.primary { background: var(--pipeline-final) !important; color: #fff !important; border: 1px solid var(--pipeline-final) !important; }
input, textarea { font-family: var(--font-mono) !important; }
input:focus, textarea:focus { border-color: var(--accent-active) !important; }
.xr-header { padding-bottom: var(--space-4); }
.xr-header h1 { font-weight: 700; font-size: 26px; letter-spacing: -0.3px; margin: 0 0 var(--space-2); text-wrap: balance; }
.xr-sub { font-size: 15px; line-height: 1.5; color: var(--text); max-width: 72ch; margin: 0 0 var(--space-3); }
.xr-meta { font-family: var(--font-mono); font-size: 12px; line-height: 1.6; color: var(--text-muted); display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-4); }
.xr-meta b { color: var(--text); font-weight: 500; }
.ink-a { color: var(--pipeline-a-ink); } .ink-b { color: var(--pipeline-b-ink); }
.tab-intro { font-size: 14px; line-height: 1.55; color: var(--text); max-width: 75ch; margin: var(--space-2) 0 var(--space-3); text-wrap: pretty; }
.tab-intro .hint { display: block; color: var(--text-muted); margin-top: var(--space-1); }
.tab-intro code, .xr-sub code { font-family: var(--font-mono); font-size: 12.5px; background: var(--surface-sunken); padding: 1px 4px; border-radius: 2px; }
.sec { margin: var(--space-6) 0 0; padding-top: var(--space-4); border-top: 1px solid var(--border); }
.sec h3 { font-size: 15px; font-weight: 600; margin: 0 0 var(--space-1); }
.sec p { font-size: 13.5px; line-height: 1.5; color: var(--text-muted); margin: 0; max-width: 75ch; }
.xr-card { background: var(--surface); border: 1px solid var(--border); border-radius: 2px; padding: 24px;
           box-shadow: 0 1px 2px rgba(0,0,0,0.03); margin: 0 0 12px; position: relative; overflow: hidden; }
.xr-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); font-weight: 500; }
.mono { font-family: var(--font-mono); }
.ms { font-family: var(--font-mono); font-size: 12px; color: var(--text-muted); }
.ms .unit { opacity: 0.5; margin-left: 1px; }
.metric { display: inline-block; margin-right: 22px; animation: tick 200ms var(--ease-out) both; }
.metric .v { font-family: var(--font-mono); font-size: 18px; font-weight: 500; }
@keyframes tick { from { opacity: 0.5; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
/* token chips */
.token-chip { display: inline-flex; align-items: center; padding: 2px 8px; margin: 2px; background: var(--surface-sunken);
  border: 1px solid var(--border); border-radius: 999px; font-family: var(--font-mono); font-size: 13px; color: var(--text);
  transition: border-color 120ms ease, background-color 120ms ease; }
@media (hover: hover) and (pointer: fine) { .token-chip:hover { border-color: var(--accent-active); background: var(--surface); } }
.token-chip.merged { background: rgba(217,119,87,0.10); border-color: var(--accent-active); }
.token-chip.stopword { color: var(--text-muted); text-decoration: line-through; }
.token-chip.punct { color: var(--text-muted); }
.token-chip.proper-noun { font-weight: 600; color: var(--pipeline-a-ink); }
.token-chip.changed { border-color: var(--pipeline-b); }
.token-chip sub { font-size: 10px; color: var(--text-muted); margin-left: 4px; font-weight: 400; }
.tok-row { display: grid; grid-template-columns: 150px minmax(0, 1fr); gap: var(--space-3); padding: var(--space-3) 0; border-top: 1px solid var(--border); }
@media (max-width: 640px) { .tok-row { grid-template-columns: 1fr; gap: var(--space-1); } }
.tok-row:first-child { border-top: 0; }
.tok-row { animation: settle 220ms var(--ease-out) both; }
.tok-row:nth-child(2) { animation-delay: 40ms; }
.tok-row:nth-child(3) { animation-delay: 80ms; }
.tok-row:nth-child(4) { animation-delay: 120ms; }
.tok-row:nth-child(5) { animation-delay: 160ms; }
.tok-row:nth-child(6) { animation-delay: 200ms; }
/* stage cards */
.stage-head { display: flex; align-items: center; gap: 12px; }
.stage-no { font-family: var(--font-mono); color: var(--text-faint); font-size: 12px; }
.stage-name { font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; font-size: 13px; }
.stage-note { color: var(--text-muted); font-size: 12px; }
.stage-right { margin-left: auto; display: flex; align-items: center; gap: 10px; }
.status { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot-pending { border: 1px solid var(--text-faint); }
.dot-active { background: var(--accent-active); animation: pulse 1s ease-in-out infinite; }
.dot-done { background: var(--accent-success); }
@keyframes pulse { 0%,100% { opacity: 0.35; } 50% { opacity: 1; } }
.stage-output { border-top: 1px solid var(--border); margin-top: 12px; padding-top: 10px; }
.stage-output.fresh { animation: settle 220ms var(--ease-out) both; }
@keyframes settle { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
@keyframes shimmer { 0% { background-position: -100% 0; } 100% { background-position: 200% 0; } }
.stage-active { background: linear-gradient(90deg, var(--surface) 0%, var(--surface) 40%, rgba(217,119,87,0.08) 50%,
  var(--surface) 60%, var(--surface) 100%); background-size: 200% 100%; animation: shimmer 1.4s linear infinite;
  border-color: var(--accent-active); }
@keyframes scan { from { transform: translateX(-100%); } to { transform: translateX(0); } }
/* full-width layer whose right edge is the 1px sweep line; translateX(%) is relative to its own width */
.scanner-line { position: absolute; inset: 0; pointer-events: none; opacity: 0.4;
  background: linear-gradient(to right, transparent calc(100% - 1px), var(--accent-active) calc(100% - 1px));
  animation: scan 800ms linear infinite; }
/* A vs B */
.cmp { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: var(--space-3); }
.cmp-col { border-top: 2px solid var(--border); animation: settle 220ms var(--ease-out) both; }
.cmp-col:nth-child(2) { animation-delay: 60ms; }
.cmp-col.a { border-top-color: var(--pipeline-a); } .cmp-col.b { border-top-color: var(--pipeline-b); }
.cmp-col h3 { margin: 0 0 8px; font-size: 14px; font-weight: 600; }
.cmp-col.a h3 { color: var(--pipeline-a-ink); } .cmp-col.b h3 { color: var(--pipeline-b-ink); }
.doc-row { font-family: var(--font-mono); font-size: 12.5px; padding: 3px 0; border-bottom: 1px solid var(--border); }
.doc-row .t { font-family: var(--font-sans); color: var(--text-muted); margin-left: 8px; }
.rel { color: var(--accent-success); }
.diff-a { color: var(--pipeline-a-ink); } .diff-b { color: var(--pipeline-b-ink); } .diff-both { color: var(--text); }
/* postings */
.post-tree { font-family: var(--font-mono); font-size: 12.5px; }
.post-tree details { border-bottom: 1px solid var(--border); padding: 4px 0; }
.post-tree summary { cursor: pointer; list-style: none; display: grid; grid-template-columns: 22px 60px 1fr 140px; }
.post-tree summary::-webkit-details-marker { display: none; }
.post-tree .ctx { color: var(--text-muted); padding: 4px 0 4px 82px; font-family: var(--font-sans); font-size: 12.5px; }
.post-tree details[open] > .ctx { animation: settle 180ms var(--ease-out) both; }
@keyframes fade { from { opacity: 0; } to { opacity: 1; } }
@media (prefers-reduced-motion: reduce) {
  .stage-output.fresh, .tok-row, .cmp-col, .metric { animation: fade 150ms ease both; }
  .stage-active, .dot-active { animation: none; }
  .scanner-line { display: none; }
  button:active { transform: none; }
  .post-tree details[open] > .ctx { animation: fade 150ms ease both; }
}
.post-tree mark { background: rgba(217,119,87,0.18); color: var(--text); padding: 0 2px; }
'''
GUI_HEAD = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
            '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">'
            # phone layout lives here: Gradio scopes media queries in css= under .contain, so container-level rules there never match
            '<style>@media (max-width: 640px) {'
            ' .gradio-container.gradio-container { padding: 16px 16px 32px !important; }'
            ' .gradio-container .main.fillable { padding-left: 0 !important; padding-right: 0 !important; }'
            ' .gradio-container .row { flex-wrap: wrap !important; }'
            ' .gradio-container .row > *, .gradio-container .form > .block { flex: 1 1 100% !important; }'
            ' .gradio-container .xr-header h1 { font-size: 21px !important; } .gradio-container .xr-sub { font-size: 14px !important; } }</style>')
GUI_JS = "() => { document.body.classList.remove('dark'); }"     # the palette is light-only; keep Gradio from switching to its dark theme
GUI_THEME = gr.themes.Base(radius_size='sm')
_fav = os.path.join(tempfile.gettempdir(), 'xray_dot.svg')
open(_fav, 'w').write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><circle cx="8" cy="8" r="5" fill="#d97757"/></svg>')

REL_DOT = '<span class="rel">●</span>'          # marks a judged-relevant document
def esc(s): return _html.escape(str(s))
def chip(t, cls='', sub=''): return f'<span class="token-chip {cls}">{esc(t)}{f"<sub>{esc(sub)}</sub>" if sub else ""}</span>'
def ms_badge(x): return f'<span class="ms">{x:.2f}<span class="unit">ms</span></span>'
def metric(label, value): return f'<span class="metric"><span class="xr-label">{esc(label)}</span><br><span class="v">{value}</span></span>'
def card(inner, cls=''): return f'<div class="xr-card {cls}">{inner}</div>'

# ---------------------------------------------------------------- 1-2 documents (plain tables)
def gui_docs_table():
    return pd.DataFrame([{'doc_id': d, 'title': TITLE[d], 'tokens': len(HYB.get(d, []))} for d in docs])
def gui_upload(files):
    # Streams one stage card per step so a long rebuild is visibly in progress (pattern of gui_trace).
    if not files:
        yield card('<span class="ms">No files selected.</span>'), gui_docs_table(); return
    steps = [('Add documents', 'clean + tokenize'), ('Rebuild index A', 'lemmas, spaCy tagger'),
             ('Rebuild index B', 'stems, Snowball')]
    done = []
    def frame(k):   # k = index of the active step, or len(steps) when all are done
        html = ''.join(_stage(*a, fresh=(j == len(done) - 1)) for j, a in enumerate(done))
        if k < len(steps):
            html += _stage(k + 1, steps[k][0], 'active', note=steps[k][1])
            html += ''.join(_stage(j + 1, steps[j][0], 'pending', note=steps[j][1]) for j in range(k + 1, len(steps)))
        return html
    yield frame(0), gui_docs_table()
    t0 = time.perf_counter(); added = []
    for f in files:
        path = f if isinstance(f, str) else f.name
        with open(path, encoding='utf-8', errors='replace') as fh:
            title = fh.readline().strip() or os.path.basename(path); body = fh.read()
        did = f'D{len(docs) + 1:02d}'
        docs[did] = {'title': vgir.clean_text(title), 'body': vgir.clean_text(body)}
        TITLE[did], TEXT[did] = docs[did]['title'], vgir.full_text(docs[did]); HYB[did] = vgir.tok_hybrid(TEXT[did])
        added.append(did)
    done.append((1, steps[0][0], 'done', '<br>'.join(f'{d} · {esc(TITLE[d])}' for d in added),
                 (time.perf_counter() - t0) * 1000, steps[0][1]))
    for k, p in ((1, 'A'), (2, 'B')):
        yield frame(k), gui_docs_table()
        t0 = time.perf_counter()
        IX[p] = vgir.PositionalIndex(vgir.PIPELINES[p], p).build(docs); QE[p] = vgir.QueryEngine(IX[p])
        done.append((k + 1, steps[k][0], 'done', f'<span class="mono">{IX[p].vocab_size():,} terms · {len(docs)} documents</span>',
                     (time.perf_counter() - t0) * 1000, steps[k][1]))
    yield (frame(len(steps)) + '<div class="ms" style="margin-top:8px">Evaluation tables still refer to D01-D53.</div>',
           gui_docs_table())

# ---------------------------------------------------------------- 3 Tokenization Lab (chips)
def gui_token_lab(text):
    rows = []
    for name in TOK_NAMES:
        toks = vgir.TOKENIZERS[name](text)
        chips = ''.join(chip(t, 'merged' if '_' in t else ('punct' if vgir.is_punct(t) else '')) for t in toks)
        rows.append((name, len(toks), chips))
    bpe = [p for w in vgir.tok_custom(text) for p in (corpus_bpe(w.lower()) if w.isalpha() else [w])]
    rows.append(('bpe (corpus)', len(bpe), ''.join(chip(p) for p in bpe)))
    if ENC:
        g = [ENC.decode_single_token_bytes(i).decode('utf-8', 'replace') for i in ENC.encode(text)]
        rows.append(('bpe (gpt-2)', len(g), ''.join(chip(p.replace(' ', '␣')) for p in g)))
    body = ''.join(f'<div class="tok-row"><div><div class="stage-name">{esc(n)}</div><div class="ms">{c} tokens</div></div><div>{ch}</div></div>'
                   for n, c, ch in rows)
    return card(body)

# ---------------------------------------------------------------- 4 Pipeline Trace (streamed stage by stage)
TRACE_DELAY = 0.15   # UI-only visualisation delay between stages so each stage is visible; NOT pipeline latency
def _stage(i, name, status, body='', t=None, note='', fresh=False):
    badge = ms_badge(t) if (t is not None and status == 'done') else ''
    cls = 'xr-card' + (' stage-active' if status == 'active' else '')
    scan = '<div class="scanner-line"></div>' if status == 'active' else ''
    out = f'<div class="stage-output{" fresh" if fresh else ""}">{body}</div>' if status == 'done' else ''
    return (f'<div class="{cls}">{scan}<div class="stage-head"><span class="stage-no">{i:02d}</span>'
            f'<span class="stage-name">{esc(name)}</span><span class="stage-note">{esc(note)}</span>'
            f'<span class="stage-right">{badge}<span class="status dot-{status}"></span></span></div>{out}</div>')

def _trace_steps(text, p):
    # Each step = (name, note, function(state) -> (state, html)). Reproduces vgir.pipeline_A / pipeline_B exactly.
    def clean(s):
        s['text'] = vgir.clean_text(s['raw']); return s, f'<div class="mono">{esc(s["text"])}</div>'
    def tokenize(s):
        s['toks'] = vgir.tok_hybrid(s['text'])
        return s, ''.join(chip(t, 'merged' if '_' in t else ('punct' if vgir.is_punct(t) else '')) for t in s['toks'])
    if p == 'A':
        def tag(s):
            s['tags'] = vgir.spacy_tag_tokens(s['toks'])
            return s, ''.join(chip(t, 'proper-noun' if u == 'PROPN' else ('punct' if vgir.is_punct(t) else ''), tg)
                              for t, (tg, u, _) in zip(s['toks'], s['tags']))
        def lemma(s):
            s['lem'] = []
            for t, (tg, u, l) in zip(s['toks'], s['tags']):
                keep = '_' in t or u == 'PROPN' or re.search(r'\d', t)
                s['lem'].append(None if vgir.is_punct(t) else (t if keep else l))
            return s, ''.join(chip(t, 'punct') if l is None else chip(l, 'merged' if '_' in l else ('changed' if l != t else ''))
                              for t, l in zip(s['toks'], s['lem']))
        def lower(s):
            s['low'] = [None if l is None else l.lower() for l in s['lem']]
            return s, ''.join(chip(l) for l in s['low'] if l is not None)
        def stop(s):
            s['terms'] = [(l, i) for i, l in enumerate(s['low']) if l is not None and l not in vgir.STOP_MINIMAL]
            return s, ''.join(chip(l, 'stopword' if l in vgir.STOP_MINIMAL else '') for l in s['low'] if l is not None)
        steps = [('Clean', 'unicode, diacritics, artefacts', clean), ('Tokenize', 'hybrid: variants + MWE merge', tokenize),
                 ('POS tag', 'spaCy, cased, in context', tag), ('Lemmatize', 'POS-aware; names and numbers kept', lemma),
                 ('Lowercase', '', lower), ('Stop words', 'minimal list (10), positions kept', stop)]
    else:
        stops, st = STOP_NLTK, vgir.stemmer('snowball')
        def lower(s):
            s['low'] = [None if vgir.is_punct(t) else t.lower() for t in s['toks']]
            return s, ''.join(chip(t, 'punct') if l is None else chip(l, 'merged' if '_' in l else '') for t, l in zip(s['toks'], s['low']))
        def stop(s):
            s['kept'] = [(l, i) for i, l in enumerate(s['low']) if l is not None and l not in stops]
            return s, ''.join(chip(l, 'stopword' if l in stops else '') for l in s['low'] if l is not None)
        def stem(s):
            s['terms'] = [(l if '_' in l else st.stem(l), i) for l, i in s['kept']]
            return s, ''.join(chip(t, 'merged' if '_' in t else ('changed' if t != l else '')) for (t, _), (l, _) in zip(s['terms'], s['kept']))
        steps = [('Clean', 'unicode, diacritics, artefacts', clean), ('Tokenize', 'hybrid: variants + MWE merge', tokenize),
                 ('Lowercase', '', lower), ('Stop words', f'NLTK list ({len(stops)}), positions kept', stop),
                 ('Stem', 'Snowball; merged names kept', stem)]
    return steps

def gui_trace(text, p):
    p = pick(p); steps = _trace_steps(text, p); n = len(steps) + 1
    done, state = [], {'raw': text}
    pending = lambda k: ''.join(_stage(j + 1, steps[j][0] if j < len(steps) else 'Index terms', 'pending') for j in range(k, n))
    head = f'<div class="xr-label" style="margin-bottom:10px">Pipeline {p} trace</div>'
    # Each yield re-sends the whole HTML, so only the stage that just finished carries the settle animation;
    # earlier stages render static and do not replay it.
    render_done = lambda: ''.join(_stage(*a, fresh=(j == len(done) - 1)) for j, a in enumerate(done))
    for k, (name, note, fn) in enumerate(steps):
        yield head + render_done() + _stage(k + 1, name, 'active', note=note) + pending(k + 1)
        t0 = time.perf_counter(); state, body = fn(state); dt = (time.perf_counter() - t0) * 1000
        time.sleep(TRACE_DELAY)
        done.append((k + 1, name, 'done', body, dt, note))
    terms = state['terms']
    same = terms == vgir.PIPELINES[p](state['text'])     # honesty check: trace == the pipeline used for indexing
    body = (''.join(chip(t, 'merged' if '_' in t else '', i) for t, i in terms) +
            f'<div class="ms" style="margin-top:10px">{len(terms)} terms (subscript = position). '
            f'{"identical to vgir.pipeline_" + p + " output" if same else "MISMATCH with vgir.pipeline_" + p}</div>')
    done.append((n, 'Index terms', 'done', body, 0.0, 'term @ position, as stored in the positional index'))
    yield head + render_done()

# ---------------------------------------------------------------- 5-9 analysis tabs (plain tables)
def gui_pos(text):
    ws = vgir.tok_nltk(text); return pd.DataFrame({'word': ws, 'nltk': tag_nltk(ws), 'spacy': tag_spacy(ws)})
def gui_custom_pos(text):
    ws = vgir.tok_nltk(text); d = tag_nltk(ws); c = tag_rule_custom(ws); k = KNN.predict(knn_feats(ws)).tolist()
    return pd.DataFrame({'word': ws, 'default_nltk': d, 'custom_rule': c, 'custom_knn': k,
                         'rule_changed_tag': [x != z for x, z in zip(d, c)]})
def gui_ner(text):
    a = [(e.text, e.label_) for e in NLP(text).ents]; b = {e.text: e.label_ for e in NLP_RULER(text).ents}
    keys = list(dict.fromkeys([t for t, _ in a] + list(b))); da = dict(a)
    return pd.DataFrame([{'entity': k, 'spacy_default': da.get(k, '-'), 'spacy_with_domain_ruler': b.get(k, '-')} for k in keys])
def gui_ngrams(p, n, k):
    c = NGRAMS[(pick(p), int(n))]; tot = sum(c.values())
    return pd.DataFrame([{'rank': i + 1, 'n_gram': ' '.join(g), 'count': v, 'frequency': round(v / tot, 5),
                          'meaningful': vgir.is_meaningful(g, STOP_NLTK) if int(n) > 1 else None}
                         for i, (g, v) in enumerate(c.most_common(int(k)))])
def gui_bpe(text):
    return pd.DataFrame([{'S.No.': i + 1, 'word': w, 'gpt2_bpe': ' | '.join(gpt2_pieces(w)), 'corpus_bpe': ' | '.join(corpus_bpe(w.lower()))}
                         for i, w in enumerate(w for w in vgir.tok_custom(text) if w.isalpha())])

# ---------------------------------------------------------------- 10 Index Explorer
def gui_terms(p, sort_by, contains):
    df = pd.DataFrame(IX[pick(p)].term_dictionary())
    if contains: df = df[df.term.str.contains(contains.lower(), regex=False)]
    df = df.sort_values(sort_by, ascending=(sort_by == 'term'), kind='stable').head(1000).reset_index(drop=True)
    df.insert(0, 'S.No.', range(1, len(df) + 1))
    return df[['S.No.', 'term', 'doc_freq', 'term_freq', 'documents']]
def gui_postings(p, term):
    pp = pick(p); ix = IX[pp]; analysed = ix.pipe(term)
    t = analysed[0][0] if analysed else term.lower()
    post = ix.post.get(t, {})
    via_mwe = sorted((QE[pp].operand(term)[0] or set()) - set(post)) if analysed and len(analysed) == 1 else []
    rows = []
    for i, (d, pos) in enumerate(sorted(post.items())):
        branch = '└─' if i == len(post) - 1 else '├─'
        ctx = []
        for x in pos[:5]:
            w = HYB[d]
            ctx.append(' '.join(esc(w[j]) if j != x else f'<mark>{esc(w[j])}</mark>' for j in range(max(0, x - 5), min(len(w), x + 6))))
        more = f' <span class="ms">(+{len(pos) - 5} more)</span>' if len(pos) > 5 else ''
        rows.append(f'<details><summary><span>{branch}</span><span>{d}</span><span>{esc(pos[:12])}{"..." if len(pos) > 12 else ""}</span>'
                    f'<span class="ms">{len(pos)} occurrence{"s" if len(pos) != 1 else ""}</span></summary>'
                    f'<div class="ctx"><b>{esc(TITLE[d])}</b><br>' + '<br>'.join(f'... {c} ...' for c in ctx) + more + '</div></details>')
    note = (f'<div class="ms" style="margin-top:10px">Keyword search also matches merged names containing it in '
            f'{len(via_mwe)} more document(s): {" ".join(via_mwe)}</div>') if via_mwe else ''
    head = (f'<div class="stage-head"><span class="stage-name">TERM: {esc(t)}</span>'
            f'<span class="stage-note">input "{esc(term)}" analysed by Pipeline {pp}</span>'
            f'<span class="stage-right ms">df = {len(post)}</span></div>')
    body = f'<div class="post-tree" style="margin-top:12px">{"".join(rows) or "<span class=ms>no postings</span>"}</div>{note}'
    return card(head + body)

# ---------------------------------------------------------------- 11-13 Search
def build_query(text, qtype):
    text = text.strip(); ws = text.split()
    if qtype == 'As typed' or re.search(r'"|\b(AND|OR|NOT)\b|[()]', text): return text
    if qtype == 'Phrase': return f'"{text}"'
    if qtype == 'Keyword' or len(ws) < 2: return text
    if qtype == 'Boolean AND': return ' AND '.join(ws)
    if qtype == 'Boolean OR': return ' OR '.join(ws)
    return ws[0] + ''.join(f' AND NOT {w}' for w in ws[1:])
def _eval_line(q, ranked):
    if q not in EVAL_FORMS: return ''
    g = RELEVANT[EVAL_FORMS[q]]; P_, R_, F_ = vgir.set_metrics(ranked, g)
    return (metric('precision', f'{P_:.3f}') + metric('recall', f'{R_:.3f}') + metric('f1', f'{F_:.3f}') +
            metric('p@5', f'{vgir.p_at_k(ranked, g, 5):.2f}') + metric('p@10', f'{vgir.p_at_k(ranked, g, 10):.2f}') +
            f'<div class="ms">{EVAL_FORMS[q]}: {len(g)} relevant documents (two-person judgments, preliminary)</div>')
def gui_search(text, qtype, p):
    q = build_query(text, qtype); pp = pick(p)
    ranked, terms, cold, warm = QE[pp].timed_search(q, repeats=3)
    gold = RELEVANT.get(EVAL_FORMS.get(q))
    rows = [{'rank': i + 1, 'document': d, 'title': TITLE[d], **({'judged relevant': 'yes' if d in gold else ''} if gold is not None else {})}
            for i, d in enumerate(ranked)]
    table = pd.DataFrame(rows, columns=['rank', 'document', 'title'] + (['judged relevant'] if gold is not None else []))
    if not ranked:
        note = '<div class="ms" style="margin-top:10px">No document matches every condition. Try fewer AND terms, or OR instead.</div>'
    else:
        note = f'<div style="margin-top:10px">{_eval_line(q, ranked)}</div>'
    info = card(f'<div class="xr-label">query run on pipeline {pp}</div><div class="mono" style="margin:6px 0 14px">{esc(q)}</div>'
                + metric('documents found', len(ranked)) + metric('first run', ms_badge(cold)) + metric('repeat run', ms_badge(warm)) + note)
    return info, table
SEARCH_EMPTY = card('<span class="ms">Results appear here: ranked documents, how long the query took, and, for the 12 evaluation '
                    'queries, precision and recall against the hand-checked relevance labels.</span>')

# ---------------------------------------------------------------- 14 Compare A vs B
def gui_compare(text, qtype):
    q = build_query(text, qtype); res = {}
    for p in ('A', 'B'):
        ranked, _, cold, warm = QE[p].timed_search(q, repeats=3); res[p] = (ranked, warm)
    gold = RELEVANT.get(EVAL_FORMS.get(q), set())
    def col(p):
        ranked, warm = res[p]
        rows = ''.join(f'<div class="doc-row">{i + 1:>2}  {d}{" " + REL_DOT if d in gold else ""}'
                       f'<span class="t">{esc(TITLE[d])}</span></div>' for i, d in enumerate(ranked[:15]))
        more = f'<div class="ms">+{len(ranked) - 15} more</div>' if len(ranked) > 15 else ''
        return (f'<div class="xr-card cmp-col {p.lower()}"><h3>Pipeline {p}</h3>' + metric('documents found', len(ranked)) +
                metric('repeat run', ms_badge(warm)) + f'<div style="margin-top:12px">{rows or "<span class=ms>no documents match</span>"}{more}</div>'
                + f'<div style="margin-top:12px">{_eval_line(q, ranked)}</div></div>')
    a, b = set(res['A'][0]), set(res['B'][0])
    diff = card(f'<div class="xr-label">diff</div>'
                f'<div class="doc-row"><span class="diff-a">only A ({len(a - b)})</span><span class="t">{" ".join(sorted(a - b)) or "none"}</span></div>'
                f'<div class="doc-row"><span class="diff-b">only B ({len(b - a)})</span><span class="t">{" ".join(sorted(b - a)) or "none"}</span></div>'
                f'<div class="doc-row"><span class="diff-both">both ({len(a & b)})</span><span class="t">{" ".join(sorted(a & b)) or "none"}</span></div>'
                + (f'<div class="ms" style="margin-top:8px">{REL_DOT} = judged relevant</div>' if gold else ''))
    return (f'<div class="mono" style="margin-bottom:10px">{esc(q)}</div><div class="cmp">{col("A")}{col("B")}</div>{diff}')

# ---------------------------------------------------------------- merged views for the consolidated tabs
def gui_tokens_all(text):
    return gui_token_lab(text), gui_bpe(text)
def gui_tagging(text):
    ws = vgir.tok_nltk(text); d = tag_nltk(ws); sp = tag_spacy(ws); c = tag_rule_custom(ws); k = KNN.predict(knn_feats(ws)).tolist()
    pos = pd.DataFrame({'word': ws, 'NLTK (default)': d, 'spaCy (default)': sp, 'rules + dictionary (custom)': c, 'KNN (custom)': k,
                        'dictionary changed NLTK': ['yes' if x != z else '' for x, z in zip(d, c)]})
    return pos, gui_ner(text).rename(columns={'spacy_default': 'spaCy (general model)', 'spacy_with_domain_ruler': 'spaCy + video-game name list'})
def friendly(df, names):
    return df.rename(columns=names)
def intro(what, hint=''):
    return gr.HTML(f'<p class="tab-intro">{what}{f"<span class=hint>{hint}</span>" if hint else ""}</p>')
def section(title, note=''):
    return gr.HTML(f'<div class="sec"><h3>{title}</h3>{f"<p>{note}</p>" if note else ""}</div>')

# ---------------------------------------------------------------- layout
with gr.Blocks(title='NLP X-Ray: Video Games') as demo:
    gr.HTML(f'<div class="xr-header"><h1>NLP X-Ray: a search engine for video-game articles</h1>'
            f'<p class="xr-sub">{len(docs)} English Wikipedia articles, processed by two pipelines and searched with Boolean queries. '
            f'Every stage, from raw text to ranked results, can be inspected in the tabs below.</p>'
            f'<div class="xr-meta"><span>final pipeline <b>{FINAL}</b></span>'
            f'<span class="ink-a">A = annotate first, lemmas</span><span class="ink-b">B = normalise first, stems</span>'
            f'<span>F1 A {MACRO["A"]["F1"]:.3f} · B {MACRO["B"]["F1"]:.3f}</span>'
            f'<span>relevance labels: two reviewers (preliminary)</span></div></div>')

    with gr.Tab('Search'):
        intro('Type a Boolean query and get ranked documents. Words, <code>"exact phrases"</code>, <code>AND</code>, <code>OR</code>, '
              '<code>NOT</code> and parentheses are supported.',
              'Pick one of the 12 evaluation queries to also see precision and recall against the hand-checked labels.')
        with gr.Row(equal_height=True):
            preset = gr.Dropdown([f for _, f, *_ in QUERIES], value=None, label='Evaluation query (optional)', scale=2)
            qbox = gr.Textbox(label='Query', value=QUERIES[2][1], scale=3)
        with gr.Row(equal_height=True):
            qtype = gr.Dropdown(QTYPES, value='As typed', label='How to read the words', scale=2)
            qpipe = gr.Radio(PIPE_CHOICES, value='Final', label='Pipeline', scale=3)
        sbtn = gr.Button('Search', variant='primary')
        sinfo = gr.HTML(value=SEARCH_EMPTY); sout = gr.Dataframe(value=pd.DataFrame(columns=['rank', 'document', 'title']))
        preset.change(lambda f: f, preset, qbox)
        sbtn.click(gui_search, [qbox, qtype, qpipe], [sinfo, sout]); qbox.submit(gui_search, [qbox, qtype, qpipe], [sinfo, sout])

    with gr.Tab('Compare A vs B'):
        intro('Run one query through both pipelines and see the results side by side. The panel below lists documents found by only one pipeline.',
              'On the 12 evaluation queries both pipelines return identical documents; try your own queries to look for differences.')
        with gr.Row(equal_height=True):
            c_preset = gr.Dropdown([f for _, f, *_ in QUERIES], value=None, label='Evaluation query (optional)', scale=2)
            c_q = gr.Textbox(value=QUERIES[1][1], label='Query', scale=3)
            c_t = gr.Dropdown(QTYPES, value='As typed', label='How to read the words', scale=2)
        c_btn = gr.Button('Run on both pipelines', variant='primary'); c_out = gr.HTML()
        c_preset.change(lambda f: f, c_preset, c_q); c_btn.click(gui_compare, [c_q, c_t], c_out)

    with gr.Tab('Pipeline trace'):
        intro('Watch a sentence pass through each processing step of a pipeline. Every card shows that step\'s output and how long it took.',
              'Outlined chips are multi-word names kept as one token; struck-through chips are removed stop words. '
              'Steps are paused 0.15 s apart so they can be followed; the times shown exclude the pause.')
        with gr.Row(equal_height=True):
            tr_in = gr.Textbox(value=TRACE, label='Sentence to process', scale=4)
            tr_p = gr.Radio([('A: annotate first', 'A'), ('B: normalise first', 'B')], value=FINAL, label='Pipeline', scale=2)
        tr_btn = gr.Button('Trace through the pipeline', variant='primary'); tr_out = gr.HTML()
        tr_btn.click(gui_trace, [tr_in, tr_p], tr_out)

    with gr.Tab('Corpus'):
        intro(f'The {len(docs)} documents being searched: full Wikipedia articles drawn from the judged pools of 12 MIRACL questions.',
              'You can add your own .txt files (first line = title). Both indexes are rebuilt, which takes about 30 seconds.')
        up = gr.File(file_count='multiple', file_types=['.txt'], label='Add .txt documents')
        upmsg = gr.HTML(); dtable = gr.Dataframe(value=gui_docs_table(), label='Documents')
        up.upload(gui_upload, up, [upmsg, dtable])
        section('Corpus statistics', 'Counted after cleaning, with the hybrid tokenizer.')
        gr.Dataframe(value=corpus_summary)
        section('Per document')
        gr.Dataframe(value=doc_stats)

    with gr.Tab('Tokenization'):
        intro('See how six tokenizers split the same text. Only the hybrid tokenizer keeps multi-word names such as <code>Game_Boy</code> together.',
              'The BPE rows build words from learned sub-word pieces; <code>&lt;/w&gt;</code> marks the end of a word.')
        tl_in = gr.Textbox(value='Counter-Strike: Global Offensive on the Gameboy and PlayStation 3 sold $8.5 million in the 1990s', label='Text to tokenize')
        tl_btn = gr.Button('Tokenize with all six methods', variant='primary'); tl_out = gr.HTML()
        b_out = gr.Dataframe(headers=['S.No.', 'word', 'gpt2_bpe', 'corpus_bpe'], label='Sub-word pieces per word (BPE)')
        tl_btn.click(gui_tokens_all, tl_in, [tl_out, b_out])
        section('Across the whole corpus', 'Token counts and vocabulary sizes for each tokenizer, then for the two BPE models.')
        gr.Dataframe(value=tok_cmp); gr.Dataframe(value=bpe_corpus_cmp)
        section('Multi-word names kept intact', 'Out of the 91 multi-word names in the domain lexicon.')
        gr.Dataframe(value=tok_dom)

    with gr.Tab('POS & NER'):
        intro('Tag each word with its part of speech, and find named entities (people, companies, products, places, dates, money, events).',
              'Compare the default taggers with the custom ones, and the general entity model with the one that also uses the video-game name list.')
        tg_in = gr.Textbox(value='The game Prey was profiled with Doom and Halo on Destiny Islands for the Xbox.', label='Sentence to analyse')
        tg_btn = gr.Button('Tag parts of speech and entities', variant='primary')
        tg_pos = gr.Dataframe(headers=['word', 'NLTK (default)', 'spaCy (default)', 'rules + dictionary (custom)', 'KNN (custom)', 'dictionary changed NLTK'],
                              label='Part-of-speech tags (Penn Treebank)')
        tg_ner = gr.Dataframe(headers=['entity', 'spaCy (general model)', 'spaCy + video-game name list'], label='Named entities')
        tg_btn.click(gui_tagging, tg_in, [tg_pos, tg_ner])
        section('Tagger accuracy', 'On 226 hand-tagged tokens from the corpus. A difference of one or two points is within noise.')
        gr.Dataframe(value=pos_acc)
        section('Video-game names in the gold sample', 'How each tagger labels the domain terms (most should be proper nouns, NNP).')
        gr.Dataframe(value=pos_domain)
        section('Entity recognition accuracy', 'On 51 hand-labelled entities. "With domain ruler" adds the video-game name list.')
        gr.Dataframe(value=friendly(ner_summary, {'system': 'model'}))
        gr.Dataframe(value=ner, label='Every gold entity')

    with gr.Tab('N-grams'):
        intro('The most frequent word sequences (1 to 5 words) in each pipeline\'s index terms.',
              '"Meaningful" means: occurs at least twice, does not start or end with a stop word or a bare number, and contains a letter.')
        with gr.Row(equal_height=True):
            ng_p = gr.Radio(PIPE_CHOICES, value='Final', label='Pipeline', scale=2)
            ng_n = gr.Slider(1, 5, value=2, step=1, label='Words per sequence (n)', scale=2)
            ng_k = gr.Slider(5, 50, value=10, step=5, label='How many to show', scale=2)
        ng_btn = gr.Button('Count n-grams', variant='primary')
        ng_out = gr.Dataframe(headers=['rank', 'n_gram', 'count', 'frequency', 'meaningful'])
        ng_btn.click(gui_ngrams, [ng_p, ng_n, ng_k], ng_out)
        section('Summary', 'Total and distinct n-grams per pipeline, and the share of the top 20 that are meaningful.')
        gr.Dataframe(value=friendly(ng_summary[['pipeline', 'n_gram', 'total', 'unique', 'meaningful_rate_top20']],
                                    {'n_gram': 'n-gram', 'unique': 'distinct', 'meaningful_rate_top20': 'meaningful share of top 20'}))

    with gr.Tab('Index'):
        intro('The positional inverted index: for every term, the documents containing it and the token positions where it occurs.',
              'Look up any word or name; the input is processed by the selected pipeline first. Click a document row to read each occurrence in context.')
        with gr.Row(equal_height=True):
            ie_p = gr.Radio(PIPE_CHOICES, value='Final', label='Pipeline', scale=2)
            ie_term = gr.Textbox(value='Game Boy', label='Word or name to look up', scale=3)
        ie_btn = gr.Button('Look up in the index', variant='primary'); ie_out = gr.HTML()
        ie_btn.click(gui_postings, [ie_p, ie_term], ie_out); ie_term.submit(gui_postings, [ie_p, ie_term], ie_out)
        section('Term dictionary', 'Every term in the selected pipeline\'s index (first 1,000 after sorting), with its document and term frequency.')
        with gr.Row(equal_height=True):
            td_f = gr.Textbox(label='Show terms containing', scale=2)
            by_tf = gr.Button('Sort by term frequency', scale=1); by_df = gr.Button('Sort by document frequency', scale=1)
            by_t = gr.Button('Sort alphabetically', scale=1)
        td_out = gr.Dataframe(headers=['S.No.', 'term', 'doc_freq', 'term_freq', 'documents'])
        by_tf.click(lambda p, f: gui_terms(p, 'term_freq', f), [ie_p, td_f], td_out)
        by_df.click(lambda p, f: gui_terms(p, 'doc_freq', f), [ie_p, td_f], td_out)
        by_t.click(lambda p, f: gui_terms(p, 'term', f), [ie_p, td_f], td_out)

    with gr.Tab('Evaluation'):
        gr.HTML(card(f'<div class="xr-label">final pipeline</div><div style="font-size:18px;font-weight:600;margin:6px 0 10px">Pipeline {FINAL}</div>'
                     f'<p style="margin:0;max-width:75ch;line-height:1.55">Both pipelines return identical documents for all 12 evaluation queries '
                     f'(F1 {MACRO["A"]["F1"]:.3f} each), so the rule fixed before the experiment fell through to its tie-breaker. '
                     f'Pipeline A keeps all {len(PRES["A"][1])} domain names intact as single terms; B keeps '
                     f'{STRUCT["B"]["Domain-term preservation"]:.1%}. Results are preliminary: two reviewers checked the relevance labels.</p>'))
        section('Pipeline A vs B', 'Size of the index, quality of its phrases, and retrieval scores averaged over the 12 queries.')
        gr.Dataframe(value=tableH)
        section('Predictions made before the experiment', 'Hypotheses H1 to H6, and whether the results support them.')
        gr.Dataframe(value=hyp)
        section('Overall retrieval performance', 'Precision, recall and F1 averaged over the 12 queries.')
        gr.Dataframe(value=tableJ)
        section('All 12 queries counted together', 'TP = relevant and found, FP = found but not relevant, FN = relevant but missed, '
                'TN = correctly left out. Accuracy is high even for a system that finds nothing, which is why precision and recall are used.')
        gr.Dataframe(value=pd.read_csv(f'{RES}/retrieval_confusion_total.csv'))
        section('By query type')
        gr.Dataframe(value=friendly(tableI, {'n_retrieved': 'documents found', 'P': 'precision', 'R': 'recall', 'warm_ms': 'repeat run (ms)'}))
        section('Every query', 'One row per query and pipeline.')
        gr.Dataframe(value=friendly(retrieval[['pipeline', 'our_qid', 'query', 'type', 'n_retrieved', 'n_relevant', 'P', 'R', 'F1', 'P@5', 'P@10', 'warm_ms']].round(3),
                                    {'our_qid': 'query id', 'n_retrieved': 'found', 'n_relevant': 'relevant', 'P': 'precision', 'R': 'recall', 'warm_ms': 'repeat run (ms)'}))

def launch_gui(**kw):
    return demo.launch(theme=GUI_THEME, css=GUI_CSS, head=GUI_HEAD, js=GUI_JS, favicon_path=_fav,
                       footer_links=[], **kw)   # no Gradio footer (Runs / Use via API / Built with Gradio / Settings)
""")

code(r"""
# GUI self-test: every handler runs once without the browser. The trace must reproduce the indexing pipelines exactly.
info, res = gui_search(QUERIES[2][1], 'As typed', 'Final'); display(res.head())
for p in ('A', 'B'):
    frames = list(gui_trace(TRACE, p))
    assert f'identical to vgir.pipeline_{p} output' in frames[-1], f'trace for {p} differs from the pipeline'
    print(f'gui_trace {p}: {len(frames)} streamed frames, final terms identical to vgir.pipeline_{p}')
for fn, args in ((gui_token_lab, (SAMPLE_TEXT,)), (gui_compare, (QUERIES[1][1], 'As typed')), (gui_postings, ('A', 'Game Boy')),
                 (gui_pos, (SAMPLE_TEXT,)), (gui_custom_pos, (SAMPLE_TEXT,)), (gui_ner, (SAMPLE_TEXT,)), (gui_ngrams, ('A', 3, 10)),
                 (gui_bpe, (SAMPLE_TEXT,)), (gui_terms, ('B', 'doc_freq', '')), (gui_tokens_all, (SAMPLE_TEXT,)), (gui_tagging, (SAMPLE_TEXT,))):
    out = fn(*args); print(f'{fn.__name__:16} ok', getattr(out, 'shape', f'{len(out)} chars of HTML'))
assert gui_search('Zelda Nintendo', 'Boolean AND', 'A')[1].shape[0] > 0
assert 'judged relevant' in res.columns   # evaluation queries mark the hand-judged documents
""")

code(r"""
# Launch (Colab gives a public share link; set share=False to keep it local)
if os.environ.get('NO_GUI_LAUNCH') != '1':
    launch_gui(share=IN_COLAB, debug=False)
""")

code(r"""
# Everything this notebook wrote (assignment section 11 names are a subset)
print(len(os.listdir(RES)), 'files in results/:', sorted(os.listdir(RES)))
""")

nb = nbf.v4.new_notebook(cells=cells, metadata={'kernelspec': {'name': 'python3', 'display_name': 'Python 3', 'language': 'python'}})
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Domain_Text_Analysis_Retrieval.ipynb')
nbf.write(nb, out)
print(f'wrote Domain_Text_Analysis_Retrieval.ipynb with {len(cells)} cells')
