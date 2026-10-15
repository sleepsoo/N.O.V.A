---
title: "Interpreting relative risks and odds ratios after propensity score matching: practical guidance for clinical research"
organization: "Korean journal of anesthesiology"
year: "2026"
language: en
source_url: "https://europepmc.org/article/MED/41918244"
license: "CC BY-NC"
---
# Interpreting relative risks and odds ratios after propensity score matching: practical guidance for clinical research

## Abstract

In observational studies, using relative risks (RRs) or odds ratios (ORs) influences the interpretation and generalizability of results, particularly after propensity-score matching (PSM). Here, we explain the theoretical and practical differences between the RR and OR across varying event probabilities and examine the influence of PSM. We illustrate the behaviors of the RR, OR, and their ratios mathematically and graphically across event probabilities. Using a simulated dataset with a binary outcome and three covariates (age, sex, and body mass index), we demonstrate how PSM can change event rates, RRs, ORs, and RR collapsibility. The OR departs from unity more steeply than does the RR as the event probabilities diverge, whereas both measures converge for probabilities below 0.10. When groups have similar event probabilities, the OR and RR diverge minimally, even at high probabilities. PSM shifts the covariate distributions and alters the event rates, RRs, and ORs. The difference between the RR and OR increases when the event rate exceeds 0.10, but remains small at lower event rates. The weighted averages of sex-specific RRs closely approximate the marginal RR, illustrating the collapsibility of an RR. Interpreting the RR and OR after PSM requires caution. While the OR may overestimate or underestimate associations, depending on the event rates, the RR is generally suitable as a marginal measure, but PSM modifies the study population, making the matched sample a product of statistical modeling. Reporting ORs after PSM is generally appropriate, but cross-checking with a collapsible measure, such as the marginal RR, can help to evaluate effect estimate robustness.

## Introduction

In clinical research, accurate interpretation of statistical measures is fundamental for making decisions regarding patient care and treatment efficacy. Among the various metrics, the relative risk (RR) and odds ratio (OR) are pivotal for quantifying the strength of association between exposures and outcomes. The RR is an intuitive measure, allowing comparison of the probability of an event between the exposed and unexposed groups, which makes it particularly suitable for cohort studies where the incidence can be observed directly. Conversely, the OR compares the odds of events and is commonly applied in case–control studies where direct measurement of incidence is not feasible.

Observational studies are vulnerable to confounding biases due to non-random treatment allocation. Propensity-score matching (PSM), a widely used statistical technique, is designed to mitigate such biases by creating matched sets of treated and untreated participants, with similar baseline confounding covariates. By simulating randomization, PSM helps researchers to approximate causal effects more reliably than can be achieved with unadjusted comparisons. Other propensity score-based approaches, such as inverse probability of treatment weighting (IPTW) or overlap weighting, also aim to balance covariates; however, these approaches retain all subjects for analysis and distribute weights, rather than selecting a matched subset. While these methods differ in implementation, the fundamental concern of estimating conditional versus marginal effects, and their impact on effect measures, such as the RR and OR, remains relevant across all these approaches.

Of note, the matching process in PSM fundamentally changes the study population by selecting comparable subsets, thereby altering the covariate distribution of the original cohort. Thus, the matched sample no longer represents the entire source population, but is rather a conditional subset. Consequently, the effect measures estimated after PSM reflect treatment effects within the matched cohort rather than those in the entire population, raising challenges for interpretation and generalization. Although the mathematical behaviors of the RR and OR have been extensively described in epidemiology and biostatistics, their behaviors in the specific context of PSM have not been systematically examined. Because PSM explicitly modifies baseline risks by altering covariate distributions through the matching process, the dynamics between the RR and OR may differ in magnitude and direction from those observed in unmatched cohorts, because matching modifies the baseline risk structure. This issue has not been clearly addressed in previous studies.

These issues are particularly important when deciding whether to report the RR or OR after PSM. ORs are mathematically related to RRs and converge under the rare-disease assumption, but they diverge substantially as event rates increase. Furthermore, the generalizability of ORs is limited by their non-collapsibility (which means that the overall association measured by ORs does not correspond to a weighted average of subgroup-specific effects). Conversely, RRs are collapsible and can be expressed as weighted averages of subgroup-specific effects, making them suitable for broader population-level interpretations. Despite these differences, many published studies present only one measure, sometimes without acknowledging its limitations in the context of PSM.

For clinicians interpreting observational studies, understanding when the RR and OR diverge and how PSM alters these measures is essential for evaluating treatment effects. In this paper, we aim to provide practical guidance on interpreting RR and OR in the context of PSM by integrating theoretical insights with empirical evidence. Specifically, we examine how RR and OR behave across a wide range of event probabilities and how these measures change before and after PSM using simulation data. By highlighting both theoretical properties and practical implications, we seek to clarify the strengths and limitations of each measure and support their appropriate interpretation in clinical research.

## Theoretical considerations

Although the RR and OR have well-defined mathematical properties, their most practical differences can be understood intuitively without needing to revert to detailed derivations. Therefore, this section provides simplified explanations, tailored for clinical readers, while full algebraic formulas and proofs are presented in the Supplementary Materials.

### RR and OR: intuitive definitions and practical differences

The RR compares probabilities, whereas the OR compares odds, which represent the number of events relative to non-events. For example, an odds of 0.25 indicates one event for every four non-events (corresponding to a risk of 0.20). When the probability of an event is low, the odds and the risk are very similar; therefore, the RR and OR approximate each other. However, as the event rate increases, the odds rise more steeply than does the risk, causing the OR and the RR to deviate substantially. For example, consider a simple 2 × 2 table in which 20 of 100 treated patients and 10 of 100 controls experience an event (Table 1). The risks are 0.20 and 0.10, respectively; thus, the RR is 2.0. In contrast, the odds is 20/80 = 0.25 in the treatment group, and 10/90 = 0.11 in the control group, giving an OR of approximately 2.25. As this example illustrates, even when both measures describe the same underlying data, the OR can be larger than the RR, suggesting the existence of a stronger association.

A key mathematical relationship is that the OR becomes larger than the RR when the event rate in the treatment group exceeds that in the control group, and their divergence increases with the increase in event rates. Conversely, when event probabilities in the two groups are similar, the RR and OR remain similar, regardless of the magnitude of the absolute probabilities. These relationships form the basis of the so-called “rare-disease assumption,” under which the OR closely approximates the RR when the event frequency is low in both groups. A simplified demonstration using a 2 × 2 table is provided in Supplementary Material 1 for readers who wish to examine the underlying equations.

### How PSM alters the RR and OR

PSM balances observed baseline covariates by selecting comparable individuals from the treatment and control groups to create matched subsets. Because matching changes the composition of the analytical sample, the event distribution typically differs from that of the original cohort. Consequently, the RR and OR calculated after matching represent the association within the matched sample, but do not necessarily reflect the effect on the entire population.

This distinction can be understood as follows:

• Marginal effect: association measured in the entire population, where individuals contribute proportionally to their prevalence.

• Conditional effect: association measured in a restricted or adjusted population, such as a regression-adjusted cohort or a matched sample, where the effect is conditioned on the covariate balance.

Thus, PSM intentionally creates a conditional population. Hence, post-matching estimates should be interpreted as effects in the matched cohort, rather than being generalized to the full source population.

Although the matched sample no longer represents the entire population, ORs preserve several mathematical properties, including symmetry, invariance to conditioning direction, and stability under transformations; therefore, they remain valid conditional effect measures within the matched cohort. These characteristics explain why ORs often remain interpretable in PSM analyses, even when marginal generalizability is limited.

### Collapsibility: why the RR and OR behave differently after matching

Collapsibility describes whether a population-level measure can be expressed as a weighted average of subgroup-specific effects. The RR is collapsible: under a fixed population structure, the marginal RR equals a weighted average of subgroup-specific RRs, of which the weights are determined by baseline risks. In contrast, the OR is non-collapsible, meaning that, even if the subgroup-specific ORs are identical, the overall OR may differ solely because the subgroup distributions vary.

This distinction explains the behavior of these measures after statistical adjustment or matching. As PSM changes the population representation by selecting subgroups of individuals with similar covariates, the weights used in the RR collapsibility formula also change. Thus, the RR calculated in a matched cohort will generally not be equal to the RR from the original population, not because the treatment effect has changed, but because the population structure has changed.

Of note to clinicians, this implies that:

• The RR is interpretable at a population level when the subgroup composition reflects the target population.

• The OR may shift with matching or adjustment, even when the true causal effect remains unchanged, due to its non-collapsibility.

Formal mathematical proofs of RR collapsibility and OR non-collapsibility can be found in Supplementary Material 1.

### Relationship between exposure-based and disease-based ORs

ORs calculated as the odds of exposure among diseased versus non-diseased individuals (such as in case–control studies) are mathematically equivalent to ORs comparing disease odds between exposed and unexposed groups. This equivalence arises directly from Bayes’ theorem and explains why the OR is widely used in case–control designs where the incidence cannot be estimated. A full algebraic conversion requires lengthy expressions; thus, a detailed derivation is provided in Supplementary Material 2. This relationship is further illustrated in Fig. 1, which shows how the equivalence of the exposure- and disease-based ORs arises from the joint and marginal probabilities defined by Bayes’ theorem. In essence, the OR remains unchanged regardless of whether one condition is an exposure or a disease status, whereas the RR does not. Given this invariance, the OR is mathematically convenient and suitable for case–control and regression-based analyses. However, this also contributes to its more complex clinical interpretation when event rates are not low.

Despite the intuitive interpretability of the RR, the OR remains widely used in clinical and epidemiological research for several practical reasons. First, the OR is the only effect measure that can be estimated in case–control studies in which the outcome incidence is unknown by design. Second, logistic regression naturally provides ORs and is computationally more stable than the models used to estimate RRs, such as log-binomial or Poisson regression with robust variance, which often suffer from non-convergence when event rates are high. Third, ORs possess mathematical properties, such as symmetry, when outcomes are relabeled, and invariance to the direction of conditioning, which makes the OR suitable for matched or conditional analyses. These advantages explain why clinicians continue to rely on ORs in many settings, even when the RR may appear more intuitively interpretable.

### Summary of key concepts for clinicians

• The RR compares probabilities; the OR compares event/non-event ratios.

• The RR and OR differ more as event rates increase, not only when effects are strong.

• PSM changes the effective study population; thus, post-matching RRs and ORs reflect conditional, rather than marginal, treatment effects.

• The RR is collapsible (population-level preserved), whereas the OR is non-collapsible (may change solely due to covariate distribution).

## Mathematical and simulation-based illustration

### Mathematical exploration of the RR and OR across event probabilities

To illustrate how varying event probabilities influence the behavior of the RR and OR, we have constructed a grid of possible event probabilities for simulated treatment and control groups. For each group, the probability of an event varied systematically from 0.01 to 0.99 in increments of 0.01, producing 9,801 unique combinations. For each combination, the RR and OR were calculated using standard definitions. Because these values span several orders of magnitude, the RR, OR, and OR/RR ratios are displayed on a logarithmic (base 10) scale. Their distributions and patterns are summarized using heat maps and surface plots. This exploration does not aim to test a hypothesis, but to illustrate how the RR and OR diverge or converge under different combinations of event probabilities and to provide insight into interpreting these measures after PSM.

### Simulation-based illustration of how PSM can affect the RR and OR

A simulated dataset was used to illustrate how PSM modifies covariate distributions and subsequently alters event rates, the RR, and the OR. We simulated 1000 individuals, of whom 500 each were assigned to the treatment and the control groups.

Three baseline covariates were selected to resemble common clinical variables:

• Sex: we included 60% males in the treatment group and 40% males in the control group.

• Age: we ensured that this was normally distributed, with a mean of 60 and standard deviation (SD) of 10 in the treatment group, and a mean of 65 and SD of 10 in the control group.

• Body mass index (BMI): we ensured that the BMI was normally distributed, with a mean of 20 and an SD of 5 in the treatment group and a mean of 25 and an SD of 5 in the control group.

These imbalances were intentional to represent typical confounding patterns seen in observational studies.

A binary outcome was simulated with an equal event probability of 0.10 in both groups. For simplicity and clarity of interpretation, we generated the outcome independently of the covariates. Propensity scores were estimated using logistic regression with treatment assignment as the dependent variable and sex, age, and BMI as independent variables. Nearest-neighbor 1:1 matching was performed with a caliper of 0.2 on the logit scale. Only matched pairs were retained for downstream analysis, yielding a matched dataset. Covariate balance before and after matching was assessed using the standardized mean difference (SMD), where an absolute SMD < 0.10 was considered acceptable. The matching results and covariate distributions are shown in Fig. 2. All computations were conducted using R version 4.4.0 (https://www.r-project.org), and the full simulation and matching codes are provided in Supplementary Material 3.

### Calculation of the RR and OR before and after matching

For both the unmatched and matched samples, the RR and OR were calculated using 2 × 2 tables of event counts. Confidence intervals were computed using standard log-transformed formulae. Because zero cell counts can lead to undefined estimates, a continuity correction of +0.5 was applied whenever needed. These calculations followed widely used epidemiological methods. Subgroup analyses were performed separately for males and females in the matched samples to illustrate the collapsibility of the RR. Matching modified the distribution of sex and other covariates; therefore, the post-matching RR and OR represent conditional effect estimates within the matched cohort, rather than population-level effects.

## Insights from the illustrations

### Relationships between the RR and OR in various combinations of event probabilities

When the probability of an event ranges between 0.01 and 0.99, the RR, OR, and OR/RR ranges from 0.01 to 99, from 0.0001 to 9801, and from 0.01 to 99, respectively. The RR, OR, and OR/RR are distributed symmetrically around 1 on a log-linear scale (Supplementary Fig. 1) when the probability of an event is equal between the two groups.

In three-dimensional surface plots, rotational symmetries can be observed about an identity line at the level of 100 (= 1) on the z-axis (Supplementary Figs. 2–4). However, they differ in terms of the RR, OR, and OR/RR. The lowest RR, OR, and OR/RR are attained when the probabilities of an event are 0.99 and 0.01 in the control and treatment groups, respectively, while the highest RR, OR, and OR/RR are attained when the probabilities are 0.01 and 0.99, respectively.

Although the RR and OR become positively or negatively extreme as the probabilities of an event in one group and the other increase and decrease, respectively, the OR changes more steeply than does the RR (Supplementary Figs. 2 and 3). Even when event probabilities differ substantially between two groups, the OR changes are steeper than the RR changes.

The lower the probability of an event (the rare-disease assumption), the closer are the OR and RR values (Supplementary Figs. 4 and 5). If the probability of an event is the same between the two groups, so are the ORs and RRs, regardless of the magnitude of the probability.

### Shift in covariate distribution and resulting changes in the RR and OR after PSM

Table 2 and Fig. 2 present the shifts in the covariate distribution before and after PSM. Based on visual inspection of the covariate distribution, good covariate balance seems to be achieved after PSM. However, PSM could not reduce the absolute value of the SMD for BMI to < 0.10 (Table 2), indicating that the balance in this variable was not sufficiently achieved. As this study intends to evaluate the shift in covariate distribution after PSM, this minor imbalance will be disregarded.

The changes in the event rate, along with changes in the RR and OR, are due to a shift in the covariate distribution (Table 3). PSM decreases the event rate in the treatment group (from 0.082 to 0.069), while it increases that in the control group (from 0.096 to 0.109). Accordingly, both the RR and OR differ before and after PSM. Given that the event rates of the two groups are below 0.10, the OR (0.84) approximates the RR (0.85) according to the rare-disease assumption. However, as the event rate in the control group (0.109) exceeds 0.10 after PSM, the difference between RR (0.63) and OR (0.61) is increased.

### Collapsibility of the RR

As shown in Table 3, the male and female RRs are 0.93 and 0.48, respectively. The number of events for each sex in the control group is 10 and 20, respectively. Based on the number of events, the baseline risks (collapsibility weights) for each sex are 1010+20=13 and 2010+20=23, respectively. Therefore, the weighted average of the RRs for each sex is 0.93×13+0.48×23=0.63325, which is comparable to the population RR (0.63333).

## Practical implications for clinical researchers

Above, we have discussed how the RR and OR behave across a broad spectrum of event probabilities and how these measures change after PSM. Across theoretical calculations, the RR and OR are symmetric around unity when groups have identical event probabilities. However, the OR increases or decreases more sharply than does the RR when event probabilities diverge. As expected from the rare-disease assumption, the two measures are nearly indistinguishable when event probabilities are low. These theoretical patterns are also reflected in the simulation analysis: when PSM alters covariate distributions and shifts event probabilities, the resulting RR and OR change accordingly. Notably, discrepancies between the RR and OR tend to increase when event probabilities exceed approximately 0.10, whereas the two measures remain similar when event rates are low or comparable between the groups.

A recent retrospective cohort study that compared acute complications between rocuronium/sugammadex and cisatracurium/neostigmine in patients with chronic kidney disease reported only RRs, even though some outcomes had incidences > 0.10. The ORs calculated from these RRs using the formula OR=RR×1-Risk11-Risk2 confirmed that the rare-disease assumption mostly held (Table 4). Interestingly, the discrepancy between the RR and OR was larger for respiratory failure (incidence < 0.10) than for heart failure and acute kidney injury (incidence > 0.10). This apparent contradiction can be explained by our finding that ORs approximate RRs when event probabilities are comparable between groups, regardless of their absolute magnitude.

PSM shifts the distribution of covariates (baseline characteristics), resulting in changes in the RR and OR before and after PSM. In particular, when unmeasured confounders are present, PSM improves the internal validity by reducing confounding bias, but inherently restricts the target population to the matched sample, limiting external generalizability. Nonetheless, by balancing the observed baseline covariates, PSM aims to create an analytical sample in which treated and untreated subjects have similar distributions of these covariates, thereby mimicking a randomized controlled trial to some extent. This internal balancing allows the estimation of marginal (or population average) causal treatment effects, which is different from the adjusted (or conditional) effects assessed in regression analysis. The question of which measures to report (RR versus OR) in a PSM study to allow generalization of the results to a broader target population, which is independent of the study population, depends on the statistical properties of these measures.

Because the marginal (population-level) OR cannot be simply calculated as a weighted average of subgroup-specific OR, ORs are generally non-collapsible, which prevents the generalization of the effects to a new target population with different covariate distributions. In addition, marginal ORs are biased from their true values when PSM is used, except for the particular case in which the true marginal OR is 1. ORs are difficult to comprehend and are often interpreted as if they are RRs. However, this interpretation holds true only under the rare-disease assumption. While ORs approximate RRs when the outcome is rare, they diverge significantly as the outcome becomes more common and the association becomes stronger, with ORs typically exaggerating the effect. Furthermore, ORs are difficult to compare across studies, or even within the same study, if different model specifications are used (e.g., the same dataset with a different set of independent variables).

In contrast, RRs are easier to interpret and are collapsible. Collapsibility means that the overall population-level RR can be understood as a weighted average of subgroup effects. This property allows for the generalization of treatment effects to a new target population by reweighting local estimates (treatment effects within a specific subgroup of the population). Additionally, less-biased RRs can be obtained by using PSM.

Nonetheless, based on Bayes’ theorem, the OR comparing the exposure odds between individuals with and without an outcome is algebraically identical to the OR comparing the outcome odds between exposed and unexposed individuals. This invariance provides a methodological foundation for using the OR in case–control studies in which outcome risks cannot be directly estimated. The OR for a covariate obtained with logistic regression analysis is constant for all values of other covariates. Unlike the RR, an OR is robust to a change in outcome labels (swapping outcome coding 0 and 1) because swapping only leads to an inverse change in the OR. Furthermore, using logistic regression to calculate ORs is computationally stable, as compared to using log-binomial regression to estimate RRs, which fails to converge for a significant percentage of iterations, particularly in cases of moderate effects and high prevalence. Although the risk difference and the number needed for treatment have considerable advantages, this discussion is beyond the scope of this study.

## Conclusion

In summary, PSM alters covariate distributions and can thereby change both the RR and OR, with greater discrepancies between these measures observed as event rates increase. ORs remain mathematically stable and are generally suitable for PSM-based analyses. However, their non-collapsibility implies the need for caution, particularly when the outcomes are common. Alternative propensity-score methods, such as IPTW or overlap weighting, also modify covariate and event distributions; however, the distinction between conditional and marginal effects persists across these approaches. In practice, checking OR estimates against a collapsible measure, such as the marginal RR, can help to evaluate the robustness of findings, particularly when the results are to be generalized to broader clinical populations.
