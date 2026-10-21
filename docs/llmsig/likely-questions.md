# EICAT-AI: likely questions

Questions an audience is likely to ask about `eicat-ai-talk.qmd`, hardest first within each section. Each one has why it is awkward and a suggested answer. Numbers are from the best run (`eval/runs/t60_v2_haiku`), `eval/runs/test60_report.md`, `eval/runs/model_comparison.md` and `figures/iaa_metrics.json`.

## The weak spots, in one place

If you only read one section, read this one.

1. **The severe categories are barely tested.** The 60-paper test set has 4 Major impacts and no Massive, and the model gets 1 of the 4 Major right. Yet the worst impact is what decides a species' EICAT score.
2. **"Within one step" counts DD as a step.** Severity ranks DD < MC < MN < …, so calling an MC paper DD (or the reverse) counts as "one step out", even though DD means "no assessment" and is not a severity.
3. **The "improved" prompt is not significantly better.** Haiku gained +0.044 F2, with a 95% CI of −0.061 to +0.150. Nova Lite's original prompt scores about the same, at a third of the cost.
4. **The judge has not been formally validated against humans.** It has only been spot-checked.
5. **Model and human agreement have not been measured on the same papers or with the same metric.** F2 against GISD cannot yet be set beside the human agreement figures.
6. **The test set is small.** It has 78 GISD impacts over 60 papers, and 46 of the 60 cases have just one GISD impact.

---

## Severity and the EICAT score

**Q: EICAT scores a species by its worst impact. How good is the model at Major and Massive?**
*Why it's tricky:* this is the policy-relevant end, and it's where the evidence is thinnest.
*Answer:* We don't know yet. The test set has 4 Major impacts and no Massive, and the model labelled 1 of the 4 Major correctly. GISD itself is only 5% Major or Massive, so a random sample of papers hardly tests them. The slide on the GISD records flags this. The fix is a targeted sample of papers with MR and MV impacts, not a bigger random one. Until then the model's severity calls are a starting point for the assessor, not a score.

**Q: You say 75% of papers are "within one step". Does that include Data Deficient?**
*Why it's tricky:* yes, it does, and DD is not a step on the severity scale.
*Answer:* Yes. The ranking puts DD below MC, so a DD-to-MC disagreement counts as one step. That flatters the number a little, because DD means "can't tell", not "less than Minimal Concern". The exact-match figure (38%) is the cleaner one. Errors are balanced: 19 papers over-estimated, 18 under-estimated, and 3 had nothing extracted. So there's no systematic bias towards inflating or deflating severity.

**Q: Is 38% exact agreement good or bad?**
*Answer:* On its own it's low. Humans agree substantially on each paper's worst category (alpha 0.69), but only 1 of the 6 IAA papers was unanimous, so exact agreement is hard for people too. We can't yet say whether 38% is inside the human range. That's the point of scaling up the agreement study.

## The evaluation itself

**Q: How do you know the GPT-5.5 judge is matching impacts correctly?**
*Why it's tricky:* everything rests on it, and it has only been spot-checked.
*Answer:* Its pairings were spot-checked by hand (`pairs.csv` keeps a one-sentence reason for every pair), but there is no formal judge-versus-human agreement figure yet, and that's a fair gap. To reduce bias, the judge sees only the evidence text and impacted taxa, not the category or mechanism labels, so it can't favour pairs that agree on labels. It's also a different model family from the Claude and Nova extractors, to limit self-preference. The literature reports LLM judges agreeing with humans only 64–68% of the time on expert tasks, so validating it on a sample is on the list.

**Q: Precision is 0.36. Two-thirds of what it reports is wrong?**
*Answer:* Not necessarily. GISD records one assessor's reading of a paper, often a subset of its impacts, so a genuine impact GISD didn't record counts as a false positive. Some of the 105 "false positives" are real impacts, some are splitting one impact into several, and some are genuinely wrong. We haven't measured the split, so the honest claim is "over-reports", not "hallucinates two-thirds of the time". That's also why we weight recall: the assessor can delete a spurious record in seconds but can't review one that was never found.

**Q: Why F2? Isn't that choosing the metric that flatters you?**
*Answer:* F1 for the best run is 0.49, against an F2 of 0.62. F2 follows from the use case: the tool drafts and an expert reviews, so a miss costs more than an extra record. Precision and recall are both shown on the slide, so nothing is hidden.

**Q: Can a Minimal Concern record ("no effect found") count as a detected impact?**
*Why it's tricky:* yes. The judge doesn't see labels, so it can pair a GISD "no effect" row with an extracted positive impact.
*Answer:* Yes. That pairing counts towards recall, and the disagreement then shows up as a category error. It inflates recall slightly. MC is 12 of the 59 matched pairs, and only 3 of those got MC right.

**Q: GISD is one person's judgement. Why treat it as gold?**
*Answer:* We don't treat it as truth, only as the best large-scale reference available. That's exactly why the inter-annotator study exists: once we know how much two experts disagree, we know how much disagreement with GISD to expect from a good system.

**Q: Are 60 papers enough?**
*Answer:* Enough for a headline, not for fine distinctions. The F2 95% CI is about ±0.07 for the best run, and every model and prompt combination overlaps. Several spokes on the label-accuracy radar charts have only 4 or 5 impacts, for example chemical impact (5) and grazing (5), each at 20%, which is 1 of 5.

**Q: How do you know the test papers weren't used in tuning?**
*Answer:* The prompt was developed on a 40-paper dev split and an earlier 20-paper sample. The 60 test papers were drawn at random from the remaining 252 distinct PDFs, checked by file content for no overlap, and not looked at during prompt development. The seven few-shot GISD examples come from references outside the evaluated set, and the pipeline skips them if they ever appear.

**Q: The model may have seen these papers, or GISD itself, in training. Isn't that leakage?**
*Why it's tricky:* we can't rule it out.
*Answer:* We can't rule it out, and nobody can for a closed model. Two points help. The model only receives the paper's text plus the species name, not GISD's records. And if it were reciting GISD, its severity calls would be far better than 38% exact. A clean test would use papers published after the model's training cutoff.

**Q: Were these single runs? How reproducible are they?**
*Answer:* Yes, one run per configuration. Haiku 5.5 doesn't accept a temperature setting, so outputs vary between runs. We've seen a re-run find one impact where the original found none. Run-to-run variance is part of why the configurations can't be separated.

## Model and prompt choices

**Q: If the improved prompt isn't significantly better, why call it improved?**
*Answer:* For detection it isn't significantly better (+0.044 F2, CI spans zero). It mainly trades precision for recall: recall rises from 0.57 to 0.74, while precision falls from 0.57 to 0.37. Where it does help is labels. Category accuracy goes from 0.47 to 0.54, and worst-category exact accuracy from 0.28 to 0.38. It also doubles records per paper (87 to 164) for about 30% more cost.

**Q: Nova Lite matches Haiku on F2 and is three times cheaper. Why not use it?**
*Answer:* Detection is a tie, but labels are not. Nova Lite's category accuracy is 0.15 to 0.33, against Haiku's 0.54, and its worst-category accuracy is 0.14 to 0.18. With the prompted-JSON fix it also failed on 5 of 61 cases. For screening alone Nova Lite is fine. For drafting assessments, Haiku is worth its 0.4 cents per paper.

**Q: Would a bigger model (Sonnet, GPT-5.5) do better?**
*Answer:* On a 20-paper comparison, no model was clearly better at detection: F1 ranged from 0.48 to 0.64 with all intervals overlapping. The frontier models were more conservative (precision above 0.8, recall about 0.5). They were somewhat better on category labels (GPT-5.5 0.57), at 10–90 times the cost. Caveat: that comparison used an older judge (Claude 3.7 Sonnet) and only 30 GISD impacts.

**Q: Why put the guidelines in the prompt rather than use RAG?**
*Answer:* The guidelines are short enough to distil, and retrieval adds a failure point (retrieving the wrong section). A typed output schema forces valid categories and mechanisms. We didn't run a formal RAG comparison, so this is a design choice, not a measured result.

**Q: Why AWS Bedrock? Could this run on open models?**
*Answer:* Bedrock was the practical route to several model families under one account. The pipeline uses Pydantic AI, so swapping in an open-weight model is a config change, but we haven't evaluated one.

## Data and retrieval

**Q: Only 45% of papers could be collected. Doesn't that bias the evaluation?**
*Answer:* Probably towards open-access and digitised papers. The collected set still covers 72% of species (106 of 148) and 46% of records. The missing papers are mostly ordinary journal articles, so access rather than paper type is the main barrier. It's also a finding in itself: an assessor would face the same wall, and a tool can only read what it can get.

**Q: What about scanned PDFs or papers not in English?**
*Answer:* Scanned PDFs with no text layer fail outright. One test paper (`tindall_2007`) failed this way because there's no OCR step yet. Non-English papers weren't tested. GISD gives no common names, so the evaluation passes the scientific name only, which under-tests papers that only use vernacular names (the app itself looks those up via GBIF).

**Q: Copyright: can you upload papers to a cloud LLM?**
*Answer:* Papers are processed through the team's own AWS account, and Bedrock doesn't use inputs for training. Licensing for bulk processing is worth checking with each institution before scaling up.

## The app

**Q: Can the model make up an evidence quote?**
*Answer:* It's told to quote verbatim, and the app then aligns every quote back to the paper text. If less than 90% of a quote aligns, it isn't treated as a verbatim match, and highlighting shows the reviewer exactly where the passage is. The reviewer is checking against the source, not trusting the model.

**Q: Does it score the species, or just the papers?**
*Answer:* It extracts impact records per paper. Combining them into a species score is left to the assessor, following EICAT's worst-impact rule.

**Q: Will reviewers just rubber-stamp the output?**
*Answer:* That's a real risk with any assistant. The app records every verify, edit and delete, with who and when, so the audit trail shows how much was changed. We haven't measured reviewer behaviour yet.

## Inter-annotator agreement

**Q: Six papers, eleven people, p = 0.026. Is that real?**
*Answer:* Treat it as indicative. Annotator pairs aren't independent (each person is in several pairs), which is why we used an exact permutation test over annotator group labels rather than a t-test. Still, with groups of 6 and 5 it's a pilot. The planned design has around 50 papers.

**Q: You excluded an annotator. Why?**
*Answer:* One annotator (A7) overlapped with almost no one else on which impacts were present, which points to a misunderstanding of the task rather than genuine disagreement. The exclusion rule is fixed in code and applied before any metric is computed. Expect a follow-up question on whether that's cherry-picking. The honest answer is to offer the figures with A7 included alongside (check `eval-data/iaa/excluded` before the talk).

**Q: Who matched up the annotators' impacts?**
*Why it's tricky:* an LLM (Claude 3.7 Sonnet) did.
*Answer:* An LLM clustered the evidence quotes into shared impacts, judging on the quote text only. Like the GISD judge, it's been spot-checked rather than formally validated, and cluster counts can shift slightly between runs.

**Q: The model gets category right about half the time. Is that worse than people?**
*Why it's tricky:* the label-agreement slide makes the comparison tempting, but the numbers aren't like for like.
*Answer:* Two annotators give the same category to a shared impact only 44% of the time (mechanism 69%). The model matches GISD on 54% of categories and 68% of mechanisms. So it looks similar, but one is human against human on 12 impacts from 6 papers, and the other is model against one GISD assessor on 59 matched impacts from different papers. Also, nearly half the human category disagreements (and 38% of all inexperienced pairs) are Data Deficient against a severity, which is a judgement about whether the evidence is enough.

**Q: So is the model as good as a human?**
*Answer:* We can't say yet, and we've been careful not to. The model is scored against GISD with F2, while humans are scored against each other with Jaccard overlap and label agreement on different papers. Next we'll run the model on the IAA papers and treat it as one more annotator, so its agreement can sit inside or outside the human range on the same metric.

## Bigger picture

**Q: What's it actually for, if it's wrong half the time on category?**
*Answer:* Triage and drafting. It finds three-quarters of the impacts GISD records, for less than half a cent per paper, and every record links to its evidence. The assessor's job shifts from reading every paper from scratch to checking and correcting a draft. Whether that's faster in practice is the next thing to measure.

**Q: Could it be used to assess species that have no EICAT assessment yet?**
*Answer:* That's the long-term aim, but not unsupervised. Given the severity results, a human must sign off on every score.
