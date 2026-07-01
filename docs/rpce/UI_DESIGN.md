# RPCE UI Design System

The plan for a UI that is **accessible**, **pretty** (a deep-blue palette — no
gray), and **intuitive**. Implemented as CSS design tokens in `qt/aqt/rpce.py`
(shared by the home banner and dashboard) plus matching Qt stylesheets for
dialogs, so every surface is consistent.

## Principles

- **One fixed theme (no light/dark modes):** both apps are locked to a single
  dark-blue theme. The desktop forces Anki's dark theme and appends an app-wide
  Qt stylesheet (`_APP_QSS`) so *every* dialog — including the AnkiWeb **Sync**
  login prompt we don't own — is navy + white with large blue buttons. The
  Android app uses a fixed `Theme.RPCE` (not `DayNight`), so it never follows the
  system light/dark setting.
- **Accessible:** body text ≥ 17px, never below 13px (only ALL-CAPS labels);
  strong contrast (light text on deep navy); clear focus/hover states; color
  is never the only signal (labels + shapes too).
- **Pretty, no gray:** a single **"Deep Blue"** palette — dark navy background,
  blue→sky accents, light-blue secondary text. No slate/gray anywhere.
- **Intuitive:** one clear hierarchy per page (title → key numbers → details →
  actions), consistent spacing, tappable/clickable targets ≥ 40px.

## Color palette (Deep Blue) — dark navy + white, no gray

| Token | Hex | Use |
| --- | --- | --- |
| `--bg-1` | `#0a1628` | page background (dark navy) |
| `--bg-2` | `#0f2447` | gradient stop / raised areas |
| `--surface` | `rgba(96,165,250,.08)` | cards / panels |
| `--border` | `rgba(96,165,250,.30)` | card / divider borders |
| `--ink` | `#f8fbff` | primary text (white) |
| `--ink-2` | `#a9c7ee` | secondary text (light blue — replaces gray) |
| `--accent` | `#2563eb` → `#38bdf8` | primary gradient (blue→sky) |
| `--ready` | `#4ade80` | high confidence / good (green) |
| `--mid` | `#38bdf8` | medium confidence (sky) |
| `--warn` | `#fbbf24` | low confidence / warnings (amber) |
| `--muted` | `#93c5fd` | abstain / neutral (light blue, not gray) |

## Type scale (consistent everywhere)

| Token | Size | Use |
| --- | --- | --- |
| `--fs-display` | 42px | hero score values |
| `--fs-h1` | 30px | page/app title |
| `--fs-h2` | 22px | section headings |
| `--fs-lead` | 18px | subtitles / lead text |
| `--fs-body` | 17px | body, chips, table cells |
| `--fs-small` | 15px | secondary lines |
| `--fs-label` | 13px | ALL-CAPS labels & pills only |

## Spacing & shape

- Spacing steps: 6 / 10 / 16 / 22 / 30 px. Card radius 20px; pill radius 999px.
- Cards: `--surface` bg, `--border`, soft navy shadow `0 6px 22px rgba(2,8,24,.5)`.

## Per-page layout

- **Home:** hero card — logo + title, then a responsive grid of 4 score cards
  (Memory, Performance, Pass I, Pass II) each with a value + confidence pill +
  progress bar; coverage bar; phase & next-topic chips; abstain notice; footer
  hint pointing at the tabs.
- **Dashboard window:** same score-card grid + a coverage table with per-domain
  bars; larger, scrollable.
- **Study (reviewer):** flashcards inherit the navy theme via CSS injected into
  the reviewer webview (`webview_will_set_content`): navy background, white card
  text, sky-blue links/cloze, navy answer bar. The Again/Good/Easy ease colors
  are left intact (color is a needed difficulty signal there).
- **Section II dialog:** navy surface, 17px prompt/answer text, blue
  "Grade" button, readable feedback block.
- **Toolbar tabs:** 16px, blue hover pill, deep-navy bar.
- **Mobile home:** same banner (logo, title, 4 score cards, coverage bar, chips,
  abstain note) rendered from `assets/home.html` in a WebView, on the fixed navy
  theme with a navy status bar.

## Accessibility checklist

- [ ] Body ≥ 17px; labels ≥ 13px (caps only)
- [ ] Text/background contrast passes AA on the navy background
- [ ] Hover + focus states on tabs, buttons, links
- [ ] Confidence shown by **label text**, not color alone
- [ ] Targets ≥ 40px tall
