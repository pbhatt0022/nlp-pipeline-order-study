"""Report.md -> Report.docx through Microsoft Word (Windows only).  Run: python tools/report_to_docx.py
Needs: pip install markdown pywin32, and Word installed."""
import os, re
import markdown
import win32com.client

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
src = open(os.path.join(ROOT, 'Report.md'), encoding='utf-8').read()
src = re.sub(r'\A---\n.*?\n---\n', '', src, flags=re.S)          # drop the YAML title block
src = re.sub(r'^ {2,3}(?=(?:[-*]|\d+\.) )', '    ', src, flags=re.M)  # python-markdown nests lists at 4 spaces
src = re.sub(r'^\*(Figure \d+\..*)\*$', r'<p class="caption">\1</p>', src, flags=re.M)
body = markdown.markdown(src, extensions=['tables', 'fenced_code', 'sane_lists'])
css = """
body { font-family: Calibri, sans-serif; font-size: 11pt; line-height: 1.3; color: #1a1a1a; }
h1 { font-size: 16pt; color: #1a1a1a; } h2 { font-size: 13pt; color: #1a1a1a; } h3 { font-size: 11.5pt; color: #1a1a1a; }
table { border-collapse: collapse; width: 100%; font-size: 9pt; }
th, td { border: 1px solid #a6a6a6; padding: 2pt 4pt; vertical-align: top; text-align: left; }
th { background: #eef0f3; }
code { font-family: Consolas, monospace; font-size: 9.5pt; }
pre { font-family: Consolas, monospace; font-size: 9pt; background: #f4f4f4; }
.caption { font-style: italic; font-size: 9.5pt; color: #444; }
"""
html_path = os.path.join(ROOT, 'Report.html')
open(html_path, 'w', encoding='utf-8').write(
    f'<!doctype html><html><head><meta charset="utf-8"><title>Report</title><style>{css}</style></head><body>{body}</body></html>')

word = win32com.client.DispatchEx('Word.Application'); word.Visible = False
try:
    doc = word.Documents.Open(html_path, ConfirmConversions=False, ReadOnly=False)
    ps = doc.PageSetup
    ps.PageWidth, ps.PageHeight = 595.3, 841.9                       # A4 in points
    ps.TopMargin = ps.BottomMargin = ps.LeftMargin = ps.RightMargin = 56.7   # 2 cm
    usable = ps.PageWidth - ps.LeftMargin - ps.RightMargin
    for shp in doc.InlineShapes:                                     # embed linked images and fit them to the page
        if shp.LinkFormat is not None:
            shp.LinkFormat.SavePictureWithDocument = True; shp.LinkFormat.BreakLink()
    for shp in doc.InlineShapes:
        if shp.Width > usable:
            shp.LockAspectRatio = True; shp.Width = usable
    for t in doc.Tables:
        t.PreferredWidthType = 2; t.PreferredWidth = 100              # 100% of the page width
    doc.ActiveWindow.View.Type = 3                                   # print layout, not web layout
    out = os.path.join(ROOT, 'Report.docx')
    doc.SaveAs2(out, FileFormat=16)                                  # wdFormatDocumentDefault (.docx)
    doc.Close(False)
    print('wrote', out)
finally:
    word.Quit()
    os.remove(html_path)
