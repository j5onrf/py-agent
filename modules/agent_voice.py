#!/usr/bin/env python3
"""Local-AI Standalone Voice to Text Module"""

import base64
import http.server
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import time
import urllib.request as urlreq

PORT = 9999
CFG_DIR = os.path.expanduser("~/.config/py-agent")
PENDING_FILE = os.path.join(CFG_DIR, ".voice_pending.txt")

RE_CLEAN_TRANSCRIPTION: re.Pattern = re.compile(r"[^a-zA-Z0-9\s?.,!\'-]")
RE_NUMERIC_DIGITS: re.Pattern = re.compile(r"^\d{1,4}$")

try:
    import agent_core as core
except ImportError:
    core = None

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <!-- Disable client-side caching -->
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>Voice to Text</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #000; color: #c0caf5; font-family: monospace; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; overflow: hidden; user-select: none; -webkit-user-select: none; touch-action: none; }
        .mic-container { position: relative; display: flex; align-items: center; justify-content: center; width: 260px; height: 260px; }
        .pulse-ring { position: absolute; width: 220px; height: 220px; border-radius: 50%; border: 2px solid #7aa2f7; opacity: 0; transition: transform 0.05s ease-out, opacity 0.2s ease; pointer-events: none; }
        button { position: relative; width: 210px; height: 210px; border-radius: 50%; border: 3px solid #7aa2f7; background: #000; color: #7aa2f7; font-size: 17px; font-weight: bold; cursor: pointer; transition: background 0.2s, color 0.2s, border-color 0.2s, transform 0.1s; outline: none; touch-action: none; -webkit-touch-callout: none; z-index: 2; }
        button.recording { background: #7aa2f7; color: #000; border-color: #7aa2f7; transform: scale(1.03); }
        #status { margin-top: 35px; font-size: 13px; color: #565f89; text-transform: uppercase; letter-spacing: 2px; height: 20px; }
        #result { margin-top: 15px; font-size: 18px; color: #9ece6a; text-align: center; max-width: 85%; min-height: 50px; line-height: 1.4; word-break: break-word; }
    </style>
</head>
<body>
    <div class="mic-container">
        <div id="ring" class="pulse-ring"></div>
        <button id="mic-btn">HOLD TO SPEAK</button>
    </div>
    <div id="status">Ready</div>
    <div id="result"></div>
    <script>
        const btn = document.getElementById('mic-btn'), ring = document.getElementById('ring'), status = document.getElementById('status'), result = document.getElementById('result');
        let mediaRecorder, audioChunks = [], audioCtx, analyser, dataArray, animId, activeMime = 'audio/webm';

        const mimeTypes = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
        for (const m of mimeTypes) {
            if (MediaRecorder.isTypeSupported(m)) { activeMime = m; break; }
        }

        navigator.mediaDevices.getUserMedia({
            audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, sampleRate: 48000 }
        }).then(stream => {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const source = audioCtx.createMediaStreamSource(stream);
            analyser = audioCtx.createAnalyser();
            analyser.fftSize = 64;
            source.connect(analyser);
            dataArray = new Uint8Array(analyser.frequencyBinCount);

            mediaRecorder = new MediaRecorder(stream, { mimeType: activeMime });
            mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
            mediaRecorder.onstop = () => {
                status.innerText = "Transcribing...";
                const audioBlob = new Blob(audioChunks, { type: activeMime });
                audioChunks = [];
                fetch('/upload', { method: 'POST', headers: { 'Content-Type': activeMime }, body: audioBlob })
                    .then(r => r.text())
                    .then(text => {
                        result.innerText = text ? `"${text}"` : "Silence detected.";
                        status.innerText = "Executed.";
                    }).catch(() => { status.innerText = "Transmission failed."; });
            };
        }).catch(() => { status.innerText = "Mic Permission Blocked"; btn.style.borderColor = "#f7768e"; });

        function updateVisualizer() {
            if (mediaRecorder?.state === "recording" && analyser) {
                analyser.getByteFrequencyData(dataArray);
                let sum = 0;
                for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
                const avg = sum / dataArray.length;
                const scale = 1 + Math.min(avg / 128, 0.45);
                ring.style.transform = `scale(${scale})`;
                ring.style.opacity = Math.min(avg / 64, 0.9);
                animId = requestAnimationFrame(updateVisualizer);
            } else {
                ring.style.transform = 'scale(1)';
                ring.style.opacity = '0';
            }
        }

        const startRec = e => {
            if (e) e.preventDefault();
            if (navigator.vibrate) navigator.vibrate(30);
            if (audioCtx && audioCtx.state === "suspended") audioCtx.resume();
            if (mediaRecorder && mediaRecorder.state === "inactive") {
                audioChunks = [];
                mediaRecorder.start(); // Collects everything into a single buffer until release
                status.innerText = "Listening...";
                btn.classList.add('recording');
                updateVisualizer();
            }
        };

        const stopRec = e => {
            if (e) e.preventDefault();
            if (mediaRecorder && mediaRecorder.state === "recording") {
                if (navigator.vibrate) navigator.vibrate(20);
                mediaRecorder.stop();
                btn.classList.remove('recording');
                if (animId) cancelAnimationFrame(animId);
                ring.style.transform = 'scale(1)';
                ring.style.opacity = '0';
            }
        };

        btn.addEventListener('pointerdown', startRec);
        window.addEventListener('pointerup', stopRec);
        window.addEventListener('pointercancel', stopRec);
        btn.addEventListener('contextmenu', e => { e.preventDefault(); e.stopPropagation(); return false; });
    </script>
</body>
</html>
"""

_voice_proc = None
_auto_submit = True


def is_bridge_running() -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            return s.connect_ex(("127.0.0.1", PORT)) == 0
    except OSError:
        return False


def load_voice_env() -> None:
    env_path = os.path.join(CFG_DIR, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if (s := line.strip()) and not s.startswith("#") and "=" in s:
                        k, v = s.replace("export ", "", 1).split("=", 1)
                        if k := k.strip():
                            os.environ[k] = (
                                v.split(" #")[0].strip().strip('"').strip("'")
                            )
        except OSError:
            pass


def transcribe_gemini(audio_data: bytes, mime_type: str = "audio/webm") -> str:
    load_voice_env()
    gkey = os.environ.get("GEM_VOICE") or os.environ.get("GEMINI_API_KEY")
    model = os.environ.get("GEM_MODEL") or os.environ.get(
        "GEMINI_MODEL", "gemini-3.7-flash"
    )
    if not gkey:
        sys.stderr.write(
            "[error] GEM_VOICE key is not set in ~/.config/py-agent/.env\n"
        )
        sys.stderr.flush()
        return ""

    encoded = base64.b64encode(audio_data).decode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gkey}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"inline_data": {"mime_type": mime_type, "data": encoded}},
                    {
                        "text": "Transcribe this audio verbatim. If the audio is silent or contains background noise, output 'SILENCE'. Output ONLY plain text."
                    },
                ]
            }
        ]
    }
    try:
        req = urlreq.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlreq.urlopen(req, timeout=10) as resp:
            try:
                with open(
                    os.path.join(CFG_DIR, ".request_log"), "a", encoding="utf-8"
                ) as lf:
                    lf.write(f"{int(time.time())}|gemini\n")
            except OSError:
                pass
            res_data = json.loads(resp.read().decode("utf-8"))
            raw = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            clean = RE_CLEAN_TRANSCRIPTION.sub("", raw).strip()
            cl_lower = clean.lower()
            if (
                not clean
                or len(clean) < 2
                or cl_lower in ("silence", "uh", "um", "mm", "thank you", "thank you.")
            ):
                return ""
            if RE_NUMERIC_DIGITS.match(clean) and len(set(clean)) == 1:
                return ""
            return clean
    except Exception as e:
        sys.stderr.write(f"[error] Transcription failed: {e}\n")
        sys.stderr.flush()
        return ""


def get_prompt_input(symbol: str = "❯") -> str:
    try:
        return input(f"{symbol} ").strip()
    except (KeyboardInterrupt, EOFError):
        raise


class VoiceHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        try:
            if self.path == "/upload":
                length = int(self.headers.get("Content-Length", 0))
                mime_type = self.headers.get("Content-Type", "audio/webm").split(";")[0]
                audio_data = self.rfile.read(length)
                query = (
                    transcribe_gemini(audio_data, mime_type=mime_type)
                    if audio_data
                    else ""
                )
                if query:
                    sys.stderr.write(f"[sys] Transcribed: {query}\n")
                    sys.stderr.flush()

                    # Universal Wayland / Hyprland virtual typing into active window
                    try:
                        subprocess.run(["wtype", query], check=False)
                        if _auto_submit:
                            time.sleep(0.05)
                            subprocess.run(["wtype", "-k", "Return"], check=False)
                    except Exception:
                        pass

                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(query.encode("utf-8"))
        except Exception as e:
            sys.stderr.write(f"[error] Server error: {e}\n")
            sys.stderr.flush()
            self.send_response(500)
            self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(HTML_CONTENT.encode("utf-8"))


def run_server() -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = "127.0.0.1"
    finally:
        s.close()

    cert_path = os.path.join(CFG_DIR, "server.pem")
    if not os.path.exists(cert_path):
        subprocess.run(
            f'openssl req -new -x509 -keyout "{cert_path}" -out "{cert_path}" -days 365 -nodes -subj "/CN={local_ip}"',
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # ThreadingHTTPServer ensures multiple requests / streaming uploads don't block the visualizer UI
    with http.server.ThreadingHTTPServer(("", PORT), VoiceHandler) as httpd:
        if os.path.exists(cert_path):
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(certfile=cert_path)
            httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)

        print(f"[ok] Voice to Text active: https://{local_ip}:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[sys] Server stopped.")


def toggle_voice_bridge(auto_toggle: bool = False) -> tuple[bool, bool]:
    global _voice_proc, _auto_submit
    if core:
        _auto_submit = core.get_state().get("voice_auto_submit", True)

    is_running = is_bridge_running()

    if auto_toggle and is_running:
        _auto_submit = not _auto_submit
        if core:
            core.save_state("voice_auto_submit", _auto_submit)
        return True, _auto_submit

    if is_running:
        if _voice_proc:
            try:
                _voice_proc.terminate()
            except OSError:
                pass
        subprocess.run(["pkill", "-f", "agent_voice.py"], stderr=subprocess.DEVNULL)
        _voice_proc = None
        return False, _auto_submit
    else:
        mod_path = os.path.abspath(__file__)
        _voice_proc = subprocess.Popen(
            [sys.executable, mod_path, "--server"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True, _auto_submit


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--server":
        run_server()
    else:
        toggle_voice_bridge()
