import functools
import http.server
import os
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
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
    tmp = tempfile.mkdtemp(prefix="probe_")
    open(os.path.join(tmp, "index.html"), "w", encoding="utf-8").write(page)
    data_dir = os.path.join(os.path.dirname(os.path.abspath(src)), "data")
    if os.path.isdir(data_dir):
        shutil.copytree(data_dir, os.path.join(tmp, "data"))
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=tmp)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        if not os.path.exists(edge):
            edge = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        cmd = (
            f'"{edge}" --headless --disable-gpu --window-size=1366,900 '
            f'--virtual-time-budget=8000 --dump-dom '
            f'"http://127.0.0.1:{port}/index.html"'
        )
        res = subprocess.run(cmd, capture_output=True, shell=True)
        httpd.shutdown()
    raw = res.stdout.decode("utf-8", errors="replace")
    i = raw.find('<div id="probeout">')
    j = raw.find('<!--PROBE_END-->', i)
    if j < 0:
        j = raw.find("</div>", i)
    text = raw[i + len('<div id="probeout">'):j]
    open(out, "w", encoding="utf-8").write(text)
    print(text)


main()
