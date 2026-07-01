# RPCE UI Design System

The plan for a UI that is **accessible**, **pretty** (a blue-on-white palette —
no gray), and **intuitive**. Implemented as CSS design tokens in `qt/aqt/rpce.py`
(shared by the home banner and dashboard) plus matching Qt stylesheets for
dialogs, so every surface is consistent.

## Principles

- **One fixed theme (no light/dark toggle):** both apps are locked to a single
  **light Blue-on-White** theme. The desktop forces Anki's light theme and
  appends an app-wide Qt stylesheet (`_APP_QSS`) so *every* dialog — including
  the AnkiWeb **Sync** login prompt we don't own — is white + dark-navy text
  with large blue buttons. The Android app uses a fixed `Theme.RPCE`
  (`Theme.AppCompat.Light.NoActionBar`, not `DayNight`), so it never follows the
  system light/dark setting.
- **Accessible:** body text ≥ 17px, never below 13px (only ALL-CAPS labels);
  strong contrast (dark navy text on white); clear focus/hover states; color
  is never the only signal (labels + shapes too).
- **Pretty, no gray:** a single **Blue-on-White** palette — white/soft-blue
  background, dark-navy text, blue→sky accents, medium-blue secondary text. No
  slate/gray anywhere (neutrals are blue-tinted).
- **Intuitive:** one clear hierarchy per page (title → key numbers → details →
  actions), consistent spacing, tappable/clickable targets ≥ 40px.

## Color palette (Blue-on-White) — white + dark navy, no gray

| Token | Hex | Use |
| --- | --- | --- |
| `--surface` | `#ffffff` | cards / panels |
| `--surface2` | `#f4f8ff` | raised areas |
| `--track` | `#dbe8fb` | progress-bar tracks |
| `--border` | `#caddf7` | card / divider borders |
| `--ink` | `#0a1f44` | primary text (dark navy) |
| `--ink-2` | `#35548c` | secondary text (medium blue — replaces gray) |
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

## Logo & branding

- **Logo:** a navy (`#0a1f44`) gavel with a blue (`#2f6fed`) head and light-blue
  (`#60a5fa`) "speed" streak — parliamentary authority + fast mastery — on a
  rounded white tile. Matches the Blue-on-White palette; no gray, no text.
- **Where it's used:**
  - Desktop: application/taskbar + window icon (`qt/aqt/data/qt/icons/rpce_logo.png`)
    and the home banner (inlined small copy `rpce_logo_small.png`).
  - Phone: launcher icon (`res/mipmap-*/ic_launcher(.|_round.)png`) and the home
    header (`assets/rpce_logo.png`).
- Source master lives outside the repo; sized copies are checked in per target.

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
