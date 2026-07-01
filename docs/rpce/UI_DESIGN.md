# RPCE UI Design System

The plan for a UI that is **accessible**, **pretty** (a warm violet palette — no
gray), and **intuitive**. Implemented as CSS design tokens in `qt/aqt/rpce.py`
(shared by the home banner and dashboard) plus matching Qt stylesheets for
dialogs, so every surface is consistent.

## Principles

- **Accessible:** body text ≥ 17px, never below 13px (only ALL-CAPS labels);
  strong contrast (light text on deep violet); clear focus/hover states; color
  is never the only signal (labels + shapes too).
- **Pretty, no gray:** a single **"Grape"** palette — deep violet background,
  violet→fuchsia accents, warm secondary text. No slate/gray anywhere.
- **Intuitive:** one clear hierarchy per page (title → key numbers → details →
  actions), consistent spacing, tappable/clickable targets ≥ 40px.

## Color palette (Grape) — no gray

| Token | Hex | Use |
| --- | --- | --- |
| `--bg-1` | `#1b0e38` | page background (deep grape) |
| `--bg-2` | `#2a1458` | gradient stop / raised areas |
| `--surface` | `rgba(167,139,250,.10)` | cards / panels |
| `--border` | `rgba(167,139,250,.30)` | card / divider borders |
| `--ink` | `#faf5ff` | primary text (warm white) |
| `--ink-2` | `#d8b4fe` | secondary text (light violet — replaces gray) |
| `--accent` | `#a855f7` → `#ec4899` | primary gradient (violet→fuchsia) |
| `--ready` | `#34d399` | high confidence / good (emerald) |
| `--mid` | `#38bdf8` | medium confidence (sky) |
| `--warn` | `#fbbf24` | low confidence / warnings (amber) |
| `--muted` | `#c4b5fd` | abstain / neutral (lavender, not gray) |

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
- Cards: `--surface` bg, `--border`, soft violet shadow `0 10px 30px rgba(88,28,135,.35)`.

## Per-page layout

- **Home:** hero card — logo + title, then a responsive grid of 4 score cards
  (Memory, Performance, Pass I, Pass II) each with a value + confidence pill +
  progress bar; coverage bar; phase & next-topic chips; abstain notice; footer
  hint pointing at the tabs.
- **Dashboard window:** same score-card grid + a coverage table with per-domain
  bars; larger, scrollable.
- **Section II dialog:** violet surface, 17px prompt/answer text, accent-gradient
  "Grade" button, readable feedback block.
- **Toolbar tabs:** 16px, violet hover pill, deep-grape bar.

## Accessibility checklist

- [ ] Body ≥ 17px; labels ≥ 13px (caps only)
- [ ] Text/background contrast passes AA on the grape background
- [ ] Hover + focus states on tabs, buttons, links
- [ ] Confidence shown by **label text**, not color alone
- [ ] Targets ≥ 40px tall
