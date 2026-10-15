---
title: "Developing a Smart Phone Application for the OMAHA System Guidelines"
organization: "Journal of Korean Academy of Community Health Nursing"
year: "2014"
language: ko
source_url: "https://nextsteppro.io/DOIx.php?id=10.12799/jkachn.2010.21.4.512"
license: "CC BY-NC"
---
# Developing a Smart Phone Application for the OMAHA System Guidelines

경북대학교간호대학교수1 , 경북대학교의료정보학과박사후연구원2 , · 3 경북대학교간호대학박사과정 경북대학교의료정보원천기술연구소연구원

## **Developing a Smart Phone Application for the OMAHA System Guidelines**

Hong, Hae Sook1 · Lee, In Keun2 · Hong, Sung Jung3 · Kim, Hwa Sun3

**1Professor, College of Nursing, 2Post-doc, Department of Medical Informatics,**

**3Doctorial Course, College of Nursing, Kyungpook National University · Researcher, MIPTH, Kyungpook National University**

**Purpose:** The remarkable progress in information and communication technology has had a great effect on the healthcare delivery system. The development of smart phone applications is a new field. The aim of our research was to provide assistance in developing smart phone applications for community health nursing. **Methods:** Based on an informative approach, this study developed persona and site maps, followed by a storyboard as a way of analyzing users requirements and designing responses in the context of smart phone application development methodology. **Results:** We developed persona, user interface and database design successfully, and then seven nurses selected four nursing problems (income, residence, pain, and digestion hydration). The search time in seconds for the 2005 English OMAHA guidelines to find three nursing interventions for these problems was used to evaluate the effectiveness of the smart phone application. The results showed that smart phone applications search was 21 times faster on the average than book guidelines. **Conclusion:** An English version of the OMAHA system application was developed for the Android smart phone market. It is hoped that smart phone applications such as this will be used internationally for nursing education.

**Key Words:** Nursing Informatics, Community health nursing, Guideline, Education

### 서 론

##### 1. 연구의필요성

현재지식기반사회로의진입은보건의료분야업무의전 산화를가속화시키면서국내대부분의의료기관에전산화 를도입시켰고전자화된기록시스템으로변화하면서간, 호에있어서정보기술을활용하고통합관리하는방법에 대한교육이절실히필요하게되었다(Yom et al., 2007). 기

존의종이기반기록에서전자기록시스템으로의변화는교 육자로하여금새로운변화에대한교육의필요성을가지게 한다교육자는임상자료의잠재적가치를이해하고임상. 자료를기록하고관리하는새로운방법론을적용하고급속 히변화하는임상환경에효율적인기능을위해서준비가 되어야한다만약교육자가미래를위해학생들을준비시. 킬수있다면학생들은임상실무에서요구되는상황에대, 해미리예견할수있고변화하도록개선할수있을것이다 (Barton et al., 2003; Hamner & Wilder, 2001). 즉학생들

주요어: 간호정보지역사회간호가이드라인교육, , ,

Address reprint requests to : Kim, Hwa Sun, College of Nursing, Kyungpook National University, 2-101 Dongin-dong, Jung-gu, Daegu 700-422, Korea. Tel: 82-53-420-4896, Fax: 82-53-423-1242, E-mail: pulala@paran.com

> - 이논문은 2010년도정부교육과학기술부의재원으로한국연구재단의지원( ) (No.2010-0017073) 및지식경제부및한국산업기술평가관리원의 지식서비스산업원천기술개발사업의일환으로수행하였음(KI10033545, KI10033576].

- This work was supported by National Reseach Foundation of Korea (NRF) grand funded by the Korea government (MEST) (No.20100017073) and the R&D Program of MKE/KEIT KI10033545, KI10033576].

> 투고일 2010년 10월 27일 / 수정일 2010년 12월 16일 / 게재확정일 2010년 12월 16일

은실무에서발생하는변화에대해적절하게접근할수있 을것이다. Tanner (1995)는교육과정이지속적으로비평 적재평가를할필요가있으며이결과에따라가능한빠른 시간내에재구성되고개발되어야한다고하였다교육자는. 학생들에게성공적으로교육과정을습득하게할필요가있 고특히이과정에서는이론과함께기술이함께제공되어 야한다또한준비된간호인력을서비스환경으로진출시. 키므로간호전달체계내부의긍정적인변화를유도하고 지식들을보급시켜야한다전문간호사의부족적시에요. , 구되는데이터의필요성증가지역사회간호의성장전문, , 적실무에대한관심증가등의변화는표준화된전문용어 체계와자동화된정보시스템을포함하는혁신적인전자기 록응용프로그램의사용을고무시키고있다(Androwich et al., 2003; Plowfield, Hayes, & Hall-Long, 2005).

미국의학연구소(Institute of Medicine, IOM)는환자중 심간호의제공여러전문분야팀의구성원으로서참여, , 근거기반실무의활용질향상접근법의적용과정보의활, 용의가지를핵심능력으로간주하고있으며정보적인측5 , 면에서미래의간호를발전시키기위해서는학생들이지식 을관리하고오류를감소하고의사결정을지원할수있기, 위해서최신정보기술을사용할수있어야한다고하였다 (Greiner & Knebel, 2003). 오늘날교육자들은간호교육과정에서학생들에게학습 기회에학습자원의결정에있어정보기술을사용하는것 에직면한다문서를관리하기위한표준화된언어는반드. 시사용해야하지만의미있는교육적인전략을세우는과 제는여전히남아있다그러나임상실습을나가는한국의. 간호대학생의경우지역사회임상실습현장에서사정단계 에서다양한도구를통해서수집되는자료를확인분류한, 후환자에대한간호진단을결정하는데미숙할뿐만아니 라용어체계에대한교육경험이부족하다특히원인에대. , 한부정확한진단은잘못된방향으로유도하여비효율적인 결과와부정확한간호를수행하게만든다최근정보기술. 의변화로는급속히성장하고있는스마트폰시장이다작. 년 11월에들어온애플의아이폰을시작으로국내에스마 트폰이들어오면서 IT 강국을자랑하는한국에서스마트폰 경쟁력이세계의흐름과거꾸로가고있다스마트폰은대. 용량애플리케이션을 PC 싱크를통해손쉽게사용할수있 다일반휴대폰또는. PDA의경우무선데이터망을이용해 야애플리케이션을다운로드받고설치할수있지만스마 트폰은 PC의웹브라우저를통해애플리케이션을다운로

드받은뒤이를 PC와싱크를통해스마트폰에전송시킬수 있다최근스마트폰은. PC와연결하는과정을거치지않고 무선데이터통신으로싱크기능을구현하고있다이를통. 해개인 PC가없는곳에서도싱크가가능해졌다.

최근의료에적용한사례로서성형외과수술적용(Hunter, Hardwicke, & Rayatt, 2010), 당뇨자가관리에서혈당관리 (Ciemins, Coon, & Sorli, 2010), 150명의자폐아동의이미 지선택을통한감정전달치료에적용한애플리케이션이 있고(De Leo, Gonzales, Battagiri, & Leroy, 2010), 국내에 서는임신부를대상으로임신확인부터주기별건강관리, 태아움직임태교및건강상식등을관리하는헬스케어스, 케줄링애플리케이션이있다(Lee, Im, & Lee, 2010). 이러 한다양하고유용한애플리케이션과사용이쉬운인터페 이스를제공하고이를통해사용자에게즐거움과유용성 을주는것이스마트폰의채택의도를높이고있다(Kim, 2010).

이에본연구에서오마하시스템가이드라인을애플리케 이션으로하여스마트폰에적용하고자하였다오마하시. 스템은지역사회기반실무를위한포괄적인용어로서다, 학제적사용이가능하도록고안되었는데개발초기에는, 지역사회에중점을두고지역사회에서발생하는실무를위 해데이터를효과적으로관리하기위해서사용되었으나현 재는지역사회를넘어서급성간호에까지적용범위를넓히 고있다(Correll & Martin, 2009; Garvin, Martin, Stassen, & Bowles, 2008; Westra, Oancea, Savik, & Marek, 2010).

지역사회에서사용되고있는국제표준용어체계인오마 하시스템의사용은교육자와동시에학습가로서의역할을 할수있도록하고몇몇학생들은지역사회임상실무에서 좀더많은오마하시스템기술을알기를원할수있다임. 상기록에대해서조직화하고사고하는다른방법을배우 는것은새로운정보의조직화와가설의일반화와테스트 를포함하는다중업무과정이며(Correll & Martin, 2009; Martin, 2004; Westra et al., 2010), 한국의지역사회에서오 마하시스템을적용한결과에서도지역사회내에서당면하 는간호서비스를식별하고분류할수있는방법으로적합 하다고보고된바있다(Cho, Yoo, Chae, Ham, & Seo, 2002; Yoo, Cho, Chae, & Kim, 2004).

그러므로오마하시스템은간호사의업무수행교육연, , 구환경에적용하면근거중심의업무문서화및정보관, , 리를쉽게할수있다또한여러분야의건강관리초보자와. 사회서비스직원및학생들에게대상자문제의료인간중,

재및대상자결과에대한표준화되고이해하기쉬운체계 를통해간호업무를소개할수있다모든의료인들에게오. 마하시스템은사용자들에가능한대상자문제와중재들, 관리의효과를측정하는방법표준업무수행과정을확인, 하는연계역할등에대한일련의단서또는피드백의고리 를제공한다초보자들이대상자데이터에오마하시스템. 을사용할때초보자에서전문가가되는업무및문서화의, 연속선상에있게될것이다(Martin, 2004).

상세한정보이용을한다는등의사용성의분석및효과를 파악할수있다.

##### 2. 연구설계

설계는오마하시스템의데이터베이스와UI (user interface) 설계로구분하였다.

##### 1) 오마하시스템의데이터베이스설계

##### 2. 연구목적

본연구의목적은지역사회기반실무를포괄하는국제 적승인을받은간호표준용어체계인오마하시스템의가이 드라인을개발하는것이다이를위한구체적인목적은다. 음과같다.

- 오마하시스템을분석하고최적의데이터베이스를설 계한다.

- 오마하시스템가이드라인에대한스마트폰기반으로 애플리케이션을설계한다.

- 오마하시스템가이드라인을위한스마트폰기반으로 애플리케이션을개발한다.

- 오마하시스템가이드라인의스마트폰기반애플리케 이션을적용한다.

### 연구방법

본연구는프로젝트개발방법론중백켄트(Beck, Kent) 의애자일(Agile)개발방법론을준수하여공통적프로세스 인사용자요구분석설계개발테스트의과정으로수행, , , 하였다(Beck, 2002).

본연구를위한오마하시스템은 2005년버전이며문제분, 류체계(Problem Classification Scheme), 중재체계(Intervention Scheme), 결과에대한문제측정척도(Problem Rating Scale for Outcomes)의가지구성요소로체계화되3 어있다각구성요소는자세한설명은다음과같다. .

(1) 문제분류체계(problem classification scheme) 개인가족지역사회를대상으로표준화된평가를위한, , 원인과결과의구조용어시스템을제공한다각단계의, , . 정의에따라개별항목들이어느부류에속하는지가결정 되었으며각단계에서사용되는용어는같은수준의추상, 성수준을가지고있고상호배타적이다문제분류의추상성. 수준은단계로서4 , 4개의단계영역1 (domain), 42개의단2 계문제(problem), 2그룹의제단계수식어구3 (modifier), 377개의제단계증상증후4 / (sign/symptom)이다수식어. 구(modifier)는그룹은건강증진1 (health promotion), 잠 재적(potential), 실제적(actual)으로구분되고, 2그룹은개 인(individual), 가족(family), 지역사회(community)로구 분되며그룹의구분에따라간호행위에따른수가가다르2 게책정된다.

##### (2) 중재체계(intervention scheme)

##### 1. 사용자요구분석

사용자요구분석을위해서페르소나(persona)를작성 하였는데페르소나는해당서비스의사용자를요약해서, 표현하는것으로일반적으로실제사람처럼묘사하며하, 나또는복수의페르소나가존재할수있다서비스에대한. 다양한사용자유형을대표하며다른이름으로사용자프로 필사용자역할정의고객프로필등으로불린다페르소나, , . 를통해서사용자가스마트폰을사용하고자하는동기시, 나리오기능행동들을구체화하고스마트폰을활용해서, , ,

중재체계는환자에게중재하는체계로서단계로서3 , 1단 계분류(category), 2단계대상(target), 3단계는중재(intervention)로서구성되어있다. 1단계인분류는지역사회간 호사에의해서자주사용되는완전하면서뚜렷이구분이 되는개념을선택하였다. 1) 건강교육안내상담, , , 2) 처치 와절차, 3) 사례관리, 4) 모니터링이포함된다. 2단계의대 상이란각중재분류체계의간호활동대상의목록으로서, 대상의예로는방광치료석고붕대관리드레싱교환상처, , / 치료투약시간정하기등이포함된다대상의목록은모두, . 76개로구성되어있고, 3단계에서는보건의료제공자에의

해서생성되고개별화된대상자에맞는 4,432 중재정보를 포함한다.

##### (3) 결과에대한문제측정척도(problem rating scale for outcomes)

결과를위한문제측정정도는개의단계개념3 1 (concepts), 5점척도의단계측정도구2 (5 point Likert-type scale)로서 2단계로체계화되어있다개념으로서지식. (knowledge), 행동(behavior), 상태(status) 가규명되었으며, 5점 Likert 형태척도가이들개개념을측정하기위해개발되어간3 , 호서비스전과정에서환자상태를평가하기위한방법이 다지식은환자가알고있는것으로정의되며행동은환자. , 가하는것그리고상태는환자의증상및징후또는나쁜, 상태의심각도와횟수에대한정의이다하위척도각각은. , 정기적이고예측가능한시간대에구체적인문제척도를, 평가하는데있어평가틀을제공하는연속체이다주장하, . 는시간대는입원과구체적인중간지점퇴원시점을포함, 한다문제분류중재분류와더불어결과에대한문제측. , 정척도를사용하는것은실무와교육연구를위한종합적, , 인문제해결모델을만들어낸다대상자기간전반에걸쳐. 특정대상자문제와관련되어타당하고신뢰성있는대상 자의진행상태의정도를제공한다.

##### 2) UI (user Interface) 설계

사용자화면설계를위해서는사이트맵과스토리보드를 사용하였다사이트맵은개발전에시나리오를분석하여. 예상하는순서를누구든지알기쉽게그림혹은도식으로 표현하는것이며스토리보드는사이트맵서제시한초기, 화면에대한기능적설명을부여하는것으로서반복적인. 사용자요구분석에따라사이트맵과스토리보드는 3 차례 에걸쳐변경되며확장과정제를반복하였다.

##### 3. 개발

스마트폰의가장큰특징은완제품으로출시되어주어진 기능만사용하던기존의휴대폰과는달리수백여종의다 양한애플리케이션을사용자가원하는대로설치하고추가 또는삭제할수있다는점이다무선인터넷을이용하여인. 터넷에직접접속할수있을뿐아니라여러가지브라우징 프로그램을이용하여다양한방법으로접속할수있는점, 사용자가원하는애플리케이션을직접제작할수도있는

점다양한애플리케이션을통하여자신에게알맞은인터, 페이스를구현할수있는점그리고같은운영체제를가진 스마트폰간에애플리케이션을공유할수있는점등도기 존휴대폰이갖지못한장점으로꼽힌다(Korea Internet & Security Agency, 2009).

본연구에서적용된스마트폰운영체제는안드로이드체 제로서최초의완전하고개방적이고무료인스마트폰플랫 폼으로서애플리케이션개발기회들을제공하는견고한소 프트웨어프레임워크를구축하고있다또한안드로이드. 플랫폼은오픈소스라이선스를통해서제공된다개발자들. 은개발시단말기의기능들에관계없이자유로이접근할 수있으며다양한형식으로배포상용화할수있는장점이, , 있다이러한장점을이유로개발환경은안드로이드기반. 으로하였다이를위해서우선. Java SE Development Kit (JDK) 6을설치하고, Android SDK 2.2를설치하였다그리. 고 Android Eclipse Plug-in을 Android SDK 2.2에맞는패키 지를설치하였다마지막으로. Eclipse를실행하여 Android SDK를 Android 2.2와 Google APIs 8로설정하였다.

##### 테스트

##### 4.

사용자배포전단계의기존북가이드라인과의평가를 위해 K대학교 RN-BSN 과정중오마하시스템에대한사용 방법을숙지한임상경력년차이상의명의간호사를대3 7 상으로테스트를하였다기존북가이드라인과스마트폰. 기반의가이드라인을활용한시간차이에대해평균및표 준편차를산출하였다.

### 연구결과

##### 1. 사용자요구분석

해당서비스의목적대상에대한페르소나개요는, Table 1과같고페르소나를기술하면다음과같다, .

오마하시스템을사용하는스마트폰사용자는지역사 회에간호임상실습을나가는학년김3 OO간호학생이다. 학생은임상실습에서발생하는문제와관련된진단또는 여러가지간호활동에대한궁금한점이발생하였다그리. 고수행한간호에대한결과에대한평가를하고자하는경 우가발생하였다이때간호학생은스마트폰애플리케이. 션을설치하므로오마하시스템의필요성과개용에대해서

이해하였고문제를검색하고관련중재가이드라인정보, , 를얻은후간호중재를수행하고평가할수있을것이다

##### 2. 설계

하는것으로서다음과같다(Figure 1).

스토리보드는사이트맵서제시한초기화면에대한기 능적설명을부여한것으로서초기화면은오마하시스템, , 문제목록찾기중재로찾기최근검색목록의가지로구, , 4 성하였다.

- 1) UI (user interface) 설계

먼저사이트맵은개발전에시나리오를분석하여예상 하는순서를누구든지알기쉽게그림혹은도식으로표현

- (1) 오마하시스템

오마하시스템에대한전반적인정보를제공하여오마하

**Figure 1.** Site maps of Omaha system guideline.

**Table 1.** Overview of Persona

|Item|Content|
|---|---|
|Purpose|Community nursing will to use the Omaha system for planing and implementing a project at the aggregate orcommunity level that emphasized primary and secondary prevention|
|Target|About 500 nursing students in Korea|
|Scale|English and Korean version|

시스템을알고접근하는사용자뿐만아니라처음접하는 사용자도쉽게이해할수있도록하였다.

##### (2) 문제목록찾기

중요메뉴로서문제분류체계의문제목록, (problem list) 을제공하고증상징후관련중재까지보여주어간호활동/ , 의가이드라인을제시할수있도록하였다.

Intervention_Scheme 테이블로정의하였다결과에대한. 문제측정척도는테이블로정의하지않고초기화면에서, 측정척도에대한설명을제시하였다.

각테이블의기본키(PK)는 Figure 2와같은관계설정을 하므로사용자가어떠한간호문제에대해서알고자하는 관련증상징후관련중재영역분류에대한정보를한눈/ , , , 에볼수있게된다(Figure 2).

##### (3) 중재로찾기

간호활동을할때자신이행한중재와관련된문제 (problem)를찾을수있게하였다.

##### (4) 최근검색목록

사용자가최근찾아본진단을찾아볼수있는기능을제 공한다많이찾아본진단은위쪽으로올라가도록되어있. 어빈도수가높은목록을편리하게볼수있다.

##### 2) 오마하시스템의데이터베이스

문제분류체계중재체계결과에대한문제측정척도의, , 3가지구성요소간에관계를설정하는것은애플리케이션 을개발하는데핵심이된다본연구는오마하시스템가이. 드라인개발로서총개의테이블을정의하였다문제분류6 . 체계의영역은 Domain 테이블문제는, Problem 테이블, 증상징후는/ Symptom 테이블로설계하였고중재체계의, 분류는 Category 테이블대상은, Target 테이블중재는,

##### 3. 개발

##### 1) 초기화면

초기화면은사이트맵과동일하게개발되었다위의부. 분은오마하시스템의로고를나타냈으며아래의부분은, 4 개의선택메뉴를배치하였다(Figure 3).

##### 2) 오마하시스템개요

오마하시스템개요 메뉴를선택하면 Figure 4와같이 오마하시스템의개요각구성요소에대한상세설명을볼, 수있다(Figure 4).

##### 문제또는중재로찾기

##### 3)

문제목록찾기 또는 중재로찾기 메뉴를선택하면 문 제목록찾기 의경우에는스크롤바를이용하여리스트 검색할수있는환경으로개발되었고, 중재로찾기 의경 우는텍스트박스가나타나서찾을수도있으며스크롤바,

**Figure 2.** Six tables of Omaha system.

를이용할수도있다예를들어. Figure 5의화면과같이문 제목록에서개인위생을선택하였을경우개인위생에대한 영문설명영역증상징후관련중재를한눈에볼수있다, , / , (Figure 5).

##### 4) 최근검색목록

사용자가최근찾아본진단을찾아볼수있는기능을제 공한다.

##### 4. 테스트및배포

1차개발완료된후사용자입장에서명의정보전문가2 가프로그램을검토하였다오마하시스템에대한설명이. 보기편하도록들여쓰기띄어쓰기글자크기등을개선하, , 였다중재로찾기에서하나의중재를선택했을때문제목. 록과중재가혼동될수있어 문제보기 를추가하였다마. 지막화면에서문제목록을정확히볼수있도록글자를중 간정렬하고글자를크게하였다또한초기화면의사이트. 맵에서제시한 Omaha System 을한글 오마하시스템개 요 로수정하였다.

사용방법을숙지한임상경력년차이상의명의간호사3 7 를대상으로 4개의지정된간호문제로서수입, (income), - 거주지(residence), 통증(pain), 소화수분공급(digestionhydration)을제시하였다. 7명의간호사는제시된간호문 제의영역을확인하고증상증후와관련중재를각각개, / 3 씩찾는시간에대해오마하시스템 2005년북가이드라인 과개발된스마트폰가이드라인과의검색시간단위초을( ) 비교한결과는다음과같다. 4개의문제에서스마트폰가이 드라인이평균적으로 21배시간에서빠른검색결과를나 타냈다(Table 2).

사용자평가와지역사회간호전공교수의검수를회마2 친후안드로이드마켓(http://www.android.com/market) 에정식배포를하였다배포를위해서애플리케이션. Apk 파일, 2개의예제화면과설명을업로드하였다.

### 논 의

본연구는오마하시스템을스마트폰애플리케이션으로 개발하여지역사회실무를위한가이드라인으로제공하고 자오마하시스템을분석하고정보학적접근으로스마트폰 애플리케이션개발을위한애자일프로젝트개발방법을준

**Figure 3.** Android based test view of main menu.

**Figure 4.** Screen shot of Omaha system overview

**Figure 5.** Searching problem or intervention.

**Table 2.** Searching Time between Book Guideline and Smart phone Guideline (Unit: Second)

||Book|Smartphone|
|---|---|---|
|Problem|guideline (n=7)|guideline (n=7)|
||M±SD|M±SD|
|Income|229.3±12.3|11.6±1.3|
|Residence|247.1±13.5|12.4±1.8|
|Pain|237.9±6.4|11.7±0.9|
|Digestion-hydration|250.1±14.6|10.9±0.9|
|Average|241.1±5.9|11.6±0.5|

수하여사용자요구사항분석및설계를위한방법으로페 르소나사이트맵및스토리보드를개발하였고이를기반, 으로프로그래밍하고평가후 11월업로드하였다가이드. 라인은현재안드로이드마켓에서다운로드하여스마트폰 에서실행할수있다사용자평가를위해서는개의지정. 4 된간호문제에대해서해당영역을확인하고증상증후와, / 관련중재를개찾는시간에대해서오마하시스템3 2005년 북가이드라인과개발된스마트폰가이드라인과의검색시 간을비교한결과 21배이상빠른결과를획득하였다이러. 한결과는간호실무에서빠르고정확하게중재및평가가 이드라인에접근할수있을것이다. 간호의전문적기준을평가하는것은어려운과정으로서 (Hardiker, Hoy, & Casey, 2000; Harris, Graves, Solbrig, Elkin, & Chute, 2000), 역사적인시초는 Wisconsin주 Milwaukee에서 Harriet Werley와 Norma Lang이공동의 장으로개최한 1985년 Nursing Minimum Data Set Conference로서간호전문직으로서의간호용어체계의자, 동화시스템에대한필요성과이러한자동화는간호수행, 교육연구간의원활한의사소통을할수있다고하였다, (Lang, 1995).

최근에는간호활동을뒷받침하는 12개의용어체계가미 국간호사협회에의해승인되고전파되었다그중에서오. 마하시스템은다학제적사용이가능하도록고안되었다. 용어체계는간호정보학및직업적기술적요소들을수집하 는NIDSEC (Data Set Evaluation Center)의기준및점수화 기준의일부이다(American Nurses Association, 2009). 즉 용어체계는사정진단중재결과를기록하기위해보여주, , , 도록선택된데이터종적으로저장된대상자건강데이터, 의물리적혹은논리적개요임상데이터저장소를사용하,

기위해요구되는하드웨어및소프트웨어관리및행정데, 이터의연결간호현장에서의의사결정지원근거기반실무, , 의기준에서가장기본이되는기준이다.

이렇게개발된많은표준용어체계가있으나대다수의간 호사들이전자화된기록시스템에개발자들이요구하지않 기때문에표준용어체계를사용하므로얻을수있는여러 가지이익들예를들면데이터의재사용근거기반실무, , , 의사결정지원에대한기회를놓치고있다.

상호운영성이가능한간호실무가이드라인적용을위해 서는표준화된간호용어체계의사용이요구한다이를기. 반한지역사회간호학의사례연구는실무에서교육자와 학생들을위한최상의근거를제공함과동시에오마하시 스템을자연스럽게습득할수있다임상상황과관련된모. 델로서사례연구는높은수준의문제를해결할수있는기 술을개발할수있도록전략으로서효과적이고효율적이 다유효한임상정보또는평가현상을분류하기위한다. , 양한가능성을가지고있는시나리오문제의속성을구별, 할수있도록학습자를도울수있는임상사례가제공될경 우에는가장효율적으로오마하시스템을습득할수있을 것이다(Tanner, 1995).

미국에서오마하시스템은지역사회에서메디케어(medicare)의 OASIS (Outcome and Assessment Information Set)및국제질병분류(International Classification of Diseases, ICD)와함께사용되고있으며(Westra, Solomin, & Ashley, 2006), 2015년까지모든미국인들이언제어디서나건강정 보에접근할수있기위해서전자의무기록시스템으로의전 환을꾀하고있으며공공보건에서는오마하시스템이가장, 적합한용어라고명시하였다여기에서가장핵심이되는. 간호데이터는환자중심의환자안전간호의효율과효과가, 향상시키기위해서반드시포함되어져야한다(Canham, Mao, Yoder, Connolly, & Dietz, 2008; Westra et al., 2010). 본연구대상인오마하시스템은지역사회간호사의전문 적인실무기록임상자료관리를향상시킬수있을것이, , 다지역사회간호학뿐아니라다른건강분야의학생들과. 교육자는자동화된정보시스템과임상자료를공유하고호 환할수있는정보학적준비가되어있어야한다특히임상. 실습에서오마하시스템을적용하는일은상당히중요한 기틀을제공하고가이드라인으로교육을받은학생들은간 호사로서실무에서용어체계의중요성을인식하고지역사 회정보시스템개발에적극적으로참여할수있는인력으 로양성될수있을것이다.

### 결론및제언

Informatics Nursing, 21(3), 128-133.

- Beck, K. (2002). Test driven development: By example. Massa-

오마하시스템가이드라인개발을위해프로젝트개발방 법론중백켄트(Beck, Kent)의애자일(Agile)개발방법론 을준수하여공통적프로세스인사용자요구분석을위한 페르소나사용자인터페이스및데이터베이스설계및개, 발과정은완성도가있을때까지프로세스를반복하는것 으로서조기에문제점을발견하여수정할수있었다테스. 트는 7명의간호사를대상으로 4개의지정된간호문제에 대해수행하였으며북가이드라인보다평균적으로, 21배 빠른검색결과를나타냈다.

본연구를통해개발된오마하시스템가이드라인은영 문판과동시에개발하였는데스마트폰애플리케이션으로, 국제적으로는간호진단(NANDA-International)이후처음 등재되는간호용어체계가이드라인으로서지역사회분야 의간호교육도구로적극적으로활용될뿐아니라미국의, 산호세주립대학(San Jose State University)의간호대학학 부생과언어재활치료의보건대학원생들에게다학제간협 력건강서비스를향상시킨것(Martin, 2004)과같이국내 지역사회건강제공자의다양한분야의서비스의협력을증 진시키는데확대활용할것을제언한다.

애플리케이션의평가는안드로이드마켓에서다운로드 한사용자들에의해이루어질것이다이평가에따라지속. 적인업그레이드가있을예정이며결과는지역사회논문, 지를통해보고할것이다향후에는가이드라인에국한되. 지않고전문적으로간호를수행할수있는다양한건강콘 텐츠가간호사에의해개발되어환자간호에적극적으로 활용될수있기를기대한다.

#### **REFERENCES**

- Korea Internet & Security Agency (2009). 2009-2010 The Korea mobile yearbook. Seoul: I News.

- American Nurses Association (2009, September 27). Recognized languages for nursing. Retrieved October 18, 2010, from http://www.nursingworld.org.

- Androwich, I. M., Bickford, C. J., Button, P. S., Hunter, K. M., Murphy, J., & Sensmeier, J. (2003). Clinical information systems: A framework for reaching the vision. Washington DC: ANA Publishing.

- Barton, A. J., Gilbert, L., Erickson, V., Baramee, J., Sowers, D., & Robertson, K. J. (2003). A guide to assist nurse practitioners with standardized nursing language. Computer

chusetts: Addison-Wesley Professional.

- Canham, D., Mao, C. L., Yoder, M., Connolly, P., & Dietz, E. (2008). The Omaha system and quality measurement in academic nurse-managed centers: Ten steps for implementation. Journal of Nursing Education, 47(3), 105-110.

- Ciemins, E., Coon, P., & Sorli, C. (2010). An analysis of data management tools for diabetes self-management: Can smart phone technology keep up? Journal of Diabetes Science and Technology, 4(4), 958-960.

- Cho, W. J., Yoo, I. Y., Chae, S. M., Ham, O. K., & Seo, K. M. (2002). Needs assessment of community health service using OMAHA system. Journal of Nursing Query, 11(1), 168-190.

- Correll, P. J., & Martin, K. S. (2009). The omaha system helps a public health nursing organization find its voice. Computer Informatics Nursing, 27(1), 12-16.

- De Leo, G., Gonzales, C. H., Battagiri, P., & Leroy, G. A. (2010, Feb 2). Smart-phone application and a companion website for the improvement of the communication skills of children with autism: Clinical rationale, technical development and preliminary results. Journal of Medical System, 1, 1-9. Retrieved November 30, 2010, from http://www. springerlink.com/content/5q574hl40p71234n/fulltext.pdf.

- Garvin, J. H., Martin, K. S., Stassen, D. L., & Bowles, K. H. (2008). The Omaha System. Coded data that describe patient care. Journal of Ahima, 79(3), 44-49.

- Greiner, A. C. & Knebel, E. (Eds.). (2003). Healthprofessions education: A bridge to quality. Washington DC: National Academies Press.

- Hamner, J., & Wilder, B. (2001). A new curriculum for a new millennium. Nursing Outlook, 49(3), 127-131.

- Hardiker, N. R., Hoy, D., & Casey, A. (2000). Standards for nursing terminology. Journal of the American Medical Informatics Association, 7(6), 523-528.

- Harris, M. R., Graves, J. R., Solbrig, H. R., Elkin, P. L., & Chute, C. G. (2000). Embedded structures and representation of nursing knowledge. Journal of the American Medical Informatics Association, 7(6), 539-549.

- Hunter, T., Hardwicke, J., & Rayatt, S. (2010). The smart phone: An indispensable tool for the plastic surgeon? Journal of Plastic, Reconstructive & Aesthetic Surgery, 63(4), e426427.

- Kim, S. H. (2010). Effects of perceived attributes on the purchase intention of smart phone. Journal of Korea Contents Association, 10(9), 318-326.

- Lang, N. M. (1995). Nursing data systems: The emerging framework. Washington DC: American Nurses Publishing.

- Lee, S. H., Im, M. J., & Lee, K. Y. (2010). Healthcare application

 - modeling using smart phone. Journal of the Institute of Webcasting, Internet and Telecommunication, 10(4), 3540.

- Martin, K. S. (2004). The Omaha system: A key to practice, documentation, and information management (2nd ed.). Nebraska: Health Connections Press.

- Plowfield, L. A., Hayes, E. R., & Hall-Long, B. (2005). Using the Omaha System to document the wellness needs of the elderly. The Nursing Clinics of North America, 40(4), 817829, xiii.

- Tanner, C. A. (1995). The times they are a-changing. Journal of Nursing Education, 34(6), 247.

- Westra, B. L., Oancea, C., Savik, K., & Marek, K. D. (2010). The feasibility of integrating the Omaha system data across home care agencies and vendors. Computer Informatics

Nursing, 28(3), 162-171.

- Westra, B. L., Solomon, D., & Ashley, D. M. (2006). Use of the Omaha System data to validate Medicare required outcomes in home care. Journal of Healthcare Infomation Management, 20(3), 88-94.

- Yom, Y. H., Kim, J. E., Chun, C. C., Choi, S. W., Whang, D. H., Park, K. M., et al. (2007). Development of standardized and competency-based curriculum in nursing informatics. Journal of Korean Society of Medical Informatics, 13(3), 224-236.

- Yoo, I. Y., Cho, W. J., Chae, S. M., & Kim, M. J. (2004). Community health service needs assessment in Korea using OMAHA Classification System. International Journal of Nursing Studies, 41(6), 697-700.
