export const meta = {
  name: "rpce-author-section2-v2",
  description: "Rewrite Section II scenarios (sample-style), 2+ per RONR section, keyword-gradeable to 5/5",
  phases: [
    { title: "Author", detail: "write scenarios + a short keyword answer, no narrow sub-questions" },
    { title: "Verify", detail: "check the short keyword answer covers the model ruling" },
  ],
}

const CORPUS = "C:\\Users\\18037\\Desktop\\Work\\rpce\\anki\\data\\roberts_rules_of_order_12th_edition.md"
const SAMPLE = "C:\\Users\\18037\\Desktop\\Work\\rpce\\anki\\data\\RPCE-Sample-Questions-v4-100625.md"

const GROUPS = [
  { domain: 1, name: "Main Motions & handling motions", secs: "3,4,6,10" },
  { domain: 2, name: "Subsidiary & Privileged Motions", secs: "11,12,13,14,15,16,17,18,19,20,21,22" },
  { domain: 3, name: "Incidental & Bring-Again Motions", secs: "23,24,25,26,27,28,29,30,31,32,33,34,35,36,37" },
  { domain: 4, name: "Organization & Conduct of Meetings", secs: "1,2,7,8,9,38,39,40,41,42,43,47,48,62,63" },
  { domain: 5, name: "Voting, Nominations, Elections", secs: "44,45,46" },
  { domain: 7, name: "Boards, Committees, Bylaws", secs: "49,50,51,52,53,54,55,56,57" },
]
const PER_SECTION = 2

const SCEN_SCHEMA = {
  type: "object", additionalProperties: false, required: ["scenarios"],
  properties: { scenarios: { type: "array", items: {
    type: "object", additionalProperties: false,
    required: ["domain", "section", "prompt", "gold_answer", "quote", "short_answer"],
    properties: {
      domain: { type: "integer" },
      section: { type: "string", description: "RONR section:paragraph, e.g. 10:5" },
      prompt: { type: "string", description: "self-contained scenario + a single clear question" },
      gold_answer: { type: "string", description: "concise model ruling naming ONLY the decisive facts asked for, in standard RONR terms" },
      quote: { type: "string", description: "short verbatim RONR sentence from that section" },
      short_answer: { type: "string", description: "the minimal correct answer: just the key terms (what a candidate could type to earn full marks)" },
    } } } },
}
const VERDICT_SCHEMA = {
  type: "object", additionalProperties: false, required: ["results"],
  properties: { results: { type: "array", items: {
    type: "object", additionalProperties: false, required: ["index", "keep", "reason"],
    properties: { index: { type: "integer" }, keep: { type: "boolean" }, reason: { type: "string" } } } } },
}

const COMMON = `Write SECTION II performance scenarios for the Registered Parliamentarian exam (RONR 12th ed.).
Read the sample style first: ${SAMPLE} (a concrete, named, self-contained scenario with ONE clear question). Ground each in the RONR corpus: ${CORPUS}.

CRITICAL RULES (a keyword grader will score answers):
- Ask ONE clear question the candidate can answer with a SHORT keyword answer. Do NOT ask "as chair, what do you do before debate?" or other narrow sub-questions that then secretly require extra facts (like the vote). Ask directly for the ruling / the decisive facts.
- The "gold_answer" is a CONCISE model ruling that plainly names ONLY the decisive facts the question asks for, in standard RONR terms — e.g. needs a second (or no second), debatable (or not debatable), the vote threshold (majority / two-thirds), the chair's action, the motion name. Keep it to at most ~15 key terms. Don't bury the answer in prose.
- "short_answer" is the minimal correct answer: JUST those key terms (e.g. "no second; not debatable; two-thirds vote; chair rules"). A candidate typing this must earn full marks, so every key term in gold_answer must appear in short_answer and vice-versa. Do NOT include a section number in the prompt.`

phase("Author")
const batches = []
for (const g of GROUPS) {
  for (const sec of g.secs.split(",")) batches.push({ g, sec })
}

const authored = await pipeline(
  batches,
  (b) => agent(
    `${COMMON}\n\nWrite ${PER_SECTION} DISTINCT scenarios grounded in RONR §${b.sec} (domain ${b.g.domain}, ${b.g.name}). Return JSON per schema (domain=${b.g.domain}, section starting "${b.sec}:").`,
    { label: `author:d${b.g.domain}-s${b.sec}`, phase: "Author", schema: SCEN_SCHEMA, effort: "high" }
  ).then(r => ((r && r.scenarios) || []).map(s => ({ ...s, domain: b.g.domain }))),
  (list, b) => {
    if (!list || !list.length) return []
    const listing = list.map((s, i) => `#${i} [${s.section}] Q: ${s.prompt}\n   model: ${s.gold_answer}\n   short: ${s.short_answer}`).join("\n\n")
    return agent(
      `Strict reviewer for keyword-graded Section II items. Keep=true only if ALL hold: (a) the question is self-contained + answerable from parliamentary knowledge (no unseen context, no section-number recall), asks ONE clear thing, and is NOT a narrow "before debate"-style sub-question; (b) the model ruling names only the decisive facts in standard RONR terms (<=15 key terms), and is correct; (c) EVERY key term in short_answer appears in gold_answer and covers it, so typing short_answer alone clearly deserves full marks. Else keep=false + one-line reason.\n\n${listing}\n\nJSON per schema (index matches #).`,
      { label: `verify:d${b.g.domain}-s${b.sec}`, phase: "Verify", schema: VERDICT_SCHEMA, effort: "high" }
    ).then(v => {
      const keep = new Set(((v && v.results) || []).filter(r => r.keep).map(r => r.index))
      return list.filter((_, i) => keep.has(i))
    })
  }
)

const all = authored.flat().filter(Boolean)
const byDomain = {}
for (const s of all) byDomain[s.domain] = (byDomain[s.domain] || 0) + 1
log(`Authored ${all.length} Section II scenarios (pre local 5/5 gate): ${JSON.stringify(byDomain)}`)
return { count: all.length, byDomain, scenarios: all }
