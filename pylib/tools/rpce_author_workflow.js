export const meta = {
  name: 'rpce-author-questions',
  description: 'Author an exhaustive scenario-style RPCE question bank (plan → author → verify cold)',
  phases: [
    { title: 'Plan', detail: 'one agent per domain maps ~85 testable concepts from the RONR corpus' },
    { title: 'Author', detail: 'batches write self-contained scenario MCQs + cloze following the rules' },
    { title: 'Verify', detail: 'each question is solved cold; unsolvable / rule-breaking ones are dropped' },
  ],
}

// ---- shared context every agent must honor -------------------------------
const CORPUS = 'C:\\Users\\18037\\Desktop\\Work\\rpce\\anki\\data\\roberts_rules_of_order_12th_edition.md'
const SAMPLE = 'C:\\Users\\18037\\Desktop\\Work\\rpce\\anki\\data\\RPCE-Sample-Questions-v4-100625.md'
const RULES = 'C:\\Users\\18037\\Desktop\\Work\\rpce\\anki\\docs\\rpce\\QUESTION_RULES.md'

const DOMAINS = [
  { d: 1, name: 'Motions in General and Main Motions', ronr: 'RONR sections 3-4, 6, 10 (main motions, incidental main motions, making/handling motions, the six steps).' },
  { d: 2, name: 'Subsidiary and Privileged Motions', ronr: 'RONR sections 11-22 (Postpone Indefinitely, Amend, Commit/Refer, Postpone to a Time, Limit/Extend Debate, Previous Question, Lay on the Table; Raise a Question of Privilege, Call for the Orders of the Day, Recess, Adjourn, Fix the Time to Which to Adjourn).' },
  { d: 3, name: 'Incidental Motions and Motions that Bring a Question Again Before the Assembly', ronr: 'RONR sections 23-37 (Point of Order, Appeal, Suspend the Rules, Object to Consideration, Division of a Question, Division of the Assembly, requests; Take from the Table, Rescind/Amend Something Previously Adopted, Discharge a Committee, Reconsider).' },
  { d: 4, name: 'Organization and Conduct of Meetings', ronr: 'RONR sections 1-2, 7-9, 38-43, 47-48, 62-63 (deliberative assemblies, quorum, order of business, agenda, minutes, officers, sessions, debate rules, decorum, disciplinary procedures).' },
  { d: 5, name: 'Voting, Nominations, and Elections', ronr: 'RONR sections 44-46 (voting bases, methods, majority vs two-thirds) and nominations/elections; ballot, roll call, plurality, ties, incomplete elections.' },
  { d: 6, name: 'Being and Serving as a Professional Parliamentarian and Teaching Parliamentary Procedure', ronr: 'The role/ethics of the professional parliamentarian, advising the chair, impartiality, opinions, teaching methods; RONR references to the parliamentarian (section 47:46-52) plus professional-practice knowledge.' },
  { d: 7, name: 'Boards and Committees, and Writing and Interpreting Bylaws', ronr: 'RONR sections 49-56 (boards, committees, small-board rules, committee reports) and 57 (bylaws: content, adoption, amendment, principles of interpretation).' },
]

const PER_DOMAIN = 85          // ~85 concepts/domain -> ~595 questions
const BATCH = 12               // concepts per author agent

const PLAN_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['concepts'],
  properties: { concepts: { type: 'array', items: {
    type: 'object', additionalProperties: false, required: ['concept', 'cite', 'kind', 'idea'],
    properties: {
      concept: { type: 'string', description: 'short concept id, e.g. "amend-germaneness"' },
      cite: { type: 'string', description: 'RONR 12th ed citation as section:paragraph, e.g. "12:19"' },
      kind: { type: 'string', enum: ['mcq', 'cloze'] },
      idea: { type: 'string', description: 'one-line scenario/testing idea' },
    } } } },
}

const AUTHORED_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['questions'],
  properties: { questions: { type: 'array', items: {
    type: 'object', additionalProperties: false,
    required: ['domain', 'concept', 'kind', 'cite', 'quote', 'plainQ', 'plainA'],
    properties: {
      domain: { type: 'integer' },
      concept: { type: 'string' },
      kind: { type: 'string', enum: ['mcq', 'cloze'] },
      // mcq fields
      stem: { type: 'string', description: 'self-contained scenario question (mcq)' },
      options: { type: 'array', items: { type: 'string' }, description: '>=4 full-sentence options (mcq)' },
      answer: { type: 'integer', description: '0-based index of the correct option (mcq)' },
      // cloze fields
      text: { type: 'string', description: 'sentence with [[0]] blanks (cloze)' },
      blanks: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['a', 'h'], properties: { a: { type: 'string' }, h: { type: 'string' } } } },
      // shared
      cite: { type: 'string', description: 'RONR section:paragraph — answer side only' },
      quote: { type: 'string', description: 'short supporting RONR sentence' },
      plainQ: { type: 'string', description: 'no-JS question text' },
      plainA: { type: 'string', description: 'no-JS answer text' },
    } } } },
}

const VERDICT_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['results'],
  properties: { results: { type: 'array', items: {
    type: 'object', additionalProperties: false, required: ['index', 'keep', 'reason'],
    properties: {
      index: { type: 'integer' },
      keep: { type: 'boolean' },
      reason: { type: 'string' },
    } } } },
}

const COMMON = `You are authoring practice questions for the Registered Parliamentarian Credentialing Exam (RPCE), which tests Robert's Rules of Order Newly Revised, 12th ed. (RONR).
MANDATORY: first Read these files:
- Rules (obey ALL of them): ${RULES}
- Sample style to imitate: ${SAMPLE}
- The RONR corpus to ground citations/quotes: ${CORPUS} (large; Read only the relevant paragraph ranges).
Hard rules recap: (R1) hints never reveal spelling/length/first-letter; (R2) never ask "which section" — a section citation appears ONLY on the answer side; (R3) every question must be solvable by a knowledgeable candidate from the info shown, with no unseen context; (R4) MCQs must be concrete, self-contained SCENARIO questions with >=4 full-sentence options and exactly one correct, in the sample style; (R5) no two-option MCQs — binary facts go in cloze; (R6) you are the author.
Citations must be real RONR 12th ed. "section:paragraph" you confirmed in the corpus; the quote must be a short real sentence from that paragraph.`

// ---- Phase Plan: map each domain's concepts -------------------------------
phase('Plan')
const plans = await parallel(DOMAINS.map(dom => () =>
  agent(
    `${COMMON}\n\nPLAN domain ${dom.d} — "${dom.name}". Scope: ${dom.ronr}\nList EXACTLY ${PER_DOMAIN} distinct, non-overlapping testable concepts a candidate must master in this domain. Spread across the whole scope (don't cluster on one motion). For each give: a short concept id, the RONR section:paragraph citation (confirm it exists in the corpus), the kind ("mcq" for anything that can be a scenario — most of them; "cloze" only for a crisp binary/definition fact), and a one-line scenario/testing idea. Prefer "mcq". Return JSON per schema.`,
    { label: `plan:d${dom.d}`, phase: 'Plan', schema: PLAN_SCHEMA, effort: 'high' }
  ).then(r => ({ dom, concepts: (r && r.concepts) || [] }))
))

// Build author batches (chunk each domain's concepts).
const batches = []
for (const p of plans.filter(Boolean)) {
  const cs = p.concepts
  for (let i = 0; i < cs.length; i += BATCH) {
    batches.push({ dom: p.dom, slice: cs.slice(i, i + BATCH), bi: Math.floor(i / BATCH) })
  }
}
log(`Planned ${batches.reduce((n, b) => n + b.slice.length, 0)} concepts across ${batches.length} author batches`)

// ---- Phase Author -> Verify (pipelined per batch) -------------------------
const authored = await pipeline(
  batches,
  // Author
  (b) => agent(
    `${COMMON}\n\nAUTHOR domain ${b.dom.d} — "${b.dom.name}". Write ONE polished question for EACH of the following concepts (kind as given), self-contained and in the sample style. For mcq: a realistic named scenario stem, >=4 full-sentence options, exactly one correct (set "answer"), plausible distractors. For cloze: a real RONR sentence with [[0]] (and [[1]]...) blanks and a category-only hint per blank (never spelling). Always fill "cite" (section:paragraph), "quote" (short real RONR sentence), "plainQ" and "plainA". Concepts:\n${b.slice.map((c, i) => `${i + 1}. [${c.kind}] ${c.concept} (cite ${c.cite}) — ${c.idea}`).join('\n')}\nReturn JSON per schema (domain=${b.dom.d}).`,
    { label: `author:d${b.dom.d}-${b.bi}`, phase: 'Author', schema: AUTHORED_SCHEMA, effort: 'high' }
  ).then(r => ((r && r.questions) || []).map(q => ({ ...q, domain: b.dom.d }))),
  // Verify cold
  (qs, b) => {
    if (!qs || !qs.length) return []
    const listing = qs.map((q, i) => {
      if (q.kind === 'mcq') return `#${i}: [MCQ] ${q.stem}\n${(q.options || []).map((o, k) => `   (${k}) ${o}`).join('\n')}\n   claimed correct index: ${q.answer}`
      return `#${i}: [CLOZE] ${q.text}\n   answers: ${(q.blanks || []).map(x => x.a).join(' | ')} ; hints: ${(q.blanks || []).map(x => x.h).join(' | ')}`
    }).join('\n\n')
    return agent(
      `You are a strict RPCE exam reviewer. For EACH question below, decide keep=true only if ALL hold: (a) solvable by a knowledgeable candidate from ONLY what's shown — no unseen context needed (R3); (b) for MCQ, exactly one option is correct and the claimed correct index is right, with >=4 options and NOT a 2-option question (R4/R5); (c) it does NOT require recalling which RONR section a rule is from (R2); (d) cloze hints reveal no spelling/length/first letter (R1); (e) it reads as a real, sensible parliamentary question. You do NOT have the corpus — judge on parliamentary knowledge and internal consistency; if a citation is obviously implausible or the "correct" answer is wrong, set keep=false. Give a one-line reason each. Questions:\n\n${listing}\n\nReturn JSON per schema (index matches #).`,
      { label: `verify:d${b.dom.d}-${b.bi}`, phase: 'Verify', schema: VERDICT_SCHEMA, effort: 'high' }
    ).then(v => {
      const keep = new Set(((v && v.results) || []).filter(r => r.keep).map(r => r.index))
      return qs.filter((_, i) => keep.has(i))
    })
  }
)

const all = authored.flat().filter(Boolean)
const byDomain = {}
for (const q of all) byDomain[q.domain] = (byDomain[q.domain] || 0) + 1
log(`Validated ${all.length} questions: ${JSON.stringify(byDomain)}`)
return { count: all.length, byDomain, questions: all }
