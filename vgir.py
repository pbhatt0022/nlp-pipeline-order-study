"""
vgir.py - shared core library (Video-Game Information Retrieval)
================================================================
Used by every script and by the GUI. Contains:
  cleaning, tokenizers (whitespace / NLTK / spaCy / custom regex / hybrid),
  Pipeline A and Pipeline B (see PREREGISTRATION.md), positional index,
  Boolean + phrase query engine, TF-IDF ranking, evaluation metrics,
  n-grams, BPE (GPT-2 via tiktoken + our own BPE trained per lecture slides).

Set the project folder with:  os.environ["VGIR_BASE"] = "/content/drive/MyDrive/Domain_Text_Analysis_Retrieval"
(default: current working directory)
"""
import os, re, json, math, time, unicodedata, statistics, glob
from collections import Counter, defaultdict

BASE = os.environ.get("VGIR_BASE", ".")
SEED = 42

def P(*parts):
    return os.path.join(BASE, *parts)

# ------------------------------------------------------------------ resources
_READY = {}

def ensure_nltk():
    if _READY.get("nltk"):
        return
    import nltk
    for r in ["punkt", "punkt_tab", "stopwords", "wordnet", "omw-1.4",
              "averaged_perceptron_tagger", "averaged_perceptron_tagger_eng"]:
        try:
            nltk.download(r, quiet=True)
        except Exception:
            pass
    _READY["nltk"] = True

_SPACY = {}
def spacy_model():
    """Full small English model (tagger, lemmatizer, NER)."""
    if "sm" not in _SPACY:
        import spacy
        _SPACY["sm"] = spacy.load("en_core_web_sm")
    return _SPACY["sm"]

def spacy_blank():
    if "blank" not in _SPACY:
        import spacy
        _SPACY["blank"] = spacy.blank("en")
    return _SPACY["blank"]

# ------------------------------------------------------------------ lexicon
_LEX = {}
def lexicon():
    """domain_lexicon.json: titles, platforms, companies, events, genre_terms, variants."""
    if not _LEX:
        with open(P("01_FROZEN", "domain_lexicon.json"), encoding="utf-8") as f:
            _LEX.update(json.load(f))
    return _LEX

def lexicon_entries(cats=("titles", "platforms", "companies", "events")):
    lx = lexicon()
    return [e for c in cats for e in lx.get(c, [])]

# ------------------------------------------------------------------ cleaning (shared)
def fold_diacritics(t):
    return "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))

def clean_text(t):
    """Shared cleaning: Unicode normalisation, diacritic folding, Wikipedia artefacts, whitespace."""
    t = unicodedata.normalize("NFKC", t)
    t = fold_diacritics(t)
    t = t.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    t = re.sub(r"\[\d+\]", " ", t)                   # citation markers [12]
    t = re.sub(r"\(\s*[;,]?\s*\)", " ", t)           # empty parentheses left by removed templates
    t = re.sub(r"^=+\s*(.*?)\s*=+\s*$", r"\1.", t, flags=re.M)   # == Section == headings -> sentence
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

def apply_variants(t):
    """Shared spelling-variant normalisation, e.g. Gameboy -> Game Boy (editable in lexicon)."""
    for pat, rep in lexicon().get("variants", []):
        t = re.sub(pat, rep, t, flags=re.I)
    return t

# ------------------------------------------------------------------ tokenizers
TOKEN_RX = re.compile(r"""
    (?:[A-Za-z]\.){2,}                        # acronyms with dots: U.S.
  | [$\u00a3\u20ac\u20b9]\d[\d,]*(?:\.\d+)?   # money: $4.85  Rs/INR 50,000
  | \d+(?:st|nd|rd|th)\b                      # ordinals: 1st, 3rd
  | \d+[A-Za-z]+\w*                           # 3D, 4K, 1990s, 64DD
  | \d[\d,]*(?:\.\d+)?%?                      # numbers: 1,000  4.85  20%
  | \w+(?=['][sS]\b)                          # word before possessive 's
  | ['][sS]\b                                 # possessive 's (separate token)
  | [A-Za-z]+\d+[A-Za-z\d]*                   # MP3, PS4, N64
  | \w+(?:[-']\w+)+                           # compounds: Counter-Strike, Type-0, TI-83, O'Brien
  | \w+                                       # plain words
  | [^\w\s]                                   # punctuation, one char
""", re.X)

def tok_whitespace(t):
    return t.split()

def tok_nltk(t):
    ensure_nltk()
    from nltk.tokenize import word_tokenize
    return word_tokenize(t)

def tok_spacy(t):
    return [x.text for x in spacy_blank()(t)]

def tok_custom(t):
    """Custom rule-based (regex) tokenizer - Ex. 3."""
    return TOKEN_RX.findall(t)

_MWE = {}
def _mwe_table():
    """Multi-word expressions from the lexicon, keyed by lower-cased token tuples (greedy longest match,
    same idea as nltk.tokenize.MWETokenizer, but case-insensitive). Skippable words: leading article
    (a/an/the) and short prepositions inside the MWE are also acceptable when absent from the input,
    so a query 'Last of Us' still forms the same MWE as a document phrase 'The Last of Us'."""
    if not _MWE:
        table = {}
        for e in lexicon_entries():
            toks = [x for x in tok_custom(apply_variants(fold_diacritics(e)))]
            if len(toks) > 1:
                key = tuple(x.lower() for x in toks)
                table[key] = True
                # Also register the form with a leading article dropped, so "Last of Us"
                # matches the same MWE as "The Last of Us".
                if key[0] in ("a", "an", "the") and len(key) > 2:
                    table[key[1:]] = True
        _MWE["t"] = table
        _MWE["maxlen"] = max((len(k) for k in table), default=1)
    return _MWE["t"], _MWE["maxlen"]

def join_mwe(parts):
    s = "_".join(parts)
    return re.sub(r"_[^\w]+_", "_", s)             # drop punctuation inside MWE ids

def tok_hybrid(t):
    """Hybrid tokenizer (shared by both pipelines):
       variants -> custom regex -> split plain lower-case hyphen compounds (first-person -> first person)
       -> merge lexicon multi-word expressions (Game Boy -> Game_Boy)."""
    toks = []
    for x in tok_custom(apply_variants(t)):
        if re.fullmatch(r"[a-z]+(?:-[a-z]+)+", x):
            toks.extend(x.split("-"))
        else:
            toks.append(x)
    table, maxlen = _mwe_table()
    out, i = [], 0
    low = [x.lower() for x in toks]
    while i < len(toks):
        for n in range(min(maxlen, len(toks) - i), 1, -1):
            if tuple(low[i:i + n]) in table:
                out.append(join_mwe(toks[i:i + n]))
                i += n
                break
        else:
            out.append(toks[i])
            i += 1
    return out

TOKENIZERS = {"whitespace": tok_whitespace, "nltk": tok_nltk, "spacy": tok_spacy,
              "custom": tok_custom, "hybrid": tok_hybrid}

def is_punct(tok):
    return re.fullmatch(r"[^\w]+", tok) is not None

# ------------------------------------------------------------------ stop lists
STOP_MINIMAL = {"a", "an", "the", "of", "and", "or", "to", "in", "is", "was"}   # Pipeline A (10 words)

def stop_nltk():
    ensure_nltk()
    from nltk.corpus import stopwords
    return set(stopwords.words("english"))

# ------------------------------------------------------------------ tagging helper (spaCy on our own tokens)
def spacy_tag_tokens(tokens):
    """Run spaCy tagger + lemmatizer on a pre-tokenized list. Returns [(tag_, pos_, lemma_)]."""
    from spacy.tokens import Doc
    nlp = spacy_model()
    if not tokens:
        return []
    doc = Doc(nlp.vocab, words=[t if t.strip() else "_" for t in tokens])
    for name, proc in nlp.pipeline:
        if name in ("tok2vec", "tagger", "attribute_ruler", "lemmatizer"):
            doc = proc(doc)
    return [(w.tag_, w.pos_, w.lemma_) for w in doc]

# ------------------------------------------------------------------ pipelines
_STEM = {}
def stemmer(name):
    if name not in _STEM:
        ensure_nltk()
        from nltk.stem import PorterStemmer, SnowballStemmer, LancasterStemmer
        _STEM[name] = {"porter": PorterStemmer(), "snowball": SnowballStemmer("english"),
                       "lancaster": LancasterStemmer()}[name]
    return _STEM[name]

def pipeline_A(text):
    """Annotate-first, lemma-based. Returns [(term, position)].
    hybrid tokens -> POS (spaCy, cased, full context) -> POS-aware lemma (proper nouns/MWEs kept)
    -> lowercase -> minimal stop list (10 words). Positions are original token positions."""
    toks = tok_hybrid(text)
    out = []
    # tag in chunks to keep memory low on long articles
    CH = 5000
    tags = []
    for s in range(0, len(toks), CH):
        tags.extend(spacy_tag_tokens(toks[s:s + CH]))
    for i, (tok, (tag, upos, lemma)) in enumerate(zip(toks, tags)):
        if is_punct(tok):
            continue
        term = tok.lower() if ("_" in tok or upos == "PROPN" or re.search(r"\d", tok)) else lemma.lower()
        if term in STOP_MINIMAL:
            continue
        out.append((term, i))
    return out

def pipeline_B(text):
    """Normalize-first, stem-based. Returns [(term, position)].
    hybrid tokens -> lowercase -> NLTK stop list (positions kept) -> Snowball (Porter2) stem."""
    stops = stop_nltk()
    st = stemmer("snowball")
    out = []
    for i, tok in enumerate(tok_hybrid(text)):
        if is_punct(tok):
            continue
        low = tok.lower()
        if low in stops:
            continue
        out.append((st.stem(low) if "_" not in low else low, i))
    return out

def make_pipeline(stop="minimal", norm="lemma"):
    """Build other configurations (for the exploratory Final pipeline / ablations).
    stop: 'none' | 'minimal' | 'nltk'   norm: 'none' | 'lemma' | 'porter' | 'snowball' | 'lancaster'"""
    def run(text):
        toks = tok_hybrid(text)
        tags = spacy_tag_tokens(toks) if norm == "lemma" else [None] * len(toks)
        stops = set() if stop == "none" else (STOP_MINIMAL if stop == "minimal" else stop_nltk())
        out = []
        for i, tok in enumerate(toks):
            if is_punct(tok):
                continue
            low = tok.lower()
            if norm == "lemma":
                tag, upos, lemma = tags[i]
                keep = "_" in tok or upos == "PROPN" or re.search(r"\d", tok)
                low = low if keep else lemma.lower()
            if low in stops:
                continue
            if norm in ("porter", "snowball", "lancaster") and "_" not in low:
                low = stemmer(norm).stem(low)
            out.append((low, i))
        return out
    run.__name__ = f"pipeline_{stop}_{norm}"
    return run

PIPELINES = {"A": pipeline_A, "B": pipeline_B}

# ------------------------------------------------------------------ corpus loading
def load_corpus(folder=None):
    """Reads data/Dxx.txt. First line = title, rest = body. Returns dict id -> {title, body}."""
    folder = folder or P("data")
    docs = {}
    for fp in sorted(glob.glob(os.path.join(folder, "D*.txt"))):
        did = os.path.splitext(os.path.basename(fp))[0]
        with open(fp, encoding="utf-8") as f:
            title = f.readline().strip()
            body = f.read()
        docs[did] = {"title": clean_text(title), "body": clean_text(body)}
    return docs

def full_text(doc):
    return doc["title"] + " .\n" + doc["body"]

# ------------------------------------------------------------------ positional index
class PositionalIndex:
    """term -> {doc_id: [positions]}. Also stores title length (title-hit flag, Brin & Page 1998)."""
    TITLE_BOOST = 2.0

    def __init__(self, pipeline, name=""):
        self.pipe, self.name = pipeline, name
        self.post = defaultdict(dict)
        self.doc_len, self.title_len, self.doc_terms = {}, {}, {}
        self.norm = {}

    def build(self, docs):
        for did, d in docs.items():
            terms = self.pipe(full_text(d))
            self.title_len[did] = len(tok_hybrid(d["title"]))
            self.doc_len[did] = len(terms)
            self.doc_terms[did] = [t for t, _ in terms]
            for t, pos in terms:
                self.post[t].setdefault(did, []).append(pos)
        self.N = len(docs)
        for did in docs:            # document vector norms for cosine ranking
            s = 0.0
            for t, c in Counter(self.doc_terms[did]).items():
                s += (self._w(t, did)) ** 2
            self.norm[did] = math.sqrt(s) or 1.0
        return self

    def df(self, t):
        return len(self.post.get(t, {}))

    def idf(self, t):
        return math.log10(self.N / self.df(t)) if self.df(t) else 0.0

    def _w(self, t, did):
        pos = self.post.get(t, {}).get(did, [])
        if not pos:
            return 0.0
        tl = self.title_len.get(did, 0)
        tf = sum(self.TITLE_BOOST if p < tl else 1.0 for p in pos)   # title hits weigh more
        return (1 + math.log10(tf)) * self.idf(t)                    # sublinear tf (saturating counts)

    def vocab_size(self):
        return len(self.post)

    def token_count(self):
        return sum(self.doc_len.values())

    def to_json(self):
        return {t: {d: p for d, p in sorted(v.items())} for t, v in sorted(self.post.items())}

    def term_dictionary(self):
        """Rows for the GUI 'Terms Dictionary' (term, doc freq, total occurrences, docs)."""
        rows = []
        for t, v in self.post.items():
            rows.append({"term": t, "doc_freq": len(v), "term_freq": sum(len(p) for p in v.values()),
                         "documents": ", ".join(f"{d}:{len(p)}" for d, p in sorted(v.items()))})
        return rows

# ------------------------------------------------------------------ query engine
QTOK = re.compile(r'"[^"]+"|\(|\)|\bAND\b|\bOR\b|\bNOT\b|[^\s()"]+')

class QueryEngine:
    """Boolean (AND/OR/NOT, parentheses), phrase ("..."), keyword queries.
    Multi-word keyword queries without operators = implicit AND (preregistered)."""

    def __init__(self, index):
        self.ix = index
        self.all = set(index.doc_len)

    def analyze(self, text):
        return self.ix.pipe(text)          # queries use exactly the document pipeline

    def operand(self, text):
        text = text.strip('"')
        terms = self.analyze(text)
        if not terms:
            return None, []                # e.g. a stop word: ignored
        if len(terms) == 1:
            t = terms[0][0]
            # Union of direct hits and MWE hits that contain this term as a component.
            # Ensures 'Xbox' matches both 'xbox' and 'xbox_360'; 'Sony' matches 'sony_computer_entertainment';
            # 'Last of Us' matches 'the_last_of_us'; 'Wars' (lemma 'war') matches 'halo_wars'.
            hits = set(self.ix.post.get(t, {}))
            q_parts = t.split("_")
            for k, posts in self.ix.post.items():
                if k == t or "_" not in k:
                    continue
                parts = k.split("_")
                matched = False
                for i in range(len(parts) - len(q_parts) + 1):
                    if parts[i:i + len(q_parts)] == q_parts:
                        matched = True
                        break
                if not matched and len(q_parts) == 1 and len(t) >= 3:
                    matched = any(t in p or p in t for p in parts if len(p) >= 3)
                if matched:
                    hits |= set(posts)
            return hits, terms
        return self.phrase(terms), terms

    def phrase(self, terms):
        p0 = terms[0][1]
        rel = [(t, p - p0) for t, p in terms]
        cand = set.intersection(*[set(self.ix.post.get(t, {})) for t, _ in rel])
        hits = set()
        for d in cand:
            pos_sets = {t: set(self.ix.post[t][d]) for t, _ in rel}
            for start in self.ix.post[rel[0][0]][d]:
                if all(start + off in pos_sets[t] for t, off in rel):
                    hits.add(d)
                    break
        return hits

    def parse(self, q):
        # If the query has no operators, quotes or parens, treat the WHOLE thing as one
        # operand so multi-word MWEs like "Game Boy" or "Sony Computer Entertainment" survive
        # the analyzer as a single term, matching how they were indexed.
        if not re.search(r'[()"]|\b(AND|OR|NOT)\b', q):
            return [("OPD", q)]
        toks = QTOK.findall(q)
        out, ops = [], []
        prec = {"NOT": 3, "AND": 2, "OR": 1}
        prev_operand = False
        for tok in toks:
            if tok in ("AND", "OR", "NOT"):
                if tok == "NOT" and prev_operand:          # "a NOT b" -> a AND NOT b
                    self._push(ops, out, "AND", prec)
                self._push(ops, out, tok, prec)
                prev_operand = False
            elif tok == "(":
                if prev_operand:
                    self._push(ops, out, "AND", prec)
                ops.append(tok); prev_operand = False
            elif tok == ")":
                while ops and ops[-1] != "(":
                    out.append(ops.pop())
                if ops: ops.pop()
                prev_operand = True
            else:
                if prev_operand:                           # implicit AND
                    self._push(ops, out, "AND", prec)
                out.append(("OPD", tok)); prev_operand = True
        while ops:
            out.append(ops.pop())
        return out

    @staticmethod
    def _push(ops, out, op, prec):
        while ops and ops[-1] != "(" and (prec[ops[-1]] > prec[op] or (prec[ops[-1]] == prec[op] and op != "NOT")):
            out.append(ops.pop())
        ops.append(op)

    def search(self, q):
        """Returns (ranked_doc_ids, positive_terms)."""
        stack, positive = [], []
        rpn = self.parse(q)
        for i, item in enumerate(rpn):
            if isinstance(item, tuple):
                s, terms = self.operand(item[1])
                negated = i + 1 < len(rpn) and rpn[i + 1] == "NOT"
                if not negated:
                    positive += [t for t, _ in terms]
                stack.append(s)
            elif item == "NOT":
                a = stack.pop() if stack else None
                stack.append(None if a is None else self.all - a)
            else:
                b = stack.pop() if stack else None
                a = stack.pop() if stack else None
                if a is None or b is None:
                    stack.append(b if a is None else a)
                else:
                    stack.append(a & b if item == "AND" else a | b)
        res = stack[-1] if stack and stack[-1] is not None else set()
        return self.rank(res, positive), positive

    def rank(self, docs, terms):
        qtf = Counter(terms)
        def score(d):
            return sum((1 + math.log10(c)) * self.ix.idf(t) * self.ix._w(t, d) for t, c in qtf.items()) / self.ix.norm[d]
        return sorted(docs, key=lambda d: (-score(d), d))

    def timed_search(self, q, repeats=5):
        t0 = time.perf_counter(); ranked, pos = self.search(q); cold = (time.perf_counter() - t0) * 1000
        warm = []
        for _ in range(repeats):
            t0 = time.perf_counter(); self.search(q); warm.append((time.perf_counter() - t0) * 1000)
        return ranked, pos, cold, statistics.median(warm)

# ------------------------------------------------------------------ metrics
def set_metrics(retrieved, relevant):
    ret, rel = set(retrieved), set(relevant)
    tp = len(ret & rel)
    p = tp / len(ret) if ret else 0.0
    r = tp / len(rel) if rel else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f

def p_at_k(ranked, relevant, k):
    return len(set(ranked[:k]) & set(relevant)) / k

def r_at_k(ranked, relevant, k):
    return len(set(ranked[:k]) & set(relevant)) / len(relevant) if relevant else 0.0

# ------------------------------------------------------------------ n-grams
def ngrams(seq, n):
    return [tuple(seq[i:i + n]) for i in range(len(seq) - n + 1)]

def ngram_stats(doc_term_lists, n, top=10):
    c = Counter()
    for terms in doc_term_lists:             # never crosses document boundaries
        c.update(ngrams(terms, n))
    return {"n": n, "total": sum(c.values()), "unique": len(c), "top": c.most_common(top), "counter": c}

def is_meaningful(gram, stops):
    """Preregistered proxy: n>=2, occurs >=2 (checked by caller), no stop word / pure number at either
    edge, and at least one alphabetic token."""
    if len(gram) < 2:
        return False
    edge_bad = lambda w: w in stops or re.fullmatch(r"[\d.,%]+", w) is not None
    return not edge_bad(gram[0]) and not edge_bad(gram[-1]) and any(re.search(r"[a-z]", w) for w in gram)

def meaningful_rate(counter, stops, top=20):
    items = [(g, c) for g, c in counter.most_common() if c >= 2][:top]
    return sum(is_meaningful(g, stops) for g, _ in items) / len(items) if items else 0.0

# ------------------------------------------------------------------ domain-term preservation
def domain_term_preservation(pipeline):
    """Share of lexicon entries that survive the pipeline as ONE intact token equal to the
    case-folded entry (spaces -> '_'). Measures E5."""
    ok, rows = 0, []
    for e in lexicon_entries():
        expect = join_mwe(tok_custom(apply_variants(fold_diacritics(e)))).lower()
        got = [t for t, _ in pipeline(e)]
        good = got == [expect]
        ok += good
        rows.append({"entry": e, "expected": expect, "output": " ".join(got), "preserved": good})
    return ok / len(rows) if rows else 0.0, rows

# ------------------------------------------------------------------ BPE
def bpe_gpt2(word):
    """GPT-2 BPE via tiktoken. Raises RuntimeError with a helpful message if the vocab file
    can't be downloaded (offline sandboxes); in Colab this always works."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("gpt2")
    except Exception as ex:
        raise RuntimeError(
            f"tiktoken could not load gpt2 encoding ({type(ex).__name__}). "
            "In Colab, retry after `pip install -q tiktoken` and check network. "
            "Fallback: use train_bpe / bpe_encode on our own corpus."
        ) from ex
    return [enc.decode_single_token_bytes(i).decode("utf-8", "replace") for i in enc.encode(word)]

def train_bpe(word_freq, num_merges=1000, min_freq=2):
    """BPE training exactly as in the lecture slides: chars + '</w>', repeatedly merge the most
    frequent adjacent pair. Ties broken alphabetically for reproducibility."""
    vocab = {tuple(w) + ("</w>",): f for w, f in word_freq.items() if f >= min_freq}
    merges = []
    for _ in range(num_merges):
        pairs = Counter()
        for sym, f in vocab.items():
            for a, b in zip(sym, sym[1:]):
                pairs[(a, b)] += f
        if not pairs:
            break
        best = max(pairs.items(), key=lambda kv: (kv[1], tuple(-ord(c) for c in "".join(kv[0]))))[0]
        merges.append(best)
        new = {}
        for sym, f in vocab.items():
            s, i = [], 0
            while i < len(sym):
                if i < len(sym) - 1 and (sym[i], sym[i + 1]) == best:
                    s.append(sym[i] + sym[i + 1]); i += 2
                else:
                    s.append(sym[i]); i += 1
            new[tuple(s)] = new.get(tuple(s), 0) + f
        vocab = new
    return merges

def bpe_encode(word, merges):
    ranks = {m: i for i, m in enumerate(merges)}
    sym = list(word) + ["</w>"]
    while True:
        cands = [(ranks[(a, b)], i) for i, (a, b) in enumerate(zip(sym, sym[1:])) if (a, b) in ranks]
        if not cands:
            return sym
        _, i = min(cands)
        sym = sym[:i] + [sym[i] + sym[i + 1]] + sym[i + 2:]

# ------------------------------------------------------------------ io helpers
def write_csv(rows, name, folder="results"):
    import pandas as pd
    os.makedirs(P(folder), exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(P(folder, name), index=False)
    return df

def read_csv(name, folder="data"):
    import pandas as pd
    return pd.read_csv(P(folder, name))
