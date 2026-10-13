# Memory error card for the controlled pipeline

This card describes gpt-oss-120b with random links at rate 0.8. The comparator is the correct index. Source names and message text remain unchanged. The pipeline uses at most eight seed people, 64 shortlisted messages, and 2,048 context tokens.

The workplace sample has 200 questions from five histories. The social sample has 80 questions from 41 histories. Each question has four option orders and three graph draws. This gives 2,400 workplace comparisons and 960 social comparisons. These repeated comparisons are not independent questions.

| Measure | Workplace | Social |
| --- | --- | --- |
| Exposure to additional people | 95.50% | 84.08% |
| Exact context change | 81.00% | 73.37% |
| Changed evidence-label set | 22.83% | 3.25% |
| Answer churn | 19.25% churn. Gains 6.04%, losses 7.79%. Net -1.75 points. | 4.07% churn. Gains 1.05%, losses 2.57%. Net -1.52 points. |
| Conditional change | Loss among right: 14.43%. Gain among wrong: 13.13%. | Loss among right: 3.20%. Gain among wrong: 5.38%. |
| Index headroom | -0.62 points | +0.51 points |
| No-memory agreement | 63.90% of stable valid answers after context change. Stratum mass 61.75%. | 29.74% of stable valid answers after context change. Stratum mass 69.31%. |
| Identical requests | 3/24 selected repeated requests disagree. | 5/24 selected repeated requests disagree. |
| Loss concentration | 75/200 questions have a loss. Top 20: 47.59% of loss; top question: 4.28%. | 5/80 questions have a loss. Top 8: 100.00% of loss; top question: 78.95%. |

Exposure uses 600 workplace question-draw pairs and 240 social question-draw pairs. Reader metrics also include the four option orders. Each history receives equal weight. Within a history, questions, draws, and orders receive equal weight. Conditional rates retain these original weights.

Churn includes a change involving an invalid response. The workplace random-link condition has one invalid answer. The social condition has none. The full transition file separates valid wrong-to-wrong changes from invalid responses. Gains and losses determine the net accuracy change. Hosted-reader variation can contribute to these observed changes. Identical requests share a saved response in the main comparison, so unchanged contexts have zero churn by construction.

The no-memory row uses valid unchanged answers whose context changed. Agreement does not establish that the reader ignored its context. The replay row uses 24 selected requests per workload across conditions. It is not a matched estimate for the complete random-link population.

Index headroom is correct-index accuracy minus unfiltered-search accuracy. It is not a harm bound. Evidence labels identify benchmark-marked messages and are not an exhaustive record of valid support. These are synthetic histories. The conditional analyses were specified after the answers were known.

The paper reports social intervals from history resampling and workplace sensitivity to removing each history. All percentages in this card are point estimates. The selected replay counts have a different denominator and use no population weighting.

The study's reproduction archive contains the source records, their hashes, and the exact model and request settings behind these rows.

See the [blank card](memory_error_card_template.md) and [record contract](stage_audit.md).

Conditional change uses two different denominators. Loss is conditioned on a correct baseline answer. Gain is conditioned on an incorrect baseline answer. Both retain the original population weights. Their difference is not the net accuracy change.

The evidence-fate results also split these rates by labeled evidence kept or lost. Kept means that no baseline-delivered label leaves. It includes empty baseline label sets and permits added labels. The nonempty-baseline sensitivity excludes those empty cases. A separate changed-context comparison excludes unchanged inputs, whose reused responses have zero loss by construction. The social evidence-lost stratum contains one question, so it does not support a population interval.

Loss concentration ranks questions by their weighted correct-to-incorrect changes. The top 10% contains 20 workplace questions and eight social questions. Only five social questions have any loss. The top-eight share must therefore be 100%; the count and top-question share provide more detail. The concentration results also give an independent equal-risk simulation reference. That reference retains question opportunity counts and original pair weights. It does not preserve shared responses or dependence across orders, graph draws, and histories. Its tail fractions are descriptive comparisons with the specified model. They are not calibrated significance tests for the study design. This analysis was specified after the answers were known.
