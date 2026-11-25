# Work Counter

A tiny always-on-top desktop widget (with a hammer and sickle ☭) that shows your payslip building up, live, while your shift runs. Each day carries on from the last, and it goes back to $0 on payday.

```
 $ 421.65
 fortnightly payslip
```

Defaults: **9am–5pm with a 30 min unpaid break = 7.5 paid hours × $34 = $255 a shift**, Mon–Fri, paid fortnightly on Wednesdays.

## Install (Windows)

1. Go to **Releases** → download `WorkCounter.exe`.
2. Run it. If SmartScreen says "Windows protected your PC", click **More info → Run anyway** (the exe isn't code-signed).
3. On first run, check your shift start time and which Wednesday was your last payday, then **Save**.

Right-click the widget → **Start with Windows** so it's always there.

Or run from source with Python 3.10+ (no extra packages): `pythonw work_counter.py`

## Using it

- **Drag** it anywhere; it remembers where you left it.
- **Right-click** for everything else:
  - **Void today**: called in sick, took leave, etc. Today's pay comes off the payslip. Click again (**Count today as worked**) to undo.
  - **Public holiday today**: pays the day at the holiday rate (default ×2.5). The counter runs faster and the $ turns amber.
  - **Days this fortnight…**: tick/untick any day in the pay period, past or future. Untick to void a day; tick a weekend to add an extra shift; tick the *public hol.* box to pay that day at the holiday rate. ‹ › steps between fortnights. Also shows the full-fortnight total and the payday.
  - **Settings…**: hourly rate, shift start and finish times (9am, 5pm or 17:00 all work), an optional unpaid break (the counter pauses during it; it shows the resulting paid hours and pay per shift), the public holiday multiplier (2.5 or 250% both work), work days, and which Wednesday was your last payday.
  - **Always on top**, **Start with Windows**, **Quit**.

The counter only moves between your start and finish times (pausing for the break). Outside work hours it holds still at your payslip so far.

Settings are stored in `%APPDATA%\WorkCounter\config.json`.

## Development

```
python -m unittest discover -s tests
```

The hammer and sickle is drawn by `tools/make_emblem.py` (needs Pillow) and baked into `emblem_data.py`, so the app itself has no dependencies.

Every push to `main` builds `WorkCounter.exe` on GitHub Actions and publishes it as release `v<VERSION>` (bump the `VERSION` file for a new release).
