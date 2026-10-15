---
title: "Safety and Usability Guidelines of Clinical Information Systems Integrating Clinical Workflow: A Systematic Review"
organization: "Healthcare informatics research"
year: "2018"
language: en
source_url: "https://europepmc.org/article/MED/30109149"
license: "CC BY-NC"
---
# Safety and Usability Guidelines of Clinical Information Systems Integrating Clinical Workflow: A Systematic Review

## Abstract

### Objectives

The usability of clinical information systems (CISs) is known to be an essential consideration in ensuring patient safety as well as integrating clinical flow. This study aimed to determine how usability and safety guidelines of CIS consider clinical workflow through a systematic review in terms of the target systems, methodology, and guideline components of relevant articles.

### Methods

A literature search was conducted for articles published from 2000 to 2015 in PubMed, Cochrane, EMBASE, Web of Science, and CINAHL. The Preferred Reporting Items for Systematic Reviews and Meta-Analyses (PRISMA) statement method was employed. Articles containing recommendations, principles, and evaluation items for CIS usability and safety were included. The selected articles were classified according to article type, methodology, and target systems. Taking clinical workflow into consideration, the components of guidelines were extracted and classified.

### Results

A total of 7,401 articles were identified by keyword search. From the 76 articles remaining after abstract screening, 15 were selected through full-text review. Literature review (n = 7) was the most common methodology, followed by expert opinions (n = 6). Computerized physician order entry (n = 6) was the most frequent system. Four articles considered the entire process of clinical tasks, and two articles considered the principles of the entire process of user interface affecting clinical workflow. Only two articles performed heuristic evaluations of CISs.

### Conclusions

The usability and safety guidelines of CISs need improvement in guideline development methodology and with consideration of clinical workflow.

## I. Introduction

Many errors regarding clinical information systems (CISs) have been reported. Research on errors and potential hazards has led to review and updating of CISs to promote patient safety. Efforts to reduce errors have assessed CISs in light of human factors. As a result, guidelines have been developed and distributed to consider usability from the CIS design stage.

However, efforts to pursue patient safety have sometimes had conflicting results regarding usability. An alert function that can filter out simple input errors may interfere with the flow of work, which may adversely affect usability. On the other hand, functions to improve usability can cause errors. For a novice user, shortcuts or abbreviations for work efficiency could threaten patient safety. Therefore, user-centered CIS design guidelines are needed, not only to prevent errors but also to improve clinical workflow.

The accumulation of structured (coded) data enables the development of decision support rules. Improvements in network speed allow immediate feedback to users, with processing of evidence-based medicine and patient data. Consequently, system-level controls to reduce user mistakes (or for best practices) have become easier. Moreover, professional considerations of usability are needed as CISs become more complex and sophisticated because novice personnel regularly enter the field and must be adapted to the system. We should consider the diverse functions of CISs and various fields of labor in CIS design and maintenance, as well as upgrades in CIS guidelines.

We conducted this study to help establish guidelines to improve the safety and usability of CIS through a systematic review and to analyze how the clinical workflow and usability principles are reflected differently in existing articles. We divided the steps of clinical workflow and performed a guideline review. Furthermore, this review sought clues to balancing CIS usability and safety.

## II. Methods

This review of CIS guidelines was based on a systematic review of the literature based on the results of searches on the related keywords. Detailed recommendations and principles of evaluation were extracted by reviewing the selected articles, whose components were classified and reassembled according to various criteria referenced in the selected literature to analyze how they affect clinical workflow. The present study protocol was reviewed and approved by the Institutional Review Board of Asan Medical Center (No. 2016-0980).

### 1. Systematic Review of Relevant Articles

Literature searches were performed in PubMed, Cochrane, EMBASE, Web of Science, and CINAHL using keywords related to health information technology (HIT), safety, and usability in guideline development published in English between January 2000 and December 2015 (Table 1). The protocol for this review was guided by the Preferred Reporting Items for Systematic Reviews and Meta-Analyses (PRISMA) statement.

The keywords used in the search were selected through discussions by the research team. Keywords were classified into three categories: guideline, HIT, and safety/usability. Each category was searched using OR for keywords and synonyms and AND between categories.

Articles containing recommendations, principles, and evaluation items for CIS design, usage, or evaluation were included. On the other hand, those with ‘content vague or with too narrow focus’, ‘issues irrelevant to safety or usability principle’, ‘no suggestion for guideline/recommendation’, or ‘unable to find full-text article’ were excluded.

Two researchers independently checked the titles and abstracts of the searched articles and conducted the first selection (Figure 1). Upon agreement between these two researchers, the selection of the documents to be included in the final evaluation was made through discussion with a third researcher. After securing the full text for the final selection, secondary review was performed independently by the first two researchers. Conflicts were resolved, and the final selection for the full literature review was made through a discussion by all three researchers. In case of non-agreement, the research team reached a decision through consultation.

### 2. Review of Selected Articles and Extraction of the Guideline Components

The selected articles were reviewed in terms of objectives, the type of articles, and nationality. The target system and methodology of the articles were also classified according to whether they presented a guideline or principle based on existing knowledge (e.g., literature review), empirical content (e.g., expert opinion or group discussion), user opinion (e.g., user survey or testing), or heuristic evaluations. The guidelines, recommendations, principles, or evaluation items from the articles were then extracted as guideline components.

### 3. Review and Re-classification of Guideline Components Affecting Clinical Workflow

We stratified the clinical workflow according to the following types of actions. A user identifies and selects patients’ data, records medical documents, orders medications or investigations, gets feedback from the system by alert or Clinical Decision Support (CDS), and manages and maintains the system. Therefore, the guideline components were classified according to clinical tasks (data identification & selection, document entry, order entry, clinical decision support & alert, and management) and usability principles (screen recognition, data view & entry, running & control, and feedback) following considerations of clinical workflow. The research team determined the final categories and methods for classifying the guideline components through discussion.

## III. Results

Among a total of 7,401 searched articles, 15 articles were finally selected through the systematic review. Table 2 summarizes the characteristics of the studies included in this systematic review. All but one of the studies were written in the United States (73%, 11/15) or Canada (20%, 3/15); the other was from the UK (Table 2). Almost half (47%, 7/15) of the articles were original research papers, followed by perspective, opinion, and commentary (5/15) and review articles (3/15). The article types were assigned based on information from the journals. For the target system, Computerized Physician Order Entry (CPOE) was the most frequent system, whereas Electronic Medical Record (EMR) was the least frequent (Table 3). Article review was the most common methodology (7/15), followed by expert opinion (6/15). An article review was followed by additional analysis in the majority of cases (4/7). Three articles concerned the results of user testing or surveys, and only two articles conducted heuristic evaluations.

Clinical components such as ‘drug-patient age checking’ were classified under ‘clinical tasks’, and usability components such as ‘clearly legible font’ were classified under ‘usability principles’. There were some conflicts within a given category. For example, default values for medication prescription are sometimes recommended (“The system should provide for selection from the dosages and forms that are available and appropriate for a given medication,” by Bell et al. ) and sometimes not (“System should limit or not use defaults for medications,” by Carvalho et al. ). A brief explanation, such as ‘Only enter default values for drug, dose, frequency, and route if it will always be correct’, balanced safety and usability.

Table 4 shows the results of the categorization of guideline components according to clinical workflow. Four of the 15 selected articles were classified as applicable to the entire process of the clinical tasks affecting clinical workflow. For example, “Content should be limited to 1–2 lines, with a justification separated by white space” by Horsky et al. for data identification & selection; “Monitor use of C/P functions in record preparation and limit use of ‘boilerplate’ content across records” by Zahabi et al. for document entry; and “Conducts a verification process to ensure that all medications comply with recommended dosing based on current evidence-based literature” by the Institute for Safe Medication Practices (ISMP) for order entry and CDS & alert. Within the clinical tasks, CDS and alert (13/15) and system management (9/12) were commented on by a majority of the articles. General principles of alert systems, such as alert priority or reduction of alert fatigue, were most frequently discussed in the articles (Table 5).

Two articles were classified as applicable to the entire process of selecting the usability principles affecting clinical workflow (Table 5). Running & control was the most frequently considered principle (10/15), and data view & entry was the least (4/15). The article by Zahabi et al. concerned the clinical tasks and usability principles affecting clinical workflow. The methodologies of the 5 commented articles were article review, group discussion, and expert opinion.

## IV. Discussion

In this study, we selected articles presenting guidelines or principles for CIS safety and usability that should be taken into account in the design, use, and management of such systems. We reviewed the target system and methodology and reviewed and summarized the guidelines and evaluation items to date. Also, we divided the steps of clinical workflow into the aspects of clinical tasks and usability principles. Articles focused on specific tasks (CDS and alert) (13/15). Also, among the usability principles, the components of data view & entry were relatively small (4/15). Articles showed a lack of diversity in clinical task and principle for each step of clinical workflow. All articles with inclusive clinical workflow components were based on existing knowledge or experience. To our knowledge, no study has reviewed the CIS safety and usability guidelines according to the detailed steps of clinical workflow.

### 1. Balance in Conflicts of Safety and Usability of CIS

Although improvement of usability is directed toward pursuing patient safety, some cases had conflicts, as mentioned above regarding default values for medication prescription. Recommendations like “Omit items for which the information is not available to the user,” which are intended to reduce cognitive load, could threaten patient safety if clinical workflow is not taken into consideration. Similarly, “Cluster related information on the same screen” and “Avoid too much information on the screen at one time” seem to be mutually contradictory without a consideration of the clinical situation.

Participation of clinicians and feedback to users can mitigate the conflicts in safety versus usability, as comments on the role of clinicians in system adaptation and order set pointed out. Some override functions have the risk of bypassing critical alerts, though they prevent alert fatigue, which reduces workflow efficiency. However, profiling and reporting the history of alert overrides can be helpful in cases where critical alerts are of overridden. Therefore, the consideration of clinical workflow from the user's point of view is important to balance safety and usability.

### 2. Challenges of Previous Studies: Localized Methodologies and Target Systems

As the terms of the systematic review were set to English articles, and all the selected articles were North American and UK studies. Among the selected articles were seven original research articles according to the publishers' classifications, but expert survey/group discussions constituted the majority of these articles. Few methodologies of heuristic evaluation were given, and only one article conducted a retrospective cohort study. The majority included existing knowledge (article review, expert opinion, or group discussion), and there were few articles on user testing/surveys.

Much of the content concerned CDS, actions, and management, but that on data presentation was relatively small. Only one-third (5/15) of the articles included all the steps of clinical tasks and/or usability principles affecting clinical workflow. Moreover, these 5 articles were based on existing knowledge, not up-to-date user experiences or experimental evidence. Article reviews and empirical knowledge are essential for the improvement of past error and usability problems. However, considering improvements in the speed of system performance and the development of infrastructure such as a CIS network, more active experiments and studies of systems-in-use and/or systems-in-advance will be needed.

There was no specific recommendation or consideration of the size or specificity of the medical institutions except for one document related to a GP system in primary care, Avery et al. (Table 2). The use of computers in medical institutions of various sizes has expanded the management of patient data. The need for the development of principles of information systems to ensure the efficient and safe exchange of information with primary care institutions and hospitals has increased.

Our findings were similar to those of previous systematic reviews on CIS safety/usability, in that most of the articles lacked a consideration of overall clinical workflow. In methodology, the majority were based on existing knowledge or empirical content and lacked an explicit theoretical framework or model, as Yen and Bakken commented.

### 3. Limitations

In this study, the components of more specific functions or tasks (e.g., patient lists, dashboards, or override alerts) were not included. Also, non-English articles and guidelines were not included, and as this study was a part of the guideline development process, experimental articles not containing guidelines or principles were excluded. This factor might have served to exclude more experimental research articles.

### 4. Conclusion

There was a lack of consideration of the entire clinical workflow in the selected articles. Also, in many cases, guidelines were developed through the synthesis of existing knowledge rather than through user testing or heuristic evaluations. Development of CIS guidelines affecting clinical workflow is needed for usability and patient safety. To promote the safety and usability of CIS, more user-oriented guidelines that take into account the clinical work-flow are needed.
