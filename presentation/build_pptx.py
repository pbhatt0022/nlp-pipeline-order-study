"""Build slides.pptx (native, editable PowerPoint) with the same content as slides.tex.
Windows only: drives Microsoft PowerPoint through COM.  Run: python build_pptx.py
Needs: pywin32, PowerPoint installed.  Speaker notes are taken from SPEAKER_NOTES.md."""
import os, re
import win32com.client

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'slides.pptx')
W, H = 960, 540                        # 16:9 in points
X0, XW = 40, 880                       # content left edge and width
TOP = 100                              # content top (below title + rule)
S = 1.25                               # content type scale (titles, footer, title page, roadmap keep their size)

def rgb(h): return int(h[0:2], 16) + int(h[2:4], 16) * 256 + int(h[4:6], 16) * 65536
INK, MUTED, RULE = rgb('1B2A41'), rgb('5F5E59'), rgb('D9D6CF')
PA, PB, ALERT, GOOD = rgb('A64B2C'), rgb('3A6676'), rgb('1D4ED8'), rgb('2E6B3F')
TINT = {'ink': rgb('F1F2F4'), 'A': rgb('F8EDE9'), 'B': rgb('EBF0F2'), 'good': rgb('EEF4F0'), 'head': rgb('EEF0F3')}
SANS, MONO = 'Calibri', 'Consolas'
FOOT_LEFT = 'Video-Game Search Engine  ·  Priyanka B, Sachin B, Tiya P, Vaidhav A'

# ---------------------------------------------------------------- inline markup
# **bold**  *italic*  `mono`  [[alert]]  {A} {B} (pipeline letters)  {a:..} {b:..} {g:..} {r:..} {m:..} {ab:..}
TOKEN = re.compile(r'\*\*(.+?)\*\*|(?<![\w*])\*(?!\*)(.+?)\*|`(.+?)`|\[\[(.+?)\]\]|\{([AB])\}|\{(ab|a|b|g|r|m):(.+?)\}')

def parse(text):
    """Return plain text and a list of (start, length, style dict)."""
    plain, spans, pos = [], [], 0
    for m in TOKEN.finditer(text):
        plain.append(text[pos:m.start()])
        start = sum(map(len, plain))
        bold, ital, mono, alert, letter, kind, body = m.groups()
        if bold is not None:   seg, st = bold, {'bold': True}
        elif ital is not None: seg, st = ital, {'italic': True}
        elif mono is not None: seg, st = mono, {'font': MONO}
        elif alert is not None: seg, st = alert, {'color': ALERT}
        elif letter is not None: seg, st = letter, {'bold': True, 'color': PA if letter == 'A' else PB}
        else:
            seg = body
            st = {'a': {'color': PA}, 'b': {'color': PB}, 'g': {'color': GOOD, 'bold': True},
                  'r': {'color': PA, 'bold': True}, 'm': {'color': MUTED}, 'ab': {'color': ALERT, 'bold': True}}[kind]
        plain.append(seg); spans.append((start, len(seg), st)); pos = m.end()
    plain.append(text[pos:])
    return ''.join(plain), spans

def fill_text(tr, text, size, color=INK, font=SANS, bold=False, italic=False):
    plain, spans = parse(text)
    tr.Text = plain
    f = tr.Font; f.Name, f.Size, f.Color.RGB, f.Bold, f.Italic = font, size, color, bold, italic
    for start, n, st in spans:
        if n == 0: continue
        c = tr.Characters(start + 1, n).Font
        if 'bold' in st: c.Bold = True
        if 'italic' in st: c.Italic = True
        if 'font' in st: c.Name = st['font']
        if 'color' in st: c.Color.RGB = st['color']

# ---------------------------------------------------------------- primitives
def textbox(sl, x, y, w, text, size=17, color=INK, font=SANS, bold=False, italic=False, align=1,
            bullets=False, numbered=False, space=5, h=40, scale=True):
    """text: a string, or a list of items for bullets (an item ('sub', text) is a second-level bullet)."""
    if scale: size, space = size * S, space * S
    shp = sl.Shapes.AddTextbox(1, x, y, w, h)
    tf = shp.TextFrame; tf.WordWrap = -1; tf.AutoSize = 0
    tf.MarginLeft = tf.MarginRight = tf.MarginTop = tf.MarginBottom = 0
    items = text if isinstance(text, list) else [text]
    levels = [2 if isinstance(i, tuple) else 1 for i in items]
    fill_text(tf.TextRange, '\r'.join(i[1] if isinstance(i, tuple) else i for i in items), size, color, font, bold, italic)
    if bullets or numbered:
        tf.Ruler.Levels(1).FirstMargin, tf.Ruler.Levels(1).LeftMargin = 0, size * 1.15
        tf.Ruler.Levels(2).FirstMargin, tf.Ruler.Levels(2).LeftMargin = size * 1.15, size * 2.2
    for k, lvl in enumerate(levels, 1):
        p = tf.TextRange.Paragraphs(k)
        pf = p.ParagraphFormat; pf.Alignment = align
        pf.LineRuleAfter = 0; pf.SpaceAfter = space
        p.IndentLevel = lvl
        if numbered and lvl == 1:
            pf.Bullet.Visible = -1; pf.Bullet.Type = 2; pf.Bullet.Style = 3
            pf.Bullet.Font.Color.RGB = INK
        elif bullets or lvl == 2:
            pf.Bullet.Visible = -1; pf.Bullet.Type = 1
            pf.Bullet.Character = 9656 if lvl == 1 else 8211
            pf.Bullet.RelativeSize = 0.75; pf.Bullet.Font.Color.RGB = INK
        else:
            pf.Bullet.Visible = 0
    shp.Height = tf.TextRange.BoundHeight + 2
    return shp, y + shp.Height

def table(sl, x, y, w, rows, widths, size=14, align=None, caption=None, bold_rows=(), pad=3):
    """rows[0] is the header. widths are fractions of w. align: string of l/c/r per column."""
    nr, nc = len(rows), len(rows[0])
    size, pad = size * S, pad + 1.5
    shp = sl.Shapes.AddTable(nr, nc, x, y, w, nr * 10)
    t = shp.Table
    t.ApplyStyle('{2D5ABB26-0587-4C30-8999-92F81FD0307C}', False)    # "No Style, No Grid"
    for j, fr in enumerate(widths, 1): t.Columns(j).Width = w * fr
    align = align or 'l' * nc
    for i, row in enumerate(rows, 1):
        for j, val in enumerate(row, 1):
            c = t.Cell(i, j); s = c.Shape; tf = s.TextFrame
            tf.MarginLeft = tf.MarginRight = 5; tf.MarginTop = tf.MarginBottom = pad
            fill_text(tf.TextRange, str(val), size, INK, SANS, bold=(i == 1 or i in bold_rows))
            tf.TextRange.ParagraphFormat.Alignment = {'l': 1, 'c': 2, 'r': 3}[align[j - 1]]
            s.Fill.Visible = -1 if i == 1 else 0
            if i == 1: s.Fill.ForeColor.RGB = TINT['head']
            for side in (1, 2, 3, 4): c.Borders(side).Visible = 0
            if i == 1: _border(c, 1, INK, 1.0); _border(c, 3, INK, 0.6)
            if i == nr: _border(c, 3, INK, 1.0)
            if i in bold_rows and i > 1: _border(c, 1, INK, 0.6)
        t.Rows(i).Height = 10
    bottom = y + shp.Height
    if caption:
        _, bottom = textbox(sl, x, bottom + 4, w, caption, size=10, color=MUTED, align=2)
    return shp, bottom

def _border(cell, side, color, weight):
    b = cell.Borders(side); b.Visible = -1; b.ForeColor.RGB = color; b.Weight = weight

def box(sl, x, y, w, h, text, size=13, line=INK, fill=TINT['ink'], color=INK, bold=False):
    s = sl.Shapes.AddShape(5, x, y, w, h)            # rounded rectangle
    s.Adjustments.SetItem(1, 0.12)
    s.Fill.ForeColor.RGB = fill; s.Line.ForeColor.RGB = line; s.Line.Weight = 1
    s.Shadow.Visible = 0
    tf = s.TextFrame; tf.WordWrap = -1; tf.MarginLeft = tf.MarginRight = 4; tf.MarginTop = tf.MarginBottom = 2
    fill_text(tf.TextRange, text, size, color, SANS, bold=bold)
    tf.TextRange.ParagraphFormat.Alignment = 2; tf.VerticalAnchor = 3
    return s

def arrow(sl, x1, y1, x2, y2, color=MUTED, weight=1.25):
    c = sl.Shapes.AddConnector(1, x1, y1, x2, y2)
    c.Line.ForeColor.RGB = color; c.Line.Weight = weight; c.Line.EndArrowheadStyle = 2
    return c

def block(sl, x, y, w, title, body, kind='ink', size=15):
    color = {'ink': INK, 'A': PA, 'good': GOOD}[kind]
    size = size * S
    head = sl.Shapes.AddShape(1, x, y, w, 30)
    head.Fill.ForeColor.RGB = color; head.Line.Visible = 0; head.Shadow.Visible = 0
    tf = head.TextFrame; tf.MarginLeft = 10; tf.MarginTop = tf.MarginBottom = 2; tf.VerticalAnchor = 3
    fill_text(tf.TextRange, title, size + 1, rgb('FFFFFF'), SANS, bold=True)
    tf.TextRange.ParagraphFormat.Alignment = 1
    bodyshape = sl.Shapes.AddShape(1, x, y + 30, w, 40)
    bodyshape.Fill.ForeColor.RGB = TINT['good' if kind == 'good' else ('A' if kind == 'A' else 'ink')]
    bodyshape.Line.Visible = 0; bodyshape.Shadow.Visible = 0
    tf = bodyshape.TextFrame; tf.WordWrap = -1; tf.AutoSize = 0
    tf.MarginLeft = tf.MarginRight = 10; tf.MarginTop = tf.MarginBottom = 7; tf.VerticalAnchor = 1
    fill_text(tf.TextRange, body, size, INK, SANS)
    tf.TextRange.ParagraphFormat.Alignment = 1
    tf.TextRange.ParagraphFormat.LineRuleAfter = 0; tf.TextRange.ParagraphFormat.SpaceAfter = 4
    bodyshape.Height = tf.TextRange.BoundHeight + 16
    return y + 30 + bodyshape.Height

# ---------------------------------------------------------------- slide scaffolding
class Deck:
    def __init__(self):
        self.app = win32com.client.DispatchEx('PowerPoint.Application')
        self.pres = self.app.Presentations.Add(0)
        self.pres.PageSetup.SlideWidth, self.pres.PageSetup.SlideHeight = W, H
        self.numbered = []          # (slide, section) for footer numbering
        self.section = ''
        self.notes = parse_notes()

    def new(self, title=None, subtitle=None, numbered=True):
        sl = self.pres.Slides.Add(self.pres.Slides.Count + 1, 12)    # blank layout
        sl.FollowMasterBackground = 0; sl.Background.Fill.ForeColor.RGB = rgb('FFFFFF')
        if title:
            textbox(sl, X0, 24, XW, title, size=28, bold=True, scale=False)
            if subtitle: textbox(sl, X0, 60, XW, subtitle, size=16, color=MUTED, scale=False)
            ln = sl.Shapes.AddLine(X0, 86, X0 + XW, 86); ln.Line.ForeColor.RGB = RULE; ln.Line.Weight = 0.75
        if numbered:
            self.numbered.append((sl, self.section))
            note = self.notes.get(len(self.numbered))
            if note: sl.NotesPage.Shapes.Placeholders(2).TextFrame.TextRange.Text = note
        return sl

    def roadmap(self, lo, hi, note):
        sl = self.new(numbered=False)
        words = ['Select', 'Order', 'Implement', 'Compare', 'Evaluate', 'Justify']
        parts = []
        for i, wd in enumerate(words, 1):
            parts.append('{r:%s}' % wd if lo <= i <= hi else '{m:%s}' % wd)
        s, _ = textbox(sl, X0, 220, XW, '   →   '.join(parts), size=28, bold=True, align=2, color=rgb('C9CCD2'), scale=False)
        textbox(sl, X0, 285, XW, note, size=19, color=MUTED, align=2, scale=False)

    def finish(self):
        total = len(self.numbered)
        for k, (sl, sec) in enumerate(self.numbered, 1):
            if k == 1 or k == total: continue            # title and closing slide: no footer
            textbox(sl, X0, 512, 520, FOOT_LEFT, size=10, color=MUTED, scale=False)
            textbox(sl, 560, 512, 220, sec, size=10, color=MUTED, align=2, scale=False)
            textbox(sl, 800, 512, 120, f'{k} / {total}', size=10, color=MUTED, align=3, scale=False)
        if os.path.exists(OUT): os.remove(OUT)
        self.pres.SaveAs(OUT)
        return self.pres

def parse_notes():
    """Map footer slide number -> speaker notes text, from SPEAKER_NOTES.md headings '**N. Title.**'."""
    path = os.path.join(HERE, 'SPEAKER_NOTES.md')
    if not os.path.exists(path): return {}
    notes, cur = {}, None
    for line in open(path, encoding='utf-8').read().split('\n'):
        m = re.match(r'^\*\*(\d+)\. (.+?)\*\*\s*(.*)$', line)
        if m:
            cur = int(m.group(1)); notes[cur] = [m.group(3)] if m.group(3) else []
        elif line.startswith('#') or line.startswith('---'):
            cur = None
        elif cur is not None and line.strip():
            notes[cur].append(line)
    clean = lambda s: re.sub(r'\*\*|`', '', s).replace('*', '')
    return {k: '\r'.join(clean(l) for l in v) for k, v in notes.items()}

# ---------------------------------------------------------------- content
def build(d):
    # 1 title
    sl = d.new()
    bar = sl.Shapes.AddShape(1, X0, 120, 46, 6); bar.Fill.ForeColor.RGB = PA; bar.Line.Visible = 0
    _, y = textbox(sl, X0, 140, XW, 'A Search Engine for Video-Game Knowledge', size=36, bold=True, scale=False)
    _, y = textbox(sl, X0, y + 6, XW, 'Text analysis, indexing and Boolean retrieval with two competing pipelines', size=20, color=MUTED, scale=False)
    _, y = textbox(sl, X0, y + 40, XW, 'Priyanka B  ·  Sachin B  ·  Tiya P  ·  Vaidhav A', size=18, scale=False)
    _, y = textbox(sl, X0, y + 8, XW, 'Course code DATA403: Natural Language Processing  ·  Assessment-1\rVidyashilp University, Bangalore', size=14, color=MUTED, space=2, scale=False)
    textbox(sl, X0, y + 8, XW, 'October 2026', size=14, color=MUTED, scale=False)

    # ================= The Problem
    d.section = 'The Problem'
    sl = d.new('What we built', 'A complete classical search engine, measured at every stage')
    textbox(sl, X0, TOP + 10, 440, [
        '**Indexer** (ahead of time): reads every document, builds a lookup table of every term and where it occurs',
        '**Searcher** (at question time): looks terms up, combines them with `AND` / `OR` / `NOT`, ranks the result',
        'Everything in between decides [[which “words” exist at all]]',
        'Two pipelines make [[opposite bets]] on that decision; we compare them under rules fixed in advance'],
        size=17, bullets=True, space=9)
    labels = ['53 Wikipedia articles', 'clean + hybrid tokenize', 'Pipeline {A}  or  Pipeline {B}',
              'positional inverted index', 'Boolean search + TF-IDF rank', 'evaluate vs gold standards']
    bx, bw, bh, gap, by = 540, 250, 36, 17, TOP + 10
    for i, lab in enumerate(labels):
        line, fill = (PA, TINT['A']) if i == 2 else ((GOOD, TINT['good']) if i == 5 else (rgb('8D95A0'), TINT['ink']))
        box(sl, bx, by + i * (bh + gap), bw, bh, lab, size=16, line=line, fill=fill)
        if i: arrow(sl, bx + bw / 2, by + i * (bh + gap) - gap, bx + bw / 2, by + i * (bh + gap))
    textbox(sl, bx + bw + 12, by + 1 * (bh + gap) + 2, 120, 'lexicon of 128 domain names', size=11, color=MUTED)
    textbox(sl, bx + bw + 12, by + 4 * (bh + gap) + 2, 120, 'query goes through the same pipeline', size=11, color=MUTED)

    sl = d.new('Domain and data', 'Why video games, and where the documents come from')
    _, y = textbox(sl, X0, TOP + 8, 440, '**Hard for generic NLP tools**', size=17)
    _, y = textbox(sl, X0, y + 4, 440, [
        'hyphens and numbers in names: *Counter-Strike*, *Destiny 2*',
        'names made of everyday words: *Tomb Raider*',
        'spelling variants: *Game Boy / Gameboy*, *SNES*'], size=17, bullets=True)
    _, y = textbox(sl, X0, y + 14, 440, '**Corpus from MIRACL** (Zhang et al. 2023)', size=17)
    textbox(sl, X0, y + 4, 440, [
        '12 real questions; their judged articles: relevant + [[hard negatives]]',
        'full Wikipedia articles, **D01–D53**'], size=17, bullets=True)
    _, y = table(sl, 530, TOP + 10, 390, [
        ['Corpus statistic', 'Value'], ['Documents', '53'], ['Sentences', '9,305'], ['Tokens (hybrid)', '251,482'],
        ['Characters', '1,362,150'], ['Vocabulary (case-folded)', '16,030'], ['Avg. length (tokens)', '4,744.9']],
        [.65, .35], size=15, align='lr', caption='`corpus_summary.csv`')
    textbox(sl, 530, y + 14, 390, '53 > 15–30 recommended: each question needs several relevant documents and some hard negatives, or precision and recall are meaningless.', size=13, color=MUTED)

    sl = d.new('Gold standards: an answer key for every stage')
    _, y = table(sl, X0, TOP + 6, XW, [
        ['Gold standard', 'Contents', 'Evaluates'],
        ['Relevance judgments', '12 questions × 53 documents = 636 labels (57 relevant)', 'searcher, ranker'],
        ['POS gold', '226 tokens, 8 corpus sentences, Penn Treebank', '5 POS taggers'],
        ['NER gold', '51 entities, 7 types (PERSON … EVENT)', '2 entity recognisers'],
        ['Domain lexicon', '128 names that must survive as one term', 'tokenizers, pipelines'],
        ['Stemming groups', 'word families + a trap: *universe* vs *university*', 'stemmers, lemmatizers']],
        [.24, .52, .24], size=15)
    block(sl, X0, y + 22, XW, 'Process discipline',
          'Hypotheses, metrics and the selection rule were [[preregistered before any result]]; every later change is a dated amendment in the decision log. '
          'Relevance labels: two reviewers under a written protocol, so search results are labelled *preliminary*.', size=15)

    # ================= Select
    d.section = 'Select'
    d.roadmap(1, 1, 'Choose each component by measuring it on the corpus')
    sl = d.new('Tokenization: where does a word end?', 'The single most important choice')
    _, y = table(sl, X0, TOP + 8, 480, [
        ['Tokenizer', 'Tokens', 'Term dict.', 'Names kept'],
        ['NLTK', '253,416', '16,619', '0 / 91'], ['spaCy', '261,849', '15,745', '0 / 91'],
        ['Custom (regex)', '252,750', '16,664', '0 / 91'], ['**Hybrid**', '251,482', '16,030', '{ab:91 / 91}']],
        [.34, .22, .22, .22], size=15, align='lrrc', caption='`tokenization_comparison.csv`, `tokenizer_domain_terms.csv`')
    textbox(sl, X0, y + 14, 480, '`Counter-Strike: Global Offensive`\r{m:spaCy:}  `Counter | - | Strike | : | Global | Offensive`\r{m:hybrid:} `Counter-Strike_Global_Offensive`', size=13, space=3)
    _, y = textbox(sl, 555, TOP + 8, 365, '**Hybrid** = custom regex rules + three domain steps:', size=17)
    _, y = textbox(sl, 555, y + 4, 365, [
        'rewrite variants (*Gameboy* → *Game Boy*)',
        'split lower-case compounds (*first-person*)',
        'merge lexicon names, longest first (`Game_Boy`)'], size=17, numbered=True)
    _, y = textbox(sl, 555, y + 10, 365, 'Custom rules keep *$8.5*, *U.S.*, *PS4*, *1990s* whole.', size=17)
    textbox(sl, 555, y + 10, 365, '[[Chosen for both pipelines.]] Limit: only names in the lexicon are protected.', size=17)

    sl = d.new('Subword tokenization (BPE)', 'Useful for vocabulary control, wrong for an index of names')
    _, y1 = table(sl, X0, TOP + 8, 420, [
        ['Method', 'Tokens', 'Vocabulary'], ['Hybrid', '251,482', '18,192'],
        ['GPT-2 BPE (tiktoken)', '284,579', '18,127'], ['Corpus BPE (1,000 merges)', '423,824', '[[3,242]]']],
        [.52, .24, .24], size=14, align='lrr', caption='`bpe_vs_tokenizers.csv`')
    _, y2 = table(sl, 500, TOP + 8, 420, [
        ['Word', 'GPT-2', 'Corpus BPE'], ['nintendo', 'n | intendo', 'nintendo</w>'],
        ['metroid', 'met | roid', 'metroid</w>'], ['multiplayer', 'multi | player', 'multi | player</w>']],
        [.3, .3, .4], size=14, caption='`bpe_results.csv`')
    textbox(sl, X0, max(y1, y2) + 18, XW, [
        'BPE (Sennrich et al. 2016) never meets an unknown word and keeps the vocabulary tiny',
        'But pieces like *met | roid* are not searchable units: users type words and names',
        'Frequent domain words are learned whole by the corpus model, not by GPT-2 → [[analysed, not used for the index]]'],
        size=17, bullets=True)

    sl = d.new('Stop words, stemming, lemmatization', 'Scored with Paice’s under- and over-stemming indices')
    _, y = table(sl, X0, TOP + 8, 470, [
        ['Method', 'UI ↓', 'OI ↓', 'universe = university?'],
        ['Porter', '0.298', '0.0087', 'merged'], ['Snowball', '0.298', '0.0087', 'merged'],
        ['Lancaster', '0.000', '0.0087', 'merged'], ['WordNet (verb)', '0.617', '0', 'kept apart'],
        ['spaCy lemma', '0.574', '0', 'kept apart']],
        [.3, .17, .17, .36], size=15, align='lccc', caption='`stemming_lemmatization.csv` (Paice 1994)')
    textbox(sl, 540, TOP + 8, 380, [
        'every stemmer [[over-stems]] the trap',
        'lemmatizers never over-merge but need the POS tag (*saw*: noun or verb?)',
        '**Order matters**: Porter *before* stop-word removal leaks `thi`, `wa`, `ha` into the index',
        'stop lists: 10 words removes 22.3% of tokens, NLTK’s 198 removes 38.1%'], size=16, bullets=True, space=8)
    textbox(sl, X0, y + 16, XW, 'Choices: {B} uses Snowball (no `thi`/`wa` leaks); {A} uses spaCy lemmas in context, never touching proper nouns, numbers or merged names.', size=14, color=MUTED)

    sl = d.new('POS tagging and named entities', 'General models do not know the domain; small domain knowledge fixes it')
    _, y1 = table(sl, X0, TOP + 8, 400, [
        ['POS tagger', 'Accuracy'], ['NLTK (default)', '0.982'], ['spaCy (default)', '0.951'],
        ['**Rules + dictionary** (custom)', '[[0.987]]'], ['KNN (custom, ML)', '0.602']],
        [.7, .3], size=15, align='lc', caption='226 gold tokens; `pos_tagging_results.csv`')
    _, y2 = table(sl, 480, TOP + 8, 440, [
        ['NER (51 entities)', 'Correct', 'Wrong', 'Missed'], ['spaCy default', '29', '13', '9'],
        ['+ EntityRuler', '[[37]]', '6', '8']],
        [.4, .2, .2, .2], size=15, align='lccc', caption='`ner_summary.csv`; mean F1 0.563 → 0.744')
    textbox(sl, X0, max(y1, y2) + 18, XW, [
        'spaCy calls *Prey*, *Doom*, *Halo* [[PERSON]]; the lexicon-driven EntityRuler relabels them PRODUCT',
        'The dictionary tagger improves NLTK by one token: with 226 gold tokens, a gain within noise; KNN is far behind'],
        size=17, bullets=True)

    sl = d.new('N-grams: which word sequences recur?', 'Counted over each pipeline’s index terms, n = 1 … 5')
    _, y = table(sl, X0, TOP + 8, 440, [
        ['n', 'distinct {A}', 'distinct {B}', 'meaningful {A}', 'meaningful {B}'],
        ['1', '13,165', '11,247', '–', '–'], ['2', '108,872', '98,356', '0.30', '1.00'],
        ['3', '159,589', '128,736', '0.55', '1.00'], ['4', '171,416', '134,305', '0.65', '1.00'],
        ['5', '173,966', '135,602', '0.85', '1.00']],
        [.08, .22, .22, .24, .24], size=14, align='crrcc', caption='`ngram_summary.csv`; meaningful = share of the top 20')
    textbox(sl, 510, TOP + 8, 410, [
        'the dictionary explodes with n: about 99% of 5-grams are distinct, so a phrase needs [[count ≥ 2]]',
        '{A} keeps function words: top bigrams *it be*, *be release*',
        '{B} removed them: *lara croft*, *smash bros*',
        'top bigram in both: *video game* ({A} 516, {B} 536)'], size=16, bullets=True, space=8)
    textbox(sl, X0, y + 18, XW, 'Meaningful = occurs ≥ 2, no stop word or bare number at either edge, contains a letter. Frequent unmerged phrases are candidates for the lexicon.', size=14, color=MUTED)

    # ================= Order
    d.section = 'Order'
    d.roadmap(2, 2, 'Combine the same components in two orders that make opposite bets')
    sl = d.new('The two pipelines', 'Same ingredients, different order')
    def lane(y, steps, color, tint):
        x = 90
        prev = None
        for i, (lab, w) in enumerate(steps):
            line, fill = (rgb('8D95A0'), TINT['ink']) if i == 0 else (color, tint)
            box(sl, x, y, w, 58, lab, size=16, line=line, fill=fill)
            if prev is not None: arrow(sl, prev, y + 29, x, y + 29, color=color, weight=1.75)
            prev = x + w; x += w + 26
    lane(TOP + 12, [('hybrid\rtokenize', 115), ('POS tag\r(spaCy, cased)', 160), ('lemmatize\r(POS-aware)', 150),
                    ('lowercase', 125), ('remove\r10 stop words', 150)], PA, TINT['A'])
    lane(TOP + 100, [('hybrid\rtokenize', 115), ('lowercase', 125), ('remove NLTK\rstop words (198)', 185),
                     ('Snowball\rstem', 140)], PB, TINT['B'])
    textbox(sl, X0, TOP + 24, 40, '{A}', size=28, align=2, scale=False)
    textbox(sl, X0, TOP + 112, 40, '{B}', size=28, align=2, scale=False)
    block(sl, X0, TOP + 200, 425, 'A: annotate first (linguist)',
          'Tag while capitals and context still exist, then reduce to dictionary forms.\r*Bet: careful analysis keeps names and meanings intact.*', kind='A', size=15)
    block(sl, 495, TOP + 200, 425, 'B: normalise first (IR engineer)',
          'Lowercase at once, drop all common words, chop to stems (Manning et al. 2008).\r*Bet: aggressive merging, more matches, smaller index.*', size=15)

    sl = d.new('Why each step sits where it does', 'Every process: dependency, and what breaks if it moves')
    table(sl, X0, TOP + 6, XW, [
        ['Process', 'Position', 'Depends on', 'If moved'],
        ['Cleaning', 'first', 'raw text', 'artefacts (`[12]`, *é*) become tokens'],
        ['Name merging', 'inside tokenization', 'original case, stop words present', 'after stop removal or stemming, names stop matching the lexicon'],
        ['POS tagging ({A})', 'before lowercasing', 'case, context', '*Halo* loses its proper-noun clue and gets lemmatized'],
        ['Lemmatization ({A})', 'after tagging', 'POS tags', 'without POS, WordNet under-merges (UI 0.62–0.87)'],
        ['Stop words ({B})', 'before stemming', 'lowercase', 'stem-first leaks `thi`, `wa`, `ha`'],
        ['Query processing', 'same as documents', 'the pipeline', 'query terms would not match index terms']],
        [.18, .19, .23, .40], size=14, pad=4)

    sl = d.new('One sentence through both pipelines',
               '*“The Legend of Zelda: Majora’s Mask was released for the Nintendo 64 in 2000 and players were praising it.”*')
    _, y = table(sl, 110, TOP + 8, 740, [
        ['Token', 'POS', '{A} term', '{B} term'],
        ['The_Legend_of_Zelda', 'NN', 'the_legend_of_zelda', 'the_legend_of_zelda'],
        ['Nintendo_64', 'NNP', 'nintendo_64', 'nintendo_64'],
        ['was', 'VBD', '{a:be}', '{m:(removed)}'],
        ['released', 'VBN', '{a:release}', '{b:releas}'],
        ['players', 'NNS', 'player', 'player'],
        ['praising', 'VBG', '{a:praise}', '{b:prais}']],
        [.3, .1, .3, .3], size=15, caption='`pipeline_trace_example.csv` (abridged)')
    textbox(sl, X0, y + 16, XW, [
        '{A} keeps [[real words]]; {B} keeps fewer, truncated stems',
        'both protect [[names identically]]: the tokenizer merged them before either pipeline started'], size=17, bullets=True)

    # ================= Implement
    d.section = 'Implement'
    d.roadmap(3, 3, 'Build the indexer and the Boolean searcher, shared by both pipelines')
    sl = d.new('The positional inverted index', 'The data structure at the heart of the system')
    _, y = textbox(sl, X0, TOP + 8, 470, '**term → document → positions**', size=17)
    _, y = textbox(sl, X0, y + 8, 470,
                   '"game_boy": {"D01": [3893], "D03": [1978],\r             "D05": [5237], ...}   12 docs\r'
                   '"metroid":  {"D01": [2160], "D05": [5808, 7090],\r             "D08": [790, 1091, 1558], ...}',
                   size=12.5, font=MONO, space=0)
    textbox(sl, X0, y + 16, 470, ['positions make [[phrase search]] possible',
                                  'same idea as Lucene / Elasticsearch, without compression'], size=17, bullets=True)
    _, y = table(sl, 560, TOP + 8, 360, [
        ['', '{A}', '{B}'], ['Terms', '13,165', '11,247'], ['Postings', '53,258', '47,557'],
        ['Positions', '176,387', '137,253'], ['In only 1 doc', '54%', '53%']],
        [.44, .28, .28], size=15, align='lrr', caption='`index_structure.csv`')
    textbox(sl, 560, y + 14, 360, 'Zipf: most terms are rare and carry the information; terms in every document get an idf of 0.', size=14, color=MUTED)

    sl = d.new('The searcher and the 12 test queries', 'Boolean decides *which* documents; ranking decides *in what order*')
    textbox(sl, X0, TOP + 8, 360, [
        'query runs through the [[same pipeline]] as the documents',
        'AND = intersect, OR = union, NOT = subtract posting lists; phrases checked by position',
        'matches ranked by TF-IDF cosine, title matches × 2'], size=17, numbered=True, space=10)
    table(sl, 430, TOP + 8, 490, [
        ['', 'Query', 'Type'], ['Q01', '`Total War`', 'keyword (bigram)'],
        ['Q03', '`Nintendo AND PlayStation`', 'AND'], ['Q04', '`"Ash Ketchum" AND NOT Japanese`', 'NOT'],
        ['Q06', '`Zelda AND (theme OR song)`', 'OR'], ['Q07', '`"Tomb Raider"`', 'phrase'],
        ['Q09', '`"Guitar Hero Live"`', 'phrase (trigram)'], ['Q12', '`SNES OR "Super Nintendo …"`', 'OR']],
        [.1, .6, .3], size=13, caption='7 of the 12 queries; every type covered')

    # ================= Compare & Evaluate
    d.section = 'Compare & Evaluate'
    d.roadmap(4, 5, 'Predictions first, then the numbers')
    sl = d.new('What we predicted, before running anything', 'Six preregistered hypotheses')
    _, y = table(sl, X0, TOP + 8, XW, [
        ['', 'Prediction', 'Evidence', 'Verdict'],
        ['H1', '{B} has fewer tokens and a smaller vocabulary', '176,387 vs 137,253; 13,165 vs 11,247', '{g:supported}'],
        ['H2', '{B} has higher recall', 'R 0.796 vs 0.796', 'no difference'],
        ['H3', '{A} has higher precision, esp. phrases', 'P 0.596 vs 0.596', 'no difference'],
        ['H4', '{B} makes false phrase matches', '16 vs 28 docs (probe)', '{g:supported†}'],
        ['H5', '{A} preserves ≥ 5 pts more names', '1.000 vs 0.898', '{g:supported}'],
        ['H6', '{A} has more meaningful bigrams', '0.30 vs 1.00', '{r:rejected}']],
        [.06, .42, .34, .18], size=15, caption='`hypotheses.csv`.  † exploratory: not testable on the 12 queries')
    textbox(sl, X0, y + 16, XW, 'Reporting the predictions that failed is part of the result: H2, H3 and H6 did not hold.', size=15, color=MUTED)

    sl = d.new('Pipeline comparison', 'Table H: the brief’s required comparison')
    table(sl, X0, TOP + 8, 540, [
        ['Measure', '{A}', '{B}', 'Final ({A})'],
        ['Token count', '176,387', '137,253', '176,387'], ['Vocabulary size', '13,165', '11,247', '13,165'],
        ['Meaningful bigrams', '0.30', '1.00', '0.30'], ['Name preservation', '[[1.000]]', '0.898', '1.000'],
        ['Precision (macro)', '0.596', '0.596', '0.596'], ['Recall (macro)', '0.805', '0.805', '0.805'],
        ['F1 (macro)', '[[0.648]]', '[[0.648]]', '0.648'], ['P@5 / P@10', '.583 / .367', '.583 / .367', '.583 / .367']],
        [.34, .22, .22, .22], size=14, align='lccc', caption='`pipeline_comparison.csv`')
    textbox(sl, 610, TOP + 8, 310, [
        '{B} index [[29% smaller]]',
        '{A} keeps [[all 128 names]]; {B} breaks 13 (*Civilization* → `civil`)',
        '**identical search results** on all 12 queries',
        'the bigram test favours {B} by construction (it checks the stop list {B} removed)'], size=16, bullets=True, space=9)

    sl = d.new('Retrieval performance', 'Why accuracy is the wrong metric for search')
    table(sl, X0, TOP + 8, 420, [
        ['Query type', 'P', 'R', 'F1'], ['AND', '0.722', '0.963', '[[0.798]]'], ['phrase', '0.738', '0.833', '0.778'],
        ['keyword', '0.636', '0.875', '0.643'], ['OR', '0.400', '0.929', '0.556'], ['NOT', '0.350', '0.333', '{a:0.325}'],
        ['All 12', '0.596', '0.805', '0.648']],
        [.34, .22, .22, .22], size=15, align='lccc', bold_rows=(7,), caption='`retrieval_by_query_type.csv` (same for {A} and {B})')
    _, y = table(sl, 520, TOP + 8, 400, [
        ['', 'relevant', 'not relevant'], ['retrieved', 'TP 48', 'FP 56'], ['not retrieved', 'FN 9', 'TN 523']],
        [.36, .32, .32], size=15, align='lcc', caption='Confusion matrix, all 636 pairs')
    block(sl, 520, y + 18, 400, 'Accuracy misleads',
          'Our searcher: accuracy **0.898**. Returning *nothing*: **0.910**. Most documents are irrelevant to any query, so we report precision and recall.',
          kind='A', size=15)

    sl = d.new('Where the searcher goes wrong', 'Every error classified: 9 misses, 56 false hits, same for both pipelines')
    _, y = table(sl, X0, TOP + 8, 420, [
        ['Cause', 'FN', 'FP'], ['Passing mention', '0', '54'], ['Query formulation', '6', '0'],
        ['Wrong relevance label', '3', '2'], ['**Any preprocessing step**', '[[0]]', '[[0]]']],
        [.6, .2, .2], size=15, align='lcc', caption='`error_analysis.csv`')
    textbox(sl, 500, TOP + 8, 420, [
        '**NOT throws away answers**: `"Ash Ketchum" AND NOT Japanese` loses the *Ash Ketchum* article, which mentions his Japanese voice actress',
        '**Passing mentions**: `Metroid` returns 11 documents; the 3 relevant ones rank 1–3, the rest are console histories'],
        size=16, bullets=True, space=10)
    textbox(sl, X0, max(y, TOP + 230) + 18, XW, 'No error comes from tokenization, stemming, lemmas, stop words or NER, which is why {A} and {B} tie.', size=15, color=MUTED)

    # ================= Justify
    d.section = 'Justify'
    d.roadmap(6, 6, 'Apply the rule fixed in advance, and explain what the numbers mean')
    sl = d.new('Choosing the final pipeline', 'A rule fixed in advance, applied in order')
    _, y = textbox(sl, X0, TOP + 10, XW, [
        '**F1 gap ≥ 0.05?**   {A} 0.648, {B} 0.648, gap 0.000 → {m:does not decide}',
        '**Domain-term preservation gap ≥ 0.05?**   {A} 1.000, {B} 0.898, gap [[0.102]] → **decides**',
        '{m:Meaningful-bigram rate: not reached}'], size=17, numbered=True, space=8)
    y = block(sl, X0, y + 18, XW, 'Final pipeline: A (annotate first, lemmas)',
              '{A} is *not* chosen because it searches better; on this corpus it does not. It is chosen because, when both find the same documents, '
              '{A}’s index represents the domain’s names faithfully: the term dictionary, postings and n-grams a person reads are real words and intact names.',
              kind='good', size=16)
    textbox(sl, X0, y + 14, XW, 'The cost of {A}: a 29% larger index and slower indexing (spaCy tagger). Query time: a few ms for both, within run-to-run noise.', size=14, color=MUTED)

    sl = d.new('An earlier run chose B: what we learned', 'One oddly worded query decided a whole comparison')
    _, y1 = textbox(sl, X0, TOP + 8, 460, [
        'first run: queries worded [[automatically]] from each question’s first content words',
        '*“Was there a Sonic game on the Sega Genesis?”* became `"there Sonic game"`',
        '{B} drops *there* as a stop word and finds the answers; {A} keeps it and finds nothing'], size=16, bullets=True, space=8)
    _, y2 = table(sl, 550, TOP + 8, 370, [
        ['F1 (automatic wording)', '{A}', '{B}'], ['all 12 queries', '0.183', '[[0.237]]'], ['without Q02', '[[0.200]]', '0.176']],
        [.56, .22, .22], size=15, align='lcc', caption='reproduced exactly, 12/12 queries')
    block(sl, X0, max(y1, y2) + 18, XW, 'What we did about it',
          'Queries rewritten by hand under a stated rule, *before* any new result existed; the amendment is dated and both runs are reported. '
          '**Finding:** differences between the pipelines come from stop words and inflections in the *query wording*, not from how they handle domain content.', size=15)

    sl = d.new('Why the pipelines agree, and the design lesson')
    _, y = textbox(sl, X0, TOP + 8, 440, '**Why they tie**', size=17)
    textbox(sl, X0, y + 4, 440, [
        'both share the component that matters most: the [[name-merging tokenizer]]',
        'our queries are about names; `tomb_raider` is never stemmed or lemmatized',
        '{A} and {B} differ on verb endings and function words, which the queries never touch'], size=17, bullets=True, space=8)
    y = block(sl, 510, TOP + 8, 410, 'Design lesson',
              'On an entity-heavy domain, the decisive preprocessing choice is the **domain-aware tokenizer and lexicon**, not stemming vs lemmatization.',
              kind='good', size=16)
    textbox(sl, 510, y + 12, 410, 'Consistent with Brin and Page (1998), who launched without stemming. Exploratory: no pipeline was run without name merging.', size=14, color=MUTED)

    # ================= Demonstration
    d.section = 'Demonstration'
    sl = d.new('The GUI: a working searcher with an X-ray', '9 tabs covering all 15 required functions')
    _, y = textbox(sl, X0, TOP + 6, 330, [
        '**Search**: Boolean query, type, pipeline; ranked results, time, P / R / F1',
        '**Compare A vs B**: side by side, with a diff',
        '**Pipeline trace**: any sentence, stage by stage, timed',
        '**Corpus**, **Tokenization**, **POS & NER**, **N-grams**',
        '**Index**: postings with positions and context',
        '**Evaluation**: the decision and every number'], size=14, bullets=True, space=5)
    textbox(sl, X0, y + 8, 330, 'Every button calls the same pipelines and index as the report. Right: Search on Q03 with timing, precision, recall and the judged-relevant column.', size=11.5, color=MUTED)
    pic = sl.Shapes.AddPicture(os.path.join(HERE, 'img', 'gui_search.jpg'), 0, -1, 400, TOP + 6, 520, 520 * 821 / 1280)
    pic.Line.Visible = -1; pic.Line.ForeColor.RGB = RULE; pic.Line.Weight = 0.75

    # ================= Conclusion
    d.section = 'Conclusion'
    sl = d.new('Limitations and next steps')
    _, y = textbox(sl, X0, TOP + 8, 430, '**Limitations**', size=17)
    textbox(sl, X0, y + 4, 430, [
        'relevance labels: 2 reviewers, no agreement measure, ≥ 5 labels look wrong (Voorhees 2000)',
        '12 queries: too few for significance tests',
        'corpus built around its queries: absolute scores optimistic, A vs B unaffected',
        'lexicon of 128 names: unknown games still split'], size=16, bullets=True, space=7)
    _, y = textbox(sl, 500, TOP + 8, 420, '**Next steps**', size=17)
    textbox(sl, 500, y + 4, 420, [
        'blind relevance judging, more annotators',
        '72 eligible questions; wordy queries to separate H2–H4',
        'one-component-at-a-time ablation with a paired test',
        'grow the lexicon from frequent n-grams (*smash bros*); BM25 ranking',
        'a small knowledge graph from NER output'], size=16, bullets=True, space=7)

    sl = d.new('Conclusion')
    _, y = textbox(sl, X0, TOP + 10, XW, [
        '**The tokenizer matters most**: only a domain-aware tokenizer keeps names intact (91/91 vs 0/91).',
        '**Order is visible**: stem before stop-word removal and `thi`, `wa`, `ha` leak; tag before lowercasing or proper nouns get lemmatized.',
        '**General models miss the domain**: an EntityRuler lifts NER F1 from 0.563 to 0.744.',
        '**Both pipelines search identically** (P 0.596, R 0.805, F1 0.648); the preregistered rule selects [[Pipeline A]] on name preservation.',
        '**Accuracy misleads**: 0.898 for our searcher, 0.910 for returning nothing.'], size=17, numbered=True, space=9)
    textbox(sl, X0, y + 16, XW, 'All search results are preliminary until the relevance labels are re-judged by more annotators.', size=14, color=MUTED)

    d.section = 'References'
    sl = d.new('References')
    refs = [
        'Brin, S. & Page, L. (1998). The Anatomy of a Large-Scale Hypertextual Web Search Engine. *WWW7*.',
        'Manning, C. D., Raghavan, P. & Schütze, H. (2008). *Introduction to Information Retrieval*. Cambridge University Press.',
        'Paice, C. D. (1990). Another Stemmer. *ACM SIGIR Forum* 24(3), 56–61.',
        'Paice, C. D. (1994). An Evaluation Method for Stemming Algorithms. *SIGIR ’94*, 42–50.',
        'Porter, M. F. (1980). An Algorithm for Suffix Stripping. *Program* 14(3), 130–137.',
        'Sennrich, R., Haddow, B. & Birch, A. (2016). Neural Machine Translation of Rare Words with Subword Units. *ACL*.',
        'Voorhees, E. M. (2000). Variations in Relevance Judgments and the Measurement of Retrieval Effectiveness. *Information Processing & Management* 36(5), 697–716.',
        'Zhang, X. et al. (2023). MIRACL: A Multilingual Retrieval Dataset Covering 18 Diverse Languages. *TACL*.']
    textbox(sl, X0, TOP + 6, XW, refs, size=13.5, space=6)

    sl = d.new()
    textbox(sl, X0, 225, XW, 'Thank You for Your Attention!', size=30, bold=True, align=2, scale=False)
    textbox(sl, X0, 275, XW, 'Questions?     The GUI is ready for a live demo.', size=17, color=MUTED, align=2, scale=False)

def check(pres):
    """Report any shape that runs past the footer line or the slide's right edge."""
    bad = []
    for sl in pres.Slides:
        for s in sl.Shapes:
            if s.Top + s.Height > 506 and s.Top < 506: bad.append((sl.SlideIndex, s.Name, round(s.Top + s.Height)))
            if s.Left + s.Width > W - 30: bad.append((sl.SlideIndex, s.Name, 'right edge', round(s.Left + s.Width)))
    return bad

if __name__ == '__main__':
    d = Deck()
    try:
        build(d)
        pres = d.finish()
        problems = check(pres)
        print('wrote', OUT, '|', pres.Slides.Count, 'slides |', 'overflow:', problems or 'none')
        png = os.environ.get('PPTX_PNG_DIR')
        if png:
            for sl in pres.Slides: sl.Export(os.path.join(png, f'p{sl.SlideIndex:02d}.png'), 'PNG', 1280, 720)
        pres.Close()
    finally:
        d.app.Quit()
