---
title: "Essential Data Elements for Laboratory Test Interoperability: An Expert Consensus-Based Framework"
organization: "Annals of laboratory medicine"
year: "2026"
language: en
source_url: "https://europepmc.org/article/MED/42236319"
license: "CC BY-NC"
---
# Essential Data Elements for Laboratory Test Interoperability: An Expert Consensus-Based Framework

## Abstract

The increasing digitalization of healthcare necessitates laboratory data interoperability to ensure reliable clinical decision-making, efficient data exchange, and effective secondary use. Most Korean institutions use electronic systems for laboratory test reporting. However, the lack of standardized terminology, measurement units, and data structures has led to reporting inconsistencies and limited integration across institutions. We have developed a guideline using a consensus-based laboratory data framework for essential laboratory data elements that is aligned with international standards and guidelines. The laboratory data framework organizes essential laboratory data elements into five categories: Patient, Test, Specimen, Date/time, and Administrative data. Each element is also assigned to one or more usage three tiers: Data for Clinical Data Interchange, Data for Report, and Data for Laboratory. Mandatory and conditional elements are further differentiated, incorporating aspects of clinical relevance, regulatory requirements, and implementation feasibility. The laboratory data framework incorporates terminology standards, such as the Logical Observation Identifiers Names and Codes, Systematized Nomenclature of Medicine–Clinical Terms, and Unified Code for Units of Measure, supporting both semantic and syntactic interoperability. This approach enables improved data consistency, facilitates national health information exchange, and lays a foundation for advanced applications, such as clinical decision support and artificial intelligence-driven analytics.

## INTRODUCTION

As the exchange of healthcare data across institutions becomes increasingly common, laboratory-related data may be subject to loss or inconsistent transmission. Unlike in the United States, where the Clinical Laboratory Improvement Amendments (CLIA) defines essential data elements for laboratory reporting, no equivalent regulatory framework exists in Korea, which may increase variability in laboratory report contents across institutions. A national reference guideline is needed to improve the consistency and interoperability of laboratory data and support the future utilization of large-scale healthcare data.

We present herein consensus recommendations on essential data elements for laboratory reporting in Korea, establishing a framework to support consistency and interoperability. This guideline provides a reference for clinical pathologists, medical technologists, informatics specialists, and laboratory information system (LIS) and electronic health record (EHR) developers, with clinical pathologists (primary producers of laboratory reports) playing central roles in its development.

This document does not provide implementation details, such as display formats, specific Logical Observation Identifiers Names and Codes (LOINC) assignments, or detailed unit specifications. For practical implementation guidance, including LOINC mapping, please refer to separate documentation. Issues of privacy, confidentiality, and data security are beyond the scope of this document and should be addressed according to national regulations and international standards, including Korea’s Personal Information Protection Act, Health Insurance Portability and Accountability Act, and International Organization for Standardization (ISO) 27799.

## GUIDELINE DEVELOPMENT METHODOLOGY

### Development group

This guideline was developed through a structured process involving dedicated development, writing, and review committees. Experts from various professional organizations participated to ensure broad coverage of laboratory medicine and healthcare informatics, including clinical laboratory professionals, informatics specialists, and regulatory experts. The committee members are listed in Supplemental Data Table S1.

### Development process

The development committee established the membership structure and determined the work direction. The writing committee comprehensively reviewed international guidelines and standards related to laboratory data interoperability, selecting and adapting the components most relevant to this guideline. Rather than involving a systematic review, the process emphasized harmonizing existing regulatory requirements with international standards.

Regulatory frameworks, such as CLIA §493.1291, and international standards, including ISO 15189:2022, define requirements for laboratory reporting. Accreditation tools, including the College of American Pathologists (CAP) checklist and Laboratory Medicine Foundation (LMF) Outstanding Laboratory Accreditation Program (OLAP), operationalize these standards. Interoperability specifications, like the Clinical and Laboratory Standards Institute (CLSI) AUTO17-ED1:2023, United States Core Data for Interoperability (USCDI) V6, and Korea Core Data for Interoperability (KR CDI) V2, provide practical guidance for essential data exchange. International initiatives, including the ISO Technical Committee (TC) 215 Health Informatics Standards, International Patient Summary (ISO 27269:2025), The Royal College of Pathologists of Australasia (RCPA) Pathology Terminology and Information Standardization, and Germany’s Medical Informatics Initiative, support global harmonization. Standardized data elements combined with controlled terminologies (such as those of the LOINC, Systematized Nomenclature of Medicine–Clinical Terms [SNOMED CT], and Unified Code for Units of Measure [UCUM]) enable machine-readable, semantically clear datasets suitable for advanced analytics and artificial intelligence (AI) applications. Supplemental Data Table S2 provides a comprehensive overview of how these standards align with our proposed framework.

Recommendations were developed in a series of committee meetings. Consensus was reached through iterative discussions and validation of each data element’s relevance, applicability, and feasibility across diverse laboratory settings. The draft was reviewed by the review committee to ensure accuracy, completeness, and clinical utility. Feedback was discussed in joint committee meetings, and recommendations were refined until consensus was achieved.

As a foundational reference framework developed through expert consensus rather than a systematic review, this guideline has inherent methodological limitations, including no formal expert selection criteria, conflict of interest documentation, or external validation. The applicability of individual recommendations might vary depending on the laboratory environment and specific characteristics of each institution. Accordingly, laboratories are encouraged to interpret and apply these recommendations in the context of their own institutional settings and laboratory-specific practices.

### Updates

This guideline will be updated every 3–5 yrs to reflect advances in healthcare information technology, evolving interoperability standards, accumulating evidence in laboratory data exchange, and key policy or healthcare changes.

## TERMINOLOGY DEFINITIONS

Fast Healthcare Interoperability Resources (FHIR) DiagnosticReportStatus: a standardized code set defined in Health Level Seven International (HL7) FHIR to represent the status of a diagnostic report (e.g., registered, partial, preliminary, final, amended, corrected, canceled). This code set supports structural interoperability by enabling consistent representation and exchange of the result status across systems.

Health information exchange: the secure, electronic transfer of patient health data across organizations, enabling providers and patients to access and share vital information for timely, safe, and cost-effective care

Interoperability: the ability of a system to exchange electronic health information with, and use electronic health information from, other systems without special effort by the user

LIS or laboratory information management system (LIMS): a software system designed to manage clinical laboratory operations, including laboratory workflows, data management, and sample tracking

LOINC: the international standard for identifying health measurements, observations, and documents

Semantic interoperability: the ability of systems to exchange data with shared, unambiguous meaning through standardized vocabularies and ontologies, enabling machine interpretation and seamless integration

SNOMED CT: systematically organized, computer-processable collection of medical terms providing codes, terms, synonyms, and definitions used in clinical documentation and reporting

Structural interoperability: the ability of systems to exchange data using standardized formats and transmission mechanisms, ensuring the data are structured and transmitted correctly but without assigning meaning to contents

UCUM: a standard terminology for units of measure based on the International System of Units (SI units) that provides standardized codes for unambiguous representation

Unique Device Identification (UDI): an international standard system that assigns a unique identification code to each medical device, enabling full life-cycle traceability from manufacturing and distribution to use and post-market management. This system is currently implemented in Korea, the United States, Europe, China, Saudi Arabia, Taiwan, and other regions.

## IMPORTANCE OF LABORATORY DATA INTEROPERABILITY

As healthcare systems become increasingly digitized, data interoperability has become essential for clinical decision-making, information exchange, and secondary uses, including big data analyses and AI development. Interoperability enables secure exchange of electronic health information across different information technology platforms without additional user effort.

In this context, laboratory data interoperability is critical for ensuring accurate test interpretation, clear documentation, and effective decision support while minimizing errors and unnecessary repeat testing, thereby reducing costs. Standardizing laboratory data strengthens public health surveillance and research by enabling accurate diagnoses and outbreak tracking. This process also supports AI applications, precision medicine, and future healthcare innovations.

## CURRENT STATUS AND CHALLENGES OF LABORATORY DATA INTEROPERABILITY

Despite its recognized importance, substantial challenges remain in achieving laboratory data interoperability. In Korea, most healthcare providers use electronic systems for laboratory requests and reporting; however, a nationwide management system for standardizing terminology and ensuring data interoperability is lacking. Healthcare institutions continue to use disparate test names and codes, with no unified regulations in place for result units, specimen types, or result formats. The first announcement of KR CDI in 2023 defined the minimum data elements for exchanging laboratory results, and the LMF published supporting articles. Growing interest in standardized, high-quality laboratory data for the AI era has spurred several relevant publications.

No consensus has been reached regarding essential data elements and management frameworks for laboratory medicine. Addressing these challenges requires harmonizing regulatory standards while maintaining flexibility and bridging international standards with local needs. We developed this document to provide structured guidance for achieving semantic interoperability across healthcare systems.

## LABORATORY DATA FRAMEWORK

### Framework development

A primary challenge in framework development is harmonizing diverse regulatory requirements while preserving flexibility. For instance, CLIA §493.1291 and CAP GEN.41096 require units “if applicable” or “when applicable,” ISO 15189:2022 requires units “where appropriate,” and USCDI V6 mandates units for quantitative results. This variability complicates the definition of mandatory data elements and highlights the need for clear guidelines on conditional information.

To address this variability, we developed a comprehensive data element framework with three dimensions based on considerations of clinical relevance, regulatory requirements, and implementation feasibility: five categories (Patient, Test, Specimen, Date/time, and Administrative data); three tiers (data scope levels); and two conditionalities (mandatory and conditional) (Fig. 1). Supplemental Data Table S2 provides supporting guideline references for each data element.

The three tiers are defined as follows:

Tier 1: Data for Clinical Data Interchange (CDI), which includes essential elements for exchanging laboratory test results between healthcare systems, ensuring semantic interoperability;

Tier 2: Data for Report, which covers essential elements for clinical laboratory test reports provided to healthcare providers; and

Tier 3: Data for Laboratory, which comprises elements that need to be maintained within the LIS to support test processing, results management, quality management, and regulatory compliance.

### Symbols used in the framework

Below, specific symbols are used to denote the tier for each data element (Table 1). Each standard symbol (solid style) indicates elements required for the Data for CDI, Data for Report, and Data for Laboratory categories. Each conditional symbol (outlined style) indicates elements required “when applicable.”

## ESSENTIAL LABORATORY TEST DATA ELEMENTS IN THE PROPOSED FRAMEWORK

### Patient data

#### Recommendations

1. The essential patient data elements are listed in Table 2.

2. Date of birth (DOB) instead of age should be recorded to ensure temporal accuracy and consistency across longitudinal laboratory data.

### Rationales

CLIA §493.1291 mandates a dual-identifier system (patient name and a unique identification number [ID]), whereas CAP GEN.41096, LMF OLAP, and the Korea Institute for Healthcare Accreditation recommend at least two identifiers (patient name, DOB, or ID) to ensure accurate laboratory test results and clinical-record linkage. Other common identifiers include the medical record number and health insurance ID, depending on the healthcare setting.

Among relevant standards and guidelines, only the LMF OLAP recommends including sex and DOB for clinical reporting. Sex and DOB are crucial demographics for accurate patient identification and clinical interpretation because reference intervals (RIs) often differ by sex and age. For example, the physiological patterns of analytes such as Hb, liver enzymes, and various hormones vary according to sex and developmental stage. Inaccurate or missing demographic data can lead to misapplied RIs, resulting in diagnostic errors or inappropriate clinical decisions.

Public health datasets often use age rather than DOB because of incomplete birth registration or missing data. However, we recommend using the DOB because age is a dynamic value recalculated each time records are accessed. EHRs typically calculate age based on the current date, which may not correspond to the patient’s age at the time of testing. For example, results reviewed long after testing may display the patient’s age at the review date rather than at testing. Conversely, the DOB remains constant and ensures temporal accuracy across longitudinal laboratory data, which is crucial when interpreting historical results or comparing values across time points.

### Test data

#### Recommendations

1. The essential test data elements are listed in Table 3.

2. Health care data standards for assignment: LOINC for test names, SNOMED CT for results and interpretations, UCUM for units of measure, and FHIR DiagnosticReportStatus for result status.

#### Rationales

Accurate test naming facilitates clear communication, result interpretation, and clinical utility. This practice links reported values to appropriate RIs and units, clarifies the test’s purpose, and ensures that the requesting physician understands the measured parameters. Consistent test naming facilitates longitudinal tracking, which is important for assessing progression and treatment responses. Ambiguous or inconsistent names can lead to misinterpretation, compromising patient safety. Standardization supports accurate laboratory practices and LIS/EHR interoperability.

LOINC provides unambiguous identification of laboratory tests, and its structured format captures key attributes (e.g., component, property, timing, system, scale, and method). The Korea Health Information Service’s commissioned research reports for 2023 and 2024 and the LOINC application guidelines provide institution-specific LOINC mapping.

Laboratory results may differ depending on the test method and individual in vitro diagnostics (IVDs) involved. Reporting the test method promotes transparency and reproducibility. For example, LMF OLAP checklist item 80.405.500 requires cytogenetic test reports to state the banding method, as different methods (e.g., G-, Q-, R-banding) affect the resolution and sensitivity of detecting chromosomal abnormalities and their clinical interpretations. However, when differing results do not affect clinical interpretation, specifying the method in the report is unnecessary. Laboratories should nevertheless retain test method information for comparison studies and to highlight analytical distinctions.

The US Food and Drug Administration’s UDI system identifies and tracks medical devices (e.g., IVD reagents and instruments) adopted by Korea’s Ministry of Food and Drug Safety. UDI inclusion was addressed in the CLSI AUTO17-ED1:2023 and USCDI V6, primarily in the context of semantic interoperability rather than laboratory reporting. Each UDI system consists of a device identifier (model/version) and production identifier with manufacturing details (e.g., lot and batch numbers, expiration date). Although direct UDI exchange is not always necessary when sharing laboratory test results, laboratories should retain UDIs for patient safety, regulatory compliance, and device-result linkage.

Laboratory test results are generated in various forms, including quantitative, qualitative, semi-quantitative, and narrative data, and the strategies required to ensure equivalence differ by data type. For quantitative results, interoperability depends on metrological equivalence, as variations in measurement methods, calibration systems, and reference materials can affect clinical interpretation. Comparability should, thus, be ensured through standardization based on metrological traceability to internationally recognized reference measurement systems. When standardization is not feasible, harmonization approaches that minimize inter-method variability are needed. Qualitative, semi-quantitative, and narrative results are particularly vulnerable to inconsistencies due to expression variability; thus, standardized terminologies such as SNOMED CT and code-based representation are recommended. To reduce the implementation burden on healthcare providers, supportive tools enabling automation and user-friendly integration, together with broad expert consensus, should guide their application.

Units clarify numerical values and ensure consistency across laboratories, making them essential for accurate test result interpretation. The ISO 15189:2022 and CLSI guidelines (e.g., EP28-A3c and C50-A) recommend reporting all quantitative results with appropriate units for patient safety and data integrity. Omitted or inconsistent units cause diagnostic errors and adverse outcomes. The SI system defines physical measurement units, whereas the UCUM provides machine-readable syntax for both SI and conventional units, supporting automated conversion and interoperability. Several non-SI units remain in use for many tests in Korean healthcare institutions. Considering local practices and international compatibility, we recommend adopting the UCUM for reporting units.

To enable meaningful interpretation of test results, appropriate criteria are required; these are typically provided in the form of RIs and/or clinical decision limits (CDLs; CDLs include diagnostic thresholds or cutoffs). RIs indicate whether a patient’s value falls within the central 95% of values observed in a healthy reference population (e.g., Hb 13–17 g/dL for adult males), supporting the clinical interpretation of test results. Laboratories should verify or establish RIs appropriate to their testing/target population and testing methods, considering the differences in demographics and pre-analytical factors. CDLs are clinically established diagnostic thresholds that guide diagnosis, treatment, and prognosis (e.g., HbA1c > 6.5% for diabetes diagnosis, specific LDL-cholesterol levels for guiding statin therapy). RIs and CDLs serve complementary roles but are often presented together without clear distinction in current practice. RIs may vary depending on demographic characteristics (e.g., age, sex, and ethnicity) and analytical methods, whereas CDLs established by national or international consensus (e.g., those from the American Diabetes Association for HbA1c and the American College of Cardiology/American Heart Association for LDL-cholesterol) should be reported in place of RIs when available. Laboratories should, thus, manage RIs and CDLs separately whenever possible. For qualitative, semi-quantitative, and narrative results, interpretive criteria are typically expressed using categorized or standardized terms that reflect findings commonly observed in healthy or non-diseased states (e.g., negative, non-reactive, no growth, wild type). Consistent use of standardized interpretive criteria across laboratories enhances comparability of results and supports accurate clinical decision-making.

Test results provide objective data; however, their clinical significance is not always self-evident or sufficient to guide patient management. Interpretation transforms raw data into actionable information for diagnostic and treatment decisions, consideration of pre-analytical and analytical factors, and recommendations for additional testing. Test interpretation is particularly useful when results are complex or ambiguous for clinicians. FHIR and USCDI define test interpretation as a coded categorical assessment conveying clinical significance (e.g., “normal/abnormal,” “low/high,” or “critical”). In Korea, reimbursement for certain high-complexity tests requires interpretation by a clinical pathologist.

Laboratory test results are usually reported as final, although preliminary findings might be released in emergency settings to support timely decision-making (e.g., microbiological cultures or bone marrow evaluation for leukemia treatment). The final report represents the definitive, fully validated, and approved result. Preliminary results should not replace final reports for definitive diagnosis. Revised results, when issued, provide corrections or additions to a previously released report. Clear designation of test result status prevents misinterpretation and ensures clinical reliability by avoiding the use of outdated or unconfirmed data. Laboratories should apply test result status categories as defined in the HL7 Laboratory Report framework, aligning them with local operational needs and reporting practices.

Critical values are laboratory results suggesting a life-threatening condition requiring prompt intervention. Prompt notification of the responsible clinician enables rapid diagnosis and treatment, which can improve patient outcomes. For example, severe hypokalemia requires immediate treatment, as it can precipitate life-threatening cardiac arrhythmias. Critical value flags help ensure that urgent notifications are not overlooked, facilitating a timely clinical response and preventing delayed diagnosis and treatment.

Error flags (e.g., delta check alerts or instrument-generated error codes) indicate potential errors that could affect patient safety. Error flags help laboratory staff identify and correct errors during result verification before reporting, reducing diagnostic mistakes and supporting quality management. Such flags may arise during the pre-analytical, analytical, or post-analytical phases. Notification methods can be determined by individual laboratories according to their operational needs. Error flags are mentioned specifically in CLIA §493.1291 but are not addressed in other semantic interoperability frameworks.

Delayed report flags indicate when retesting, resampling, or technical issues postpone the expected reporting time, thereby preventing unnecessary inquiries and alerting clinicians to exceptions that might affect patient management. Transparent delay communication fosters trust and enables clinicians to adjust care plans. Analyzing delayed report flags helps laboratories identify the causes of reporting delays and improve operational efficiency.

### Specimen data

#### Recommendations

1. Essential specimen data elements are listed in Table 4.

2. The level of granularity regarding specimen type (e.g., blood) may differ between collection and analysis. For example, a specimen might be recorded as blood at the time of collection but further specified as serum, plasma, or whole blood after pretreatment. The appropriate level of detail also varies depending on the purpose. For example, when guiding specimen collection, a more specific classification (such as arterial blood or capillary blood) may be necessary, whereas for result interpretation a broader category, such as blood, may be sufficient. Specimen types should be recorded with granularity appropriate to the testing stage (e.g., collection, analysis) and their intended clinical or operational use.

3. The specimen site should be documented when applicable, particularly for tests in which it directly impacts result interpretation or clinical decision-making, especially in microbiology and anatomical pathology.

4. The specimen type, site, and quality should be encoded using SNOMED CT to ensure semantic interoperability.

5. The specimen identifier, although essential for internal tracking and sample management, is local and should be managed within the LIS.

#### Rationales

Pre-analytical errors (primarily related to specimen quality and handling) comprise 80%–90% of all laboratory errors. These errors delay or distort test results, influencing treatment decisions in approximately 70% of cases and imposing a substantial financial burden. Maintaining specimen integrity to reflect in vivo conditions ensures accurate and reliable test results. ISO 15189:2022 Clause 7.2 mandates standardized handling procedures to minimize pre-analytical errors.

Specimen identifiers facilitate internal sample tracking, audit trail maintenance, and error mitigation. The CLSI PRE01-ED1:2024, CLIA §493.1291, ISO 15189:2022, and CAP checklists do not require specimen identifiers in clinical reports, whereas USCDI V6 requires them for structured data exchange. As the specimen identifier is used primarily for operational (e.g., referred tests) and tracking purposes, it is classified as a Laboratory (L)-tier element.

The specimen type determines test selection, handling protocols, and RIs for proper interpretation. The choice of specimen type can markedly impact test performance and result interpretation (e.g., lower, rather than upper, respiratory tract specimens exhibited higher sensitivity in detecting coronavirus disease 2019). Many assays are validated for specific specimen types, and misidentification can lead to invalid results or misinterpretation. Between-matrix differences (e.g., venous vs. arterial blood, EDTA vs. heparinized plasma) can affect test results, reinforcing the necessity of accurate specimen type documentation. As examples, arterial blood typically shows a higher partial pressure of oxygen (pO2) and pH than venous blood, with a lower pCO2, requiring different RIs, and B-type natriuretic peptide concentrations were notably lower in K2-EDTA plasma than in heparinized plasma.

The specimen site is conditionally required to balance completeness with reporting efficiency, particularly when its identification determines accurate interpretation. This distinction is crucial in different contexts, such as microbiology, where the collection site strongly influences result interpretation and clinical decision-making. For example, distinguishing between peripheral and central blood culture specimens helps differentiate contamination from true bacteremia. Similarly, identifying right or left iliac crest bone marrow aspirates can aid in assessing focal disease involvement. International standards require documentation of specimen site information when clinically relevant, though terminology varies (e.g., specimen source in the CLIA §493.1291 and CAP checklist, body site (source) in the CLSI AUTO17-ED1:2023, type of primary sample with source or site information in the ISO 15189:2022, and specimen source site in the USCDI V6 ).

Specimen quality is a fundamental requirement for reliable laboratory testing. Poor specimen quality (e.g., hemolysis, clotting, contamination, insufficient volume) correlates with operational inefficiencies and costs. Glucose levels may decrease by 5%–7%/h without glycolysis inhibitors; RNA preservation depends on stabilizing agents during transport and storage; and hemolysis can introduce substantial analytical errors by falsely increasing potassium, lactate dehydrogenase, and aspartate aminotransferase or by decreasing sodium and glucose concentrations. Consistent specimen quality documentation across systems ensures data integrity and reliability.

### Date and time data

#### Recommendations

1. Essential date/time elements are presented in Table 5.

2. The specimen collection date/time are required when clinically indicated.

3. When specimens are transferred through multiple laboratories, the date and time of receipt at each testing laboratory should be documented.

4. The FHIR dateTime standard should be followed to ensure intersystem consistency and interoperability.

#### Rationales

Accurate date/time documentation is essential during testing. Unlike imaging or functional tests performed directly on patients, laboratory testing occurs after specimen collection and transport, often involving delays or transfers between multiple institutions. Recording temporal data at each testing phase supports interpretation, tracking, and clinical decision-making, and real-time documentation enhances interoperability and timely care.

Specimen collection date/time information directly affects sample suitability and is critical for studying time-sensitive analytes, such as therapeutics, hormones, and circadian markers. Accurate information also enables monitoring of turnaround times and supports outbreak tracking in public health. The Centers for Disease Control and Prevention emphasized that precise specimen collection timing was vital for diagnostic accuracy with time-sensitive infections.

Requirements vary across standards: USCDI level 0 and LMF OLAP mandate collection dates/times; ISO 15189:2022 and CAP GEN.41096 mandate dates and, when clinically necessary, times (7.4.1.6 a; 7.4.1.7 a); and the CLIA §493.1291 requires only the test report date. Despite the importance of both timestamps, documentation remains inconsistent in many European laboratories. In Korea, the collection time is not routinely documented owing to limited awareness, high volume workflow burdens, and a lack of automated systems. Considering these practical challenges, our framework designates the specimen collection time as “applicable,” required only when clinically necessary. With advancing digitization, the collection time should become mandatory, and real-time capture will enhance documentation accuracy.

Documentation of the specimen receipt date/time at the testing laboratory is required for pre-analytical process tracking, especially when specimens are transferred between multiple laboratories. Although the date/time of test performance is not directly used in clinical interpretation or external data exchange, this information supports internal quality assurance and traceability, consistent with the general records management principles outlined in ISO 15189:2022 (8.4.1). The test date/time were addressed only in LMF OLAP and USCDI level 0 and were not required by most reporting standards; our framework classifies it as an L-tier element.

The reporting timestamp indicates the official release of results; determines decision-making timelines; provides a legal audit trail; and is required by ISO 15189:2022 (7.4.1.6 a), USCDI level 0, and CLIA §493.1291.

### Administration data

#### Recommendations

1. Essential administration data elements are presented in Table 6.

2. Specialist interpretation is required for tests involving interpretive reporting.

3. Laboratory-level metadata (e.g., institution name, accreditation, or external quality assessment [EQA]) should indicate the testing institution.

#### Rationales

Laboratory information identifies the testing institution and establishes an accountability trail, ensuring patient safety and supporting quality assurance, especially when between-laboratory variability might influence test results and clinical interpretations. Essential elements include the laboratory name, address, and contact details. CLIA §493.1291, CAP GEN.41096, ISO 15189:2022 (7.4.1.6 b), and LMF OLAP support this requirement. Notably, ISO 15189:2022 further mandates the identification of examinations performed by referral laboratories, including their names (7.4.1.7 c).

Laboratory quality information, including accreditation and the EQA status, demonstrates technical competence and operational reliability. Accreditation confirms adherence to established standards (LMF OLAP, CAP, or ISO 15189). The EQA status indicates participation in and, where applicable, certification of inter-laboratory performance evaluations through recognized programs (e.g., Korean Association of External Quality Assessment Service, CAP surveys, Royal College of Pathologists of Australasia quality assurance programs). Although not directly required for data exchange, these indicators provide valuable context for healthcare providers and enhance the quality of reported results; hence, they are classified under the Report and Laboratory tiers. In Korea, EQA participation is not mandatory, and participation rates remain markedly low: a 10-yr national analysis reported mean EQA participation rates of only 1.9% for clinics and 27.7% for small-to-medium hospitals. Under these circumstances, explicit documentation of the EQA status in laboratory reports provides meaningful quality information beyond the accreditation status alone.

Personnel information identifies key individuals involved in testing. The requesting physician’s information is mandated in KR CDI V2, CAP GEN.41096, and ISO 15189:2022 (7.4.1.6 c and 7.2.3.1 b), linking tests to clinical context and enabling timely communication. Missing physician information can delay result notification, particularly in resource-limited settings. Personnel documentation supports accountability tracking, traceability, and quality control. CLIA §493.1283 mandates maintaining records identifying personnel who performed each test, whereas CLIA §493.1425 outlines testing personnel responsibilities, including specimen processing, test performance, and result reporting.

Documenting the names and credentials of interpreting specialists is essential for clinical and legal accountability, particularly in genetic testing or complex diagnostics, where interpretive judgment markedly impacts patient care. ISO 15189:2022 requires that interpretive comments from qualified personnel be provided and that their identity and credentials be documented in both internal records and final reports, when applicable (5.3.3, 6.2.2, 7.4.1.6, 7.4.1.7). This practice supports transparency, reinforces medicolegal defensibility, and fosters clinician confidence in the reported results.

## ELEMENTS NOT INCLUDED IN THE PROPOSED FRAMEWORK

Several elements, although commonly maintained in the local LIS, were deliberately excluded from the mandatory or conditional requirements of our framework owing to practical implementation challenges, redundancy considerations, or scope limitations, as discussed below.

### Test data

#### Result-harmonization status

The result-harmonization status (USCDI level 0 ) has limited practical use and lacks standardized representation. Although conceptually desirable, its inclusion is hindered by limited practical utility, a lack of expert consensus on harmonization across individual tests, and implementation challenges in Korea’s healthcare system.

#### Supporting charts and nomograms

ISO 15189:2022 (7.4.1.6.h) and LMF OLAP recommend including biological RIs, CDLs, or supporting diagrams and nomograms in laboratory reports. However, these elements were excluded due to limited applicability, a lack of standardized formats, and variability at different institutions.

#### Test-development status

The ISO 15189:2022 (7.4.1.6 i) and LMF OLAP recommend using the test-development status to distinguish routine patient testing from non-routine testing (e.g., for research and development). However, this element was considered outside the scope of this guideline, which is focused on routine clinical reporting.

#### Page number, including total pages

The ISO 15189:2022 and LMF OLAP recommend including page numbers in patient reports for completeness. However, page numbering was considered a formatting element rather than an essential semantic data element and was therefore excluded.

### Specimen data

#### Specimen collection method

The specimen collection method is referenced in the CLSI AUTO17-ED1:2023 and USCDI level 0; however, it relates to semantic interoperability rather than mandatory reporting. Although excluded from the core data set, laboratories may want to consider documenting clinically relevant collection methods when necessary.

#### Additives

The CLSI AUTO17-ED1:2023 highlights the relevance of additives, and ISO 15189:2022 mandates additive details in pre-collection instructions (7.2.4.2.b). Examples include the type of anticoagulant, presence of a gel separator, or inclusion of specific stabilizers. However, additive details are often inferred from the combination of specimen type, container code, and test order. A separate additives field was considered redundant and excluded.

#### Fasting status

ISO 15189:2022 emphasizes verifying the fasting status when applicable (7.2.4.4 b), but such verification depends on patient self-reports and is rarely documented in LIS or EHR systems. Despite clinical importance for glucose or triglyceride tests, practical considerations led to its exclusion.

#### Specimen origin

Specimen origin refers to the individual, organ, or tissue from which the specimen was derived (e.g., human versus animal, liver, tumor). The CLSI AUTO17-ED1:2023 and HL7 FHIR define this as the observation focus when different from the patient on record. The specimen origin was excluded as a separate element because the same purpose can be met by specifying specimen types (e.g., “amniotic fluid,” “cord blood”) with appropriate identifiers.

### Administration data

#### Referral status

LMF OLAP, ISO 15189:2022, CLIA §493.1291(i) (3), and CAP GEN.41096 mandate referral laboratory information. Because our framework recommends documenting performing laboratory information, a separate referral status field was considered unnecessary.

## GUIDELINE UTILIZATION

### Developing standardized reports

This guideline provides the first framework for systematically organizing laboratory data elements for use in developing standardized laboratory reports. Figs. 2 and 3 illustrate how the proposed framework can be applied practically: quantitative and interpretive test reports requiring specialist interpretation with essential data elements (i.e., patient demographics, test results, laboratory information) are organized according to a three-tier structure.

### National healthcare data integration

Data for CDI aligns with national initiatives, such as the Personal Health Record (PHR) Project and Health Information Exchange (HIE) program, enabling patients to access and share laboratory data across institutions. This integration supports the Health Screening Program of the National Health Insurance Service (NHIS) and is essential for comprehensive health management of the national population.

### Applications in research and public health

When applied to the structuring of national datasets (e.g., NHIS, Korea National Health and Nutrition Examination Survey, Korean Genome and Epidemiology Study), this guideline supports data integration. Standardized data elements facilitate linking diverse laboratory data sources, thereby improving research accuracy and efficiency. Adopting international standards, such as LOINC and SNOMED CT, enables seamless data integration for clinical research and public health applications.

### Stakeholder benefits

For laboratory professionals, this document provides evidence-based guidance for structuring test reports in accordance with international standards and local practices. For software developers implementing LISs and EHRs, the defined data elements offer a blueprint for developing interoperable interfaces. The framework supports the incorporation of AI and advanced analytics by promoting machine-readable, semantically clear datasets.

### Current standardization status in Korea and importance of this guideline

The KR CDI selects data elements based on immediate exchange needs and the current standardization status. Consequently, some laboratory result elements may not be included due to limited readiness in practice. This guideline provides a comprehensive set of essential data elements, enabling advance preparation in real-world settings and offering a valuable resource for future updates to KR CDI and other national initiatives.

## FUTURE DIRECTIONS

As Korea builds centralized health information platforms (PHR, HIE, Health Information Highway), inconsistencies in test names, codes, and units hinder interoperability. Implementing this guideline framework is essential for unifying the national health data infrastructure. Priority tasks include adopting international standards, such as LOINC and SNOMED CT, unit standardization, qualitative results mapping, and UDI integration. Policy support, regulatory guidance, and incentive mechanisms will be critical for widespread adoption. A coordinated implementation plan with clear milestones will facilitate a smooth transition across systems. Clinical pathologists are positioned to lead ongoing maintenance, ensuring alignment with technological advances and international best practices.

## SUPPLEMENTARY MATERIALS

Supplementary materials can be found via https://doi.org/10.3343/alm.2026.0051.
