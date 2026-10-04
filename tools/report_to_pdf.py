"""Report.md -> Report.html -> Report.pdf (headless Chrome/Edge).  Run: python tools/report_to_pdf.py
Needs: pip install markdown"""
import os, re, shutil, subprocess, sys
import markdown

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
src = open(os.path.join(ROOT, 'Report.md'), encoding='utf-8').read()
src = re.sub(r'\A---\n.*?\n---\n', '', src, flags=re.S)          # drop the YAML title block
src = re.sub(r'^ {2,3}(?=(?:[-*]|\d+\.) )', '    ', src, flags=re.M)  # python-markdown nests lists at 4 spaces
body = markdown.markdown(src, extensions=['tables', 'fenced_code', 'sane_lists'])
css = """
@page { size: A4; margin: 14mm 14mm; }
body { font-family: 'Segoe UI', Calibri, Arial, sans-serif; font-size: 10pt; line-height: 1.35; color: #1a1a1a; }
h1 { font-size: 17pt; border-bottom: 1px solid #999; padding-bottom: 3px; margin-top: 26px; page-break-after: avoid; }
h2 { font-size: 13pt; margin-top: 18px; page-break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 8.5pt; page-break-inside: avoid; }
th, td { border: 1px solid #bbb; padding: 3px 5px; vertical-align: top; text-align: left; }
th { background: #eef0f3; }
code { font-family: Consolas, monospace; font-size: 8.8pt; background: #f4f4f4; padding: 0 2px; }
img { max-width: 100%; border: 1px solid #ddd; margin: 6px 0 2px; page-break-inside: avoid; }
hr { border: 0; border-top: 1px solid #ddd; margin: 18px 0; }
"""
html = f'<!doctype html><html><head><meta charset="utf-8"><title>Report</title><style>{css}</style></head><body>{body}</body></html>'
html_path, pdf_path = os.path.join(ROOT, 'Report.html'), os.path.join(ROOT, 'Report.pdf')
open(html_path, 'w', encoding='utf-8').write(html)

browsers = [shutil.which('chrome'), shutil.which('msedge'),
            r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe', '/usr/bin/google-chrome', '/usr/bin/chromium']
exe = next((b for b in browsers if b and os.path.exists(b)), None)
if not exe:
    sys.exit('No Chrome/Edge found; open Report.html and print to PDF.')
subprocess.run([exe, '--headless', '--disable-gpu', '--no-pdf-header-footer', f'--print-to-pdf={pdf_path}',
                'file:///' + os.path.abspath(html_path).replace('\\', '/')], check=True)
os.remove(html_path)
print('wrote', pdf_path)
