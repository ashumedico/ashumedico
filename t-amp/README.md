# T-Amp: a Winamp-classic player for YouTube Music

A native Windows player that looks and behaves like Winamp 2. It searches the
**YouTube Music** catalogue as you type and plays only what it finds there. You don't
need an API key, a login or a browser.

![T-Amp: main window, equalizer, playlist and the docked YouTube Music search](docs/t-amp.png)

*Rendered by the test suite with a sample playlist. The equalizer, analyser and time
display are working on real decoded audio.*

## Run it

| Way | What you do | Good for |
|---|---|---|
| **Ready-made .exe** | Actions tab → **T-Amp Windows build** → latest run → download **T-Amp-windows** → unzip → `T-Amp\T-Amp.exe` | No Python needed |
| **From this folder** | Double-click `RUN.bat` (first run sets up `.venv`, about 3 min, once) | You have Python 3.10+ |
| **Your own .exe** | `RUN.bat` once, then `BUILD-EXE.bat`: it builds `dist\T-Amp\T-Amp.exe` and puts **T-Amp** on the Desktop | Same as above, plus a shortcut |

Something not working? `SELFTEST.bat` checks every part with real data and says
which one failed: ffmpeg, the JavaScript runtime, your speakers, a live search, a stream,
and 3 seconds of decoded audio. The report is saved to `%APPDATA%\T-Amp\selftest.txt`.

## What's in it

- **Main window:** green LCD time (click it for remaining time; it blinks when paused),
  a scrolling song title (Hindi and other non-Latin titles switch to a real font),
  kbps / kHz / mono-stereo from the actual stream, volume and balance (with a centre
  detent), a seek bar, transport, shuffle and repeat, and the **O A I D V** clutterbar.
- **Visualiser:** a spectrum analyser with falling peaks, or an oscilloscope; click to
  cycle. It analyses the samples that are reaching your speakers *now*, not a guess.
- **Equalizer:** preamp plus 10 bands (60 Hz–16 kHz, ±12 dB), applied in real time, 18
  presets, and a graph of the filters' true response. **AUTO** remembers your EQ per song.
- **Playlist editor:** Winamp's green-on-black list with the current track in white and
  the selection in blue. Drag rows to reorder, use the ADD / REM / SEL / MISC / LIST OPTS
  menus, save and load `.m3u8`, and resize in 29-px steps.
- **YouTube Music search:** results follow your typing. **SONGS / VIDEOS / ALBUMS**
  (Tab switches); pick an album and its tracks are added in order. Paste a YouTube
  Music link (song, album or playlist) to add it.
- **Windowshade** (double-click the title bar), **double size** (Ctrl+D), always on top,
  snapping to screen edges, and the search window docking beside the player.
- **Media keys** (Play/Pause, Next, Previous, Stop) work even when T-Amp isn't focused.
  You can turn this off in Options.
- **Remembers everything:** playlist, volume, EQ, window positions, and sizes.
- **Only one T-Amp:** opening it again brings the running one forward.

## Keys (the original Winamp map)

| Key | Action | Key | Action |
|---|---|---|---|
| `Z` `X` `C` `V` `B` | Prev, Play, Pause, Stop, Next | `L` / `J` / `Ins` | Search YouTube Music |
| `←` `→` | Seek 5 s | `↑` `↓` | Volume |
| `S` / `R` | Shuffle / Repeat | `Ctrl+D` | 1x / 2x size |
| `Ctrl+W` | Windowshade | `Ctrl+A` | Always on top |
| `Alt+G` / `Alt+E` | Equalizer / Playlist | `Alt+3` | Track info |
| `Del` | Remove selected rows | `Alt+↑` `Alt+↓` | Move selected rows |

In the search box: `↑` `↓` choose, `Enter` play, `Shift+Enter` enqueue,
`Ctrl+Enter` enqueue every result, `Tab` switches Songs / Videos / Albums, `Esc` clears and then closes.

## How it works

```
type -> ytmusicapi (YouTube Music search) -> pick -> yt-dlp + Deno (direct audio URL)
     -> ffmpeg (decode to PCM) -> buffer -> EQ (scipy biquads) -> visualiser tap
     -> volume / balance -> PortAudio -> speakers
```

`tamp/engine.py` never blocks the window: decoding runs in a thread and playback
in the sound card's callback. Network hiccups are absorbed by a 20-second buffer. An
expired stream URL is fetched again and playback resumes where it stopped. The next
song's URL is prefetched halfway through the current one.

## Things to know

- **YouTube changes often, and old yt-dlp versions stop working.** T-Amp checks PyPI
  every 3 days and installs newer yt-dlp / ytmusicapi (SHA-256 verified) into
  `%APPDATA%\T-Amp\pylib`. Restart to use them. You can also check now from the menu:
  *Update YouTube engine*.
- **Some tracks need a signed-in account** (age-restricted, members-only, blocked in
  your region). T-Amp shows the reason in the title display and moves on to the next track.
- Search results are for region **IN** (`"region"` in `%APPDATA%\T-Amp\state.json`).
- For personal listening. Streams come straight from YouTube, so YouTube's terms
  apply. Inspired by Winamp 2; not affiliated with Winamp or YouTube, and no Winamp
  skin bitmaps are used (the classic look is drawn in code).

## Development

```
pip install -r requirements.txt pytest
python -m pytest tests -q          # engine, EQ, visualiser, offscreen UI, parsing, updater
python -m tamp                     # run from source
python -m tamp --selftest          # the end-to-end check
```

CI (`.github/workflows/t-amp-windows.yml`) runs the tests on Windows and builds the
.exe. It then runs the built .exe's self-test against live YouTube Music.
