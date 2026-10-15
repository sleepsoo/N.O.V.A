---
title: "Proposal on Guideline for Quality Assurance of Radiation Treatment Planning System"
organization: "Korea Institute of Radiological and Medical Sciences"
year: "2017"
language: en
source_url: "https://synapse.koreamed.org/articles/1098580"
license: "CC BY-NC"
---
# Proposal on Guideline for Quality Assurance of Radiation Treatment Planning System

Progress in Medical Physics 28(4), December 2017 https://doi.org/10.14316/pmp.2017.28.4.197 pISSN 2508-4445, eISSN 2508-4453

# **Proposal on Guideline for Quality Assurance of Radiation Treatment Planning System**

**Yoonjin Oh*, Dong Oh Shin‡, Juhye Kim*, Nahye Kwon*, Soon Sung Lee§,** ΙΙ **, Sang Hyoun Choi** ΙΙ **, Sohyun Ahn** ¶ **, Dong-wook Park#, Dong Wook Kim†**

*Research Institute of Clinical Medicine, Kyung Hee University Hospital at Gangdong, †Department of Radiation Oncology, Kyung Hee University Hospital at Gangdong, ‡Department of Radiation Oncology, Kyung Hee University Hospital, §Department of Radiological & Medico Oncological Sciences, University of Science and Technology,ΙΙ Division of Medical Radiation Equipment, Korea Institute of Radiological and Medical Sciences,¶ Department of Radiation Oncology, School of Medicine, Yonsei University, Seoul, #Department of Radiation Oncology, Inje University Ilsan Paik Hospital, Goyang, Korea

**Received** 16 November 2017 **Revised** 18 December 2017 **Accepted** 19 December 2017

**Corresponding author** Dong Wook Kim (joocheck@gmail.com) Tel: 82-2-440-6071 Fax: 82-2-440-7393 **Corresponding author** Dong Oh Shin (ohsd32@gmail.com) Tel: 82-2-958-9467 Fax: 82-2-958-9469

We develop guidelines for the quality assurance of radiation treatment planning systems (TPS) by comparing and reviewing recommendations from major countries and organizations, as well as by analyzing the AAPM, ESTRO, and IAEA TPS quality assurance guidelines. We establish quality assurance items for acceptance testing, commissioning, periodic testing, system management, and security, and propose methods to perform each item within acceptable standards. Acceptance includes tests of hardware and network environments, data transmission, software, and benchmarking as specified by the system supplier, and apply the IAEA classification criteria. Commissioning includes dosimetric and non-dosimetric items for assessing TPS performance by applying the AAPM classification criteria and the latest technical items from the IAEA. Periodic quality assurance tests include daily, weekly, monthly, yearly, and occasional items by applying the AAPM classification criteria. System management and security items include the state and network connectivity of TPS, periodic data backup, and data access security. The guidelines for TPS quality assurance proposed in this study will help to improve the safety and quality of radiotherapy by preventing incidents related to radiotherapy.

**Keywords:** Radiation treatment planning system, Acceptance test, Commissioning, Quality assurance

## **~~Introduction~~**

Because of the rapidly aging population, the number of cancer patients has increased continually by 5.5% each year.1) In the U.S., approximately 50% of cancer patients receive radiation therapy, and in Korea, which has fewer cancer patients than the U.S, approximately 25% patients receive radiation therapy, with an annual increase of 6.2%.2) Radiation therapy plays an important role in cancer

treatment, and with the rapid development of medical technology and high-precision radiation therapy methods, the quality of life of cancer patients is gradually improving. Currently, in every medical institution, in order to safely perform high-precision, high-dose radiation therapy such as intensity-modulated radiation therapy, stereotactic body radiation therapy, and stereotactic radiosurgery, a systematized and periodic quality assurance and control (QA) approach for use with therapy equipment is very

> Copyright © 2017 Korean Society of Medical Physics

> CC This is an Open-Access article distributed under the terms of the Creative Commons Attribution Non-Commercial License (http://creativecommons.org/licenses/bync/4.0) which permits unrestricted non-commercial use, distribution, and reproduction in any medium, provided the original work is properly cited.

#### important.

The WHO reported that between 1976 to 2007, personnel training and improvements to treatment environments did not keep up with the rapid development of radiation therapy technology, leading to 55% of the deleterious causes of radiation therapy on patients to be related to radiation treatment planning.3) For example, in England’s North Staffordshire Royal Infirmary, a new treatment system was introduced, but owing to discord between the new and existing systems, from 1982 to 1991, there were over 1,000 instances of patients receiving the wrong radiation treatment.4)

The key reasons behind the incidents related to radiation treatment planning included an insufficient understanding of the radiation treatment planning system (RTPS), a lack of commissioning, and no verification of independent calculations, and that educational training and quality assurance processes were not properly managed.5,6) Currently, according to examinations of a domestic radiation therapy quality assurance organization, the Nuclear Safety & Security Commission, and published technical reports of the Korean Society of Medical Physics,7-9) quality assurance experts are available, and quality assurance performed mechanical dosimetry is recommended. However, currently quality assurance guidelines for RTPS do not exist. Thus, in this research, to improve the quality assurance of treatment planning, which when poorly executed is one of the causes behind main radiation therapy incidents and accidents, the current state of international quality assurance is analyzed, and RTPS quality

assurance guidelines are proposed.

## **~~Materials and Methods~~**

1. Current state of foreign radiation treatment planning quality assurance

Radiation treatment planning and the current state of QA from related foreign organizations were analyzed and organized, from which relevant standards and procedures were prepared. Several quality control items and methods were separated by type, compared, and evaluated. These include the proposed RTPS (radiation treatment planning system) described in “Quality assurance for clinical radiotherapy treatment planning (TG-53)”10) from the AAPM (American Association of Physicists in Medicine), “Commissioning and Quality assurance of computerized planning systems for radiation treatment of cancer”5) from the IAEA (International Atomic Energy Agency), and “Quality assurance of treatment planning systems. Practical examples for non-IMRT photon beams”6) from ESTRO (European Society for Radiotherapy & Oncology).

2. Radiation treatment planning system quality assurance items and procedures

The goal of this study was to prepare integrated RTPS QA guidelines by referring to the relevant information for radiation treatment planning systems from developed countries and international organizations, and to deduce

**Table 1.** Status of acceptance test.

|Items|AAPM|ESTRO|IAEA|
|---|---|---|---|
|Hardware|Check CPU, monitor, printer,and all peripheral instruments|(Not described)|Check CPU and memory, diskoperation, input/output devices|
|Network environment|(Not described)|Network connection|Network connection|
|Data transmission|(Not described)|Data transmission|Data transmission|
|Software|According to specification,mark as ‘exists/does not exist’|Basic patient registrationSystem function check|Verification of system functionsCheck calculation functionsCheck utilities|
|Benchmark test|Measurement of accuracy of thedose calculation algorithm andcalculation times under veryspecific circumstances withspecific beam data|Basic treatment descriptionVerification of dose distributionMLC field|Measurement of data for the photonbeams of two machines (4 MV and18 MV linear accelerators) and theresults of a series of testsTests under standard fields|

them in order to prepare implementation procedures. such as tolerances were checked. Guidelines were divided into RTPS acceptance tests and commissioning, periodic quality control, and system management and security, and the QA items and methods

**Table 2.** Status of non-dosimetric commissioning.

|Items|AAPM|ESTRO|IAEA|
|---|---|---|---|
|Check systeminstallation|(Not described)|(Not described)|Installation of system hardwareSoftware selectionDetailed parameter selection|
|Patient image data|Patient positioning andimmobilizationImage acquisition|Image registrationInput of outline data|Collection of patient dataInput and transmission of anatomical data|
|Outline creation|Anatomical description|Definition of anatomical structureOutline modificationConstruction of volumes|Creation of the anatomical model|
|Beam data checks|Beam arrangements anddefinitionMachine description, limits andreadoutsGeometric accuracyField shape designWedge, compensatorMethodology, algorithmsDensity corrections, etc.|Beam geometryBeam display functions (BEV, beamlocation/shape, Block location inBEV, MLC field, Bolus location,etc.)|Beam parametersBeam geometryField definitionWedges, Beam modifiersNormalizationsPlan output checkParameter checks and documentationSAD, SSD setupBEV, field checkPortal image indicator|

**Table 3.** Status of dosimetric commissioning.

|Items|AAPM|ESTRO|IAEA|
|---|---|---|---|
|Beam data input|Measurement of beam datasetTransfer of measured data fromwater phantomManual data entryVerification of input data|Data inputDocumentation|Transfer of measured data from waterphantomAlgorithm input data|
|Dose calculation|Square and rectangular fieldAsymmetric fieldsBlocked fieldsMLC-shaped fieldWedged fieldExternal surface variationsSSD variations|Open field and rectangular fieldBlocked fieldsMLC-shaped fieldsWedged fieldOff-axis fieldSSD variationsInhomogeneity|Square and rectangular fieldAsymmetric fieldsWedged fieldSSD variationsOblique incidenceComplicated surface formationBuild-up region|
||Inhomogeneity, etc.|Missing tissue, etc.|Density correctionInhomogeneity correctionCompensator, etc.|
|Examination ofdose calculations|1-D comparisonsDifference between FDD(fractional depth dose) and TPR2-D isodose curve|2-D and 3-D dose distributionDVH|Beam dependence verificationAlgorithms and clinical examination1-D comparison: Depth dose differencesaccording to field|
||Color wash dose indicatorDose difference indicatorDVH analysisDistance maps||2-D comparison: isodose curve3-D comparison: Comparison of 3-D dosedistribution and DVH|
|MU calculation|MU calculationMU calculation QAProcess Verification|MU calculation|MU calculationProcess verification|

## **~~Results and Considerations~~**

1. Current state of foreign quality assurance related radiation treatment planning

When purchasing and setting up a RTPS, as well as when performing updates, a clinically qualified medical physicist (CQMP), performs acceptance tests and commissioning in a manner similar to that needed for the use of radiation treatment machines, and the RTPS needs to be managed in part with periodic quality assurance. The AAPM proposed items and detailed information on the construction of a structure, acceptance tests, commissioning, and periodic quality control, for the QA of a RTPS. In addition, the IAEA and ESTRO guidelines for RTPS QA were proposed.

The RTPS vendor and the CQMP perform an acceptance test using the specifications, along with an inspection of the hardware and related equipment, algorithms, DVH, software, and a check of the system input and output during normal operations. For these items, the AAPM and IAEA propose hardware, software, and benchmarking inspection items. The ESTRO and IAEA recommend investigating network connections and data transmission (Table 1). The ESTRO does not describe acceptance test items for hardware and related equipment, but does recommend that during inspections of software and related items that the RTPS vendor and medical physicist roles and responsibilities should be separated.

For commissioning, the CQMP, after investigating various benchmarks, compares and verifies calculation results

and measured values during clinical operations to check whether usage is within an error tolerance. The AAPM divides such items into two categories: those that are related to dose and those that are not (Tables 2, 3). In particular, as a supplement the IAEA recommends comprehensive quality control items including asymmetric jaws, multi-leaf collimator (MLC), and similar new technologies.

For periodic quality assurance tests, the job of the CQMP is to check via acceptance tests and commissioning whether expected system functions are maintained in the clinic. The AAPM recommends investigating management items daily, weekly, monthly, and yearly, and the IAEA recommends the same at any time, but monthly and yearly. The ESTRO recommends that periodic QA based on acceptance tests and commissioning items be performed, but does not propose an inspection frequency for each quality assurance item, instead recommending that QA be performed to suit the conditions of each organization (Table 4).

System management and security are operations that include activities such as system maintenance and data backup and security of system use. The AAPM designates a system administrator and a computer system administrator, and recommends that system management and security operations be performed. For data management, development and maintenance of documented policies and procedures for patient data records and readouts are recommended. Moreover, to prevent data loss, every 5 to 10 years, records and important backup data should be stored separately. The IAEA recommends frequent data backup

**Table 4.** Status of periodic quality assurance testing.

|Items|AAPMESTRO|IAEA|
|---|---|---|
|Daily|Error and change log(Refer to items for acceptance test)|(Not described)|
|Weekly|Computer filesReview clinical planning|(Not described)|
|MonthlyYearly|CT data inputProblem reviewReview of RTP systemDose calculationData and I/O devices, critical software tools|CPUPlan detailsMUs/time|
|Variable|Beam parameterization|Backup recoveryCT (or other) scan transfer, geometryand density checkPatient anatomyMUs/time|

restorations as part of periodic QA operations, and the ESTRO restricts system access to those who have sufficient authorization, and recommends that valid inspection items be designed in the related departments according to their use.

### 2. Proposed guidelines for quality assurance of radiation treatment planning systems

#### 1) Acceptance test

An acceptance test is an examination as to whether the RTPS is operated according to specifications. Based on the specification standard provided by a vendor, acceptance tests include the introduction and repair of instruments, verification of the hardware and network environment during updates, data transmission, software functions and operations, and examinations that check accuracy, and benchmark tests (Table 5). The results of acceptance tests are documented and stored while the system is used, and are consulted during system maintenance.

#### 2) Commissioning

Commissioning is an operation that verifies items found to be insufficient in the acceptance test, and evaluates

**Table 5.** Items for acceptance test.

|Items|Test|
|---|---|
|Hardware|Check whether computer peripheraldevices operate according tospecifications|
|Network environment|Check all network connectionstransmitting data in the RTPS andthe network|
|Data transmission|Check CT and MRI image data,treatment plan data transmitted bythe RTPS, MLC data transmittedby the MLC control system, DRRdata, and data transmitted bythe compensator design device,simulation, and the radiationoncology management systems|
|Software|CT input and anatomicaldescription, beam data input, dosecalculations, dose indicators, dosevolume histograms, documentoutput accuracy checks|
|Benchmark test|Check calculation function usingstandard beam data|

whether the accuracy and measured values are within the allowed tolerances of an instrument by evaluating the RTPS performance and comparison measured data under various conditions. This is performed during the introduction of the system and during software version upgrades. When restoring the hospital network and related instruments, operations are divided into those that do and do not depend on dose.

#### (1) Non-dosimetric commissioning

Non-dosimetric commissioning includes procedures

**Table 6.** Items for non-dosimetric commissioning.

|Items|Test|
|---|---|
|System installationchecks and userdefinition|Hardware and software checksSystem limits checksPatient data checksData conversion of RTPSIndicators and output devices installationchecksTreatment plan protocol checksConversion of CT number to electron densityDatabase checks|
|Patient anatomicaldescription,transmission, andregistration|CT image acquisitionCT image indicator related toolsPatient anatomical data formation fromother non-CT image modalities andmanual operationsPatient database|
|Structure outlinecreation|Manual outline formation using CT imagesAutomatic outline formation using CTimages3-D structure formationOutline formation using interpolationAutomatic margin functionSet-up of relative electron densityBolus formation|
||Points and line marker definition|
|Beam data|System parameter checksSystem parameter limitsCollimator and jaw setupShielding block definition and formationMLCAutomatic field formationBeam installation checksGantry and collimator, treatment table angleWedgeBeamDRR|

for checking the RTPS installation, checking that items suit user-oriented use cases, acquiring patient image data, creating, transmitting, and recording anatomical structures, outline formation, three-dimensional structure formation, field selection, and beam data entry. Checking data transmission and display functions through a connected machine and the network, and checking connections with the linear accelerator are important. Non-dosimetric commissioning items are in Table 6, and the procedures are defined as follows.

First, to check the system installation and user environment, server instruments, and majority of the terminal equipment and peripheral devices, the whole system is assessed, and early parameters are determined. Second, to check the transmission and record of patient anatomical data, a phantom is used, wherein CT data is transmitted and its geometric data verified, and a check is made as to whether any problems arose with the CT image-related tools. Additionally, apart from the manual operation and CT images, other image modalities such as outline formation functions are verified, and patient data is confirmed to have been correctly entered and used. Third, to check the structural outline, whether by manual or automatic means, the outline functions that use CT images, 3D structure drawing functions, outline formation through interpolation, and automatic margin functions are checked to be within allowed errors. The relativistic electron density is manually set up, and whether or not changes in the density and MU value density reflections occurred for each pixel is checked. Additional checks include whether, the MU value changed with regard to the bolus function, points or lines exist, normal marks from markers are shown, and dose output is correct. Fourth, in order to check the beam data, the accuracy of data entry into the radiation treatment machine is checked. A check is also performed to verify that the field size and table field angle cannot be entered so as to exceed the regulated range of system parameters. Additionally, elements of the apparatus are examined, including the collimator and jaw, shielding block, MLC, automatic field, SAD and SSD, gentry, collimator, treatment table angle, and wedge. Finally, the beam and DRR target values are confirmed to lie within the allowed range.

#### (2) Dosimetric commissioning

The goal of dosimetric commissioning is to understand the dose calculation algorithms embodied in a RTPS, assess dose accuracy, minimize the uncertainty in dose calculations, and avoid inappropriate clinical use, while clearly delineating the clinically-allowed use range. The items in dosimetric commissioning are in Table 7, and the procedures are as follows.

First, to verify the beam model, measured and modeled beam data are compared to evaluate the modeling accuracy. Comparisons are performed with the deviation δ proposed by Venselaar et al.11) (Fig. 1), and the allowed standard is as seen in Table 8. The parameter δ 1 refers to a region that is a high-dose region, located above the beam’s central axis, and exceeding the maximum dose depth. A region with a small dose angle, δ 2, refers to the neighboring boundary where an increased dose and penumbral, inhomogeneous region exists. δ 3 refers to a region in a field exceeding the maximum dose depth, i.e., a high dose region with a small dose angle. δ 4 refers to a region outside the field, such as a penumbral region, with a low dose region and small dose angle. δ (RW50) refers to a field’s size deviation, and δ 50-90 refers to the deviation of a beam’s edge profile.

Second, to prevent errant investigations, a water phantom, 0.6-cc ion chamber, and 0.1-cc ion chamber were used as standard electrometers. With open square fields

**Table 7.** Items for dosimetric commissioning.

|Items|Test|
|---|---|
|Verification ofbeam modeling|Comparison of measured and calculatedbeam data|
|Verification undersimple conditions|Relative dose distribution and absolutedose verification|
|Verification in|Variation in SSD|
|clinical conditions|Open oblique incidence fieldWedged oblique incidence field|
||Missing tissueOpen off-axis field|
||Wedged off-axis fieldIrregular field|
||Build-up regionInhomogeneity correction (Rectangularinhomogeneous model phantom orhuman body phantom)|

**Fig. 1.** Location of dose calculation verification (solid line: measured profile, dot line: calculated profile).

**Table 8.** Tolerance of assessing dose for external radiation treatment.

|Doseevaluation region|(1) Homogeneous, open field,symmetry beam|(2) Simple inhomogeneous wedge,MLC-shaped field, asymmetry beam|(3) Beam used by thecombination of more than 2 types|
|---|---|---|---|
|δ1|2%|3%|4%|
|δ2|2 mm, 10%|3 mm, 15%|3 mm, 15%|
|δ3|3%|3%|3%|
|δ4|3% (30%)|3% (40%)|3% (50%)|
|δ(RW50)|2 mm, 1%|3 mm, 1%|3 mm, 1%|
|δ50-90|2 mm|3 mm|3 mm|

of 5×5, 10×10, 20×20, 30×30, 40×40, 5×20, 20×5 cm2 and rectangular-wedge-shaped fields of 5×5, 10×10, 15×15 cm2, the relative and absolute dose distributions were investigated. The relative dose distribution was analyzed by selecting a one- or two-dimensional comparison. In one dimension, in a cross-section passing through the isocenter, at least one standard-depth PDD, with a maximum depth of 10 cm, and in some cases, two depth profiles were compared. Absolute dose verification was performed at a standard depth and at several other depths, doses were evaluated, and dosimeters were placed in the isocenter. The tolerances are shown in Table 5. For the calculated value with a wedge and the MLC-combined beam, a higher tolerance was allowed than with the open beam.

Third, in clinical settings, minimizing dose calculation uncertainty and avoiding inappropriate use of calculation algorithms requires several pieces of equipment. A water phantom and 0.6-cc ion chamber, 0.1-cc ion cham ber, standard electrometer, tissue-equivalent solid phantom,

film, micro ion chamber, solid-state dosimeter, glass dosimeter, and thermoluminescence dosimeter (TLD) were used. As shown in Fig. 2, dose testing was investigated under various conditions. Implementation of the test was performed under various SSD conditions with a 10×10 cm2 field, and 80-, 100-, 130-cm SSDs, as shown in Fig. 2a. These conditions included an open oblique arrangement of a 10×10 cm2 incident field, 100 cm SSD, and 30° gentry angle (Fig. 2b), and a wedged-oblique inclination of a 10×10 cm2 incident field size, 100 cm SSD, 30° gentry angle. At the wedge angle frequently used, and at a wedge angle where algorithm errors are easily generated (Fig. 2c), the PDD and profile, and absolute dose above the beam central axis were evaluated. Within the incident field, the tissue loss condition was tested in a 20×20 cm2 incident field (Fig. 2d); field conditions included an open off-axis field and wedged off-axis field (Fig. 2e, 2f), and the indeterminate field condition was with respect to the MLC (Fig. 2g). Evaluations of the PDD and profile in each field, and of the absolute dose above the beam central

**Fig. 2.** Verification in (a) SSD variation, (b) open oblique incidence field, (c) wedged-oblique incidence field, (d) missing tissue, (e) open off-axis field, (f) wedged off-axis field, (g) MLC-shaped field.

axis, were performed. The buildup region condition was an inhomogeneous compensation condition using a rectangular inhomogeneous model phantom and a mock human phantom, and the dose distribution and abovebeam-center absolute dose according to the field size were evaluated.

3) Periodic quality assurance test

A periodic QA test checks whether the evaluated system performance and accuracy has been maintained and is reproducible, with respect to the RTPS acceptance test and

commissioning during ordinary radiation treatment. Its goal is to check the stability and security of the treatment data files, verify the accuracy and function of peripheral devices used for data entry, check the security of the TPS software and output instruments, and verify software operations and accuracy. Periodic QA tests are performed often—daily, weekly, monthly, and yearly (Table 9), and the data is organized and stored so that changing trends in the results over time can be checked.

Daily operations are performed to examine and repair errors and changes in records. Every week, examination of

**Table 9.** Items for periodic quality assurance test

|Items|Test|
|---|---|
|Daily|Review error logReview change log|
|Weekly|Verify computer filesVerify clinical plan|
|Monthly|Verify stability about CT data and CT value andrelative electron densityReview problems of RTPS and prioritize resolutionof problemsReview configuration and state of RTPS|
|Yearly|Check concordance between measured andcalculated doseReview accuracy of data and operation of I/O devicesReview important software|
|Variable|Check beam parameter and restartCheck software including OS and restart|

computer file security, re-examination of clinical treatment planning, and problem-solving operations are performed. Every month, examination of the security of the RTPS CT data entry is performed, and the status of all RTPS equipment is examined. The correspondence between the measured and calculated doses is checked, and data accuracy and input/output devices are examined, with important software operations performed yearly. Finally, mechanical updates and fixed-time beam are checked, and checks and resulting restarts of the system software, including the operating system, are performed.

treatment plan files, is backed up monthly.

## **~~Conclusion~~**

In radiation treatment, the quality assurance of a RTPS is a very important in preventing radiation treatment accidents and qualitatively improving treatment. Such QA is divided into acceptance tests and commissioning, peri odic tests, and system management and security. The verification and maintenance of RTPS performance and dose precision and accuracy are necessary for patient and equipment data management. Through this research, the key QA items from international reports by the AAPM, IAEA, and ESTRO on RTP QA are assembled and recommended, confirming that different QA items are recommended by each organization. Currently in Korea, reports from the Nuclear Safety and Security Commission examinations and the Korean Society of Medical Physicists are limited to the QA of radiation treatment items, and while their legal implementation and resulting recommendations are made, standards and procedures for RTP QA systems have not been prepared. The analysis of the current state of foreign QA guidelines in conjunction with the guidelines from this research can be used to establish an approach for RTPS QA, which will enhance radiation safety and improve treatment.

#### 4) System management and security

A RTPS is comprised of computer hardware and software, related equipment, and RTP software. A combined system has networked and divided graphical workstations and servers and associated equipment which require maintenance to ensure nominal system functions. For this, monthly software and hardware checks and daily, weekly, or monthly data backup operations are required.

To support software management, the RTPS server and its backup log are checked monthly. Hardware management is also performed monthly by examining the server and storage devices, uninterruptible power supply (UPS), workstation LEDs denoting their operational state, and network connectivity. New and modified files are backed up daily, all files related to treatment plans are backed up weekly, and the entire system, including the system software and RTP software, beam data files, and

## **~~Acknowledgements~~**

This work was supported by the General Researcher Program (NRF-2015R1D1A1A09056828), the Nuclear Safety Research Program (Grant No. 1603016) through the Korea Foundation of Nuclear Safety (KOFONS), and financial resources granted by the Nuclear Safety and Security Commission (NSSC) of the Republic of Korea.

## **~~Conflicts of Interest~~**

The author(s) indicated no potential conflicts of interest.

## **~~Availability of Data and Materials~~**

All relevant data are within the paper and its Supporting

Information files.

## **~~References~~**

1. Whosaeng: Increased radiation therapy in cancer patients (http://m.whosaeng.com/a.html?uid=94023).

2. KEIT. 2017. PD Issue report. Technology trend and industry status of radiation therapy equipment. Korea Evaluation Institute of Industrial Technology.

3. WHO. 2008. Radiotherapy risk profile. World Health.

4. RPOP. Short case histories of major accidental exposure events in radiotherapy (https://rpop.iaea.org/RPOP/ RPoP/Content/InformationFor/HealthProfessionals/2_ Radiotherapy/AccidentPrevention.htm).

5. IAEA. Technical Reports Series no. 430. Commissioning and quality assurance of computerized planning systems for radiation treatment of cancer. International Atomic Energy Agency, Vienna. 2004; 430.

ment planning systems. Practical examples for non-IMRT photon beams. European Society for Radiotherapy & Oncology.

 7. AAPM. 1998. Radiation Therapy Committee Task Group 53. Quality assurance for clinical radiotherapy treatment planning. American Association of Physicists in Medicine.

 8. NSSC. 2015. Notification no. 2015-005. Technological standards for radiation safety of medical field. Nuclear Safety and Security Commission.

 9. KSMP. AAPM Task Group 142 report. Quality assurance of medical accelerators. Korean Society of Medical Physics. 2016;142.

 10. S. Choi, D. Park, K. Kim, et al. Suggestion for Comprehensive Quality Assurance of Medical Linear Accelerator in Korea. Prog. Med. Phys. 2015;26(4):294-303.

 11. J. Venselaar, H. Welleweerd, B. Mijnheer. Tolerances for the accuracy of photon beam dose calculations of treatment planning systems. Radiother. Oncol. 2001;60(2):191-201.

6. ESTRO. 2004. Booklet no. 7. Quality assurance of treat-
