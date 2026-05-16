import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import GioUnix from 'gi://GioUnix';

export class Recorder {
    constructor(pythonAppPath) {
        this._appPath = pythonAppPath;
        this._proc = null;
        this._childWatchId = null;
        this._timeoutId = null;
        this.onTranscription = null;
        this.onAudioLevel = null;
        this.onTimeout = null;
        this.onError = null;
    }

    start() {
        const argv = [this._appPath, '--output', 'stdout'];
        const [ok, pid, stdin, stdout, stderr] =
            GLib.spawn_async_with_pipes(null, argv, null,
                GLib.SpawnFlags.DO_NOT_REAP_CHILD, null);

        GLib.close(stdin);
        GLib.close(stderr);

        this._proc = pid;
        this._stdout = new Gio.DataInputStream({
            base_stream: new GioUnix.InputStream({ fd: stdout, close_fd: true })
        });
        this._readOutput();

        this._childWatchId = GLib.child_watch_add(
            GLib.PRIORITY_DEFAULT, pid, (p, status) => {
                this._childWatchId = null;
                this._proc = null;
                GLib.spawn_close_pid(p);
            }
        );

        this._timeoutId = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT, 300, () => {
                this.stop();
                this.onTimeout?.();
                return GLib.SOURCE_REMOVE;
            });
    }

    stop() {
        if (this._timeoutId) {
            GLib.source_remove(this._timeoutId);
            this._timeoutId = null;
        }
        if (this._proc) {
            const pid = this._proc;
            this._proc = null;
            Gio.Subprocess.new(
                ['kill', '-INT', String(pid)], 0
            ).wait_async(null, null);
        }
    }

    _readOutput() {
        this._stdout.read_line_async(0, null, (src, res) => {
            const [line] = src.read_line_finish_utf8(res);
            if (line !== null) {
                if (line.startsWith('LEVEL:')) {
                    const level = parseFloat(line.slice(6));
                    this.onAudioLevel?.(level);
                } else if (line.startsWith('TEXT:')) {
                    this.onTranscription?.(line.slice(5).trim());
                } else if (line.startsWith('ERROR:')) {
                    this.onError?.(line.slice(6).trim());
                }
                this._readOutput();
            }
        });
    }
}
