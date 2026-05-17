import GLib from "gi://GLib";
import Gio from "gi://Gio";
import GioUnix from "gi://GioUnix";
import { typeText } from "./typer.js";

export class Recorder {
  constructor(pythonAppPath, timeoutSeconds = 600) {
    this._appPath = pythonAppPath;
    this._timeoutSeconds = timeoutSeconds;
    this._proc = null;
    this._childWatchId = null;
    this._stdout = null;
    this._stderr = null;
    this._timeoutId = null;
    this._cancellable = null;
    this.onTranscription = null;
    this.onAudioLevel = null;
    this.onTimeout = null;
    this.onError = null;
    this.onProcessExit = null;
  }

  start() {
    const argv = [this._appPath, '--output', 'stdout'];
    const [ok, pid, stdin, stdout, stderr] = GLib.spawn_async_with_pipes(
      null,
      argv,
      null,
      GLib.SpawnFlags.DO_NOT_REAP_CHILD,
      null,
    );

    if (!ok) {
      GLib.close(stdin);
      GLib.close(stdout);
      GLib.close(stderr);
      this.onError?.("Failed to spawn voice-to-text process");
      return;
    }

    GLib.close(stdin);

    this._proc = pid;
    this._cancellable = new Gio.Cancellable();
    this._stdout = new Gio.DataInputStream({
      base_stream: new GioUnix.InputStream({ fd: stdout, close_fd: true }),
    });
    this._stderr = new Gio.DataInputStream({
      base_stream: new GioUnix.InputStream({ fd: stderr, close_fd: true }),
    });
    this._readOutput();
    this._readStderr();

    this._childWatchId = GLib.child_watch_add(
      GLib.PRIORITY_DEFAULT,
      pid,
      (p, status) => {
        this._childWatchId = null;
        this._proc = null;
        GLib.spawn_close_pid(p);
        if (this._timeoutId) {
          GLib.source_remove(this._timeoutId);
          this._timeoutId = null;
        }
        this.onProcessExit?.();
      },
    );

    this._timeoutId = GLib.timeout_add_seconds(
      GLib.PRIORITY_DEFAULT,
      this._timeoutSeconds,
      () => {
        this.stop();
        this.onTimeout?.();
        return GLib.SOURCE_REMOVE;
      },
    );
  }

  stop() {
    if (this._timeoutId) {
      GLib.source_remove(this._timeoutId);
      this._timeoutId = null;
    }

    if (this._proc) {
      const pid = this._proc;
      this._proc = null;
      this._stderr = null;
      Gio.Subprocess.new(["kill", "-INT", String(pid)], 0).wait_async(
        null,
        null,
      );
    }
  }

  _readOutput() {
    this._stdout.read_line_async(
      GLib.PRIORITY_DEFAULT,
      this._cancellable,
      (src, res) => {
        let line;
        try {
          [line] = src.read_line_finish_utf8(res);
        } catch (e) {
          console.warn('VoiceToText: stdout read error:', e.message);
          return;
        }

        if (line === null) return;

        if (line.startsWith("LEVEL:")) {
          const level = parseFloat(line.slice(6));
          if (!Number.isNaN(level)) {
            this.onAudioLevel?.(level);
          }
        } else if (line.startsWith("TEXT:")) {
          const text = line.slice(5).trim();
          if (text && text.length > 0) {
            typeText(text);
          }
        } else if (line.startsWith("FINAL:")) {
          const text = line.slice(6).trim();
          if (text && text.length > 0) {
            typeText(text);
          }
        } else if (line.startsWith("ERROR:")) {
          const errorMsg = line.slice(6).trim();
          this.stop();
          this.onError?.(errorMsg);
          return;
        }

        this._readOutput();
      },
    );
  }

  _readStderr() {
    if (!this._stderr) return;
    this._stderr.read_line_async(
      GLib.PRIORITY_DEFAULT,
      this._cancellable,
      (src, res) => {
        let line;
        try {
          [line] = src.read_line_finish_utf8(res);
        } catch (e) {
          return;
        }

        if (line !== null) {
          console.error('VoiceToText: child stderr:', line.trim());
        }
        this._readStderr();
      },
    );
  }
}
