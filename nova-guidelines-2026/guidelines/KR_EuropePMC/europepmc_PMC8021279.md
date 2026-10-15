---
title: "Development of safety and usability guideline for clinical information system"
organization: "Medicine"
year: "2021"
language: en
source_url: "https://europepmc.org/article/MED/33787612"
license: "CC BY-NC"
---
# Development of safety and usability guideline for clinical information system

## Abstract

Clinical information systems (CISs) that do not consider usability and safety could lead to harmful events. Therefore, we aimed to develop a safety and usability guideline of CISs that is comprehensive for both users and developers. And the guideline was categorized to apply actual clinical workflow and work environment.

The guideline components were extracted through a systematic review of the articles published between 2000 and 2015, and existing CIS safety and/or usability design guidelines. The guideline components were categorized according to clinical workflow and types of user interface (UI). The contents of the guideline were evaluated and validated by experts with 3 specialties: medical informatics, patient safety, and human engineering.

Total 1276 guideline components were extracted through article and guideline review. Of these, 464 guideline components were categorized according to 5 divisions of the clinical workflow: “Data identification and selection,” “Document entry,” “Order entry,” “Clinical decision support and alert,” and “Management”. While 521 guideline components were categorized according to 4 divisions of UI: UIs related to information process steps, “Perception,” “Recognition,” “Control,” and “Feedback”. We developed a guideline draft with 219 detailed guidance for clinical task and 70 for UI. Overall appropriateness and comprehensiveness were proven to achieve more than 90% in experts’ survey. However, there were significant differences among the groups of specialties in the judgment of appropriateness (P <.001) and comprehensiveness (P =.038).

We developed and verified a safety and usability guideline for CIS that qualifies the requirements of both clinical workflows and usability issues. The developed guideline can be a practical tool to enhance the usability and safety of CISs. Further validation is required by applying the guideline for designing the actual CIS.

## 1 Introduction

Despite the controversy over safety and usability problems, clinical information systems (CISs) continue to expand and demonstrate their necessity, and efficiency Problems indicated previously, such as user adaptation, education, and software usability, are being addressed. However, there are continued efforts to use CISs more safely and efficiently. From the initial implementation issues, issues related to electronic medical records (EMRs) and computerized provider order entry (CPOE) systems have shifted to support users and promote more patient safety considering more advanced health information technology (HIT).

CISs have expanded not only as a means of maintaining medical records but also as a tool for data management, clinical decision support, user feedback, and patient monitoring. Diversification of CIS functioning allows more tasks to be performed with the same effort but increases the complexity of tasks as well as the risk to safety and usability. Therefore, it is necessary to consider more varied aspects of safety and usability of CISs.

As more complex tasks are required, specific usability principles are needed at each stage. In addition, various tasks and functions should be organically linked according to the flow of work. For this purpose, it is necessary to consider what kind of design factors affect the user. Thus, the need for design considering human factors, ongoing management and update, and safety and usability evaluation has increased.

For this reason, in the US, the government distributed safety and usability guidelines and assessment indicators for state-led CIS management. It has been used to evaluate the information system, and there were incentives or penalties to induce vendors or medical centers to actively cooperate. Though there are no government-led safety or usability guidelines for CISs in Korea, the need for CISs to promote healthcare quality improvement and patient safety has been steadily emerging.

Moreover, the general safety and usability guidelines may require modification depending on the national policy and domestic CIS environment. For example, in Korea, e-prescription is not legally permitted, and this must be considered when applying the guideline. In addition, users who have perspectives from the different backgrounds on the development and distributions of CIS from country to country should be considered.

To develop CIS safety and usability guidelines, various fields must be considered such as user education, system maintenance, and user interface (UI)-oriented design elements. According to a systematic review of 2012 HIT usability, the theoretical foundation for the usability of HIT must be strengthened for better validity. Thus, it is necessary to have an in-depth review of usability and clinical workflow to apply the existing usability theories to CISs.

In addition, there is a lack of consideration of actual clinical workflow, which may lead to a deviation from actual work or work environment. There is also a bias in the specific content of existing guidelines. In contrast to the 10% (32/343) of the medication-related content in the Design Basics for Health IT (National Institute of Standards and Technology Grant/Contract Reports NIST GCR 15–996), in the Healthcare Information and Management Systems Society electronic health record (EHR) Usability Evaluation Guide for Clinicians’ Practices, medication-related content accounts for about 50% (10/21). Many studies of usability or errors in CPOE and clinical decision support systems focus on medication errors rather than overall clinical workflows.

Therefore, a more practical and valid guideline based on both usability principles and overall clinical workflow is required. To this end, collaboration between UI professionals and real users, that is, healthcare workers, is needed for development and validation. Additionally, development and dissemination of guidelines for safety and usability that complement the limitations of existing guidelines are required because it should be universally applicable and available for CIS evaluation.

This study aimed to develop a guideline suitable for the workflow of medical practices and usability principles through systematic review of related articles and guidelines. Additionally, we considered the CIS environment of Korea throughout the process of guideline development through expert consultation from related specialties (i.e., medical informatics, patient safety, and ergonomics).

## 2 Methods

This study for CIS safety and usability guideline development was performed from August 2015 to July 2017. An extensive literature review for related source documents (i.e., articles and existing CIS safety or usability guidelines) was performed as a baseline study. The guidelines were extracted and summarized from the collected source documents through several group discussions. Then, the guidelines were divided into 2 groups—UI-related and task-related—and were revised and validated by related experts. The institutional review board of the Asan Medical Center (IRB no. 2016–0980) approved this study.

### 2.1 Systematic review for source documents

Literature searches were performed in PubMed, Cochrane, Embase, Web of Science, and CHINAL using keywords related to HIT, safety, and usability to develop guidelines published in English between January 2000 and December 2015 (Fig. 1). After 2 researcher groups reviewed the primary abstract, conflict resolution, and the final selection through full literature review were done through discussions among the researchers. The systematic review was conducted in adherence with the PRISMA guideline, and its process and results were reported in the previous study.

[그림/Figure] Figure 1 Flowchart of clinical information system safety and usability guideline development.

Existing guidelines were selected by discussion among the research team. These include the guidelines distributed by the National Institute of Standards and Technology, US government, Healthcare Information and Management Systems Society, and Department of Health & Human Services as well as “Inspired EHR” developed and distributed by Jeff Belden et al.

### 2.2 Extraction and categorization of the guidelines

The analysis of UI that could affect the usability and clinical workflow under the CIS was performed before classifying the guideline components. Thus, the hierarchical structure was developed consisting of general UI and task-specific components (Table 1). The 2 main elements were divided by purpose, such as evaluating the usability issues of general UI components and supporting clinical decision making or clinical practices, respectively. “Clinical workflow” classifies the process of identifying, recording, and prescribing patient information according to the flow of work. The detailed classification of clinical workflow contains

- Data identification & selection,
- Document entry,
- Order entry,
- Clinical decision support & alert, and
- Management.

**Table 1 The stucture for guideline collection and classification.**

| Level 1 | Level 2 | Level 3 |
|---|---|---|
| General User Interface Components | Screen recognition | Button, Icon/Symbols, Cursor, Menu, Tab, Label, Chart/Graph, Table/List, Window/Screen, Scroll, Pages, Preview, Color, Terminology, Layout |
| | Data view & entry | Searching, Sorting/Filtering, |
| | Running & control | Undo/Revert, Control, Setting |
| | Feedback | Warning, Pop-up, Error message/Notification |
| Task-specific Components (Clinical workflow) | Data identification & selection | Patient identification/Presentation of clinical information |
| | Document entry | Standard and terminology, EMR data, Entry, Entry formats, Templates |
| | Order entry | Basic requirements of order system, Medication order entry, Other order entry, Order processing and Completion |
| | Clinical decision support & alert | General principles of alert, Clinical decision support & alert for medication order/Other alerts and reminders |
| | Management | Information transfer, Maintenance, Help & education |

In case of UI, its general components were divided logically and sequentially using the information processing model. The detailed classification of UI contains

- Perception,
- Recognition,
- Control, and
- Feedback.

Based on the classified contents, detailed usability principles for each category (perception, recognition, etc) were summarized and revised after reviewing the main principles presented in various usability articles (Table 2). According to the classification criteria, cognitive process, actions, or tasks associated with each element were assigned to the second level, such as screen recognition for general UI components and data identification and selection for task-specific components. More detailed and contextual items were added to the third level to take advantage of clearer guideline components. For example, perception in the general UI components include items such as button, icon, and menu, and task-specific components include items reflecting clinical context such as patient list and selecting for patient identification (Table 1). As a result, the 4 main categories were given operational definitions suitable for this study, and 20 UI component-related principles were selected.

**Table 2 Usability principles for the general user interface components.**

| Information processing stage | Summary | Principles |
|---|---|---|
| Perception | The system should be designed so that the user can clearly perceive the various internal functions of the system using minimal perceptual resources. | Visibility, Distinctiveness, Emphasis |
| Recognition | Users should be able to design mental models for their systems easily and clearly, and they should be arranged in a familiar and logical way so that they do not go far beyond the users’ general expectations and the overall flow of the system | Clarity, Predictability, Briefness, Consistency, Structurality, Familiarity, Status display |
| Control | The system should provide a specialized environment that meets the various requirements for user's work and helps the user to achieve the desired goal flexibly and efficiently. | Controllability, Extendability, Task support, Task migratability, Simplicity, Customizability, Elasticity |
| Feedback | The system should increase the responsiveness to user behavior and provide users with the necessary information immediately and continuously so that they can work more smoothly and quickly. When errors occur, users can identify, correct, and repair the problems themselves. The system should also protect its users from dangerous environments. | Feedback, Error prevention, Safety and security |

### 2.3 Developing guidelines and validation by expert group survey

The developed guidelines were organized by combining the existing guideline components with the repeated classification and integration of the collected guidelines. The whole structure was divided into 2 rows in terms of UI components and clinical workflows, and each row was further divided into 3 columns (Fig. 2). Each column was set up with corresponding sub-elements, principles, and guideline components. From the developed guideline structure, the extracted guideline components were distinctly allocated and reinterpreted in a more systematic format.

[그림/Figure] Figure 2 The structure and examples of the developed guidelines.

The practical guidance for clinical workflow and UI were translated into Korean and adjusted to accommodate the regional characteristics. The self-assessment and improvement for the developed guideline were performed through group discussions and online survey. After reviewing and revising the translation, the guideline was shown to some experts for consultation. The groups of experts for consultation included patient safety experts, informaticians, and ergonomics specialists. The expert groups were surveyed to evaluate each detailed guideline for its comprehensiveness and appropriateness (yes or no question), and a free opinion description was additionally requested. Thereafter, the analysis of the difference of consultation results by experts was performed using the Chi-Squared test. In addition, the comments in free-text form in the experts’ survey were categorized according to their requests (Fig. 3).

[그림/Figure] Figure 3 Flowchart for consultation from the expert groups.

## 3 Results

### 3.1 Systematic review and extraction of the guideline components

Among 7401 searched articles, 16 documents were finally selected through the systematic review. In addition, 16 existing guidelines were selected through team discussions. After reviewing all the articles, 402 guideline components were extracted, and 874 guideline components were extracted by the existing guideline review. Each guideline component was numbered and tagged for original sources, additional explanation or examples, and target systems (Fig. 4).

[그림/Figure] Figure 4 Screen capture of listed guideline components.

Four hundred sixty-four guideline components related to clinical workflow were classified according to detailed classifications. The 521 guideline components were organized according to the types of UI components. In the case of the guidelines related to clinical workflow, the subcategories were classified into 3 levels (Table 3). At each lowest level, 219 detailed guidelines were described with figures for additional explanation (Fig. 5). On the other hand, the guidelines on the UI components were classified into 20 detailed usability principles corresponding to the 4 categories of perception, recognition, control, and feedback, and 70 corresponding detailed guidelines are described in Table 4.

**Table 3 Levels and the number of detailed guidelines according to clinical workflow.**

| Level 1 | Level 2 | No. of Level 3 | No. of detailed guidelines |
|---|---|---|---|
| Data identification & selection | Patient identification, Presentation of clinical information | 8 | 29 |
| Document entry | Standard and terminology, EMR data entry, Entry formats and templates | 10 | 35 |
| Order entry | Basic requirements of order system, Medication order entry, Other order entry, Order processing and completion | 13 | 56 |
| Clinical decision support & alert | General principles of alert, Clinical decision support & alert for medication order, Other alerts and reminders | 12 | 65 |
| Management | Information transfer, Maintenance, Help and education | 9 | 34 |

[그림/Figure] Figure 5 Examples of the detailed guidelines and figures for additional explanation.

**Table 4 Levels and the number of detailed guidelines according to user interface.**

| Human Information processing | Heuristic principles | No. of detailed guidelines |
|---|---|---|
| Perception | Visibility | 5 |
| | Distinctiveness | 3 |
| | Emphasis | 5 |
| Recognition | Clarity | 5 |
| | Predictability | 2 |
| | Briefness | 3 |
| | Consistency | 4 |
| | Structurality | 3 |
| | Familiarity | 3 |
| | Status display | 2 |
| Control | Controllability | 2 |
| | Extendability | 2 |
| | Task support | 4 |
| | Task migratability | 2 |
| | Simplicity | 2 |
| | Customizability | 2 |
| | Elasticity | 2 |
| Feedback | Feedback | 6 |
| | Error prevention | 8 |
| | Safety and security | 5 |

### 3.2 Validation by an expert group survey

A total of 10 experts responded to the validation survey. In evaluating comprehensiveness and appropriateness, more than 90% of the total detailed guidelines were appropriate. Based on the comments in the free-text form, concrete examples and further explanations in the guidelines for clinical workflow were most frequently requested (129/300). On the other hand, requests for modification of expressions in the guidelines for UI were the most common (26/73).

In the expert group survey on clinical workflow, an average of 92% of the responses showed that appropriateness was acceptable (Table 5). Among ergonomic specialists (96%), informaticians (91%), and patient safety specialists (92%), ergonomic specialists were more likely to rate the guidelines as appropriate than informaticians and patient safety specialists (P <.05). Comprehensiveness was positively evaluated by the experts with an average of 92%. Among ergonomic specialists (89%), informaticians (93%), and patient safety experts (92%, P <.05), the ergonomic specialists assessed the guidelines significantly more negatively in comprehensiveness than the informaticians (P <.05). Furthermore, there was no significant difference with other groups.

**Table 5 The percentages of positive answers from expert survey for the appropriateness and comprehensiveness of the guideline, including the differences in subcategories.**

| | Experts (number of respondents) | | | | |
|---|---|---|---|---|---|
| Category (number of detailed guidelines) | Ergonomics (3) | Medical informatics (4) | Patient safety (3) | Total (10) | P value |
| Clinical workflow (219) | | | | | |
| Appropriateness | 96.19 | 91.43 | 88.43 | 91.96 | <.001 |
| Comprehensiveness | 89.34 | 92.92 | 92.08 | 91.59 | .038 |
| 1. Data identification & selection (29) | 92.53 | 90.52 | 92.53 | 91.72 | .690 |
| 2. Document entry (35) | 87.62 | 88.57 | 81.90 | 86.29 | .083 |
| 3. Order entry (56) | 94.94 | 93.08 | 93.45 | 93.75 | .547 |
| 4. Clinical decision support & alert (65) | 92.05 | 92.12 | 90.51 | 91.62 | .643 |
| 5. Management (34) | 96.08 | 95.96 | 91.18 | 94.56 | <.001 |
| User interface (70) | | | | | |
| Appropriateness | 91.42 | 99.64 | 100.00 | 97.28 | <.001 |
| Comprehensiveness | 82.85 | 99.64 | 99.04 | 94.42 | <.001 |
| 1. Perception (13) | 78.21 | 100.00 | 100.00 | 93.46 | <.001 |
| 2. Recognition (22) | 87.12 | 100.00 | 100.00 | 96.14 | <.001 |
| 3. Control (16) | 88.54 | 98.44 | 98.96 | 95.63 | <.001 |
| 4. Feedback (19) | 92.11 | 100.00 | 99.12 | 97.37 | <.001 |
| Total (289) | | | | | |
| | 91.41 | 93.99 | 92.50 | 92.77 | <.001 |

In the expert group survey on UI, an average of 97% of responses showed that appropriateness was acceptable. Among ergonomic specialists (96%), informaticians (91%), and patient safety specialists (92%), ergonomic specialists were more likely to rate the guidelines as suitable than informaticians and patient safety specialists (P <.05). Comprehensiveness was positively evaluated by the experts with an average of 92%. Among ergonomic specialists (89%), informaticians (93%), and patient safety experts (92%, P <.05), the ergonomic specialists assessed the guidelines significantly more negatively in comprehensiveness than the informaticians and patient safety specialists (P <.05).

In the clinical workflow guideline, 11 detailed guidelines were inappropriate in appropriateness (more than 2 experts replied “negative”), and 22 were inappropriate in comprehensiveness. In the UI guideline, only 2 detailed guidelines were inappropriate in comprehensiveness (more than 2 experts replied “negative”). The most common free-text comment of negatively assessed detailed guidelines were “It needs more detailed explanation” or “It may be differently applied by situations”.

## 4 Discussion

Among the contents collected through the related article review, many conceptual contents, and ambiguous expressions are difficult to understand without a detailed explanation. In addition, the existing guidelines tend to contain UI-oriented guidelines that are unfamiliar to the user and clinical contents that are difficult for developers. The CIS guideline should be understood by both developers and users of various occupations; however, there are limitations to satisfying both. Through this study, the research team from various fields discussed the requirements and contents and made guidelines to support both the clinical workflow and usability of UI components. Through the creation of guidelines that are available to both users and developers, more than 90% comprehensiveness and appropriateness were identified by the experts in various fields.

Safety and usability guidelines were separated according to clinical workflow and UI components. The guidelines for the UI components classified the design requirements of CIS for more usable UIs considering the users and their environment. The guidelines for the clinical workflow were user-centered and developed to make it easier to present problems or errors that could occur while using CISs. In this study, the usability disturbance factors that could be generated while using CISs were described, and solutions were suggested. Moreover, dividing the guideline into clinical contents and UI-related problems allowed an in-depth consideration of each field.

The contents of the developed guidelines are related to not only specific events but also broad clinical workflow including usability concerns. The subcategories are divided to be used as comprehensively as needed. Based on this, it will be easy to expand the content from designing issues to usability of health records. As the usability principles were mapped with the detailed guideline, the intent of the guideline was clearly revealed, and it helped users through concrete examples or explanations.

In this study, researchers had gone through the following preliminary steps to have a consistent understanding of patient safety and usability. They reviewed the existing guidelines and related documents at the team meeting and shared related contents and issues. Medical information specialists and patient safety specialists with clinical experience had mainly provided opinions from the users’ perspective. Ergonomics specialists had conducted a separate study to identify UI problems specific to CISs through EMR/OCS reviews, user interviews, and surveys actually used at a medical institution. After the clinical-UI division of guideline development, researchers exchanged opinions organically, and shared and discussed the research results through regular meetings.

Korean hospitals show a high CPOE adoption rate (91.9%) because of the unique Korean health insurance system based on a single-payer system. Since the CIS in Korea has been developed in a domestic environment, universally applicable principles and guidelines are insufficient. To improve the safety and usability of the CIS, it is necessary to provide guidelines through various special fields that cover the design and use of the software. However, there are few opportunities for exchanges between the respective fields, and there is a lack of experience sharing for CIS implementation, usage errors, and efforts to improve. Therefore, this study has an attribution in that it can be used as reference in the development of other non-English-language guidelines in the future.

It is meaningful to collect opinions from experts in various fields to broaden the utilization of guidelines. In addition, this study reflects the necessity of user-friendly terms and the necessity of modulation for the domestic situation. Both universal application and localization are important for the guidelines to be used in practice. It is also important for users and evaluators to understand the guidelines. The non-English guideline was developed considering the above issues and received more than 90% positive evaluation of content and comprehension.

Though the guideline contents are validated quantitatively as appropriate and comprehensive (92.77%), there were significant differences among the consultant groups. The differences according to the background of the expert group (i.e., ergonomics—industrial engineering; patient safety, medical information—medicine) were identified. It should also be considered that there was a difference in the results of free-text form comments between the clinical workflow- and UI-oriented guidelines. While the evaluation of UI component-related guidelines from ergonomic experts was significantly worse, most of the comments (61 out of 73) of ergonomic experts showed that the depth of understanding in each field might be different.

While the guideline was developed by researchers with various specialties, there were significant differences in the field evaluation. It indicates that 1) sufficient discussion and understanding among the specialties are needed to achieve common goals, and 2) separate guidelines based on mutual understanding of each area of specialty can be reflected more effectively in real work. Moreover, very few ergonomic experts in Korea participate in healthcare research, and the low understanding due to this was discovered through this study. Continuous efforts are needed to include people with diverse expertise in the healthcare field. We are constantly striving for our research to arouse interest among ergonomic experts through related academic activities.

To develop the guideline, the existing guideline review as well as the related article review were performed so that the limitation of the existing guidelines could be identified and supplemented. The limitations identified in the existing guideline review process include:

- The content is concentrated in a specific area (e.g., medication-related problems),
- some contents can be compromised on the same topic (e.g., prohibit default values for dosing doses vs allow defaults for frequently used values), and
- clinical content is difficult for developers and ergonomics experts.

In addition, as for the selected articles through the systematic review process, some of the contents have ambiguous expressions and conceptual contents (e.g., “Speed is everything”) that cannot be comprehended without additional explanations. Moreover, some of usability-specific expressions are difficult for users to understand in practice (i.e., clinicians and healthcare providers).

In the process of organizing the guidelines of this study, the contents that could be understood inconsistently were clarified by putting the category separately, and the similar or redundant contents were collected and organized. As a result, 1276 guideline components were summarized effectively. The clinical workflow and the UI were divided into contents to fulfill the clearer purpose of use. In addition, a detailed explanation, examples, and pictures were compiled to facilitate easy understanding regardless of the field of specialization.

In this study, however, a systematic review of literature was confined to the English language, and the existing guidelines on review were limited to those led by the US government. Due to this limitation, a broader view of CIS safety and usability could be constricted. Additionally, the recent research literature was not included since the literature review was until 2016. Instead, we checked for updates to the existing guidelines (SAFER Guides, 2016) and reviewed the recently developed guidelines (ECRI Institute-originally founded as Emergency Care Research Institute, The Safe Use of Health IT in Patient Identification). SAFER guides 2016 added evaluation items for organizational responsibilities for safety strategy and patient privacy, contingency planning for ransomware prevention and system downtimes. ECRI's guideline for patient identification was developed based on the existing guidelines used for the development of our guideline. It was determined that the content did not require additions or modifications even after the review.

Although the expert consultation showed that more than 90% of the contents verified the appropriateness and comprehensiveness of the developed guidelines, there was still a need to supplement additional examples and explanations. In addition, to be applied to medical institutions of various sizes, it is necessary to collect more opinions from various types of users and environments. These limitations are expected to improve by reflecting on the feedback received after distributing and utilizing the guideline in actual medical practices.

Recommendations for situations that are likely to occur in the patient under special conditions are included, and the guidelines for pediatric patients (NISTIR 7865) were used as one of the source data. However, these considerations are limited to dose calculations or to display patient information (date of birth, anthropometric values). It is highly likely to dictate a direction that conflicts with other recommendations in terms of work efficiency (e.g., automatic input of the dosage or unit of measure for adults vs default value, as the adult standard dose is not allowed). In the clinical field, for vulnerable groups, such as children and the elderly, it may be difficult to protect their sensitive information and decision-making rights. For these factors to be reflected in the system, social consensus, and political foundation should be present prior to the system. However, equality in the clinical field is also an important factor in the quality of care, which should be considered when developing guidelines.

Validation is required by applying the guideline developed in this study for designing the actual CIS. After applying the guideline, quantitative, and qualitative assessments of how patient safety and usability are improved must be conducted in future studies. In addition, an evaluation based on the content of the developed guideline should be performed for the actual CIS, and the safety and usability must also be evaluated after improvement according to the evaluation. Such verification should be conducted with the CIS of various medical institutions to secure the reliability of the results. However, it is very difficult to implement it for individuals or in single study groups. In Korea, the national level EMR certification system is being prepared. The certification system is expected to be implemented effectively in the field when these guidelines are applied.

## 5 Conclusion

In this study, we developed a guideline for improving usability and safety of CISs that complements the limitations of the existing guidelines. Additionally, it is designed to be easily understood and applied by designers and users of various related fields. Deployment and upgrading of the developed guideline is still needed. It is encouraged to be used as a usability and safety evaluation item of CISs. Furthermore, the developed guideline can be extended to the areas of e-health and m-health in the future.

## Acknowledgments

We are grateful to the Asan Medical Library and its staff for their contribution to article search for guideline development.

## Author contributions

Conceptualization: Yura Lee, Sangwoo Bahn, Jae-Ho Lee.

Data curation: Yura Lee, Min-Young Jung.

Formal analysis: Yura Lee, Gee Won Shin.

Methodology: Yura Lee, Sangwoo Bahn, Taezoon Park.

Validation: Yura Lee, Sangwoo Bahn, Insook Cho, Jae-Ho Lee.

Writing – original draft: Yura Lee, Sangwoo Bahn.

Writing – review & editing: Taezoon Park, Insook Cho, Jae-Ho Lee.
