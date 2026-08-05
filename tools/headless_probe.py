import os
import subprocess
import sys
import tempfile

def main():
    src = sys.argv[1]      # path to index.html (regenerated)
    probe_js = sys.argv[2] # JS (или путь к .js-файлу с кодом)
    out = sys.argv[3]      # path to output .txt (UTF-8)
    html = open(src, encoding="utf-8").read()
    if os.path.isfile(probe_js):
        probe_js = open(probe_js, encoding="utf-8").read()
    wrapper = (
        '<div id="probeout"></div>\n<script>\n' + probe_js + "\n</script>"
    )
    page = html.replace("</body>", wrapper + "</body>")
    tmp = os.path.join(tempfile.gettempdir(), "probe_page.html")
    open(tmp, "w", encoding="utf-8").write(page)
    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if not os.path.exists(edge):
        edge = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    cmd = (
        f'"{edge}" --headless --disable-gpu --window-size=1366,900 '
        f'--virtual-time-budget=8000 --dump-dom "file:///{tmp}"'
    )
    res = subprocess.run(cmd, capture_output=True, shell=True)
    raw = res.stdout.decode("utf-8", errors="replace")
    i = raw.find('<div id="probeout">')
    j = raw.find('<!--PROBE_END-->', i)
    if j < 0:
        j = raw.find("</div>", i)
    text = raw[i + len('<div id="probeout">'):j]
    open(out, "w", encoding="utf-8").write(text)
    print(text)

main()
