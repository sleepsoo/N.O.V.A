---
title: "항공안전분야 인공지능 개발 지침"
organization: "Korea Air Force Aviation Safety Agency"
year: "2025"
language: ko
source_url: "https://www.kjasem.org/journal/view.html?doi=10.46246/KJAsEM.250007"
license: "CC BY-NC"
---
# 항공안전분야 인공지능 개발 지침

*Guidelines for the Development of Artificial Intelligence in Aviation Safety*

**THE KOREAN JOURNAL OF AEROSPACE & ENVIRONMENTAL MEDICINE**

### **Review Article**

## **항공안전분야 인공지능 개발 지침**

**김대호**

**공군 항공안전단**

## **Guidelines for the Development of Artificial Intelligence in Aviation Safety**

**Daeho Kim, Ph.D.**

**Republic of Korea Air Force Aviation Safety Agency, Seoul, Korea**

**Received:** February 26, 2025 **Revised:** March 12, 2025 **Accepted:** March 19, 2025 **Corresponding Author** Daeho Kim Republic of Korea Air Force Aviation Safety Agency, 77 Yeouidaebang-ro 22-gil, Dongjakgu, Seoul 07056, Korea Tel: +82-2-827-7735 Fax: +82-2-827-7735 E-mail: daehoda@hanmail.net **ORCID** https://orcid.org/0000-0001-9013-3381

In recent years, artificial intelligence (AI), a collection of core technologies leading the 4th Industrial Revolution, is playing an important role in national innovation. AI is not just a new technology, but an innovative technology that brings about widespread changes in industrial and social structures and is a key driving force that will lead to strengthening the quality of life and national competitiveness of the people. The aviation safety sector also expects AI technology to be used as an error prevention and risk management tool in aircraft design and operation, aircraft production and maintenance, environmental problems, and airport operation. The national strategies of advanced countries for AI include securing professional manpower, securing their own AI technology, establishing an ecosystem and establishing ethics for human-centered AI development. However, most AI-related strategic plans and operational guidelines in the public sectors, including aviation, are focused on technology development and services, so they do not consider essential items such as reliability and ethics when developing and applying AI in the public sector. Therefore, this study aims to present guidelines that should be considered and applied when developing and introducing systems using the latest AI technology in the aviation safety and public sector.

Keywords: Artificial intelligence, Aviation safety, Guideline

#### **I. 서 론**

4차 산업혁명 기술의 비약적인 발전은 각 조직의 역량을 좌우하 는 핵심 키워드로 자리하고 있다. 특히, 4차 산업혁명을 선도하는 핵심기술의 집합체인 인공지능(artificial intelligence, AI)은 국 가 혁신에 중요한 역할을 담당하고 있다. AI는 단순한 신기술이 아 니며 4차 산업혁명을 이끌 핵심동력으로써, 산업·사회 구조의 광

범위한 변화를 불러오는 혁신 기술로 국민 삶의 질과 국가 경쟁력 강화를 가져올 수 있다[1].

Davos Agenda를 주최한 세계경제포럼에 따르면 AI는 2030년 까지 세계 경제의 15조 달러 이상 이바지할 것으로 전망하고 있 으며, 이는 세계 국내총생산(gross domestic product, GDP)의 14%를 차지하고, Google, Apple, Amazon 등 기업들은 범용 AI 플랫폼으로 다양한 AI 제품·서비스 개발을 통해 시장을 선점하기

위해 노력하고 있다. IBM 등의 기업들은 의료, 금융, 법률과 같은 특정 산업영역에 특화된 전문 AI 플랫폼 고도화와 생태계 구축에 주력하고 있다[2].

항공분야도 유럽항공안전기구(European Aviation Safety Agency)의 보고서[3]를 참고하면, AI 기술은 항공기 디자인과 운 영 측면에서 조종사의 효과적인 의사결정 지원시스템, 최적 운항 시스템, 조종사-AI teaming, 최적 훈련 프로그램 개발 등의 솔루 션으로 적용될 것을 예상하고 있으며, 항공기 생산과 정비 분야 에서는 디지털 트윈, AI-기반 예측정비가 가능할 것이고, 그 외에 도 환경 문제 저감, 공항 운영에 있어서 외부이물질피해(foreign object damage) 예방 및 공항보안, 그리고 위험관리 도구로 활용 할 수 있을 것으로 밝히고 있다.

우리나라 정부는 경제·사회 전반의 혁신 프로젝트로 과학기술정 보통신부를 비롯한 전 부처가 참여하여 마련한 ‘인공지능 국가전 략’을 발표하고 추진전략 및 계획을 실행 중이다[4]. 우리나라 국 가 AI 전략은 AI 반도체 핵심기술 확보와 신개념 반도체 개발, AI 교육체계 구축, 최첨단 정보통신기술(Information and Communication Technology, ICT)을 기초로 하여 전자정부에서 AI 기반 지능형 정부로 탈바꿈, 일자리 안전망 확충, 그리고 AI 윤리 정립 등으로 사람 중심의 AI 시대를 만드는 정책적 노력을 기울이 고 있다. 그러나, 현재 항공분야를 포함한 공공분야 대부분의 AI 관련 계획 및 운영지침은 기술개발과 서비스 위주로 작성되어 있 어, 개발 및 적용 시 필수적으로 참고해야 할 AI 신뢰성, 도입 고려 사항 등의 내용은 숙고하지 못하고 있다.

따라서, 본 연구는 주요국의 AI 동향, AI 세부기술의 현황 분석 과 적용동향을 고찰하고, 항공안전분야 및 공공분야에서의 AI 신

뢰성 가이드라인과 최신 AI 기술을 활용한 시스템 개발 및 도입 시 고려 사항에 대해서 제시하고자 한다.

#### **II. AI의 이해와 현황**

##### **1. 각국의 AI 전략 동향**

현재 AI는 경제 및 사회 발전의 핵심 동력으로 전망되고 있으며, 선진국은 AI 기술력을 선점하기 위해 국가 차원의 전략 및 대책을 마련하고 있다[5,6]. 본 절에서는 AI 분야의 대표적 선도국가인 우 리나라와 미국, 유럽연합(European Union, EU)의 현황에 대해 서 고찰하도록 한다.

첫 번째, 우리나라는 AI 분야의 전문인력 확보와 자체 AI 기술 력 확보, 생태계 구축은 아직 미진하지만, 국가 대응 전략을 마련 하고 있으며, 대표적인 경제·사회 전반의 혁신 프로젝트로서는 과 학기술정보통신부를 주관으로 전 정부 부처의 참여로 마련한 ‘인 공지능 국가전략’이 있다[4]. 국가전략에는 세계 최고의 메모리 반 도체 경쟁력을 지렛대로 활용해 AI 반도체 경쟁력 세계 1위를 목 표로, 핵심기술 확보와 신개념 반도체인 차세대 메모리 반도체 Processing-In-Memory 개발에 전략적으로 투자를 강화하는 방 안이 있다. 또한, 어릴 때부터 쉽고 재미있게 software와 AI를 배 우고 모든 연령, 직군에 걸쳐 전 국민이 AI 기초 역량을 습득할 수 있는 교육체계의 구축, 최첨단 ICT 기반을 토대로 세계적 수준의 전자정부를 넘어서는 AI 기반 차세대 지능형 정부로의 탈바꿈, 수 준 높은 공공서비스의 제공, 혜택을 모든 국민이 고루 누릴 수 있 는 일자리 안전망 확충, 그리고 AI 윤리 정립 등을 통해 사람 중심 의 AI 시대를 만드는 정책적 노력 강화가 있다.

**Table 1.** US AI R&D area and core programs

||**Strategic priority**|**Key R&D challenge**|
|---|---|---|
|1|A long-term investment in artificial intelligence research: a great transformation inevery part of society, coordinate long-term federal investment in AI R&D|Advanced air mobility, agriculture utilizing AI, etc.|
|2|Developing effective methods for Human-AI collaboration that achieve optimalperformance, efficiency, safety, and well-being through advanced AI technologies forhuman augmentation, visualization, and Human-AI interfaces|AI usefulness, artificial social intelligence, autonomousexploration in science and engineering, etc.|
|3|Promote understanding of ethics, law, and social impact: development of designmethods for reliable AI that meet ethical, legal, social goals and expectations|Improving AI risk management playbook, designingresponsible software systems, etc.|
|4|Ensure safety and security to ensure that AI systems work in a controlled, well-defined, and understand manner|Guaranteed autonomy, secure AI, secure and reliablecyberspace, etc.|
|5|Develop share public data sets and environments for AI training and testing that enablesearch, access, and use|Advanced AI-based programs, advanced informationsystem technology, open knowledge networks, etc.|
|6|Measure and evaluate AI technology with standards and benchmarks to address safety,reliability, accuracy, usability, interoperability, robustness and security|Development of AI standards, AI verification, validationand evaluation, autonomy/integration/test, etc.|
|7|Identify the demand for national AI R&D personnel, Fostering AI R&D manpower USleads future AI innovation|Education/training and human resources developmenttasks of government agencies|
|8|Expanding public-private partnerships to accelerate the development of AI andstrengthen the national R&D ecosystem|Accelerating healthcare partnership, digital assistants forscience and engineering, mission-oriented AI and datascience challenges, etc.|

US: United States, AI: artificial intelligence, R&D: research and development. Data from the article of National Science and Technology Council. (2023) [9].

두 번째, 미국의 국가 AI 정책 기본 방향은 국가 AI 이니셔티브 법에 의거 마련된 국가 AI 전략인 ‘국가 AI 이니셔티브(National Artificial Intelligence Initiative)’[7]가 있다. 국가 AI 이니셔티 브의 주요 내용은 AI 개발에 있어서 미국의 리더십을 유지하고, 신 뢰할 수 있는 AI의 개발과 이용에 있어서 세계를 선도하며, 사회와 경제 각 부문 적용을 위해 인력을 준비하고, 미국 연방기관에서 추 진하는 AI 사업에 대한 상호 정보를 공유하는데 그 목표를 두고 있 다. 국가 AI 이니셔티브의 실행과제는 혁신(innovation), 신뢰할 수 있는 AI 발전(advancing trustworthy AI), 교육훈련(education and training), 인프라(infrastructure), 다양한 활용(applications) 및 국제협력(international cooperation)의 6가지 전략 방향(pillars)이다[8]. 백악관 과학기술위원회(National Science and Technology Commission)의 예산계획에서는 AI 연구개발 (research and development) 과제를 전략적 우선순위에 따른 8 개 분야로 구분하고 세부적인 연구개발 과제를 기술하고 있으며, Table 1에서 정리한 바와 같이 AI 연구의 국제협력에 대한 원칙적 이고 조정된 접근방식을 포함하여 실행과제를 제시하고 있다[9].

세 번째, EU의 AI 전략은 AI 기술 능력과 신뢰성을 확보하여 산 업 역량을 강화하고, 동시에 인간의 기본권을 강화하는 것에 중 점을 두고 있다. 유럽 집행위원회는 2018년부터 ‘유럽을 위한 AI’ 전략에서 AI기술발전과 위험대처에 대한 균형 있는 접근과 관련 사항에 대한 법제화를 하고 있다[10]. 관련 AI 법안은, 2021년 4

월 유럽 의회(European Parliament)와 유럽 이사회(European Council)의 요구에 의거, AI 활용·투자·혁신 강화, AI개발·활용 신 뢰, 기본권 보장, 그리고 이용자 안전 강화를 위해 제안되었으며, 2023년 6월 14일 본회의에서 법안을 가결했다. EU AI 법안의 주 요 내용은 Table 2와 같이 핵심 정리할 수 있다[11]. EU AI 법안 속 위험관리 규정 요건은 AI 기반모델이 인간의 건강 및 안전, 기 본권, 환경, 민주주의, 법규 등에 대해 초래하는 위험을 적정한 설 계, 시험, 분석을 통해서 식별, 감소 및 완화 관리해야 한다는 것이 다. AI 기반모델 개발 기간에 AI 위험관리를 위해 독립적인 외부 전문가로부터 자문 받아 시스템 개발 및 적용 시 다양한 위험을 검토 및 예측해야 하며, AI 시스템의 서비스를 위해 잔여 위험을 문서화 하고, AI 시스템 생명주기의 다양한 단계에서 광범위한 테 스트를 수행해야 한다. 그리고 기반모델의 법률 준수를 추적하기 위해 품질관리 시스템을 구축해야 한다.

##### **2. AI 주요기법**

AI는 인간의 인지, 추론, 판단 등의 능력을 컴퓨터로 구현하기 위한 기술 또는 그 연구 분야 등을 총칭하는 용어로 정의되고, 기 계가 상황을 인지하여 이성적·논리적으로 판단·행동하며, 감성적, 창의적인 기능을 수행하는 능력까지 포함한다[12]. 사람 고유의 능력을 컴퓨터에서 구현해 보고자 시작된 것으로, 사람의 지능과 관련된 의사결정, 문제 해결, 학습 등의 활동을 자동화 하는 것으

**Table 2.** Main contents of the European Commission AI law

|**Content**|**Main content**|
|---|---|
|1The direction of propulsion|Proposing the direction of AI regulation- Ensuring compliance with existing laws regarding the safety of AI within the EU, fundamentalrights and values of the EU- Eliminating legal uncertainty to drive AI investment and innovation- Improve governance on basic rights and safety requirements applicable to AI systems,enhance the enforcement effectiveness of existing laws- Promote the development of the EU single market and prevent market fragmentation forlegal, safe and reliable AI systems|
|2Risk-based regulatory approach3Regulation and punishment of high risk AI systems|AI risk 3 level: risk level (unacceptable risk, high risk, non-high risk, low or minimal risk) takinginto account the impact on human fundamental rights and safety- Unacceptable risk: risk of infringement on EU values, such as fundamental rights violations- High risk: risk that could pose a significant risk to people’s health, safety and fundamentalrights- Non-high risk, low or minimal risk: a low risk of violating people’s health, safety andfundamental rights· Perform regulation in proportion to the risk level of the AI- Establish a regulatory framework proportional to the level of risk for AI systems, appropriatelegal interventions if risks are reasonably expected in the near future Imposing legal obligations on high risk AI system providers and users for safe use of high riskAI systemsPenalties proportions to the severity of regulatory violations, penalties are imposed inconsideration of the possibility of economic coexistence with the interests of small suppliersand startup|

EU: European Union, AI: artificial intelligence. Data from the article of European Commission. (2021) [11].

###### 로 정의한다[13].

AI 기술의 발전에 따라 기존 공공분야, 산업기반 및 사회 전반 에 끼치는 영향력이 클 것으로 예상한다. 글로벌시장 조사기관 인 Statista [14]는 세계 AI 시장 규모를 2021년 956억 달러에 서 2030년 1조 8,475억 달러로 성장할 것으로 전망하였다. Rudnitsky [15]는 Fig. 1과 같이 ChatGPT와 Gemini 등 소비자용 AI 도구 출시에 힘입어 생성 AI시장이 2022년 400억 달러에서 2032년 1조 3천억 달러 규모로 성장할 것으로 전망했다. 단기적 으로는 AI 학습 인프라가, 중장기적으로는 대규모 언어모델(large language model)용 추론 기기와 디지털 광고, 전문 소프트웨어 와 서비스가 생성 AI 시장의 성장을 주도하며 향후 10년간 연평균 성장률이 42%에 이를 것으로 전망하고, 생성 AI가 전체 정보통신 기술(information technology, IT) 하드웨어, 소프트웨어 서비 스와 광고 지출, 게임 시장에 영향을 줄 것을 예상하고 있다. 향후 생성 AI는 관련 기술 분야의 운영 방식을 근본적으로 뒤바꾸며 폭 발적으로 성장하여 IT 분야, 광고 분야, 사이버 보안 분야에서 핵 심 기술이 될 것으로 전망하였다. 최대 성장 동력인 소프트웨어는 AI 모델 학습용 데이터 인프라, AI 생성 기반 디지털 광고, 생성 AI 어시스턴트 소프트웨어 등이 있으며, 하드웨어 측면에서는 AI 서버, AI 스토리지, 컴퓨터 비전 AI 제품, 대화형 AI 기기 분야에 서 견인할 전망으로 나타났다.

AI 기술의 주요 기법은 인공신경망(Artificial Neural Network, ANN), 심층 신경망(Deep Neural Network, DNN), 합 성곱 신경망(Convolutional Neural Network, CNN), 순환 신 경망(Recurrent Neural Network, RNN), 생성적 적대 신경망 (Generative Adversarial Network, GAN), 트랜스포머(Transformer), 연합학습(Federated Learning), 지도학습(Supervised Learning)·비지도학습(Unsupervised Learning), 강화학습(Reinforcement Learning)·심층 강화학습(Deep Reinforcement Learning), 전이학습(Transfer Learning), 그리고 설명 가능한 AI (eXplainable AI, XAI) 등으로 정리할 수 있다[16].

첫 번째, ANN은 사람 뇌의 뉴런 작용을 참고하여 데이터 패턴 을 구상한 컴퓨팅 기술로 뇌에서 뉴런들의 신호 전달 과정의 연결

###### 형태를 수학적으로 모방한 모델이다.

두 번째, DNN은 ANN보다 복잡한 패턴을 학습하고 인식하는 컴퓨팅 기술로 학습을 향상하는 모델이다. ANN에 비해 적은 수의 unit으로 모델링 할 수 있는 장점이 있다.

세 번째, CNN은 이미지 관련 AI 알고리즘으로, 이미지 인식 분 야에 주로 사용되는 신경망 구조이다.

네 번째, RNN은 순차적으로 데이터를 변환하는 알고리즘으로, 반복적이고 순차적인 데이터 학습에 특화된 순환구조를 이용하여 과거의 학습된 결과를 현재 학습에 반영한다.

다섯 번째, GAN은 이미지 생성용 AI 알고리즘으로 실제 데이터 와 유사한 데이터를 생성하고, 결과를 비교하면서 성능을 개선하 여 합성된 데이터를 생성한다. 데이터 증강 분야에 활용할 수 있지 만, 딥페이크(deepfake) 영상, 생체 인식 데이터 위조 등 관련 기 술의 오용에 대한 부작용이 있을 수 있다.

여섯 번째, Transformer 기술은 자연어 처리에 있어서 기계번역 시 나타난 문제를 해결하기 위한 알고리즘으로, 병렬화를 통해 대규 모 데이터 세트를 학습할 수 있게 하였고 계산 효율성을 향상시켰다.

일곱 번째, Federated Learning은 개인정보보호를 위해 개발 된 AI 모델로, 보유 데이터를 분산 학습시켜 모델을 업데이트 하 는 방식이다. 여러 기관이 보유한 방대한 데이터를 이동시키지 않 고 학습시킬 수 있어 데이터의 유출 위험이 없이 원하는 데이터를 도출할 수 있다.

여덟 번째, Supervised Learning은 주어진 데이터에 정답이 있 는 경우 사용하는 학습모델이며, Unsupervised Learning은 정 답이 없는 데이터에서 패턴이나 구조를 찾아내는 학습모델이다. Supervised Learning은 예측모델을 만드는데 중점을 두며, Unsupervised Learning은 데이터의 구조를 이해하는데 중점을 둔 다. 이와 같은 학습모델은 대규모 데이터 정제에 많은 시간과 비용 이 드는 문제점을 해결하였으며, 새로운 학습데이터의 정제, 자연 어 학습, 이미지 복원 분야에서 활용되고 있다[17].

아홉 번째, Reinforcement Learning은 시행착오적 방식으로 동작하는 학습모델로, 반복 학습 과정에서 보상 시스템을 이용하 여 학습 효과를 높인다. 환경 내에서 특정 목적을 달성할 때 보상

**Fig. 1.** Chat-GPT to fuel $1.3 trillion AI market by 2032. AI: artificial intelligence. Ada pted from the article of Rudnitsky. (https://www.bloomberg.com/ news/articles/2023-06-01/chatgptto-fuel-1-3-trillion-ai-market-by2032-bi-report-says) [15] with original copyright holder’s permission.

을 하는 방식의 알고리즘이다. 예를 들어 게임에서 인공지능이 높 은 점수를 얻기 위한 전략을 학습할 때 사용된다.

열 번째, Transfer Learning은 특정 분야에서 학습한 지식을 다 른 분야에 재학습시켜 원하는 모델로 생성하는 방법이다. 특정 분 야의 모델을 유사 분야에 재사용함으로 데이터가 부족한 경우에 빠르고 효과적으로 모델을 생성할 수 있다.

마지막으로, XAI는 AI의 판단에 대한 근거를 사람이 이해할 수 있도록 제시하는 알고리즘으로 현재 AI 기술의 한계인 불투명성 에 대한 판단근거를 설명하는 기술이다. 모델 내부에 설명 가능한 모델(알고리즘)을 추가하여, 결과와 그 근거를 제시하는 방향으로 연구되고 있다. 특히, 설명 가능한 AI는 의사결정에 논리적 근거가 필요한 분야에 고려되고 있으며, 미 국방부 산하 고등연구계획국 (Defense Advanced Research Projects Agency)은 AI 알고리 즘의 해석 모델을 개발하고 있다. 설명 가능한 AI 모델의 개념도 는 Fig. 2와 같다[18].

##### **3. AI 주요 적용 분야 및 세부 요소기술**

AI 구축범위는 상황인지, 자기학습, 패턴 인식, 자연어처리, 음 성인식, 컴퓨터 비전 등의 분야로 계속 발전할 것이며, 각 산업의 다양한 서비스로 적용될 것으로 전망된다. 현재 우리나라 AI 기 술의 주요 적용 분야와 전략 기술은 AI 기반 교육서비스, 자가학 습 기반(self-supervised learning) AI 솔루션, automated machine learning (AutoML) 솔루션, 공간정보분석 및 공간 빅데이 터 융·복합 솔루션, AI 소재 설계시스템, edge-device 기반 실시 간 지능 플랫폼, 학습데이터 증식 및 오류방지 솔루션, 빅데이터 기반 마켓 인텔리전스 플랫폼(market intelligence platform), 그리고 단순반복 업무 자동화(robotics process automation, RPA) 시스템으로 정리할 수 있다[19,20].

첫 번째, AI 기반 교육서비스는 AI 기술을 접목한 차세대 교육 (에듀테크, EduTech)을 의미한다. 우리나라 국내 주요 교육 기 업은 에듀테크에 전폭 투자하고 있으며, 공공 교육 분야에서는

2025년 AI 디지털 교과서를 적용할 예정이다. AI 디지털 교과서 는 맞춤형 AI 기반 교육서비스를 제공하기 위한 기반 기술과 기술 인프라가 필요하다. AI 기반 교육서비스 세부 요소 기술은 학습자 행동 측정 및 모델링 기술, 학습 데이터베이스 구축, 분석, 운영 기 술, 콘텐츠 분석기술, 학습자 패턴 분석 및 평가 기술, 학습자 성적 예측 모델링, 문제 컨텍스트 추론기술, 실시간 정·오답 예측 모델 링, 그리고 맞춤형 학습 콘텐츠 추천 기술 등이다.

두 번째, self-supervised learning AI 솔루션은 초거대 AI 모 델 구현을 위한 핵심 기반 기술로서, 사람에 의한 데이터 레이블링 (labeling) 없이 컴퓨터가 스스로 데이터로부터 유의미한 특성을 학습하는 기술이다. 세부 요소 기술로는 시각, 언어, 시계열, 그래 프 데이터 기반 자가학습 기술, 멀티모달(multi-modal) 자가학습 기술, 그리고 초거대 AI 구축 기술 등이 있다.

세 번째, AutoML 솔루션은 기계학습, 딥러닝 과정을 자동화하여 AI 모델을 개발하는, ‘AI를 만드는 AI’ 기술이다. AI 시스템 개발 소 요가 폭등하고 있는 시점에서 AI 연구개발 전문인력의 부족을 극 복할 수 있는 기술로, 비전문가도 활용 가능한 그래픽 사용자 인터 페이스(graphic user interface)기반 AutoML 솔루션이다. AutoML 솔루션 세부 요소 기술로는 데이터 구조 및 ML 문제 자동 식 별, 데이터 전처리 및 피처 엔지니어링 자동화 기술, 최적 알고리즘 및 하이퍼 파라미터 설정 자동 탐색 기술, 최적 인공신경망 구조 자 동 탐색 기술, ML 모델 성능 평가 자동화 기술, ML 파이프라인 최 적화 기술, 그리고 AutoML을 위한 컴퓨팅 자원 효율화 기술이다.

네 번째, 공간정보분석 및 공간 빅데이터 융·복합 솔루션은 공간 정보를 활용하여 가상의 공간상에 빅데이터를 매시업(mashup) 한 서비스 구현 기술을 의미하며, 대표적으로 범 지구 위치결정 시 스템(global positioning system, GPS) 기반 구현 기술, 디지털 트윈, 그리고 메타버스 기술이다. 공간정보분석 및 공간 빅데이터 융·복합 솔루션 세부 요소 기술로는 3차원 모델링 기술인 지리정 보시스템(geographic information system, GIS), 컴퓨터 지원 설계(computer-aided design, CAD), 빌딩 정보 모델링(build-

**Fig. 2.** Explainable artificial intelligence (XAI) concept. Adapted from the article of Defense Advanced Research Projects Agency. (https://research-vp.tau. ac.il/sites/resauth.tau.ac.il/files/DARPA-BAA-16-53_Explainable_Artificial_ Intelligence.pdf) [18].

ing information modeling, BIM) 등의 공간측정 기술, 메타버 스 플랫폼, 가상현실(virtual reality, VR)·증강현실(augmented reality, AR)·확장현실(eXtended Reality, XR) 등 실감형, 몰입 형 가상현실 시각화 체험기술, 디지털 트윈 플랫폼, 사물인터넷 (Internet of Things, IoT) 센서·빅데이터·AI 학습데이터 등 데이 터의 수집 및 분석기술, IoT 센서 네트워크·5G 네트워크, 클라우 드 컴퓨팅, 그리고 엣지 컴퓨팅이 있다.

다섯 번째, AI 소재 설계시스템은 목표 물성을 갖는 소재를 AI 가 자동으로 설계하는 기술이다. AI 소재 설계시스템의 세부 요소 기술로는 소재 관련 빅데이터 공유 플랫폼 기술, 소재 물성 가상 평가 및 예측기술, 신규 소재 설계·역설계 기술, 소재 구조-물성 관계 해석 기술, 고속 대량 스크리닝(high-throughput virtual screening) 플랫폼, 스마트 소재 생산 기술(소재 생산 최적화 기 술), 소재 구조 최적화 기술, 그리고 물리·화학 이론 융합 소재 물 성예측 기술이 있다.

여섯 번째, edge-device 기반 실시간 지능 플랫폼은 독립적으로 분석 가능한 경량 AI를 탑재한 소형 디바이스(hardware)가 서버 가 연결되지 않은 상황에서 분석·판단·예측·시각화를 가능하게 하 는 기술이다. Edge-device 컴퓨팅은 스마트 팩토리, 자율주행 자 동차, 이동통신, 가전제품, 발전소 운영 최적화 등 다양한 분야에 의 적용이 확대되고 있다. Edge-device 기반 실시간 지능 플랫폼 은 엣지 디바이스, 클라우드 컴퓨팅 네트워크 구성 및 네트워크 연 동 협업 서비스 구축이 필요하다. Edge-device 기반 실시간 지능 플랫폼 세부 요소 기술로는 딥러닝 엔진 경량화(모델 압축) 기술, 딥러닝 엔진 고속화 기술, 시각 객체 인식기술, 분산 Edge-device 간 협업 데이터 처리 및 협업 분석, 위급 상황 인식 기술, 플랫폼 기 술, 데이터 베이스(data base, DB) 프로세싱, 그리고 중앙처리장치 (central processing unit, CPU)+이미지처리장치(graphic processing unit, GPU)를 탑재한 AI 동작 DB 설계기술 등이 있다.

일곱 번째, 학습데이터 증식 및 오류방지 솔루션은 데이터 세트 가 충분하지 않아 딥러닝 기법을 사용하기에 제한이 있는 경우, 특 정 알고리즘에 따라 데이터의 특징을 반영하거나 원본 데이터의 확률을 반영한 데이터를 생성, 데이터의 양을 늘리는 데이터 증식 기술과 학습데이터 구축과정에서의 데이터 오류방지 솔루션(오버 피팅, overfitting) 기술이다. 학습데이터 증식 및 오류방지 솔루 션 세부 요소기술로는 이종(heterogeneous) 데이터 증식기술, 개 인정보보호 기술, 데이터 오토 라벨링 기술, 이미지 및 영상 등 자 동 객체 인식기술, 개체명 인식기/형태소 분석기 등 자연어처리 기술, 학습용 데이터 품질관리 기술, 그리고 엣지 컴퓨팅-클라우 드 연계형 컴퓨팅 기술 등이 있다.

여덟 번째, 빅데이터 기반 마켓 인텔리전스 플랫폼은 빅데이터 정보분석 도구와 방법론을 활용하여 시장 및 정책정보를 분석하 여 예측하는 기술이다. 데이터의 패턴 및 추세를 시각화하는 기술 과 통계, 시계열 예측모형 및 AI 등 머신러닝 기법이 활용되며, 주 요 생태계는 미국의 아마존과 같은 유통 업계와 국내 SK C&C, KB 국민카드 등이 있다. 빅데이터 기반 마켓 인텔리전스 플랫폼

세부 요소기술로는 마켓 인텔리전스, 감성 및 사용자 사전 분류기 술, 텍스트 데이터 분석기술, 자연어 처리기술, 개인화 마케팅, 비 정형 지수산출 기술, 비정형 텍스트 데이터 처리기술, 그리고 비정 형 텍스트 추출 및 처리기술 등이 있다.

마지막으로, RPA 시스템은 표준화된 수행 업무 중 규칙기반의 반복적인 업무를 컴퓨터가 자동으로 수행할 수 있도록 하는 업무 프로세스를 의미한다. RPA 시스템은 데이터 획득 프로세스에서 이미지 인식 기술(optical character reader, OCR) 등을 사용하 여, 자동으로 작업이 진행될 수 있도록 하는 작업절차와 규칙에 관 한 엔진 솔루션이다. RPA 기술은 챗봇을 활용한 비대면 대출, 보 상 신청 업무, 신규 고객 등록, 제조사의 경우 품질관리, 수입 통관 허가서 입력, 공급사슬관리(supply chain management)·물류 분야의 경우 선적 문서 자동 인식, 수출 시 적용 환율 확인 등의 업 무에서 적용되고 있다. RPA 세부 요소기술로는 AI형 자동화 프로 그램(AI 알고리즘), 이미지 인식 기술과 OCR, 프로세스 분석시스 템, 어플리케이션 객체 인식 및 추적, 로봇 프로세스 자동화, RPA 맞춤 챗봇, 워크플로우와 규칙엔진, 트랜잭션 처리 그리고 로봇 AI 플랫폼 등이 있다.

#### **III. AI 기술 적용 지침**

현재 항공·우주 분야를 포함한 공공부문에서 서비스 및 의사결 정을 개선하기 위해 AI 애플리케이션을 적용하고 있으며, AI 기 술을 적용한 공공서비스 활용을 통해 정부의 업무량과 비용을 절 감하려 하고 있다[21,22]. 그러나 AI 기술 적용은 보안 및 공공성 의 이유로 적용에 제한이 많다. 특히, 항공분야에서는 안전이 최우 선적으로 확보되어야 하기 때문에 타 분야에 비해 신뢰성 있는 AI 시스템의 적용이 반드시 필요하다. 이러한 신뢰성 있는 AI의 개발 이나 도입 시에 고려해야 할 사항이 많다. 따라서, 본 절에서는 관 련 항목을 중심으로 신뢰성 있는 AI 개발과 공공분야에서 AI 시스 템의 도입 시 고려사항을 고찰하였다.

##### **1. 신뢰성 있는 AI**

신뢰성 있는 AI 도입을 위해서는 거버넌스와 가이드라인을 개발 하고 구현해야 하는데, 이때 EU의 사례처럼 윤리적 관점을 포함 하여야 한다. 항공안전분야 및 공공부문 신뢰성 있는 AI의 가이드 라인 요소는 AI 적용을 위한 규제 및 거버넌스, 정당성 및 부인방 지(non-repudiation 원칙), 안전 및 보안, 사회경제적 영향, 그리 고 도덕성에 관한 것이다.

첫 번째로, 규제 및 거버넌스 요소는 ‘신뢰 가능한 AI의 도입을 위한 거버넌스의 원칙은 무엇인지’, ‘신뢰 가능한 AI의 특성은 무 엇인지’, ‘AI가 자율적으로 의사결정을 하는지’, 그리고 ‘AI가 결정 하는 결과의 편향을 인코딩 하지 못하게 하려면 어떻게 해야 하는 지’ 등에 관한 것이다.

두 번째로, 정당성 및 부인방지 요소는 ‘AI 학습데이터가 합법적 으로 무결점임을 어떻게 알 수 있는지’, ‘어떻게 무결점을 증명할

것인지’, ‘AI와 사람과의 협업이 합법적인지’, 그리고 ‘AI가 의사결 정을 내릴 수 있는지’ 등에 관한 것이다.

세 번째로, 안전 및 보안 요소는 ‘AI 시스템이 안전한지’, ‘AI가 사람을 해치지 않는다고 보장할 수 있는지’, ‘AI로 인한 손상의 경 우 누가 보상할 것인지’, 그리고 ‘AI가 일으킨 사고에 대한 책임을 누가 져야 하는지’ 등에 관한 것이다.

네 번째로, 사회경제적 영향 요소는 ‘AI가 예측한 프로파일링의 사회적 및 도덕적 위험은 무엇인지’, ‘AI 도입으로 인한 일자리 상 실을 어떻게 막을 수 있는지’, 그리고 ‘AI로 인해 직업을 잃은 인간 은 어떤 유형의 일을 해야 하는지’에 관한 것이다.

마지막으로 도덕성 요소는 ‘AI를 파괴할 권리가 있는지’, ‘우리가 이해할 수 있는 수준을 넘어선 AI를 어떻게 제어할 수 있는지’, ‘AI 는 의사결정, 자산 등을 소유할 수 있는지’, ‘AI는 법적 지위와 권 리를 가져야 하는지’, 그리고 ‘AI는 개인 재산인지 공공 재산인지’ 등에 관한 것이다.

신뢰성 있는 AI 도입을 위한 일반관리 원칙은 다음과 같다. 우 선, AI와 관련된 위험은 기관의 위험관리 프로세스 내에서 관리할 수 있어야 하며, 각 기관의 AI 거버넌스는 최고경영진과 이사회의 적극적인 지원 및 참여가 권고된다. AI 사용의 성과목표로는 의사 결정의 효과성, 일관성, 기관 운영 효율성 개선, 비용 개선, 그리고 새로운 제품 및 서비스 제공을 통한 소비자 만족도 등을 설정할 수 있다. 소비자와 커뮤니케이션 및 고객 관리를 위해서 AI 의사결 정이 개인에게 어떤 영향을 미치는지 투명하게 정보를 공개할 필 요가 있으며, AI 의사결정에 대하여 소비자가 이해할 수 있는 쉬 운 용어를 사용하여야 하고, 설명할 수 있어야 하며, 그리고 서비 스 결과를 제시하여야 한다. AI 시스템은 ‘사람-우선’ 원리로 설계 되어야 하며, 설명 가능해야 하며, 투명해야 하며, 사람이 해석할 수 있어야 하고, 그리고 편향되지 않은 데이터를 기반으로 구축하 여야 한다. 그리고 시스템의 투명성과 책임성을 객관적으로 평가 (감사)할 수 있도록 설계되어야 한다.

##### **2. AI 시스템 적용**

현재 AI 기술은 ‘전자정부’를 넘어 ‘지능정부’의 구현에 있어 좋 은 해결방안이 될 수 있지만, 기관 보유 데이터 이해 및 활용 준비, 조직 내 AI 기술 및 개인정보 관리 기술, 스타트업 중심의 AI 생태 계 환경, 공공조직의 민첩성과 보상체계, 그리고 정부 조달체계 등 의 항목에서 AI 도입을 주저하게 된다[23].

첫 번째, 기관 보유 데이터 이해 및 활용 준비에 관한 내용이다. 대부분 조직은 데이터 자산에 대한 이해가 부족하여, 조직 내 데이 터베이스에 어떤 정보가 있는지, 어떻게 활용해야 하는지 모르는 경향이 있으며 활용 준비가 미흡하다.

두 번째, 조직 내 AI 기술 및 개인정보 관리 기술에 관한 내용이 다. 공공부문의 특성상 데이터의 관리와 AI 솔루션에 필요한 기술 확보와 전문인력 유치에 어려움을 겪고 있다. 특히 데이터 관련 법 률에 대한 이해 없이 AI 프로젝트를 착수하는 경우 개인정보보호 와 같은 구성원의 권리가 침해 당할 수 있으며 활용이 어려울 수 있다.

세 번째, 스타트업 중심의 AI 생태계 환경에 관한 내용이다. 현 재 국내외 AI 생태계 환경은 많은 소규모 업체가 시장을 주도하고 있다. 이에 공공기관은 대규모 프로젝트의 경험이 없는 소규모 신 생업체를 프로젝트에 효과적으로 참여시킬 방법을 찾아야 한다.

네 번째, 공공조직의 민첩성과 보상체계에 관한 내용이다. 대부 분 조직에서 새로운 기술을 채택하고 적용하는 데 있어서 어려움 이 있으나 특히 공공부문은 업무 프로세스의 경직성으로 인해 민 간 부문보다 민첩하지 않다. 공공조직은 서비스 제공이 크게 향상 되어도 민간과 비교해서 보상이 크지 않아 개발 담당자가 위험을 감수하지 않을 경향이 크다. 성공적인 개발이 되기 위해서는 개발 프로젝트 성공 시 적정한 인센티브를 제공하고 실패 시 담당자를 보호하는 보상체계가 필요하다.

마지막으로, 공공부문의 조달체계이다. 공공부문의 조달체계는 지적 재산권의 문제가 있으며, 길고 복잡한 의사결정 구조이기에 공급자의 경영 전반에 상당한 영향을 준다. 특히 스타트업과 같은

**Table 3.** Public sectors AI system procurement consideration

||**Consideration**|
|---|---|
|1|Rather than prescribing specific solutions in advance, the procurement process is utilized to identify problems and opportunities, and it isconsistently maintained|
|2|Define the public benefits of using AI systems and evaluate risks|
|34|Refer to the government’s existing strategies related to the AI project to be introduced to control procurement and explain further improvementReflects the relevant legislation and regulations necessary for implementation in the RFP|
|5|Specifically state the technical and administrative possibilities for accessing relevant data|
|6|Emphasize the technical and ethical limitations of using data to avoid problems such as bias|
|7|Cooperate with teams of various departments|
|8|Throughout the bidding process, we focus on the institutional arrangements of the algorithm’s accountability and transparency criteria|
|9|Introduce a process that allows AI system provides to continue to engage with companies performing knowledge transfer and long-term riskassessment tasks|
|10|Encourage AI solution providers to participate and creating a fair competition environment|
|AI: art|ificial intelligence, RFP: request for proposal. Data from the National Information Society Agency. (2019) [24].|

중소규모 업체는 업무 프로세스가 길어지게 되면 현금 흐름 관리 와 필수 직원의 채용 등에 애로사항이 있다. 주된 장애 요인을 극 복하기 위해서는 공공부문 조달시스템에서 그 해결책을 찾아야 하 는데, 전 세계적으로 정부 차원에서 AI 시스템 공공부문 조달과정 에서 발견되는 문제를 확인하고 해결책을 지원하기 위해 노력하고 있다. 특히, 세계경제포럼(World Economic Forum)은 2019년 9월 ‘AI 공공부문 조달 가이드라인’을 발간하여 AI 솔루션 도입 경 험이 부족한 각국 정부와 공공기관의 AI 시스템 조달 기획단계에 도움을 줄 수 있을 것으로 기대하고 있다[24]. AI 시스템 공공부 문 조달 가이드라인은 Table 3과 같이 발주기관인 공공부문의 제 안요청서 작성 및 검토 시 AI 적정 기술, 위험도 평가, 관련기관 간 협력, 법 규정, 데이터 활용, 편향성 방지, 팀 협조, 책임과 투명성, 지식 이전, 그리고 공정 경쟁 등의 고려사항을 정의하고 있다.

#### **Ⅳ. 결 론**

본 연구에서는 항공안전분야 등 공공부문 AI 개발 및 도입에 있 어서 신뢰성이 중요하게 대두되는 현 시점에서, 신뢰성 있는 AI 시 스템 개발과 도입 시 고려사항을 도출하였다.

신뢰성 있는 AI 도입 시에는 AI 도입을 위한 규제 및 거버넌스 원칙 설정, 데이터의 무결점 확인, AI 시스템 안전 및 보안 확보, 사회 경제적 영향 확인, 그리고 도덕성의 원칙 수립과 같은 사항을 고려해야 할 것이다. 또한, 신뢰성 있는 AI의 개발 및 도입 시 의사 결정 및 의사소통 방법의 결정과 AI 시스템의 책임, 감사 등의 원 칙에 대한 내용을 검토하였다.

그리고 AI 시스템의 적용과정에서 발견되는 문제를 해결하기 위 한 가이드라인을 제시하였다. 주된 장애요인으로 작용하는, 기관 이 보유하고 있는 데이터의 이해 부족과 준비사항 미흡, 데이터 관 련 법률에 대한 이해부족으로 인한 개인 정보보호 권리 침해, 스타 트업 중심의 AI 생태계 환경으로 경험 부족으로 인한 높은 프로젝 트 실패 확률, 프로젝트 성공으로 인한 서비스가 향상되어도 보상 이 크지 않기 때문에 개발 담당자가 위험을 감수하지 않는 환경, 그리고 공공분야의 복잡하고 경직된 의사결정 구조인 조달과정의 문제 등에 대한 고려사항을 고찰하였다.

AI 기술의 발전은 항공 안전분야의 오류방지를 위한 안전프로 그램 개발에 도움이 될 것으로 판단하고 있다. 본 연구에서 제시된 내용은 항공안전분야 및 공공기관의 AI 개발 및 도입의 기획, 준 비 그리고 운영단계에서 기초자료로 활용될 수 있을 것이다. 본 연 구에서 제시하는 내용은 AI 기술의 발전 동향을 고려하여 유연하 게 수정 적용할 필요가 있다.

#### **CONFLICTS OF INTEREST**

No potential conflict of interest relevant to this article was reported.

#### **FUNDING**

None.

#### **ACKNOWLEDGEMENT**

None.

#### **ORCID**

Daeho Kim, https://orcid.org/0000-0001-9013-3381

#### **REFERENCES**

1. Presidential Committee on the 4th Industrial Revolution. Presidential Committee on the 4th Industrial Revolution data [Internet]. Government of the Republic of Korea; 2017 [cited 2025 Mar 10]. Available from: http://webarchives. pa.go.kr/19th/www.4th-ir.go.kr/

2. World Economic Forum. The global risks report 2024. 19th ed. World Economic Forum; 2024.

3. European Union Aviation Safety Agency (EASA). Artificial intelligence roadmap 2.0: human-centric approach to AI in aviation. Version 2.0. EASA; 2023.

4. Government of the Republic of Korea. National strategy for artificial intelligence. Ministry of Science and ICT; 2019.

5. Organisation for Economic Co-operation and Development (OECD). Artificial intelligence in society. National Information Society Agency, translator. OECD; 2019.

6. Yoo JH, Lee JS, Ahn SW. Artificial intelligence industry trends in Korea and overseas in 2023. Software Policy & Research Institute; 2023 Dec. Report No.: RE-17.

7. United States Congress. National Artificial Intelligence Initiative Act of 2020 [Internet]. United States Congress; 2021 [cited 2025 Mar 10]. Available from: https://world.moleg.go.kr/web/ wli/lgslInfoReadPage.do?CTS_SEQ=50782&AST_SEQ=313

8. Networking and Information Technology Research and Development (NITRD). Artificial intelligence R&D investments fiscal year 2019 – fiscal year 2025 [Internet]. NITRD [cited 2025 Mar 10]. Available from: https://www.nitrd.gov/aird-investments/#Chart-1-Federal-Budget-for-AI-RD-FYs2021-2023

9. National Science and Technology Council (NSTC). National Artificial Intelligence Research and Development Strategic Plan 2023 update. NSTC; 2023.

10. European Commission (EC). Proposal for a Regulation of the European Parliament and of the Council Laying Down Harmonised Rules on Artificial Intelligence (Artificial Intelligence Act) and Amending Certain Union Legislative Acts [Internet]. EC; 2021 [cited 2025 Mar 10]. Available from: https://eur-lex.europa.eu/legal-content/EN/ TXT/?uri=celex:52021PC0206

11. European Commission (EC). Coordinated plan on artificial intelligence 2021 review [Internet]. EC; 2021 [cited 2025 Mar 10]. Available from: https://digital-strategy.ec.europa.eu/en/library/coordinated-plan-artificial-intelligence-2021-review

12. Government of the Republic of Korea. A policy briefing ‘AI’, 2021 [Internet]. Government of the Republic of Korea; 2021 [cited 2025 Mar 10]. Available from: https://www.korea.kr/ special/policyCurationView.do?newsId=148868542

13. Bellman R. An introduction to artificial intelligence: can computers think? Boyd & Fraser; 1978.

14. Statista. Artificial intelligence (AI) market size worldwide from 2020 to 2030 [Internet]. Statista; 2024 [cited 2025 Mar 10]. Available from: https://www.statista.com/forecasts/ 1474143/global-ai-market-size

15. Rudnitsky J. ChatGPT to fuel $1.3 trillion AI market by 2032, new report says [Internet]. Bloomberg; 2023 [cited 2025 Mar 10]. Available from: https://www.bloomberg.com/ news/articles/2023-06-01/chatgpt-to-fuel-1-3-trillion-aimarket-by-2032-bi-report-says

16. Korea Research Institute for Defense Technology Planning and Advancement (KRIT). Future defense 2030 technology strategy. KRIT; 2022.

17. Institute of Information & Communications Technology Planning & Evaluation (IITP). AI technology blueprint 2030. IITP; 2020.

18. Defense Advanced Research Projects Agency (DARPA). Explainable artificial intelligence (XAI). DARPA; 2016 Aug. Report No.: DARPA-BAA-16-53.

19. Ministry of SMEs and Startups, Korea Technology and Information Promotion Agency for SMEs. Technology roadmap for SME 2023-2025: AI·big data. Jinhan M&B; 2023.

20. Artificial Intelligence Industry Association. A research for establishment of artificial intelligence industry classification system. Ministry of Science and ICT; 2019 Jan. Report No.: 2018-0-01665.

21. Kim DH. Key to public sector AI ‘reliable AI’ - need to develop AI governance guidelines. National Information Society Agency; 2019 Sep. Report No.: SPECIAL REPORT 2019-8.

22. Eggers WD, Schatsky D, Viechnicki P. AI-augmented government: using cognitive technologies to redesign public sector work [Internet]. Deloitte Insights; 2017 [cited 2025 Mar 10]. Available from: https://www2.deloitte.com/us/ en/insights/focus/cognitive-technologies/artificial-intelligence-government.html

23. National Information Society Agency (NIA). AI-era government, how AI will change government? NIA; 2017 Jul. Report No.: IT & Future Strategy 2017-3.

24. National Information Society Agency (NIA). Guidelines for AI procurement. NIA; 2019 Dec. Report No.: DNA Plus 2019-11.
