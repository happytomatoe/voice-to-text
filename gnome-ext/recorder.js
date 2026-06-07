import GLib from "gi://GLib";
import Gio from "gi://Gio";
import GioUnix from "gi://GioUnix";

export class Recorder {
  constructor(pythonAppPath, settings) {
    this._appPath = pythonAppPath;
    this._settings = settings;
    this._proc = null;
    this._childWatchId = null;
    this._stdout = null;
    this._cancellable = null;
    this.onTranscription = null;
    this.onAudioLevel = null;
    this.onError = null;
    this.onProcessExit = null;
  }

  start() {
    const provider = this._settings.get_string('provider');
    const language = this._settings.get_string('language');
    const mode = this._settings.get_string('mode');
    const decreaseSpeakerVolume = this._settings.get_int('decrease-speaker-volume');
    const argv = [
      this._appPath,
      '--output', 'stdout',
      '--provider', provider,
      '--language', language,
      '--mode', mode,
    ];
    if (decreaseSpeakerVolume > 0) {
      argv.push('--decrease-speaker-volume', String(decreaseSpeakerVolume));
    }
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
    GLib.close(stderr);

    this._proc = pid;
    this._cancellable = new Gio.Cancellable();
    this._stdout = new Gio.DataInputStream({
      base_stream: new GioUnix.InputStream({ fd: stdout, close_fd: true }),
    });
    this._readOutput();

    this._childWatchId = GLib.child_watch_add(
      GLib.PRIORITY_DEFAULT,
      pid,
      (p, status) => {
        this._childWatchId = null;
        this._proc = null;
        GLib.spawn_close_pid(p);
        this.onProcessExit?.();
      },
    );
  }

  stop() {
    if (this._proc) {
      const pid = this._proc;
      this._proc = null;
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
          return;
        }

        if (line === null) return;

        if (line.startsWith("LEVEL:")) {
          const level = parseFloat(line.slice(6));
          if (!Number.isNaN(level)) {
            this.onAudioLevel?.(level);
          }
        } else if (line.startsWith("TEXT:")) {
          this.onTranscription?.(line.slice(5).trim());
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
}
