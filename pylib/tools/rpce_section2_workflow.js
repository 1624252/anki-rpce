export const meta = {
  name: "rpce-author-section2",
  description: "Author Section II performance scenarios (sample-style), 1+ per RONR section",
  phases: [
    { title: "Author", detail: "batches write scenario prompts + model rulings grounded in RONR sections" },
    { title: "Verify", detail: "each scenario checked: solvable, gradeable, faithful to RONR" },
  ],
}

const CORPUS = "C:\\Users\\18037\\Desktop\\Work\\rpce\\anki\\data\\roberts_rules_of_order_12th_edition.md"
const SAMPLE = "C:\\Users\\18037\\Desktop\\Work\\rpce\\anki\\data\\RPCE-Sample-Questions-v4-100625.md"

// RONR 12th ed. sections grouped by the 7 RPCE domains (one+ scenario per section).
const GROUPS = [
  { domain: 1, name: "Main Motions & handling motions", secs: "3,4,6,10" },
  { domain: 2, name: "Subsidiary & Privileged Motions", secs: "11,12,13,14,15,16,17,18,19,20,21,22" },
  { domain: 3, name: "Incidental & Bring-Again Motions", secs: "23,24,25,26,27,28,29,30,31,32,33,34,35,36,37" },
  { domain: 4, name: "Organization & Conduct of Meetings", secs: "1,2,7,8,9,38,39,40,41,42,43,47,48,62,63" },
  { domain: 5, name: "Voting, Nominations, Elections", secs: "44,45,46" },
  { domain: 7, name: "Boards, Committees, Bylaws", secs: "49,50,51,52,53,54,55,56,57" },
]

const SCEN_SCHEMA = {
  type: "object", additionalProperties: false, required: ["scenarios"],
  properties: { scenarios: { type: "array", items: {
    type: "object", additionalProperties: false,
    required: ["domain", "section", "prompt", "gold_answer", "quote"],
    properties: {
      domain: { type: "integer" },
      section: { type: "string", description: "RONR section:paragraph, e.g. 10:5" },
      prompt: { type: "string", description: "self-contained scenario asking what the parliamentarian should do / the ruling" },
      gold_answer: { type: "string", description: "model ruling: the correct handling, naming the key facts (second? debatable? vote threshold? chair action)" },
      quote: { type: "string", description: "short verbatim RONR sentence from that section supporting the ruling" },
    } } } },
}
const VERDICT_SCHEMA = {
  type: "object", additionalProperties: false, required: ["results"],
  properties: { results: { type: "array", items: {
    type: "object", additionalProperties: false, required: ["index", "keep", "reason"],
    properties: { index: { type: "integer" }, keep: { type: "boolean" }, reason: { type: "string" } } } } },
}

const COMMON = `Author SECTION II performance scenarios for the Registered Parliamentarian exam (RONR 12th ed.).
Read the sample style first: ${SAMPLE} — a Section II item is a short, concrete, self-contained SCENARIO (named body, realistic situation) where the candidate must state the correct ruling / what the chair or parliamentarian should do. Ground each in the RONR corpus: ${CORPUS} (read the relevant section).
Each scenario needs: a "prompt" (the scenario + the question), a "gold_answer" (the model ruling that NAMES the decisive facts — needs a second or not, debatable or not, the vote threshold, the chair's action — so it can be graded by keyword rubric), a "section" citation, and a short verbatim "quote" from that section. Do NOT put the section number in the prompt (candidates don't recall section numbers). Keep it answerable from parliamentary knowledge.`

phase("Author")
const batches = []
for (const g of GROUPS) {
  const secs = g.secs.split(",")
  for (let i = 0; i < secs.length; i += 8) batches.push({ g, secs: secs.slice(i, i + 8), bi: i / 8 })
}

const authored = await pipeline(
  batches,
  (b) => agent(
    `${COMMON}\n\nAUTHOR one Section II scenario for EACH of these RONR sections in domain ${b.g.domain} (${b.g.name}): §${b.secs.join(", §")}. Return JSON per schema (domain=${b.g.domain}). Pick a real paragraph within each section for the citation.`,
    { label: `author:d${b.g.domain}-${b.bi}`, phase: "Author", schema: SCEN_SCHEMA, effort: "high" }
  ).then(r => ((r && r.scenarios) || []).map(s => ({ ...s, domain: b.g.domain }))),
  (list, b) => {
    if (!list || !list.length) return []
    const listing = list.map((s, i) => `#${i} [${s.section}] ${s.prompt}\n   model: ${s.gold_answer}`).join("\n\n")
    return agent(
      `Strict reviewer. Keep=true only if the scenario is: self-contained + solvable from parliamentary knowledge (no unseen context, no section-number recall), the model ruling is correct and names the decisive facts (second/debatable/threshold/chair action) so a keyword rubric can grade it, and it reads like a real Section II item. Else keep=false with a one-line reason.\n\n${listing}\n\nJSON per schema (index matches #).`,
      { label: `verify:d${b.g.domain}-${b.bi}`, phase: "Verify", schema: VERDICT_SCHEMA, effort: "high" }
    ).then(v => {
      const keep = new Set(((v && v.results) || []).filter(r => r.keep).map(r => r.index))
      return list.filter((_, i) => keep.has(i))
    })
  }
)

const all = authored.flat().filter(Boolean)
const byDomain = {}
for (const s of all) byDomain[s.domain] = (byDomain[s.domain] || 0) + 1
log(`Validated ${all.length} Section II scenarios: ${JSON.stringify(byDomain)}`)
return { count: all.length, byDomain, scenarios: all }
