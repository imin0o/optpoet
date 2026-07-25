# P0-017 ローカル UI 候補スパイク
#
# 目的: Gradio / Streamlit / NiceGUI の 3 候補を参照 PC の Python 3.14 で実際に起動し、
#       (1) 版・導入性、(2) loopback 固定 (既定の待受アドレスと 127.0.0.1 への固定可否を
#       netstat で実測)、(3) 進捗表示 API、(4) 取消 (実行中生成の中断) 能力 を確認する。
#       用途は authoring UI (architecture.md「初期版: Gradio / Streamlit」/ requirements FR-18
#       進捗・中断・失敗、architecture.md「UI は loopback のみに公開する」)。
#
# 実行: 隔離 venv に gradio streamlit nicegui を導入して実行 (Windows / netstat 前提)。
#   python ui_loopback_spike.py            # 人間可読の要約
#   python ui_loopback_spike.py --json     # 生データ(JSON)

import json
import re
import socket
import subprocess
import sys
import time
from importlib.metadata import version as _v


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def netstat_listen(port):
    """port を LISTENING しているローカルアドレス一覧を netstat から取得。"""
    try:
        # 日本語ロケールの netstat は見出しが非UTF-8。バイト取得して破損文字は無視。
        raw = subprocess.run(["netstat", "-ano", "-p", "tcp"],
                             capture_output=True, timeout=15).stdout
        out = raw.decode("ascii", errors="ignore")
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    addrs = []
    for ln in out.splitlines():
        if "LISTENING" not in ln:
            continue
        # 例: TCP    127.0.0.1:7860   0.0.0.0:0   LISTENING   1234
        m = re.search(r"\s(\S+):(\d+)\s+\S+:\S+\s+LISTENING", ln)
        if m and int(m.group(2)) == port:
            addrs.append(m.group(1))
    return addrs


def wait_and_probe(cmd, port, timeout=45):
    """cmd をサブプロセス起動し、port が LISTEN するまで待って待受アドレスを実測。"""
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    listen = []
    connected = False
    t0 = time.monotonic()
    try:
        while time.monotonic() - t0 < timeout:
            if proc.poll() is not None:
                return {"started": False, "reason": f"process exited rc={proc.returncode}"}
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    connected = True
            except OSError:
                time.sleep(0.5)
                continue
            listen = netstat_listen(port)
            break
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
    return {
        "started": connected,
        "loopback_connect_ok": connected,
        "listen_addrs": listen,
        # 0.0.0.0 / :: を含めば全 IF 公開、127.0.0.1 / ::1 のみなら loopback 限定
        "loopback_only": bool(listen) and all(
            a in ("127.0.0.1", "::1", "[::1]") for a in listen),
        "exposes_all_interfaces": any(
            a in ("0.0.0.0", "::", "[::]") for a in listen),
    }


# ---- Gradio -----------------------------------------------------------------
def probe_gradio():
    import gradio  # noqa: F401
    port_def = free_port()
    port_lb = free_port()
    # 既定 (server_name 未指定) の待受
    default = wait_and_probe(
        [sys.executable, "-c",
         "import gradio as gr;"
         "gr.Interface(lambda x:x,'text','text').launch("
         f"server_port={port_def},share=False,quiet=True)"],
        port_def)
    # 明示 loopback 固定
    locked = wait_and_probe(
        [sys.executable, "-c",
         "import gradio as gr;"
         "gr.Interface(lambda x:x,'text','text').launch("
         f"server_name='127.0.0.1',server_port={port_lb},share=False,quiet=True)"],
        port_lb)
    # 進捗・取消 API
    import gradio as gr
    caps = {
        "progress_api": hasattr(gr, "Progress"),
        "progress_how": "gr.Progress / yield によるストリーミング更新",
        "cancel_api": True,
        "cancel_how": "queue() + event の cancels=[...] で実行中イベントを中断",
    }
    return {"name": "Gradio", "version": _v("gradio"),
            "install": "wheel のみ (cp314 対応)",
            "default_bind": "127.0.0.1 (loopback 既定)",
            "default": default, "locked": locked, "caps": caps}


# ---- Streamlit --------------------------------------------------------------
def probe_streamlit():
    import streamlit  # noqa: F401
    import tempfile, os
    port_def = free_port()
    port_lb = free_port()
    app = os.path.join(tempfile.gettempdir(), "p0017_st_app.py")
    with open(app, "w", encoding="utf-8") as f:
        f.write("import streamlit as st\nst.write('p0-017')\n")
    base = [sys.executable, "-m", "streamlit", "run", app,
            "--server.headless", "true", "--browser.gatherUsageStats", "false"]
    default = wait_and_probe(base + ["--server.port", str(port_def)], port_def, timeout=60)
    locked = wait_and_probe(
        base + ["--server.port", str(port_lb), "--server.address", "127.0.0.1"],
        port_lb, timeout=60)
    caps = {
        "progress_api": hasattr(streamlit, "progress"),
        "progress_how": "st.progress / st.status / st.spinner",
        "cancel_api": False,
        "cancel_how": "スクリプト再実行モデル。実行中の python コールバックを直接中断不可"
                      "(session_state フラグ + 再実行で疑似中断)",
    }
    return {"name": "Streamlit", "version": _v("streamlit"),
            "install": "wheel のみ",
            "default_bind": "全 IF (server.address 未設定時) — 明示固定が必要",
            "default": default, "locked": locked, "caps": caps}


# ---- NiceGUI ----------------------------------------------------------------
def probe_nicegui():
    import nicegui  # noqa: F401
    import inspect
    from nicegui import ui
    port_def = free_port()
    port_lb = free_port()
    default = wait_and_probe(
        [sys.executable, "-c",
         "from nicegui import ui; ui.label('p0-017');"
         f"ui.run(port={port_def},show=False,reload=False)"],
        port_def)
    locked = wait_and_probe(
        [sys.executable, "-c",
         "from nicegui import ui; ui.label('p0-017');"
         f"ui.run(host='127.0.0.1',port={port_lb},show=False,reload=False)"],
        port_lb)
    sig = inspect.signature(ui.run)
    host_default = sig.parameters["host"].default
    caps = {
        "progress_api": hasattr(ui, "linear_progress") or hasattr(ui, "circular_progress"),
        "progress_how": "ui.linear_progress / ui.circular_progress (async 更新)",
        "cancel_api": True,
        "cancel_how": "async ネイティブ。asyncio.Task.cancel() で実行中生成を即中断",
    }
    return {"name": "NiceGUI", "version": _v("nicegui"),
            "install": "wheel のみ (FastAPI/uvicorn ベース)",
            "default_bind": f"host 既定={host_default!r} — 明示固定が必要",
            "default": default, "locked": locked, "caps": caps}


def fmt(p):
    if not p.get("started"):
        return f"起動せず ({p.get('reason','?')})"
    tag = "loopback限定" if p["loopback_only"] else (
        "全IF公開" if p["exposes_all_interfaces"] else "?")
    return f"listen={p['listen_addrs']} → {tag}"


def main():
    results = []
    for fn in (probe_gradio, probe_streamlit, probe_nicegui):
        try:
            results.append(fn())
        except Exception as e:
            results.append({"name": fn.__name__, "error": f"{type(e).__name__}: {e}"})

    if "--json" in sys.argv:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    for r in results:
        print("=" * 72)
        if "error" in r:
            print(r["name"], "ERROR:", r["error"])
            continue
        print(f"# {r['name']}  (v{r['version']})  導入: {r['install']}")
        print(f"  既定bind : {r['default_bind']}")
        print(f"  既定起動 : {fmt(r['default'])}")
        print(f"  loopback固定: {fmt(r['locked'])}")
        c = r["caps"]
        print(f"  進捗     : {'有' if c['progress_api'] else '無'}  {c['progress_how']}")
        print(f"  取消     : {'有' if c['cancel_api'] else '限定'}  {c['cancel_how']}")


if __name__ == "__main__":
    main()
