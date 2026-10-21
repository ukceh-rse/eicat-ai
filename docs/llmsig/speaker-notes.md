# EICAT-AI: speaker notes

Short prompts for each slide of `eicat-ai-talk.qmd`, in slide order. The fuller scripts are in the slide notes.

## 1. Title: EICAT-AI

- OneSTOP: *OneBiosecurity: Systems and Technology for People, Places and Pathways*, a Horizon Europe project (grant 101180559) coordinated by Quentin Groom at Meise Botanic Garden, with 20 partner organisations
- Aim: minimise the introduction, establishment, spread and impact of terrestrial invasive alien species, through new detection methods, prioritisation, data dissemination and policy engagement
- This work is Task 4.4: using LLMs to extract the evidence needed to assess the impacts of invasive alien species
- The question: can a large language model do the reading behind an EICAT assessment?

## 2. EICAT in brief

- EICAT is the IUCN standard for scoring how badly an alien species harms native biota
- Each impact gets one of 12 mechanisms (competition, predation, hybridisation…) and a severity from Minimal Concern to Massive
- A species is scored by its worst documented impact
- The scheme is simple; gathering the evidence is the hard part

## 3. Section: Building EICAT-AI

- Can we hand that reading to a language model?
- First what we built, then how well it does
- Two parts: the extraction pipeline, then the app assessors use

## 4. The pipeline

- PDF → GROBID for clean body text → LLM agent
- EICAT guidance goes straight into the prompt rather than through retrieval
- A typed output schema means the model cannot invent a category; the latest prompt adds seven worked GISD examples
- Runs on AWS Bedrock in five containers: deliberately boring, so it is reproducible

## 5. The app

- Upload papers for a species and run the analysis in one click
- Every impact carries a category, mechanism, confidence and the exact evidence quote
- Video (56 s, Handal 2021, common myna): upload 0:00 → extract 0:21 → check evidence 0:30 → verify 0:37 → correct severity 0:40 → history 0:49
- Meant for triage and drafting; the expert still signs off

## 6. Section: Evaluating against GISD

- Building it is the easy half
- Does it actually agree with the experts?
- Our yardstick is GISD: first its records, then getting the papers; then we compare on detection, labels and severity

## 7. GISD impact records

- GISD is our gold standard: about 1,200 EICAT impact records from 800 references
- Each record means someone read a paper and judged mechanism and severity
- 71% terrestrial; competition and predation make up 60%; Data Deficient is the largest category at 37%
- Major and Massive are only 5% of records, which matters for the results later
- To compare against GISD, we first need the papers its assessors read

## 8. Retrieving the papers

- GISD lists references, not PDFs, so every paper had to be found: most searching by an AI assistant, the rest by hand
- Of 804 references: 45% collected (364), 11% located but download blocked (89), 44% not found (351)
- Collected papers hold 46% of impact records (537 of 1,174) and cover 72% of species (106 of 148)
- Missing ones are mostly ordinary journal articles, so access is the barrier; the evaluation draws only on collected papers

## 9. Evaluation design

- 60 held-out papers, never seen during prompt development, run through the live app like a normal upload
- An independent model (GPT-5.5) matches each extracted impact to the GISD impact describing the same effect
- We score with F2, which weights recall over precision: a missed impact costs an assessor more than a spurious one

## 10. Best configuration

- Claude Haiku 5.5 with the improved prompt
- Finds about three-quarters of GISD impacts on unseen papers
- Mechanism right about two-thirds of the time, category about half
- Worst category within one step of GISD's for 75% of papers

## 11. Model comparison

- Haiku 5.5 and Nova Lite, each with the original and improved prompt
- All land at F2 ≈ 0.6, with overlapping confidence intervals
- The improved prompt mainly moves Haiku along the precision-recall trade-off: it finds more and over-reports more
- Costs about 0.4 cents per paper

## 12. Label accuracy

- Mechanisms that papers state outright (predation, competition) are above 85%
- Ones that need inference (chemical, grazing) are around 20%
- Minor and Data Deficient categories are recognised well; Minimal Concern and Major less so
- Small n on several spokes, so read with care

## 13. Severity

- For each paper's worst impact, 38% exact and another 37% one category out
- In the right neighbourhood, rarely at the right address
- Raises the question: how often do human experts agree?

## 14. Section: Inter-annotator agreement

- To judge the model fairly we need a human baseline
- How consistent are experts given the same papers?
- If humans disagree, a single gold standard is a hard target for the model too

## 15. Annotator experience

- 11 annotators (6 experienced in EICAT, 5 not) each assessed the same 6 papers
- Each dot is a pair of annotators, scored by how much their impacts overlap
- Experienced pairs overlap at 0.81, inexperienced pairs at 0.48 (exact permutation test, p = 0.026)
- Groups of 6 and 5, so indicative rather than definitive
- Experience mainly helps people agree on which impacts count

## 16. Category and mechanism

- Every pair of annotators who found the same impact: did they give it the same label?
- Mechanism: experienced pairs 78% same, the rest only added a second mechanism, never a different one; inexperienced 62% same, 11% different
- Category: experienced pairs 51% same, and most of the rest one step apart (30%)
- Inexperienced pairs 34% same; their biggest disagreement (38%) is Data Deficient vs a severity, i.e. "is there enough evidence?", not "how bad?"
- Two or more steps apart is rare
- Model vs GISD (mechanism ~⅔, category ~½) is in the same range, but different measures and papers: a hint, not a benchmark

## 17. Questions

- Thank you; code, evaluation scripts and figures are in the EICAT-AI repository
- Wrap-up if needed: a diligent but over-enthusiastic research assistant that finds ¾ of impacts, over-reports (precision 0.36), and needs severity checked
- Next: a larger agreement study, so the model can be benchmarked against human agreement
- Acknowledge OneSTOP's EU Horizon Europe funding
