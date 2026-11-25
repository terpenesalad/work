# Work Counter

A tiny always-on-top desktop widget that counts up what you've earned today, live, while your shift runs. A smaller line underneath shows the running total for the current pay fortnight.

```
 $ 166.65
 this fortnight $1,441.65
```

Defaults: **$34/hr × 7.5 h = $255 a shift**, Mon–Fri, paid fortnightly on Wednesdays. The fortnight total resets to $0 on each payday.

## Install (Windows)

1. Go to **Releases** → download `WorkCounter.exe`.
2. Run it. If SmartScreen says "Windows protected your PC", click **More info → Run anyway** (the exe isn't code-signed).
3. On first run, check your shift start time and which Wednesday was your last payday, then **Save**.

Right-click the widget → **Start with Windows** so it's always there.

Or run from source with Python 3.10+ (no extra packages): `pythonw work_counter.py`

## Using it

- **Drag** it anywhere; it remembers where you left it.
- **Right-click** for everything else:
  - **Void today**: called in sick, took leave, etc. Today drops to $0 and comes off the fortnight total. Click again (**Count today as worked**) to undo.
  - **Days this fortnight…**: tick/untick any day in the pay period, past or future. Untick to void a day; tick a weekend to add an extra shift. ‹ › steps between fortnights. Also shows the full-fortnight total and the payday.
  - **Settings…**: hourly rate, paid hours, shift start, an optional unpaid break (the counter pauses during it), work days, and which Wednesday was your last payday.
  - **Always on top**, **Start with Windows**, **Quit**.

Before the shift starts it shows $0.00; once the paid hours are done it holds at the full day's pay.

Settings are stored in `%APPDATA%\WorkCounter\config.json`.

## Development

```
python -m unittest discover -s tests
```

Pushing a tag like `v1.0.1` builds `WorkCounter.exe` on GitHub Actions and attaches it to a release.
