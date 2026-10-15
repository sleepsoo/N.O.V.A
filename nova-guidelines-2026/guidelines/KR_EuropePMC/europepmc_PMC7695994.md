---
title: "Prognostic Significance of COVID-19 Receptor ACE2 and Recommendation for Antihypertensive Drug in Renal Cell Carcinoma"
organization: "World Health Organization on March"
year: "2020"
language: en
source_url: "https://europepmc.org/article/MED/33274196"
license: "CC BY"
---
# Prognostic Significance of COVID-19 Receptor ACE2 and Recommendation for Antihypertensive Drug in Renal Cell Carcinoma

## Abstract

### Purpose

Owing to its worldwide spread, the coronavirus disease (COVID-19) epidemic was declared a pandemic by the World Health Organization on March 11, 2020. Angiotensin-converting enzyme 2 (ACE2) is the outer surface protein of the cell membrane that is abundantly distributed in the heart, lungs, and kidneys and plays an important role in molecular docking of the severe acute respiratory syndrome coronavirus 2. In this study, we aimed to analyze the difference in the survival rate according to ACE2 expressions in pan-cancer.

### Materials and Methods

We downloaded clinical and genomic data from The Cancer Genome Atlas. We used Kaplan-Meier with a log-rank test, and the Cox proportional hazards regression to analyze prognostic significance.

### Results

In the Kaplan-Meier curve, clear cell renal cell carcinoma (ccRCC), uveal melanoma, and prostate adenocarcinoma showed statistical significance. In the Cox regression, thyroid carcinoma and glioblastoma multiforme and ccRCC showed significant results. Only ccRCC had statistical significance, and high ACE2 expression is related to good prognosis. It is known that the ACE inhibitor, a primary antihypertensive agent, increases ACE2 expression.

### Conclusion

Based on these results, we believe that the ACE inhibitor will be important to increase the lifespan of ccRCC patients. This study is the first research to offer a recommendation on the use of anti-hypertensive drugs to ccRCC patients.

## 1. Introduction

Coronavirus (CoV) belongs to a family of viruses characterized by highly diverse, enveloped, positive-sense, and single-stranded RNA genomes. They cause respiratory, gastrointestinal, hepatic, and neurological symptoms in animals or humans according to their type. The well-known Middle East respiratory syndrome CoV and severe acute respiratory syndrome CoV (SARS-CoV) are fatal to humans, while human CoV (HCoV) OC43, HCoV-229E, and HCoV-NL63 cause only mild respiratory symptoms. In December 2019, cases of unknown pneumonia occurred in Wuhan, Hubei Province, China. Subsequently, the causative virus was extracted from human patients, and a molecular analysis revealed that it was a novel coronavirus. The virus was tentatively named “severe acute respiratory syndrome coronavirus 2 (SARS-CoV-2)” by the International Committee on Taxonomy of Viruses. The World Health Organization (WHO) named the disease caused by SARS-CoV-2 as COVID-19 on February 11, 2020. With its worldwide spread, the COVID-19 epidemic was declared a pandemic by the WHO on March 11, 2020.

Angiotensin-converting enzyme 2 (ACE2) is the outer surface protein of the cell membrane that is abundantly distributed in the heart, lungs, and kidneys. ACE2 is a functional receptor of SARS-CoV. SARS-CoV-2 shares 80% similarity with the genome of SARS-CoV, and its cell entry mechanism is mediated by the ACE2 receptor. ACE2 is currently emerging as a new research topic in the wake of SARS-CoV infection. The ACE inhibitor, which is widely used as a therapeutic agent for hypertension, is reported to upregulate the ACE2 receptor expression. The use of ACE inhibitors has been suggested to increase the susceptibility to COVID-19 and worsen the COVID-19 outcome through an increase in the viral load. However, owing to the insufficient evidence at present, the management of hypertension in patients with COVID-19 is controversial.

TCGA is a large prospective cohort with data on several variables (demographic, clinical, and genomic data) of approximately 11,000 patients for 33 common cancers. Especially in the field of big data, high-dimensional genomics is available. As the importance of managing cancer diseases increases in the COVID-19 pandemic era, we analyzed the difference in the survival rate according to ACE2 expression levels in 31 cancers by using The Cancer Genome Atlas (TCGA) dataset. Accordingly, we aimed to provide recommendations for the treatment of viral infection or use of ACE inhibitors in certain patients with cancer.

## 2. Material and Methods

### 2.1. Patients

The clinical and genomic data of 33 cancers listed in TCGA were downloaded from the Firehose database (https://gdac.broadinstitute.org/) in February 2020. All TCGA data were available without restrictions from publications or presentations in accordance with TCGA publication guidelines. Patients' clinical variables such as cancer stage, age, sex, and censoring status, as well as ACE2 expression levels, were also extracted. Patient data with insufficient clinical or genetic information were excluded. Two cancers without ACE2 expression levels were excluded from the analysis.

### 2.2. Statistical Analyses

A violin plot with log2 transformed ACE2 expression on the y-axis and cancer types on the x-axis was created to compare the gene expression levels between the different cancers (Figure 1). In the present study, we performed a Kaplan-Meier analysis and log-rank tests. A continuous ACE2 expression level was converted to a binary factor low (0) and high (1), with a median cutoff; two distinct survival distributions expressed in binary form were developed. Cancers with positive and negative relationships with the ACE2 expression level and survival rate were defined as “positive” and “negative” cancers, respectively. Nineteen cancers were positive, and 12 were negative on the basis of the odds ratios.

We also used univariable and multivariable Cox proportional hazards regression models for all 31 cancers to estimate the hazard ratio, 95% confidence interval, and p value of ACE2 and the other clinical variables in the data for each cancer as we described previously. Finally, we checked the significance of the values and combined the results with the survival analysis output to conclude which type of cancer could be most affected by the ACE2 gene. The concordance index was used to evaluate the prediction accuracy of our statistical models. A flowchart is provided in Figure 2 to visually represent the process. All statistical analyses were performed using R version 3.6.0 (R Foundation for Statistical Computing, Vienna, Austria).

## 3. Results

### 3.1. Patient Data and ACE2 Expression

The numbers of samples obtained from TCGA dataset for all cancer types are shown in Table 1. Demographic and clinical details are not shown in this paper. Two cancers, clear cell renal cell carcinoma and renal papillary cell carcinoma, stood out in the violin plot (Figure 1) because their median log2 transformed ACE2 expression levels were >10. Eight cancers, namely, brain lower-grade glioma, invasive breast carcinoma, uveal melanoma, glioblastoma multiforme, mesothelioma, pheochromocytoma and paraganglioma, sarcoma, and skin melanoma, were found to have median values of <2.5.

### 3.2. Survival Analyses

None of the negative cancers had significant log-rank test results. Of the 19 positive cancers, three, namely clear cell renal cell carcinoma, uveal melanoma, and prostate adenocarcinoma, had p values of <0.05 and thus were considered significant in the Kaplan-Meier analysis and log-rank test (Figure 2). The survival plots of these cancers are shown in Figure 3.

Although two negative cancers, thyroid carcinoma and glioblastoma multiforme, and two positive cancers, adrenocortical carcinoma and mesothelioma, were significant in the multivariable regression results, they were still insignificant in the univariable Cox regression models (Figure 2). As the multivariable models of these cancers could elicit a false idea of interaction effects between covariates, we decided not to further investigate them.

Clear cell renal cell carcinoma was the only cancer with significant results in both the univariable and multivariable Cox regression analyses (Figure 2). The cancer had hazard ratios of 0.571884 and 0.61273 in the univariable and multivariable Cox regression models, respectively. These values indicate that the relative risks of death in the defined period were approximately 43% and 39% lower, respectively, in the high gene expression group than in the low gene expression group. These results were also observed in a forest plot, as only clear cell renal cell carcinoma had a confidence interval of <0 in both the univariable and multivariable regression analyses (Figures 4 and 5).

The concordance indexes of the univariable Cox regression models for clear cell renal cell carcinoma, uveal melanoma, and prostate adenocarcinoma were 0.6874, 0.59, and 0.5351, respectively (Table 2). As a model with a concordance index of >0.55 is considered a good model, this implies a good predictive ability for clear cell renal cell carcinoma and uveal melanoma. We conclude that high ACE2 gene expression levels could positively influence the survival rate of patients with clear cell renal cell carcinoma and have high model accuracy levels.

## 4. Discussion

In this study, we analyzed the survival rate according to ACE2 expression level for various cancers by using statistical models such as the Kaplan-Meier analysis and log-rank test and univariable and multivariable Cox regression analyses. In addition, the survival prediction performance of ACE2 expression level was evaluated with the concordance index to corroborate the significantly different results from the previous tests.

The results of the Kaplan-Meier analysis and log-rank test indicated significant differences in survival rates among patients with renal cell carcinoma, uveal melanoma, and prostate adenocarcinoma according to ACE2 expression level. The results of the univariable and multivariable Cox regression analyses indicated that the ACE2 expression level had a significant effect on the survival rates of patients with renal clear cell carcinoma, thyroid carcinoma, and glioblastoma multiforme. Only clear cell renal cell carcinoma showed significant results in both the Kaplan-Meier analysis and log-rank test/univariable and multivariable Cox regression analyses. Therefore, we could assume that in clear cell renal cell carcinoma, the ACE2 expression level is strongly associated with survival rate and acts as an important causal factor for predicting the survival rate. The concordance index of clear cell renal cell carcinoma was 0.687, confirming its good survival prediction performance. As the hazard ratio of clear cell renal cell carcinoma was significantly <1 in both the univariable and multivariable Cox regression analyses, we estimated that the higher the patient's ACE2 expression level, the lower the patient's estimated risk, which corresponds to a higher survival rate.

The ACE inhibitor is used as an initial therapy for high blood pressure in many situations (e.g., heart failure with reduced ejection fraction and chronic kidney disease). It inhibits the conversion of angiotensin I to angiotensin II to reduce the activity of the renin-angiotensin-aldosterone system. The use of ACE inhibitor has been shown to increase the ACE2 expression level in human and animal studies. Therefore, we assumed that the use of ACE inhibitors for controlling high blood pressure in patients with clear cell renal cell carcinoma will increase their ACE2 expression levels, which may help to improve survival rates if the administration of the ACE inhibitor is prioritized when choosing a high blood pressure control drug for these patients.

As mentioned earlier, ACE2, which is known to play an important role in molecular docking in the cell entry process of CoVs, is associated with mainly respiratory symptoms. In addition, an increased ACE2 expression level induces more CoV viral loads, including those of SARS-CoV and SARS-CoV-2. Cancers with significant results in this study were less relevant to respiratory viruses. Therefore, ACE2 expression level and survival rate seem to have no significant correlation in patients with respiratory cancer. The cancers with significant results in this study are presumed to be less relevant to respiratory viruses, including CoVs. Therefore, we speculated that SARS-CoV infection does not have a significant effect on the survival rate of certain cancer patients.

In several carcinomas (breast cancer, uterus corpus endometrial carcinoma, kidney renal papillary carcinoma, non-small-cell lung cancer, hepatocellular carcinoma, and pancreatic cancer), ACE2 expression was downregulated, which is thought to be a poor prognostic factor. This is consistent with the content of our study. In a recent paper, CD4 memory, CD8 effector, T helper cell, dendritic cell, and NK cell, which are associated with tumor infiltration, are reported to increase in ccRCC tissues. The decrease in ACE2 expression is related to tumor proliferation, stemness, and epithelial-mesenchymal transition even at the micro environmental level. It was assumed that the change in the immune microenvironment resulted in a difference in survival rates, and the increase in ACE2 expression is thought to mainly play an antitumor role. However, to the author's knowledge, it is assumed that the clear mechanisms of ACE2 expression and ccRCC are not established. The further clinical validation study that correlated between ACE2 expression and survival rates is required.

The limitation of this study is that the statistical analyses were conducted only with a single cohort. The results must be verified through a multicohort analysis. Second, the suggested drugs for hypertension and viral infections were hypothesized through statistical results, and the actual clinical outcomes require validation through further clinical trials. Third, because the number of samples collected for each cancer varied (range, 68–985), the power of the statistical results also varied among the cancer types.

## 5. Conclusion

By using big data, we analyzed the differences in survival rates among certain cancers according to ACE2 expression, which is known to be important for the entry of SARS-CoV2, the virus responsible for the COVID-19 pandemic. The ACE2 expression level was highly relevant to the survival rate of patients with clear cell renal cell carcinoma and could be an important factor for predicting survival. The results of this study might be useful for further studying ACE-related treatments, care, and outcomes in patients with ccRCC (Figure 6).
