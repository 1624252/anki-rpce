# RPCE BrainLift

## Owners

- Jiaying Song

---

## Purpose

### Purpose

The purpose of this BrainLift is to build a research-grounded foundation for **how to design a study tool for the NAP Registered Parliamentarian Credentialing Exam (RPCE)** — grounding each product and AI-feature decision in evidence about _how parliamentary skills are actually learned, why the skill and the credential matter, who the market is, and where today's prep falls short_ — so the tool is driven by evidence rather than flashcard intuition. The RPCE is unusual in structure: it is administered in a single day (within quarterly 7-day windows) and has two independently scored sections — **Section I**, **100 multiple-choice questions** in **3 hours**, auto-scored by the exam platform, and **Section II**, a written **performance** exam of scenarios scored by trained examiners in **3 hours**. A candidate must score **80% on _each_ section independently**, so "passing" means demonstrating that you can _apply_ and _cite_ rules under both formats, under time pressure, not just recall them.

### In Scope

- **How parliamentary skills are learned:** the simulation-vs-flashcards question, retrieval/spacing for durable facts, and scenario+debrief for applied performance — at the graduate/college/adult-professional level.
- **Why parliamentary procedure matters and works:** its applications across governance and the _mechanism_ (procedural justice / meeting science) by which structured procedure produces accepted decisions.
- **What the Registered Parliamentarian (RP) credential provides and who the market is:** the value of the credential and both the candidate market (who sits the exam) and the demand market (who hires parliamentarians).
- **The competitive landscape:** the format/style of existing prep, what each competitor does well and poorly, and where the gap is.

### Out of Scope

- **Teaching parliamentary procedure itself:** this BrainLift covers _how people learn it and how the exam/market works_, not a substitute for RONR.
- **Re-deriving the full exam-structure fact base:** the exam's section/scoring/Performance-Expectation details are treated as background; this document focuses on the _design-relevant_ research.
- **Engineering/product implementation:** architecture, schemas, and APIs are out of scope here.
- **High-school / FFA contexts:** evidence here is deliberately graduate/college/adult-professional only.

---

## DOK 4: Spiky Points of View (SPOVs)

- **Spiky POV 1:** Consistency is a trap — practicing one question format breeds a false sense of mastery, so the tool should _vary the format_ even when the underlying content is the same.
  - **Elaboration:** Drilling the same style of question every day _feels_ like progress, but it is exactly how recall-heavy practice lures a learner into a false sense of temporary mastery (Insight 1): you get good at the format, not at the knowledge. True mastery is the ability to apply the same knowledge across _different_ contexts — which is precisely what the RPCE demands, since Section I and Section II test the same Performance Expectations in two entirely different formats, and a real meeting never presents a rule in the tidy shape a flashcard did. Consistent, same-wording practice trains pattern-matching to the question rather than the concept, so it collapses the moment the context shifts. The design implication is direct: for a given piece of content, the tool should deliberately rotate the format — cloze recall, applied multiple-choice, free-text scenario, advising prompt — so the learner proves they can transfer the knowledge, not just recognize a familiar template. This also dovetails with fading scaffolding as mastery grows (Insight 3): the _same_ fact should resurface in progressively harder formats over time rather than in one comfortable, repeated shape.
- **Spiky POV 2:** Even the single most effective learning method is insufficient on its own — the tool must combine methods, because each one builds a different skill.
  - **Elaboration:** "Simulation vs. flashcards" is a false binary (Insight 1): spaced-repetition flashcards build durable factual recall and fight the skill decay that one-shot practice cannot prevent (BMC Medical Education 2019; Brazilian Journal of Health Review 2024), while simulation builds the applied competence and confidence that recall drills never produce (Chernikova et al. 2020) — and that competence only sticks when paired with debriefing (JPSE 2018). A recall-only tool and a simulation-only tool are each half a solution, and worse, a recall-heavy tool can lure a candidate into a false sense of temporary mastery. Because the RPCE itself is split into a recall section and a performance section, the design conclusion is forced: a hybrid engine whose two modes mirror the two sections — spaced retrieval for Section I, scenario + debrief simulation for Section II — sequenced to lean on worked examples early and reflection as mastery grows (Insight 3). Optimizing any one method to perfection still loses, because it leaves an entire tested skill untrained.
- **Spiky POV 3:** The AI's job in this tool is to be an _examiner_, not a _tutor_.
  - **Elaboration:** Every RPCE candidate has already cleared the NAP membership (RONRIB) exam, so they enter with high prior knowledge — and the learning science says high-prior-knowledge learners gain from _reflection_, not from being fed more worked examples (Insight 3). At the same time, the entire exam is grounded in a closed, definitive corpus (RONR 12th edition), which means factual answers are fixed and citable; an AI tutor inventing or fumbling facts is both low-value and actively harmful, exactly the trust failure visible in competitors that ship incorrect answers (NAPMobile). The genuinely hard, under-taught skill is _application_ — reading a scenario, choosing and justifying the correct ruling — and the active ingredient that makes simulation work is the debrief/feedback, not the spectacle (Insight 4). Putting these together: the AI should grade and debrief the candidate's performance answers against the seven Performance Expectations like an examiner, demanding RONR citations and probing the reasoning, rather than lecturing facts the candidate is presumed to know. This is also the one lever the incumbent's delayed, instructor-mediated feedback structurally cannot pull at scale.

---

## Experts

- **National Association of Parliamentarians (NAP)**
  - **Who:** The body that owns the RP/PRP credentials and administers the RPCE; also runs NAP University and the official prep.
  - **Focus:** Defines the Registered Parliamentarian Performance Expectations, the exam format, and the credential pathway; certifies and lists professional parliamentarians.
  - **Why Follow:** It is simultaneously the authority on exam content and the incumbent competitor — the bar any study tool must align to and beat.
  - **Where:** [National Association of Parliamentarians](https://www.parliamentarians.org/) · [RP credentialing](https://www.parliamentarians.org/credentialing/prp)
- **Olga Chernikova**
  - **Who:** Lead author of the major meta-analysis of simulation-based learning in higher education (LMU Munich).
  - **Focus:** When and why simulation teaches complex applied skills; how scaffolding should change with a learner's prior knowledge.
  - **Why Follow:** Grounds the case that Section II (applied performance) is best built through simulation, and that the RPCE's high-prior-knowledge candidate needs reflection over worked examples.
  - **Where:** [Google Scholar](https://scholar.google.com/citations?user=C_WWnIAAAAAJ&hl=en)
- **Frank Fischer**
  - **Who:** Senior author of the simulation-based-learning meta-analysis; chair of education and educational psychology at LMU Munich and a leading learning-sciences researcher.
  - **Focus:** Scaffolding frameworks for simulation-based learning — specifically the prior-knowledge → scaffolding-type mapping (worked examples for novices, reflection for the more expert).
  - **Why Follow:** His scaffolding framework is the direct basis for _sequencing_ the tool's support — worked examples early, reflection as mastery grows.
  - **Where:** [Google Scholar](https://scholar.google.com/citations?user=YL1eEDEAAAAJ&hl=en) · [LMU Munich profile](https://www.psy.lmu.de/ffp_en/persons/chair-holder/fischer-frank/index.html)
- **Tina Seidel**
  - **Who:** Co-author of the meta-analysis; educational psychologist known for research on teaching quality and learning processes.
  - **Focus:** How instructional design and reflection phases shape learning from authentic and simulated practice.
  - **Why Follow:** Reinforces that structured reflection/debrief is what makes simulation pay off — the active ingredient behind the Section II design.
  - **Where:** [Google Scholar](https://scholar.google.com/citations?user=e-kd_M0AAAAJ&hl=en) · [TUM profile](https://www.professoren.tum.de/en/seidel-tina)
- **Tom R. Tyler**
  - **Who:** Social psychologist; foremost researcher on procedural justice and legitimacy.
  - **Focus:** Why _fair procedures_ drive acceptance of decisions and institutional legitimacy, independent of whether people like the outcome.
  - **Why Follow:** Supplies the "why parliamentary procedure works" mechanism — procedure manufactures legitimacy — which reframes the RP's competence as applied judgment.
  - **Where:** [Google Scholar](https://scholar.google.com/citations?user=Z_94FToAAAAJ&hl=en) · [Yale Law School](https://law.yale.edu/tom-r-tyler)
- **Steven G. Rogelberg (with Leach, Warr, Burnfield, Cohen)**
  - **Who:** Organizational scientist; leads the modern "science of meetings."
  - **Focus:** Which meeting-design features (agendas, punctuality, facilitation, records) measurably raise meeting quality.
  - **Why Follow:** Independent, outside-the-parliamentary-world evidence that the very things RONR codifies are what makes meetings work.
  - **Where:** [stevenrogelberg.com](https://www.stevenrogelberg.com/) · [UNC Charlotte](https://pages.charlotte.edu/steven-rogelberg/)
- **Jeffrey L. Bernstein & Deborah S. Meizlish**
  - **Who:** Political-science-education researchers.
  - **Focus:** Legislative/parliamentary simulations and their effect on student knowledge and attitudes.
  - **Why Follow:** College-level, explicitly procedural evidence that simulating an assembly beats passive instruction for learning how it runs.
  - **Where:** [Jeffrey L. Bernstein — published works (OpenAlex)](https://www.rankless.org/authors/jeffrey-l-bernstein)

---

## DOK 3: Insights

### How parliamentary skills are learned

- **Insight 1 (the false binary):** "Simulation vs. flashcards" is the wrong question — the evidence says you need _both_, because they do different jobs. Spaced-repetition flashcards build durable factual recall while simulation builds applied competence and confidence (Brazilian Journal of Health Review 2024), and simulation skill _decays_ without spaced re-exposure (BMC Medical Education 2019). A recall-only tool and a simulation-only tool are each half a solution.
- **Insight 2 (map methods to the exam's two halves):** The RPCE's structure hands you the design: Section I (machine-scored recall of RONR facts/citations) maps to **spaced retrieval/flashcards**, and Section II (human-scored written performance — advising, opinion/script writing, presiding) maps to **scenario + debrief simulation**. The tool should be a hybrid whose two modes mirror the two sections, not one engine stretched across both.
- **Insight 3 (sequence by expertise):** Scaffolding should change as the learner improves — worked examples for low-prior-knowledge learners, reflection for high-prior-knowledge learners (Chernikova et al. 2020). Because the RPCE candidate has already cleared the RONRIB membership exam, they enter as _high prior knowledge_, so the tool should lean toward reflection/scenario practice rather than feeding more examples — and can transition from worked examples to reflection as mastery grows.
- **Insight 4 (feedback is the active ingredient):** What makes simulation work is the _debrief_, not the spectacle — simulation **with** debriefing produced the best long-term retention; simulation alone was second; non-simulation worst (JPSE 2018). Current NAP prep's feedback is delayed and instructor-mediated; immediate, per-item feedback is the specific lever a tool can pull that the incumbent cannot.
- **Insight 5 (recall fights decay, and matches the credential's own cadence):** Spaced retrieval exists precisely to counter the skill decay that one-shot simulation can't prevent (BMC 2019) — and that maps onto the RP credential's own 2-year continuing-education renewal cycle, extending the tool's usefulness past exam day into maintenance.

### Why parliamentary procedure matters and works

- **Insight 6 (procedure manufactures legitimacy):** Parliamentary procedure works because _fair process produces acceptance_ — people support outcomes they voted against when the procedure gave them voice and neutrality (Tyler, "Governing amid Diversity"). This reframes "knowing the rules" as applied judgment in service of legitimacy, which is why the exam tests application and the tool should too.
- **Insight 7 (procedure = codified meeting science):** The features RONR standardizes — agendas, orders of business, recorded motions/minutes, time discipline, a neutral facilitator — are exactly the design characteristics that independent meeting-science research finds raise meeting quality (Rogelberg/Leach/Cohen). Parliamentary procedure is a mature implementation of what works, and a trained parliamentarian (the RP) is its steward — the real-world value behind the credential (UNC School of Government).

### What the credential provides and who the market is

- **Insight 8 (the credential is a scarcity/trust signal):** In a field with _no required license_, the NAP/AIP credential is what separates "casual dabblers" from people organizations will pay (LegalClarity), and the credentialed pool is tiny — only several hundred CPP/PRP holders among thousands of members (NAP / Slaughter). Passing the RPCE buys the right to market yourself, directory discovery, and a scarcity premium.
- **Insight 9 (target working adults in governance settings):** The demand market is broad and governance-centric — nonprofits, corporations, government, HOAs, trade/professional/religious associations (NAP "Find a PRP") — and the paid work is heavily _applied_ (presiding, advising live, drafting). The ideal user is therefore a working adult already embedded in one of these settings, and the tool must build performance, not just recall.

### The competitive landscape

- **Insight 10 (the unoccupied intersection):** No competitor combines all four of (a) RP-blueprint + RONR-citation alignment, (b) spaced retrieval for Section I, (c) simulation + immediate debrief for Section II, and (d) an honest, calibrated readiness signal. NAP has the content but a lecture/cohort format with no adaptivity or readiness score; NAPMobile is a plain quiz bank (with some unverified answers); the commercial board-training courses have polished UX but only basic motions — though RobertsRules.org's AI-opponent simulation is the single feature worth emulating. That four-way intersection is the wedge.

---

## DOK 2: Knowledge Tree

The Knowledge Tree below contains DOK 1 facts and DOK 2 summaries only. Scope: graduate / college / adult-professional sources only.

- **The RPCE Exam: Structure And Administration**
  - **Format, Sections, Scoring, And Content**
    - **Source: NAP, "Registered Parliamentarian" credentialing page; NAP Commission on Credentialing, "Criteria for Credentialing" (2025).**
      - **DOK 1 - Facts:**
        - The RPCE is administered on a single day during quarterly, week-long (7-day) examination windows; the candidate selects a testing day within the window.
        - It has two sections. **Section I** is 100 multiple-choice questions derived from the Registered Parliamentarian Performance Expectations, auto-scored by the exam platform.
        - **Section II** is a written performance exam of scenarios derived from the same Performance Expectations, scored by trained examiners.
        - Candidates must achieve **80% on each section independently** to earn the credential; results are reported within 60 days of the window's close.
        - The content is organized into **seven Performance Expectation domains**: (1) Motions in General and Main Motions; (2) Subsidiary and Privileged Motions; (3) Incidental Motions and Motions that Bring a Question Again Before the Assembly; (4) Organization and Conduct of Meetings; (5) Voting, Nominations, and Elections; (6) Being and Serving as a Professional Parliamentarian and Teaching Parliamentary Procedure; (7) Boards and Committees, and Writing and Interpreting Bylaws.
        - The exam is proctored online via ExamSoft.
      - **DOK 2 - Summary & Analysis:**
        - The two sections test two different abilities (recall vs. applied written performance) and are passed independently, so the exam structurally rewards a hybrid prep rather than recall alone. The publicly published seven-domain blueprint pins testable content to specific competencies, which is what makes coverage measurable and an honest coverage/readiness map possible.
      - **Link to source:** [NAP — Registered Parliamentarian](https://www.parliamentarians.org/credentialing/rp) · [Criteria for Credentialing (2025)](https://www.parliamentarians.org/wp-content/uploads/2025/10/2025-9-28-Criteria-for-Credentialing-UPDATED-v1.pdf)
  - **Timing And Logistics**
    - **Source: NAP, "RPCE Rules" (amended through April 4, 2023).**
      - **DOK 1 - Facts:**
        - Each section must be completed within **three hours** of the exam start time.
        - A total of **seven hours** is allowed to complete both sections, with up to a **one-hour break** between them.
        - Exams not uploaded within **eight hours** of the exam start time will not be scored.
        - Candidates must use Examplify by ExamSoft, which locks down the computer and will not run on Chromebooks, Android, or Linux.
      - **DOK 2 - Summary & Analysis:**
        - Time pressure is a distinct, testable skill: three hours for 100 multiple-choice items plus three hours to _write_ performance answers means pacing and rapid rule-location matter, not just whether the candidate ultimately knows the rule. A prep tool should rehearse timed performance, not only untimed recall.
      - **Link to source:** [RPCE Rules](https://www.parliamentarians.org/credentialing/rp-rules)
- **How Parliamentary Skills Are Learned (Simulation vs. Flashcards)**
  - **Simulation For Complex, Applied Skills**
    - **Source: Chernikova et al. (2020), "Simulation-Based Learning in Higher Education: A Meta-Analysis," _Review of Educational Research, 90_(4).**
      - **DOK 1 - Facts:**
        - Meta-analysis of 145 empirical studies of simulation-based learning in higher education.
        - Large overall positive effect on complex-skill learning: g = 0.85 (95% CI [0.69, 1.02]).
        - High-prior-knowledge learners benefited most from reflection phases; low-prior-knowledge learners from worked examples.
        - Effects robust across domains (medical, teacher, management education).
      - **DOK 2 - Summary & Analysis:**
        - Simulation is among the most effective ways to teach complex applied skills — exactly what RPCE Section II demands. Because the RPCE candidate already passed the RONRIB membership exam (high prior knowledge), reflection/feedback after simulated scenarios should beat being fed more examples, so the performance layer should be scenario+debrief, not more cards.
      - **Link to source:** [https://journals.sagepub.com/doi/10.3102/0034654320933544](https://journals.sagepub.com/doi/10.3102/0034654320933544)
    - **Source: Bernstein & Meizlish (2006), "Simulating a Senate Office: The Impact on Student Knowledge and Attitudes," _Journal of Political Science Education, 2_(2).**
      - **DOK 1 - Facts:**
        - Pre/post comparison across two college "Intro to American Government" sections: one lecture-only (control), one supplemented with an online legislative simulation.
        - Simulation students gained significantly more knowledge of the legislative process and showed decreased cynicism.
        - Authors stress simulations work only when objectives are clear and expectations realistic.
      - **DOK 2 - Summary & Analysis:**
        - College-level evidence that simulating a procedural/legislative process beats passive instruction for procedural knowledge — transferable to learning how a deliberative assembly runs. The "clear objectives" caveat means each scenario must map to a specific RP Performance Expectation, not gamify for its own sake.
      - **Link to source:** [https://www.tandfonline.com/doi/abs/10.1080/15512160600668967](https://www.tandfonline.com/doi/abs/10.1080/15512160600668967)
    - **Source: "Simulating Parliamentary Budget Debates: Role-Play as a Pedagogical Tool …," _IJARPED, 15_(1) (Malaysia).**
      - **DOK 1 - Facts:**
        - University-level role-play of parliamentary budget debates (students act as legislators/ministers/opposition).
        - Reports improved understanding and retention of legislative processes vs. lecture-based learning.
        - Frames parliamentary simulation as experiential learning that builds critical thinking.
      - **DOK 2 - Summary & Analysis:**
        - Reinforces, in an explicitly parliamentary higher-ed context, that procedure is learned by enacting roles — supporting a "perform the motion / preside / advise" practice mode for the applied half of the RPCE.
      - **Link to source:** [https://hrmars.com/IJARPED/article/view/27834/](https://hrmars.com/IJARPED/article/view/27834/)
  - **Feedback / Debrief As The Active Ingredient**
    - **Source: "Assessing Knowledge Retention, With and Without Simulations," _Journal of Political Science Education_ (2018).**
      - **DOK 1 - Facts:**
        - Compared four modes on a delayed (~3-month) quiz: simulation + debriefing; simulation only; discussion + research essay; discussion only.
        - Simulation **with debriefing** produced the best long-term retention; simulation alone nearly as good; non-simulation modes least effective.
        - Used an anonymous extra-credit pop quiz months later as the retention measure.
      - **DOK 2 - Summary & Analysis:**
        - The active ingredient is debriefing/feedback, not the simulation alone. NAP prep gives delayed, instructor-mediated feedback; a tool with immediate per-item feedback targets the exact lever isolated here. The delayed-quiz design also models honest delayed-retention testing over in-session scores.
      - **Link to source:** [https://www.tandfonline.com/doi/full/10.1080/15512169.2017.1405355](https://www.tandfonline.com/doi/full/10.1080/15512169.2017.1405355)
  - **Why You Need Flashcards Too (Decay And Hybrid Design)**
    - **Source: Long-term retention after simulation-based training of procedural skills, _BMC Medical Education_ (2019).**
      - **DOK 1 - Facts:**
        - Adult emergency physicians/residents; technical skill measured on a validated scale at intervals after a single simulation course.
        - Performance high immediately post-training but declined ~15% by 6 months, plateaued, then dropped ~35% and was effectively lost by ~4 years without practice.
        - Authors recommend re-training roughly every 2 years.
      - **DOK 2 - Summary & Analysis:**
        - Simulation alone is not durable — skills decay without spaced re-exposure. The answer to "simulation vs. flashcards" is _both_: spaced retrieval combats decay while simulation builds applied competence. It also mirrors the RP credential's 2-year continuing-education renewal cycle.
      - **Link to source:** [https://doi.org/10.1186/s12909-019-1793-6](https://doi.org/10.1186/s12909-019-1793-6)
    - **Source: Active-learning review incl. spaced-repetition flashcards (Anki) and virtual simulation in medical education, _Brazilian Journal of Health Review_ (2024).**
      - **DOK 1 - Facts:**
        - Reviews evidence-based methods: problem-based learning, spaced repetition, virtual simulation, gamification.
        - Spaced-repetition flashcards (e.g., Anki) effective for knowledge retention; virtual simulations improved confidence and applied skill but did not always beat conventional methods on objective measures.
      - **DOK 2 - Summary & Analysis:**
        - The two methods do different jobs: flashcards/spacing = durable factual recall; simulation = applied performance and confidence. For the RPCE's two-section design, the implication is a hybrid engine — Anki-style spaced recall for Section I, simulation/scenario practice for Section II.
      - **Link to source:** [https://ojs.brazilianjournals.com.br/ojs/index.php/BJHR/article/download/77666/53900/192652](https://ojs.brazilianjournals.com.br/ojs/index.php/BJHR/article/download/77666/53900/192652)
- **Why Parliamentary Procedure Matters And Works**
  - **Importance And Applications**
    - **Source: UNC School of Government, "A Parliamentary Procedure Primer for Local Governments," Public Management Bulletin No. 28 (2023).**
      - **DOK 1 - Facts:**
        - Parliamentary procedure is a set of rules/customs that let deliberative assemblies (boards, commissions, committees) make decisions and take action.
        - Robert's Rules (first published 1876) is among the oldest and most widely used manuals; its policy is to let a body do business efficiently _despite_ internal tension, giving the minority a full chance to be heard before the majority decides.
        - Procedural rules should promote orderly business, fairness, decorum, and a common decision framework — and should be simplified if they impair business.
      - **DOK 2 - Summary & Analysis:**
        - Authoritative confirmation that parliamentary skill is core governance infrastructure, not a niche hobby — it is how boards at every level transact business, grounding the RP's real-world value. "Simplify if it impairs business" also explains why a tool focused on _applying_ rules (not memorizing 700 pages) matches how the skill is used.
      - **Link to source:** [https://www.sog.unc.edu/sites/default/files/reports/PMB%2028_2023207.pdf](https://www.sog.unc.edu/sites/default/files/reports/PMB%2028_2023207.pdf)
  - **The Mechanism: Why It Works**
    - **Source: Tyler & Mitchell, "Governing amid Diversity: The Effect of Fair Decisionmaking Procedures on the Legitimacy of Government," _Law & Society Review_.**
      - **DOK 1 - Facts:**
        - Two experiments and a survey tested whether judgments about the fairness of lawmaking procedures drive perceived legitimacy of a national institution (Congress), versus self-interested agreement with decisions.
        - Procedural-justice judgments strongly influenced legitimacy evaluations.
        - Demographic factors (ethnicity, gender, education, age, income, ideology) did not change the criteria people use to judge procedural fairness.
        - Conclusion: fair procedures sustain support _despite_ disagreement on the outcome.
      - **DOK 2 - Summary & Analysis:**
        - The core "why it works" finding: parliamentary procedure manufactures legitimacy — people accept an outcome they voted against when the process was fair (voice + neutrality), exactly what motions, debate rights, and majority-rule-with-minority-protection do. RONR's stated policy is a working mechanism for binding, durable decisions, not etiquette.
      - **Link to source:** [https://doi.org/10.2307/3053998](https://doi.org/10.2307/3053998)
    - **Source: Leach, Rogelberg, Warr & Burnfield (2009) / Cohen et al. (2011), "Meeting Design Characteristics and Attendee Perceptions of Staff/Team Meeting Quality," _Group Dynamics / J. Applied._**
      - **DOK 1 - Facts:**
        - Survey of 367 working adults within 48 hours of their most recent staff/team meeting tested 18 meeting-design characteristics (temporal, physical, procedural, attendee).
        - Nine characteristics significantly predicted perceived meeting quality, including agenda use, punctuality, facilitation, and use of written agreements/records.
        - Replicated/extended earlier findings (Leach et al. 2009) on agenda use and punctuality.
      - **DOK 2 - Summary & Analysis:**
        - Independent organizational-psychology evidence that the procedural design features parliamentary procedure codifies (agendas, orders of business, recorded motions/minutes, time discipline, neutral facilitator) measurably raise meeting quality. Parliamentary procedure is a standardized implementation of what meeting science independently finds works.
      - **Link to source:** [https://doi.org/10.1037/a0021549](https://doi.org/10.1037/a0021549)
- **The RP Credential: Value And Market**
  - **What The Certification Provides**
    - **Source: NAP, "Find a Professional Registered Parliamentarian"; Slaughter, "Finding the Right Parliamentarian."**
      - **DOK 1 - Facts:**
        - NAP certifies that a PRP has met the knowledge/professional-development requirements, and lists them in a referral directory by specialty/location (general procedure, bylaws, presiding, opinion writing, board training, conventions, elections, teaching, minutes).
        - National organizations "almost always" use a Certified Professional Parliamentarian (AIP) or PRP (NAP); a basic certification may suffice for small local groups.
        - NAP and AIP have thousands of members combined, but only several hundred hold a CPP or PRP, and fewer than ~50 hold both.
      - **DOK 2 - Summary & Analysis:**
        - The credential provides three concrete things: the right to market yourself as a credentialed parliamentarian, referral/discovery via NAP's directory, and a scarcity premium — passing the RPCE moves a candidate into a small, in-demand tier. This is the tangible value beyond wages.
      - **Link to source:** [https://www.parliamentarians.org/find-a-professional-registered-parliamentarian/](https://www.parliamentarians.org/find-a-professional-registered-parliamentarian/)
    - **Source: NAP, "Professional Registered Parliamentarian" credential page (PRP exam format) — context on the credential ladder.**
      - **DOK 1 - Facts:**
        - The PRP is NAP's highest credential; its exam is a two-day simulation in which candidates write a meeting script, develop a workshop, draft an opinion, and rotate as presiding officer and parliamentarian through live business sessions.
        - The RP credential is the prerequisite tier below PRP.
      - **DOK 2 - Summary & Analysis:**
        - The profession's own top exam is a simulation, confirming applied performance — not recall — is the terminal competency the field certifies. The RPCE is the on-ramp; a tool that builds simulation-ready performance early serves RPCE candidates and positions them for the PRP later (extends the user lifecycle).
      - **Link to source:** [https://www.parliamentarians.org/credentialing/prp](https://www.parliamentarians.org/credentialing/prp)
  - **Who The Market Is**
    - **Source: NAP, "Find a Professional Registered Parliamentarian" (client-sector list).**
      - **DOK 1 - Facts:**
        - Organizations seeking parliamentarians span nonprofits, corporations, government (federal, state/provincial, local), home/condominium owners associations, trade associations, professional associations, PanHellenic organizations, and church/religious organizations.
        - Engagement types include bylaws/governing documents, presiding, opinion writing, board training, conventions/meetings, elections, teaching, and minutes.
      - **DOK 2 - Summary & Analysis:**
        - The demand market is broad and governance-centric. The candidate who benefits most already works near these settings (association staff, board officers, HOA/union/church leaders, attorneys), so the tool's ideal user is a working adult embedded in one of these organizations, not a general test-prep student.
      - **Link to source:** [https://www.parliamentarians.org/find-a-professional-registered-parliamentarian/](https://www.parliamentarians.org/find-a-professional-registered-parliamentarian/)
    - **Source: LegalClarity, "What Is a Parliamentarian and What Do They Do?"**
      - **DOK 1 - Facts:**
        - No government license is required to call oneself a parliamentarian; the NAP/AIP credentialing system separates "casual dabblers" from people organizations will pay.
        - Parliamentarians work for professional associations, nonprofits, corporate boards, HOAs, labor unions, and large conventions.
        - Fees scale with complexity (a 2-hour board meeting vs. a multi-day convention with contested elections and bylaw amendments); pre-meeting work (bylaw review, agenda prep, officer training) is commonly scoped separately.
      - **DOK 2 - Summary & Analysis:**
        - Because no license is mandated, the credential is the differentiator — reinforcing its value as a trust signal. The fee structure shows the paid work is heavily applied (presiding, advising live, drafting), again pointing the tool toward performance practice, not just recall.
      - **Link to source:** [https://legalclarity.org/what-is-a-parliamentarian-and-what-do-they-do/](https://legalclarity.org/what-is-a-parliamentarian-and-what-do-they-do/)
- **The Competitive Landscape (Existing Prep)**
  - **The Incumbent: Official NAP Prep**
    - **Source: NAP University — RP Prep Course, ParliPrep 2026, Parliamentary Fundamentals 102.**
      - **DOK 1 - Facts:**
        - RP Prep Course: self-paced lessons built on the RP Performance Expectations; free to NAP members; some lessons reference an older exam version.
        - ParliPrep 2026: 17 weekly live Zoom sessions (1-hr lecture + up to 30-min demo/Q&A) by expert parliamentarians; paid; earns 1 CEU/session.
        - Parliamentary Fundamentals 102: ~$199 self-paced intro course.
      - **DOK 2 - Summary & Analysis:**
        - _Does well:_ directly blueprint-aligned (the legitimate authority on content), expert instructors, official CEUs, low/zero cost for the core course, social accountability via live cohorts.
        - _Does poorly:_ lecture/static-video and scheduled-cohort format; no adaptive spaced repetition; delayed, instructor-mediated feedback (not per-item); some content lags current exam rules; no calibrated readiness estimate.
      - **Link to source:** [https://napuniversity.com/courses/51179](https://napuniversity.com/courses/51179) · [https://napuniversity.com/courses/119775](https://napuniversity.com/courses/119775)
    - **Source: NAPMobile (official NAP app).**
      - **DOK 1 - Facts:**
        - Official NAP app offering quiz questions and a vote/ballot calculator; explicitly marketed as practice for the membership exam and the RP exam.
        - Appears to contain a few incorrect answers (a direct contradiction observed in use).
      - **DOK 2 - Summary & Analysis:**
        - _Does well:_ official, mobile, exam-branded, includes a practical tool (ballot calc).
        - _Does poorly:_ a simple quiz bank — no spacing/scheduling, no Section II performance practice, no readiness modeling or coverage map, and no verification of answers.
      - **Link to source:** [https://apps.apple.com/us/app/napmobile/id1352218439](https://apps.apple.com/us/app/napmobile/id1352218439)
  - **Commercial Robert's Rules Training (Adjacent: Board Skills, Not Exam Prep)**
    - **Source: Robert's Rules Made Simple; AMC Governance Academy ("Meeting Rules Made Easy"); RobertsRules.org.**
      - **DOK 1 - Facts:**
        - Robert's Rules Made Simple (Susan Leahy): short entertaining video course on the "7 fundamental motions," used by 10,000+ boards; sells instructor certification.
        - AMC "Meeting Rules Made Easy": self-paced course (~7 lessons + worksheets, instructor Q&A), completion certificate; 35 yrs training boards.
        - RobertsRules.org: free 6-lesson interactive tutorial, a meeting app, and "Parliamentary Games" (Model UN/Congress simulations with AI opponents).
      - **DOK 2 - Summary & Analysis:**
        - _Does well:_ approachable UX, video/interactive, simplification of an 800-page book, and (RobertsRules.org) a genuine AI-opponent simulation — the closest existing analog to a Section II performance mode.
        - _Does poorly:_ target board members who want to run meetings, not RPCE candidates; cover only basic motions, far below RPCE depth (no opinion/script writing, no full RONR citation rigor); no exam blueprint, no readiness scoring. "Parliamentary Games" is not openly accessible (appears invite-only with applications closed — likely still in testing).
      - **Link to source:** [https://robertsrulesmadesimple.com/](https://robertsrulesmadesimple.com/) · [https://www.amcnposolutions.com/roberts-rules-made-easy/](https://www.amcnposolutions.com/roberts-rules-made-easy/) · [https://robertsrules.org/games](https://robertsrules.org/games)
