# Memory error card template

Use one card for each pipeline and evaluation population. Fill every field. Write `not measured` when a stage was not recorded.

| Field | Entry |
| --- | --- |
| System and version | Exact implementation, model, prompt, tokenizer, and decoding settings. |
| Population | Workloads, independent histories, distinct questions, selection rules, and exclusions. |
| Intervention | Link source, link rate, draws, displayed-name rule, and paired baseline. |
| Request coverage | Planned and completed requests, repeated comparisons, failures, and unavailable results. |
| Weights | Population weights, conditional denominators, and sampling inclusion probabilities. |
| Exposure | Share of question weight that reaches at least one additional person. |
| Context | Share with changed shortlist, selected message IDs, and exact context bytes. State each denominator. |
| Evidence | Retained benchmark evidence labels, lost labels, and questions with no labels. State annotation limits. |
| Churn | Gains, losses, wrong-to-wrong changes, invalid answers, and net accuracy change. |
| Conditional change | Loss among correct baseline answers and gain among incorrect baseline answers, with separate weighted denominators. |
| Index headroom | Correct-index accuracy minus unfiltered-search accuracy on matched questions and budgets. |
| No-memory control | Accuracy and answer agreement, conditional on context and answer changes. |
| Identical requests | Repeated-request population, disagreement, failures, timing, and whether weighting matches the main comparison. |
| Loss concentration | Questions with any correct-to-incorrect change, ranked weighted loss shares, and the top 10% and top question shares. |
| Uncertainty | Independent unit, interval method, resamples, sensitivity checks, and empty strata. |
| Cost and recovery | Usage, spend, unresolved reservations, fixed cap, cutoff, and restart behavior. |
| Evidence and access | Exact result files, generator, source receipt, license, and available artifact location. |
| Scope | Synthetic or natural histories, missing stages, post hoc analyses, and supported conclusions. |

Churn means answers that change between conditions. A net accuracy change can be small when gains and losses cancel. State whether churn includes invalid answers.

For evidence-fate groups, state whether kept includes empty baseline label sets and added labels. Give pair, question, and history counts. Report a sensitivity that excludes empty baseline sets. Separate changed and unchanged contexts when identical inputs reuse a saved response.

For a concentration reference, state the eligible comparisons, fitted loss probability, simulation count, random seed, tail rule, and zero-loss handling. State which dependencies the reference preserves or omits. A reference that assumes independent comparisons is not a calibrated test when comparisons share saved responses.

Use original population weights before conditioning on a stage event. An empty denominator is undefined. It is not zero. Keep workloads and native-system results separate.

Index headroom describes the intact filter's measured benefit. It is not a bound on harm from false links. Agreement with a no-memory answer does not identify how the reader used its context.

See the [filled card](memory_error_card.md) and [stage-audit record contract](stage_audit.md).
