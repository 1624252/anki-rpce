export const meta = {
  name: "rpce-author-cloze",
  description: "Author ~300 more hint-free RPCE cloze cards to balance type counts",
  phases: [
    { title: "Plan", detail: "one agent per domain lists distinct fact-recall targets" },
    { title: "Author", detail: "batches write hint-free cloze cards from real RONR sentences" },
    { title: "Verify", detail: "each cloze checked: solvable, no hint, no section-recall" },
  ],
}

const CORPUS = "C:\\Users\\18037\\Desktop\\Work\\rpce\\anki\\data\\roberts_rules_of_order_12th_edition.md"
const RULES = "C:\\Users\\18037\\Desktop\\Work\\rpce\\anki\\docs\\rpce\\QUESTION_RULES.md"

const DOMAINS = [
  { d: 1, name: "Motions in General and Main Motions" },
  { d: 2, name: "Subsidiary and Privileged Motions" },
  { d: 3, name: "Incidental Motions and Bring-Again Motions" },
  { d: 4, name: "Organization and Conduct of Meetings" },
  { d: 5, name: "Voting, Nominations, and Elections" },
  { d: 6, name: "The Professional Parliamentarian and Teaching" },
  { d: 7, name: "Boards, Committees, and Bylaws" },
]
const PER_DOMAIN = 45     // ~315 cloze total
const BATCH = 15

const PLAN_SCHEMA = {
  type: "object", additionalProperties: false, required: ["facts"],
  properties: { facts: { type: "array", items: {
    type: "object", additionalProperties: false, required: ["fact", "cite"],
    properties: { fact: { type: "string" }, cite: { type: "string" } } } } },
}
const CLOZE_SCHEMA = {
  type: "object", additionalProperties: false, required: ["questions"],
  properties: { questions: { type: "array", items: {
    type: "object", additionalProperties: false,
    required: ["domain", "concept", "text", "answer", "cite", "quote", "plainQ", "plainA"],
    properties: {
      domain: { type: "integer" }, concept: { type: "string" },
      text: { type: "string", description: "sentence with a [[0]] blank (and [[1]]… if needed)" },
      answer: { type: "string", description: "the blanked term(s), comma-separated if multiple" },
      cite: { type: "string" }, quote: { type: "string" },
      plainQ: { type: "string" }, plainA: { type: "string" },
    } } } },
}
const VERDICT_SCHEMA = {
  type: "object", additionalProperties: false, required: ["results"],
  properties: { results: { type: "array", items: {
    type: "object", additionalProperties: false, required: ["index", "keep", "reason"],
    properties: { index: { type: "integer" }, keep: { type: "boolean" }, reason: { type: "string" } } } } },
}

const COMMON = `Author fill-in-the-blank (cloze) study cards for the Registered Parliamentarian exam over RONR 12th ed.
First Read the rules (obey all): ${RULES}. Ground every card in the corpus: ${CORPUS} (large — read only the relevant parts).
HARD RULES: (R1) NO hint of any kind — the blank shows only "?"; the sentence itself must make the answer inferable to someone who knows RONR. (R2) never require recalling which section a rule is from; the section citation is metadata only, never in the blanked sentence. (R3) the card must be answerable from the sentence + general RONR knowledge. Blank a KEY term (a name, threshold, or defining word), not a trivial function word, and never blank something the sentence itself spells out elsewhere. Keep the sentence a real/faithful RONR statement.`

phase("Plan")
const plans = await parallel(DOMAINS.map(dom => () =>
  agent(`${COMMON}\n\nPLAN domain ${dom.d} — "${dom.name}". List EXACTLY ${PER_DOMAIN} distinct fact-recall targets (a crisp RONR fact good for a single-blank cloze), each with its section:paragraph citation confirmed in the corpus. Spread widely across the domain. Return JSON per schema.`,
    { label: `plan:d${dom.d}`, phase: "Plan", schema: PLAN_SCHEMA, effort: "high" }
  ).then(r => ({ dom, facts: (r && r.facts) || [] }))
))

const batches = []
for (const p of plans.filter(Boolean)) {
  for (let i = 0; i < p.facts.length; i += BATCH) {
    batches.push({ dom: p.dom, slice: p.facts.slice(i, i + BATCH), bi: Math.floor(i / BATCH) })
  }
}
log(`Planned ${batches.reduce((n, b) => n + b.slice.length, 0)} cloze facts in ${batches.length} batches`)

const authored = await pipeline(
  batches,
  (b) => agent(`${COMMON}\n\nAUTHOR domain ${b.dom.d}. Write ONE hint-free cloze card for EACH fact below. Put the answer term in [[0]] within a faithful RONR sentence; fill "answer" (the blanked term), "cite", "quote" (the real sentence), "plainQ" (sentence with the blank as "_____"), "plainA" (the answer). Facts:\n${b.slice.map((f, i) => `${i + 1}. ${f.fact} (cite ${f.cite})`).join("\n")}\nReturn JSON per schema (domain=${b.dom.d}).`,
    { label: `author:d${b.dom.d}-${b.bi}`, phase: "Author", schema: CLOZE_SCHEMA, effort: "high" }
  ).then(r => ((r && r.questions) || []).map(q => ({ ...q, domain: b.dom.d }))),
  (qs, b) => {
    if (!qs || !qs.length) return []
    const listing = qs.map((q, i) => `#${i}: ${q.text}\n   answer: ${q.answer}`).join("\n\n")
    return agent(`Strict reviewer. For EACH cloze, keep=true only if: (a) solvable from the sentence + RONR knowledge with NO hint shown (R3/R1); (b) it does not require recalling a section number (R2); (c) the blank is a meaningful term the sentence doesn't otherwise reveal; (d) it reads as a real RONR statement. Else keep=false with a one-line reason. Cloze cards:\n\n${listing}\n\nReturn JSON per schema (index matches #).`,
      { label: `verify:d${b.dom.d}-${b.bi}`, phase: "Verify", schema: VERDICT_SCHEMA, effort: "high" }
    ).then(v => {
      const keep = new Set(((v && v.results) || []).filter(r => r.keep).map(r => r.index))
      return qs.filter((_, i) => keep.has(i))
    })
  }
)

const all = authored.flat().filter(Boolean)
const byDomain = {}
for (const q of all) byDomain[q.domain] = (byDomain[q.domain] || 0) + 1
log(`Validated ${all.length} cloze: ${JSON.stringify(byDomain)}`)
return { count: all.length, byDomain, questions: all }
