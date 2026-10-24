# 📋 รายงานสรุปรายการความผิดปกติของคำแปลและบทที่ลืมแปลทั้งหมด (300 แถว)

- **วันที่ตรวจสอบ:** 2026-10-02 21:20:39
- **จำนวนรายการที่พบทั้งหมด:** 151 แถว
- **เป้าหมาย:** สแกนตรวจสอบเพื่อเตรียมล้างช่อง Initial เป็นค่าว่างสำหรับส่งไปแปลซ่อมในขั้นตอนถัดไป

---

## 📊 สรุปจำนวนแยกตามหมวดหมู่

| ลำดับ | หมวดหมู่ความผิดปกติ | จำนวน (แถว) |
| :---: | :--- | :---: |
| 1 | Speaker Collisions | **0** |
| 2 | Semantic Drift | **1** |
| 3 | Silent Hallucinations | **0** |
| 4 | Choice Branch Leaks | **0** |
| 5 | Consecutive Duplicates | **37** |
| 6 | Untranslated Story Dialogues | **113** |
| | **รวมทั้งหมด** | **151** |

---

## 📌 หมวดหมู่: Speaker Collisions (0 รายการ)

*ไม่พบรายการความผิดปกติในหมวดนี้*

## 📌 หมวดหมู่: Semantic Drift (1 รายการ)

| แถว (CSV Row) | ไฟล์ (File) | เหตุผล (Reason) | Original | Initial (คำแปลปัจจุบัน) |
| :---: | :---: | :--- | :--- | :--- |
| `38064` | `Map082` | `SHORT_ORIG_HUGE_INIT (15 chars vs 37 chars)` | \n<Dan:>(Their..\.skin..\.) | \n<Dan:>Dan:<br>(ผิวของพวกเขา..\.ผิว..ของพวกเขา..\.) |

---

## 📌 หมวดหมู่: Silent Hallucinations (0 รายการ)

*ไม่พบรายการความผิดปกติในหมวดนี้*

## 📌 หมวดหมู่: Choice Branch Leaks (0 รายการ)

*ไม่พบรายการความผิดปกติในหมวดนี้*

## 📌 หมวดหมู่: Consecutive Duplicates (37 รายการ)

| แถว (CSV Row) | ไฟล์ (File) | เหตุผล (Reason) | Original | Initial (คำแปลปัจจุบัน) |
| :---: | :---: | :--- | :--- | :--- |
| `1156` | `CommonEvents` | `CONSECUTIVE_DUPLICATE (Sim: 0.80)` | \n<Dan:>Okay, I'm going for the card with the dog <br>imprint. | \n<Dan:>โอเค ผมจะเลือกการ์ดที่มีรอย<br>พิมพ์หมา |
| `4809` | `Map009` | `CONSECUTIVE_DUPLICATE (Sim: 0.70)` | \n<Rum:>You need more Tomatoes, kid. Get them at Mayor's<br>Farms.  | \n<Rum:>ต้องการมะเขือเทศเพิ่มสินะ<br>เจ้าหนู ไปเอาที่ฟาร์มของนายกเทศมนตรีสิ |
| `8196` | `Map017` | `CONSECUTIVE_DUPLICATE (Sim: 0.86)` | \n<Dan:>(The vehicle plate reads \\|\\|\fb\C[18]RV039\\|6\C\fb)\\|\\| | \n<Dan:>(ป้ายทะเบียนรถเขียนว่า \\|\\|\fb\C[18]RV039\\|6\C[0]\fb)\\|\\| |
| `9909` | `Map021` | `CONSECUTIVE_DUPLICATE (Sim: 0.75)` | \n<Shion:>(Y-\.Yeah!\\| This is the last time <br>I'll be spending time with that person..!)  | \n<Shion:>(อ-\.อือ!\\|<br>นี่จะเป็นครั้งสุดท้ายแล้ว ที่ฉันจะได้ใช้เวลากับคนคนนั้น..!) |
| `12203` | `Map030` | `CONSECUTIVE_DUPLICATE (Sim: 0.79)` | \n<Lily:>Kikazaru, who represents \fbHear no evil\fb.<br>Covering his ears.\. | \n<Lily:>Kikazaru ผู้เป็นตัวแทนของ \fbการไม่ฟังสิ่งชั่วร้าย\fb<br>กำลังเอามือปิดหูเอาไว้ค่ะ\. |
| `12306` | `Map031` | `CONSECUTIVE_DUPLICATE (Sim: 0.89)` | \n<Lily:>What are you doing here, big bro..?\. | \n<Lily:>พี่มาทำอะไรที่นี่เหรอคะ..?\. |
| `12935` | `Map031` | `CONSECUTIVE_DUPLICATE (Sim: 0.73)` | \n<Erica:>My age is 28..\\|I will always...28..\. | \n<Erica:>อายุของฉันคือ 28 ปี..\\|ฉันจะอายุ...28 ปีตลอดไป..\. |
| `13138` | `Map032` | `CONSECUTIVE_DUPLICATE (Sim: 0.83)` | \n<Lucas:>Ah hello there. I was about to leave but<br>our village's Lumberjack told me to stay here because it<br>would be a good idea to promote our teahouse to the<br>people here... | \n<Lucas:>อา สวัสดีครับ ผมกำลังจะกลับพอดี แต่<br>คนตัดไม้ประจำหมู่บ้านของเราบอกให้ผมอยู่ที่นี่ต่อ<br>เพราะ เขาคิดว่าน่าจะเป็นความคิดที่ดีที่จะโปรโมตร้านน้ำชา<br>ของเราให้ผู้คนที่นี่ได้รู้จัก... |
| `14831` | `Map036` | `CONSECUTIVE_DUPLICATE (Sim: 0.86)` | \n<Dan:>(The vehicle plate reads \\|\\|\fb\C[18]RV039\\|6\C\fb)\\|\\| | \n<Dan:>(ป้ายทะเบียนรถเขียนว่า \\|\\|\fb\C[18]RV039\\|6\C[0]\fb)\\|\\| |
| `17713` | `Map040` | `CONSECUTIVE_DUPLICATE (Sim: 0.76)` | \n<Dan:>(Bakery's not this way.) | \n<Dan:>(เบเกอรี่ไม่ได้อยู่ทางนี้) |
| `23606` | `Map050` | `CONSECUTIVE_DUPLICATE (Sim: 0.80)` | \n<Jinnie:>Mmm..well, I have a few friends over here.<br>And I've found a way to make money.\. So..<br>y'know, a girl's got to eat!  | \n<Jinnie:>อืมม..คือว่า ฉันมีเพื่อนอยู่แถวนี้นิดหน่อยค่ะ<br>แล้วฉันก็หาวิธีหาเงินได้แล้วด้วย\. เพราะงั้น..<br>ก็รู้นี่คะ ผู้หญิงเราก็ต้องกินต้องใช้เหมือนกัน! |
| `24635` | `Map050` | `CONSECUTIVE_DUPLICATE (Sim: 0.82)` | \n<University Student B:>\}the seniors better pay us<br>or something after this..what even is the point of <br>humoring this newbie?  | \n<เด็กมหา'ลัย B:>\}พวกรุ่นพี่น่าจะจ่ายอะไรให้พวกเราบ้างนะ<br>หลังจากเรื่องนี้..<br>แล้วจะเอาใจเด็กใหม่คนนี้ไปทำไมกัน? |
| `27686` | `Map060` | `CONSECUTIVE_DUPLICATE (Sim: 0.73)` | \n<Erica:>...ha..\\|...ggh...ha....\\| | \n<Erica:>...ฮา..\\|...อึก...ฮา....\\| |
| `28428` | `Map064` | `CONSECUTIVE_DUPLICATE (Sim: 0.74)` | \n<Shion:>Thanks for accompanying me, Dan..\\|<br>Even though I didn't buy much, it was still a nice<br>way to destress~♥ | \n<Shion:>ขอบคุณที่มาด้วยกันนะคะ Dan..\\|<br>ถึงฉันจะไม่ได้ซื้ออะไรมาก แต่ก็เป็นวิธีคลายเครียด<br>ที่ดีเหมือนกันนะคะ~♥ |
| `29047` | `Map066` | `CONSECUTIVE_DUPLICATE (Sim: 0.74)` | \n<Shion:>(I wish I can say something, anything, <br>that will help cheer him up...) | \n<Shion:>(ฉันอยากพูดอะไรสักอย่าง ไม่ว่าอะไรก็ได้<br>ที่จะช่วยทำให้เขารู้สึกดีขึ้นสักหน่อย...) |
| `29740` | `Map066` | `CONSECUTIVE_DUPLICATE (Sim: 0.85)` | \n<Shion:>That's not the issue at all..!\\| I can't <br>believe you..\.you....\\| | \n<Shion:>Shion: นั่นไม่ใช่ประเด็นเลยสักนิดค่ะ..!\\|<br>ฉันไม่อยากเชื่อคุณเลย..\.คุณ....\\| |
| `30221` | `Map069` | `CONSECUTIVE_DUPLICATE (Sim: 0.90)` | \n<Otto:>Ah hello..\\|Um, do you happen to know where the<br>lady who came with you work..?\\| A-Ah no, it's nothing<br>suspicious..she's just so beautiful that I want to<br>see her again..\\| | \n<Otto:>Otto: อา สวัสดีครับ..\\|เอ่อ คุณพอจะทราบไหมครับ<br>ว่าคุณผู้หญิงที่มากับคุณทำงานอยู่ที่ไหนเหรอครับ..?\\|อ-อา เปล่านะครับ<br>ไม่ได้มีอะไรน่าสงสัย..เธอแค่สวยมากจนผมอยากจะเจอเธออีก<br>สักครั้งน่ะครับ..\\| |
| `30768` | `Map071` | `CONSECUTIVE_DUPLICATE (Sim: 0.90)` | \n<Erica:>R-Right..!\\| Um..some place called Young<br>Sapphire..\.That's where Ritchie used to work..\\|<br>....\\|I have to go..!  | \n<Erica:>Erica: จ-จริงด้วยค่ะ..!\\|เอ่อ..ที่หนึ่งที่เรียกว่า<br>Young Sapphire ค่ะ..\.ที่นั่นคือที่ที่ Ritchie เคยทำงานอยู่ค่ะ..\\|<br>​....\\|ฉันต้องไปแล้วค่ะ..! |
| `31377` | `Map072` | `CONSECUTIVE_DUPLICATE (Sim: 0.76)` | \n<Masaru:>uugggh...\\|yeah...\\|they weren't<br>able to make it tonight..\. | \n<Masaru:>Masaru: อั้กกก...\\|ใช่ครับ...\\|<br>พวกเขามาไม่ได้ในคืนนี้น่ะครับ..\. |
| `33984` | `Map077` | `CONSECUTIVE_DUPLICATE (Sim: 0.78)` | \n<Dan:>(I'm a little worried about Shion but there's<br>no reason for me to go back to the RV. If I waste<br>anymore time, we'll lose our seat at the Robster.)  | \n<Dan:>Dan: (ผมแอบเป็นห่วง Shion อยู่นิดหน่อย<br>แต่ผมไม่มีเหตุผลอะไรให้ต้องกลับไปที่รถ RV<br>ถ้าผมเสียเวลาไปมากกว่านี้ เราจะเสียที่นั่งที่ Robster ไป) |
| `36756` | `Map081` | `CONSECUTIVE_DUPLICATE (Sim: 0.71)` | \n<Crowd:>And it will begin anew!!!\\|\^ | \n<ฝูงชน:>Crowd:<br>และทุกอย่างจะเริ่มต้นขึ้นใหม่อีกครั้ง!!!\\|\^ |
| `47276` | `Map091` | `CONSECUTIVE_DUPLICATE (Sim: 0.83)` | \n<Dan:>(I guess this area's no go for now. I'm<br>not invited to whatever this is.) | \n<Dan:>(ผมเดาว่าพื้นที่ตรงนี้คงเข้าไม่ได้ชั่วคราวสินะ<br>ผมไม่ได้รับเชิญให้มาร่วมงานอะไรแบบนี้สักหน่อย) |
| `47937` | `Map092` | `CONSECUTIVE_DUPLICATE (Sim: 0.98)` | \n<Priest:>And may faith guide the way..\. | \n<นักบวช:>และขอให้ศรัทธานำทาง..\.\. |
| `52461` | `Map105` | `CONSECUTIVE_DUPLICATE (Sim: 0.98)` | \n<Young boy:>\fbWe don't have a name.\fb\. | \n<หนุ่มน้อย:>\fbพวกเราไม่มีชื่อหรอกครับ\fb\.\. |
| `56781` | `Map117` | `CONSECUTIVE_DUPLICATE (Sim: 0.70)` | \n<Rum:>You need more Tomatoes, kid. Get them at Mayor's<br>Farms.  | \n<Rum:>ต้องการมะเขือเทศเพิ่มสินะ<br>เจ้าหนู ไปเอาที่ฟาร์มของนายกเทศมนตรีสิ |
| `62560` | `Map128` | `CONSECUTIVE_DUPLICATE (Sim: 0.75)` | \n<Shion:>Nyah? Nyah nyah nyah? Nya! | \n<Shion:>เหมียว? เหมียว เหมียว เหมียว? เหมียว! |
| `62561` | `Map128` | `CONSECUTIVE_DUPLICATE (Sim: 0.85)` | \n<Cat-person:>Hmm, nya nyah nya meow nya.  | \n<มนุษย์แมว:>อืม เหมียวเหมียว เหมียว เมี้ยว เหมียว. |
| `63715` | `Map132` | `CONSECUTIVE_DUPLICATE (Sim: 0.76)` | \n<Dan:>Huh?! Okay, you got to be messing with me.\.<br>I knew it, Drake must have sent you to stall for<br>time!\. | \n<Dan:>หา?! เอาล่ะ คุณต้องล้อผมเล่นแน่ๆ\.<br>ผมว่าแล้วเชียว Drake<br>ต้องส่งคุณมาถ่วงเวลาแน่ๆ!\.\. |
| `65427` | `Map136` | `CONSECUTIVE_DUPLICATE (Sim: 0.86)` | \n<Jinnie:>Uhm..sorry to interrupt your meeting with<br>this..\.I-I hope it doesn't get in Hikari's way too..\. | \n<Jinnie:>อืม..ขอโทษที่ต้องมาขัดจังหวะการประชุมของคุณด้วย<br>เรื่องนี้นะคะ..\.\|ข-ฉันหวังว่ามันจะไม่ไปขวางทาง Hikari ด้วยนะคะ..\.\.\. |
| `65739` | `Map138` | `CONSECUTIVE_DUPLICATE (Sim: 0.76)` | \n<Dan:>(The film wallpaper..\.<br>Man, they look so slim that it's crazy how advanced<br>monitors and screens has become throughout<br>the years.)\. | \n<Dan:>(วอลเปเปอร์ฟิล์มพวกนั้น..\.<br>\|โธ่เอ๊ย พวกมันบางเฉียบจนไม่น่าเชื่อเลยว่าเทคโนโลยีมอนิเตอร์และ<br>หน้าจอจะก้าวหน้าไปได้ไกลขนาดนี้ตลอดหลายปี<br>ที่ผ่านมา)\.\.\. |
| `66318` | `Map139` | `CONSECUTIVE_DUPLICATE (Sim: 0.80)` | \n<Dan:>(Now, because of the tech, you can fold your<br>phone into a little square and put it in your pocket.\.<br>That tech was then brought over to TVs and Monitors..)\. | \n<Dan:>(เดี๋ยวนี้ด้วยเทคโนโลยี<br>เราสามารถพับโทรศัพท์ให้เป็นสี่เหลี่ยมเล็กๆ แล้วใส่กระเป๋าได้แล้ว\.<br>\|เทคโนโลยีนั่นก็ถูกนำมาต่อยอดกับทีวีและมอนิเตอร์ด้วย..)\.\.\. |
| `67147` | `Map141` | `CONSECUTIVE_DUPLICATE (Sim: 0.77)` | \n<Dan:>(I'll need to be more \fiprecise\fi on<br>where I'm focusing on. What I can see is so limited<br>that if I can't focus on two things at once so..) | \n<Dan:>(ผมคงต้อง\fiเล็งให้แม่นยำ\fiกว่านี้<br>ว่ากำลังโฟกัสตรงไหนอยู่ สิ่งที่ผมมองเห็นมีจำกัดมาก<br>จนถ้าผมโฟกัสสองอย่างพร้อมกันไม่ได้ เพราะงั้น..) |
| `70916` | `Map147` | `CONSECUTIVE_DUPLICATE (Sim: 0.84)` | \n<Dan:>Yeah! Don't worry about a thing.<br>(I won't let anything happen to Hikari.) | \n<Dan:>ใช่! ไม่ต้องกังวลอะไรทั้งนั้นนะครับ<br>(ผมจะไม่ยอมให้ Hikari เป็นอะไรไปเด็ดขาด) |
| `71077` | `Map147` | `CONSECUTIVE_DUPLICATE (Sim: 0.78)` | \n<Dan:>(And finally, the top part..) | \n<Dan:>(และสุดท้าย ส่วนด้านบน..) |
| `71080` | `Map147` | `CONSECUTIVE_DUPLICATE (Sim: 0.77)` | \n<Dan:>(Finally...the top part.) | \n<Dan:>(ในที่สุด...ส่วนด้านบน) |
| `77018` | `Map155` | `CONSECUTIVE_DUPLICATE (Sim: 0.77)` | \n<Jinnie:>What you're carrying...\.<br>together, they weight a total of 3kg.<br>Whatever's in there is slightly heavy.. | \n<Jinnie:>ของที่คุณกำลังถืออยู่...\.<br>รวมกันแล้วหนักทั้งหมด 3 กิโลกรัมค่ะ<br>อะไรก็ตามที่อยู่ข้างในค่อนข้างหนักนะคะ.. |
| `77903` | `Map158` | `CONSECUTIVE_DUPLICATE (Sim: 0.81)` | \n<\C[31]Jinnie\C>What you're carrying...\.<br>together, they weight a total of 2kg.<br>Whatever's in there is not really heavy.. | \n<\C[31]Jinnie\C>ของที่คุณกำลังถืออยู่...\.<br>รวมกันแล้วหนักทั้งหมด 2 กิโลกรัมค่ะ<br>อะไรก็ตามที่อยู่ข้างในไม่ค่อยหนักเท่าไหร่ค่ะ.. |

---

## 📌 หมวดหมู่: Untranslated Story Dialogues (113 รายการ)

| แถว (CSV Row) | ไฟล์ (File) | เหตุผล (Reason) | Original | Initial (คำแปลปัจจุบัน) |
| :---: | :---: | :--- | :--- | :--- |
| `1451` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 18G)` | 18G | 18G |
| `1452` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 20G)` | 20G | 20G |
| `1453` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 21G)` | 21G | 21G |
| `1457` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 48G)` | 48G | 48G |
| `1458` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 42G)` | 42G | 42G |
| `1459` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 54G)` | 54G | 54G |
| `1460` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 15G)` | 15G | 15G |
| `1461` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 14G)` | 14G | 14G |
| `1462` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 27G)` | 27G | 27G |
| `1463` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 23G)` | 23G | 23G |
| `1464` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 33G)` | 33G | 33G |
| `1465` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 24G)` | 24G | 24G |
| `1466` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 38G)` | 38G | 38G |
| `1467` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 26G)` | 26G | 26G |
| `1468` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 28G)` | 28G | 28G |
| `1469` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 67G)` | 67G | 67G |
| `1470` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 57G)` | 57G | 57G |
| `1471` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 58G)` | 58G | 58G |
| `1472` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 62G)` | 62G | 62G |
| `1473` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 64G)` | 64G | 64G |
| `1474` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 66G)` | 66G | 66G |
| `1475` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 12G)` | 12G | 12G |
| `1476` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 53G)` | 53G | 53G |
| `1477` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 36G)` | 36G | 36G |
| `1549` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 46G)` | 46G | 46G |
| `1550` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 29G)` | 29G | 29G |
| `1551` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 30G)` | 30G | 30G |
| `1552` | `CommonEvents` | `UNTRANSLATED_DIALOGUE (Words: 52G)` | 52G | 52G |
| `29933` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 18G)` | 18G | 18G |
| `29934` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 20G)` | 20G | 20G |
| `29935` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 21G)` | 21G | 21G |
| `29939` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 48G)` | 48G | 48G |
| `29940` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 42G)` | 42G | 42G |
| `29941` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 54G)` | 54G | 54G |
| `29942` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 15G)` | 15G | 15G |
| `29943` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 14G)` | 14G | 14G |
| `29944` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 27G)` | 27G | 27G |
| `29945` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 23G)` | 23G | 23G |
| `29946` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 33G)` | 33G | 33G |
| `29947` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 24G)` | 24G | 24G |
| `29948` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 38G)` | 38G | 38G |
| `29949` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 26G)` | 26G | 26G |
| `29950` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 28G)` | 28G | 28G |
| `29951` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 67G)` | 67G | 67G |
| `29952` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 57G)` | 57G | 57G |
| `29953` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 58G)` | 58G | 58G |
| `29954` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 62G)` | 62G | 62G |
| `29955` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 64G)` | 64G | 64G |
| `29956` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 66G)` | 66G | 66G |
| `29957` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 12G)` | 12G | 12G |
| `29958` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 53G)` | 53G | 53G |
| `29959` | `Map066` | `UNTRANSLATED_DIALOGUE (Words: 36G)` | 36G | 36G |
| `35914` | `Map080` | `UNTRANSLATED_DIALOGUE (Words: HJ2)` | HJ2 | HJ2 |
| `35915` | `Map080` | `UNTRANSLATED_DIALOGUE (Words: HJ3)` | HJ3 | HJ3 |
| `42986` | `Map086` | `UNTRANSLATED_DIALOGUE (Words: MASAAAARUUU)` | \n<KJ:>Masaru..\\|MASAAAARUUU!!!!! | \n<KJ:>KJ:<br>Masaru..\\|MASAAAARUUU!!!!! |
| `48999` | `Map094` | `UNTRANSLATED_DIALOGUE (Words: Shioon)` | \n<Dan:>\C[27]Shioon!!!\C\\|\\|\^ | \n<Dan:>\C[27]Shioon!!!\C[0]\\|\\|\^ |
| `52609` | `Map105` | `UNTRANSLATED_DIALOGUE (Words: Red)` | \n<Saru:>\fb\C[18]Red Arthur\fb\C | \n<Saru:>\fb\C[18]Red Arthur\fb\C[0] |
| `55897` | `Map112` | `UNTRANSLATED_DIALOGUE (Words: Li, ly)` | \n<Dan:>Li..\.ly..?\.<br>....Lily!!\. | \n<Dan:>Li..\\|Lily..?\\|<br>....Lily!!\\|\.\.\. |
| `61410` | `Map127` | `UNTRANSLATED_DIALOGUE (Words: Daann)` | \n<Shion:>Daann!!♥ | \n<Shion:>Daann!!♥ |
| `61866` | `Map127` | `UNTRANSLATED_DIALOGUE (Words: Dex)` | \n<Dan:>(Dex..?)\. | \n<Dan:>(Dex..?)\. |
| `69094` | `Map145` | `UNTRANSLATED_DIALOGUE (Words: Vive, la, France)` | \n<Shion:>Bonjour!!~ Vive la France! | \n<Shion:>Bonjour!!~ Vive la France! |
| `69106` | `Map145` | `UNTRANSLATED_DIALOGUE (Words: Ratatouille)` | \n<Man with Gold Tie:>..Ratatouille!!~ | \n<ชายเนกไททอง:>..Ratatouille!!~ |
| `69157` | `Map145` | `UNTRANSLATED_DIALOGUE (Words: Gratin, Baguette)` | \n<Shion:>Jean Gratin Baguette? | \n<Shion:>Jean Gratin Baguette? |
| `69717` | `Map145` | `UNTRANSLATED_DIALOGUE (Words: Cherina)` | Cherina | Cherina |
| `69719` | `Map145` | `UNTRANSLATED_DIALOGUE (Words: Cherika)` | Cherika | Cherika |
| `74530` | `Map151` | `UNTRANSLATED_DIALOGUE (Words: Cherina)` | Cherina | Cherina |
| `74532` | `Map151` | `UNTRANSLATED_DIALOGUE (Words: Cherika)` | Cherika | Cherika |
| `75632` | `Map152` | `UNTRANSLATED_DIALOGUE (Words: Riiley)` | \n<Dan:>R-Riiley..?! | \n<Dan:>R-Riiley..?! |
| `76022` | `Map152` | `UNTRANSLATED_DIALOGUE (Words: Cherina)` | Cherina | Cherina |
| `76024` | `Map152` | `UNTRANSLATED_DIALOGUE (Words: Cherika)` | Cherika | Cherika |
| `79374` | `Map163` | `UNTRANSLATED_DIALOGUE (Words: Bloody)` | <c:8,280,60,Window4>\}\}\}\}\fb\C[18]Bloody Mary..~\C\fb  | <c:8,280,60,Window4>\}\}\}\}\fb\C[18]Bloody Mary..~\C[0]\fb |
| `80735` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP002)` | MAP002 | MAP002 |
| `80736` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP003)` | MAP003 | MAP003 |
| `80737` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP004)` | MAP004 | MAP004 |
| `80747` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP014)` | MAP014 | MAP014 |
| `80755` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP022)` | MAP022 | MAP022 |
| `80760` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP026)` | MAP026 | MAP026 |
| `80761` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP027)` | MAP027 | MAP027 |
| `80782` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: Useless)` | BeachGameDRAFTS(Useless) | BeachGameDRAFTS(Useless) |
| `80800` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP067)` | MAP067 | MAP067 |
| `80822` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP090)` | MAP090 | MAP090 |
| `80838` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: Shinomiyalab2)` | Shinomiyalab2 | Shinomiyalab2 |
| `80839` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: Shinomiyalab3)` | Shinomiyalab3 | Shinomiyalab3 |
| `80840` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP109)` | MAP109 | MAP109 |
| `80841` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: event)` | SaunaRoom(event) | SaunaRoom(event) |
| `80844` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: Bakeryminigame)` | Bakeryminigame | Bakeryminigame |
| `80847` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: Cellar, Passage)` | Cellar Passage 1 | Cellar Passage 1 |
| `80854` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP123)` | MAP123 | MAP123 |
| `80857` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: BB_Washroom)` | BB_Washroom | BB_Washroom |
| `80861` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: BB_Washroom, REC)` | BB_Washroom(REC) | BB_Washroom(REC) |
| `80877` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: PG, Backstreet)` | PG(Backstreet) | PG(Backstreet) |
| `80880` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP149)` | MAP149 | MAP149 |
| `80881` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP150)` | MAP150 | MAP150 |
| `80882` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP151)` | MAP151 | MAP151 |
| `80883` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP152)` | MAP152 | MAP152 |
| `80884` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP153)` | MAP153 | MAP153 |
| `80885` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP154)` | MAP154 | MAP154 |
| `80886` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP155)` | MAP155 | MAP155 |
| `80887` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP156)` | MAP156 | MAP156 |
| `80888` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP157)` | MAP157 | MAP157 |
| `80889` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP158)` | MAP158 | MAP158 |
| `80890` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP159)` | MAP159 | MAP159 |
| `80891` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP160)` | MAP160 | MAP160 |
| `80892` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: BB, First, Stage)` | BB (Bar) First Stage | BB (Bar) First Stage |
| `80894` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: BB, Tutorial)` | BB (Tutorial | BB (Tutorial |
| `80895` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: BB, Second, Stage)` | BB (Bar) Second Stage | BB (Bar) Second Stage |
| `80897` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: MAP166)` | MAP166 | MAP166 |
| `80898` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: BB, Third, Stage)` | BB (Bar) Third Stage | BB (Bar) Third Stage |
| `80899` | `MapInfos` | `UNTRANSLATED_DIALOGUE (Words: BB, Fourth, Stage)` | BB (Bar) Fourth Stage | BB (Bar) Fourth Stage |
| `82505` | `Tilesets` | `UNTRANSLATED_DIALOGUE (Words: Shopping2)` | Shopping2 | Shopping2 |
| `82507` | `Tilesets` | `UNTRANSLATED_DIALOGUE (Words: Shopping3)` | Shopping3 | Shopping3 |
| `82527` | `Tilesets` | `UNTRANSLATED_DIALOGUE (Words: VIPAREA)` | VIPAREA(PeachGarden) | VIPAREA(PeachGarden) |
| `82531` | `Tilesets` | `UNTRANSLATED_DIALOGUE (Words: Underground2)` | Underground2 | Underground2 |

---

