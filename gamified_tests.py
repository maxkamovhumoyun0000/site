"""
Gamified tests engine — Duolingo-style, multi-type questions (no audio).

Self-contained, deterministic generation from a curated, LEVEL-TIERED word /
sentence bank so it never depends on flaky AI output or on the words table being
populated. Questions are matched to the student's level (basic / intermediate /
advanced). The public question payload never includes the correct answer;
scoring is done server-side.

Every returned question is an individually scored/numbered unit — earlier
versions bundled 5 word-translation pairs or 3 reading passages into a
single question object that was graded all-or-nothing; each pairing and
each passage is now its own question so a partially-correct attempt earns
partial credit and gets its own number in the sequence.

Reading passages are a separate, much larger pool (multiple full passages
per subject/level, each with three different possible question kinds —
heading-matching, true/false, and multiple-choice comprehension) so two
attempts rarely look identical, and the number of reading questions in a
test varies attempt to attempt instead of always being exactly 3.

Scoring per question:  correct = +2,  wrong = -3,  skipped = -1.5
"""
from __future__ import annotations

import random
from typing import Any

QUESTION_COUNT = 20
SCORE_CORRECT = 2.0
SCORE_WRONG = -3.0
SCORE_SKIP = -1.5

TIERS = ("basic", "intermediate", "advanced")

# Translations are into Uzbek (the platform base language) for both subjects.
# Each `ex` sentence contains the dictionary form of `word` verbatim so the
# fill-gap / word-order builders can locate it cleanly (incl. Russian).
_BANK: dict[str, dict[str, list[dict[str, str]]]] = {
    "English": {
        "basic": [
            {"word": "cat", "tr": "mushuk", "ex": "The cat drinks milk"},
            {"word": "dog", "tr": "it", "ex": "My dog likes to run"},
            {"word": "sun", "tr": "quyosh", "ex": "The sun is very hot"},
            {"word": "book", "tr": "kitob", "ex": "I have a new book"},
            {"word": "red", "tr": "qizil", "ex": "She has a red bag"},
            {"word": "big", "tr": "katta", "ex": "This is a big house"},
            {"word": "eat", "tr": "yemoq", "ex": "We eat bread every morning"},
            {"word": "water", "tr": "suv", "ex": "I drink water every day"},
            {"word": "house", "tr": "uy", "ex": "Their house is very clean"},
            {"word": "friend", "tr": "do'st", "ex": "He is my best friend"},
            {"word": "school", "tr": "maktab", "ex": "The school is near home"},
            {"word": "food", "tr": "ovqat", "ex": "The food is hot and tasty"},
            {"word": "happy", "tr": "baxtli", "ex": "The children are very happy"},
            {"word": "car", "tr": "mashina", "ex": "My father has a blue car"},
            {"word": "cold", "tr": "sovuq", "ex": "The water is very cold"},
        ],
        "intermediate": [
            {"word": "language", "tr": "til", "ex": "English is a useful language"},
            {"word": "weather", "tr": "ob-havo", "ex": "The weather is nice today"},
            {"word": "market", "tr": "bozor", "ex": "We buy fruit at the market"},
            {"word": "doctor", "tr": "shifokor", "ex": "The doctor helps sick people"},
            {"word": "student", "tr": "talaba", "ex": "Every student has a laptop"},
            {"word": "important", "tr": "muhim", "ex": "Sleep is important for health"},
            {"word": "difficult", "tr": "qiyin", "ex": "This exercise is quite difficult"},
            {"word": "answer", "tr": "javob", "ex": "Please write the correct answer"},
            {"word": "money", "tr": "pul", "ex": "He saves money every month"},
            {"word": "travel", "tr": "sayohat", "ex": "They love to travel abroad"},
            {"word": "future", "tr": "kelajak", "ex": "We must plan the future well"},
            {"word": "reason", "tr": "sabab", "ex": "Give me a good reason please"},
            {"word": "improve", "tr": "yaxshilamoq", "ex": "I want to improve my English"},
            {"word": "decide", "tr": "qaror qilmoq", "ex": "You must decide very soon"},
            {"word": "describe", "tr": "tasvirlamoq", "ex": "Please describe your best friend"},
        ],
        "advanced": [
            {"word": "achievement", "tr": "yutuq", "ex": "Her achievement made us proud"},
            {"word": "consequence", "tr": "oqibat", "ex": "Every action has a consequence"},
            {"word": "significant", "tr": "muhim", "ex": "This is a significant discovery"},
            {"word": "establish", "tr": "tashkil qilmoq", "ex": "They plan to establish a company"},
            {"word": "genuine", "tr": "haqiqiy", "ex": "She showed genuine interest today"},
            {"word": "inevitable", "tr": "muqarrar", "ex": "Change is inevitable in life"},
            {"word": "accomplish", "tr": "bajarmoq", "ex": "We can accomplish great things together"},
            {"word": "sufficient", "tr": "yetarli", "ex": "We have sufficient time now"},
            {"word": "deliberately", "tr": "ataylab", "ex": "He deliberately ignored the rule"},
            {"word": "enhance", "tr": "kuchaytirmoq", "ex": "Reading can enhance your vocabulary"},
            {"word": "comprehensive", "tr": "keng qamrovli", "ex": "This is a comprehensive report"},
            {"word": "anticipate", "tr": "oldindan bilmoq", "ex": "We anticipate a busy season"},
            {"word": "contribute", "tr": "hissa qo'shmoq", "ex": "Everyone should contribute good ideas"},
            {"word": "remarkable", "tr": "ajoyib", "ex": "She made remarkable progress lately"},
            {"word": "reluctant", "tr": "istaksiz", "ex": "He was reluctant to leave early"},
        ],
    },
    "Russian": {
        "basic": [
            {"word": "кот", "tr": "mushuk", "ex": "кот пьёт молоко утром"},
            {"word": "собака", "tr": "it", "ex": "собака любит быстро бегать"},
            {"word": "солнце", "tr": "quyosh", "ex": "солнце сегодня очень тёплое"},
            {"word": "книга", "tr": "kitob", "ex": "эта книга очень интересная"},
            {"word": "красный", "tr": "qizil", "ex": "у неё красный рюкзак"},
            {"word": "большой", "tr": "katta", "ex": "это очень большой дом"},
            {"word": "вода", "tr": "suv", "ex": "вода очень холодная сегодня"},
            {"word": "дом", "tr": "uy", "ex": "дом стоит у реки"},
            {"word": "друг", "tr": "do'st", "ex": "друг всегда помогает мне"},
            {"word": "школа", "tr": "maktab", "ex": "школа рядом с домом"},
            {"word": "еда", "tr": "ovqat", "ex": "еда была очень вкусная"},
            {"word": "счастливый", "tr": "baxtli", "ex": "сегодня я очень счастливый"},
            {"word": "машина", "tr": "mashina", "ex": "машина стоит возле дома"},
            {"word": "рука", "tr": "qo'l", "ex": "рука была очень холодная"},
            {"word": "холодный", "tr": "sovuq", "ex": "сегодня холодный зимний день"},
        ],
        "intermediate": [
            {"word": "язык", "tr": "til", "ex": "русский язык очень богатый"},
            {"word": "погода", "tr": "ob-havo", "ex": "погода сегодня очень хорошая"},
            {"word": "рынок", "tr": "bozor", "ex": "рынок находится за углом"},
            {"word": "врач", "tr": "shifokor", "ex": "врач помогает больным людям"},
            {"word": "студент", "tr": "talaba", "ex": "студент читает новую книгу"},
            {"word": "важный", "tr": "muhim", "ex": "сон важный для здоровья"},
            {"word": "трудный", "tr": "qiyin", "ex": "это трудный вопрос сегодня"},
            {"word": "ответ", "tr": "javob", "ex": "ответ был совершенно правильный"},
            {"word": "деньги", "tr": "pul", "ex": "деньги лежат на столе"},
            {"word": "путешествие", "tr": "sayohat", "ex": "путешествие было очень интересное"},
            {"word": "будущее", "tr": "kelajak", "ex": "будущее зависит от нас"},
            {"word": "причина", "tr": "sabab", "ex": "причина была совсем простая"},
            {"word": "улучшить", "tr": "yaxshilamoq", "ex": "я хочу улучшить произношение"},
            {"word": "решить", "tr": "qaror qilmoq", "ex": "нужно решить эту задачу"},
            {"word": "описать", "tr": "tasvirlamoq", "ex": "надо описать своего друга"},
        ],
        "advanced": [
            {"word": "достижение", "tr": "yutuq", "ex": "достижение команды нас впечатлило"},
            {"word": "последствие", "tr": "oqibat", "ex": "последствие было очень серьёзное"},
            {"word": "значительный", "tr": "ahamiyatli", "ex": "это значительный научный результат"},
            {"word": "подлинный", "tr": "haqiqiy", "ex": "она проявила подлинный интерес"},
            {"word": "неизбежный", "tr": "muqarrar", "ex": "перемены неизбежный процесс жизни"},
            {"word": "достаточный", "tr": "yetarli", "ex": "достаточный запас времени есть"},
            {"word": "установить", "tr": "o'rnatmoq", "ex": "нужно установить новые правила"},
            {"word": "усилить", "tr": "kuchaytirmoq", "ex": "чтение помогает усилить словарь"},
            {"word": "содействовать", "tr": "hissa qo'shmoq", "ex": "каждый должен содействовать общему делу"},
            {"word": "замечательный", "tr": "ajoyib", "ex": "она сделала замечательный прогресс"},
            {"word": "намеренно", "tr": "ataylab", "ex": "он намеренно нарушил правило"},
            {"word": "всесторонний", "tr": "keng qamrovli", "ex": "это всесторонний подробный отчёт"},
            {"word": "предвидеть", "tr": "oldindan bilmoq", "ex": "трудно предвидеть такой результат"},
            {"word": "выдающийся", "tr": "ko'zga ko'ringan", "ex": "это выдающийся современный учёный"},
            {"word": "неохотный", "tr": "istaksiz", "ex": "он дал неохотный короткий ответ"},
        ],
    },
}

# Real multi-sentence reading passages, tiered by difficulty. Each entry
# carries THREE independent question kinds so the same passage can surface
# as a heading-match, a true/false judgement, or a comprehension MCQ —
# `build_questions()` picks a variable number of DISTINCT passages per
# attempt and rotates which kind is asked, so readings differ both in
# content and in question style each time, not just in the 3 headings
# that used to be sampled from one tiny shared pool.
_READINGS: dict[str, dict[str, list[dict[str, Any]]]] = {
    "English": {
        "basic": [
            {
                "passage": "Tom has a small dog named Rex. Rex likes to play in the garden every morning. He runs fast and jumps over the flowers.",
                "heading": "Tom's Dog",
                "true_false": {"statement": "Rex likes to play in the garden.", "correct": True},
                "mcq": {"question": "What is the dog's name?", "options": ["Rex", "Max", "Buddy", "Leo"], "answer_index": 0},
            },
            {
                "passage": "Anna goes to school by bus every day. The bus stop is near her house. She always arrives at school on time.",
                "heading": "Anna's School Trip",
                "true_false": {"statement": "Anna walks to school every day.", "correct": False},
                "mcq": {"question": "How does Anna get to school?", "options": ["by bus", "by car", "by bike", "on foot"], "answer_index": 0},
            },
            {
                "passage": "The weather today is sunny and warm. Many people are walking in the park. Children are playing games near the lake.",
                "heading": "A Sunny Day",
                "true_false": {"statement": "It is raining today.", "correct": False},
                "mcq": {"question": "Where are the children playing?", "options": ["near the lake", "at school", "in the house", "at the shop"], "answer_index": 0},
            },
            {
                "passage": "My mother cooks dinner every evening. Today she is making soup and bread. The whole family eats together at the table.",
                "heading": "Family Dinner",
                "true_false": {"statement": "The family eats dinner together.", "correct": True},
                "mcq": {"question": "What is the mother cooking today?", "options": ["soup and bread", "rice and fish", "salad and juice", "cake and tea"], "answer_index": 0},
            },
            {
                "passage": "Sara likes to draw pictures. She draws flowers, animals, and houses. Her teacher says her pictures are very colorful.",
                "heading": "Sara Loves Drawing",
                "true_false": {"statement": "Sara draws only flowers.", "correct": False},
                "mcq": {"question": "What does Sara's teacher say about her pictures?", "options": ["they are colorful", "they are boring", "they are too small", "they are not good"], "answer_index": 0},
            },
        ],
        "intermediate": [
            {
                "passage": "Learning a new language takes time and practice. Many students give up too quickly because they expect fast results. However, small daily efforts often lead to real progress over months.",
                "heading": "The Key to Learning Languages",
                "true_false": {"statement": "Learning a language happens quickly without effort.", "correct": False},
                "mcq": {"question": "What helps most according to the text?", "options": ["small daily efforts", "giving up quickly", "expecting fast results", "avoiding practice"], "answer_index": 0},
            },
            {
                "passage": "Exercise is important for both the body and the mind. Regular physical activity can reduce stress and improve sleep. Doctors recommend at least thirty minutes of exercise most days of the week.",
                "heading": "Why Exercise Matters",
                "true_false": {"statement": "Doctors recommend exercising for hours every day.", "correct": False},
                "mcq": {"question": "How much exercise do doctors recommend?", "options": ["thirty minutes most days", "one hour every day", "ten minutes a week", "exercise is not necessary"], "answer_index": 0},
            },
            {
                "passage": "Social media has changed how people communicate. Friends and family can stay connected even when they live far apart. At the same time, spending too much time online can affect real relationships.",
                "heading": "Social Media and Communication",
                "true_false": {"statement": "Social media has no effect on relationships.", "correct": False},
                "mcq": {"question": "What can too much time online affect?", "options": ["real relationships", "the weather", "the price of food", "school buildings"], "answer_index": 0},
            },
            {
                "passage": "Recycling helps protect the environment by reducing waste. When people separate paper, plastic, and glass, factories can reuse these materials. This process saves natural resources and energy.",
                "heading": "The Benefits of Recycling",
                "true_false": {"statement": "Recycling helps protect the environment.", "correct": True},
                "mcq": {"question": "What can be reused after recycling?", "options": ["paper, plastic and glass", "only paper", "only plastic", "nothing"], "answer_index": 0},
            },
            {
                "passage": "Cooking at home is often healthier than eating at restaurants. People can choose fresh ingredients and control how much salt and sugar they use. It can also save a lot of money over time.",
                "heading": "Benefits of Cooking at Home",
                "true_false": {"statement": "Cooking at home is always more expensive than restaurants.", "correct": False},
                "mcq": {"question": "What can people control when cooking at home?", "options": ["salt and sugar amounts", "restaurant prices", "the weather", "traffic"], "answer_index": 0},
            },
        ],
        "advanced": [
            {
                "passage": "Artificial intelligence is rapidly transforming numerous industries, from healthcare to finance. While these technologies offer significant efficiency gains, they also raise important ethical questions about privacy and employment. Policymakers must balance innovation with responsible regulation.",
                "heading": "The Impact of Artificial Intelligence",
                "true_false": {"statement": "Artificial intelligence raises no ethical concerns.", "correct": False},
                "mcq": {"question": "What must policymakers balance?", "options": ["innovation and responsible regulation", "profit and marketing", "speed and color", "only privacy"], "answer_index": 0},
            },
            {
                "passage": "Climate change poses one of the most pressing challenges of our time, affecting ecosystems and human societies worldwide. Reducing carbon emissions requires coordinated international effort and significant changes in energy production. Individual actions, while valuable, cannot fully solve a problem of this scale.",
                "heading": "Addressing Climate Change",
                "true_false": {"statement": "Individual actions alone can fully solve climate change.", "correct": False},
                "mcq": {"question": "What does reducing emissions require?", "options": ["coordinated international effort", "only individual actions", "ignoring energy production", "nothing at all"], "answer_index": 0},
            },
            {
                "passage": "Effective leadership requires more than technical expertise; it demands emotional intelligence, clear communication, and the ability to inspire trust. Great leaders often listen carefully before making decisions. This approach helps them build strong, motivated teams.",
                "heading": "Qualities of Effective Leadership",
                "true_false": {"statement": "Great leaders never listen to others.", "correct": False},
                "mcq": {"question": "What helps leaders build strong teams?", "options": ["listening carefully before deciding", "ignoring their team", "making decisions alone", "avoiding communication"], "answer_index": 0},
            },
            {
                "passage": "Globalization has increased economic interdependence among nations, creating both opportunities and vulnerabilities. Supply chains now span multiple continents, making businesses more efficient but also more exposed to disruptions. Recent events have prompted many companies to reconsider their reliance on distant suppliers.",
                "heading": "Globalization and Supply Chains",
                "true_false": {"statement": "Global supply chains are only located in one country.", "correct": False},
                "mcq": {"question": "What have recent events prompted companies to do?", "options": ["reconsider reliance on distant suppliers", "expand further without limits", "ignore all risks", "stop trading entirely"], "answer_index": 0},
            },
            {
                "passage": "Urban planning plays a crucial role in shaping sustainable cities for future generations. Thoughtful design of public transportation, green spaces, and housing can significantly reduce a city's environmental footprint. Many cities are now investing heavily in these areas to prepare for continued population growth.",
                "heading": "The Importance of Urban Planning",
                "true_false": {"statement": "Urban planning has no effect on a city's environment.", "correct": False},
                "mcq": {"question": "What are many cities investing in?", "options": ["transportation, green spaces and housing", "only entertainment", "nothing new", "foreign trade"], "answer_index": 0},
            },
        ],
    },
    "Russian": {
        "basic": [
            {
                "passage": "У Тома есть маленькая собака по имени Рекс. Рекс любит играть в саду каждое утро. Он бегает быстро и прыгает через цветы.",
                "heading": "Собака Тома",
                "true_false": {"statement": "Рекс любит играть в саду.", "correct": True},
                "mcq": {"question": "Как зовут собаку?", "options": ["Рекс", "Макс", "Бадди", "Лео"], "answer_index": 0},
            },
            {
                "passage": "Анна ездит в школу на автобусе каждый день. Автобусная остановка рядом с её домом. Она всегда приходит в школу вовремя.",
                "heading": "Поездка Анны в школу",
                "true_false": {"statement": "Анна ходит в школу пешком каждый день.", "correct": False},
                "mcq": {"question": "Как Анна добирается до школы?", "options": ["на автобусе", "на машине", "на велосипеде", "пешком"], "answer_index": 0},
            },
            {
                "passage": "Сегодня солнечная и тёплая погода. Многие люди гуляют в парке. Дети играют в игры возле озера.",
                "heading": "Солнечный день",
                "true_false": {"statement": "Сегодня идёт дождь.", "correct": False},
                "mcq": {"question": "Где играют дети?", "options": ["возле озера", "в школе", "дома", "в магазине"], "answer_index": 0},
            },
            {
                "passage": "Моя мама готовит ужин каждый вечер. Сегодня она готовит суп и хлеб. Вся семья ужинает вместе за столом.",
                "heading": "Семейный ужин",
                "true_false": {"statement": "Семья ужинает вместе.", "correct": True},
                "mcq": {"question": "Что мама готовит сегодня?", "options": ["суп и хлеб", "рис и рыбу", "салат и сок", "торт и чай"], "answer_index": 0},
            },
            {
                "passage": "Сара любит рисовать картинки. Она рисует цветы, животных и дома. Её учительница говорит, что её картинки очень яркие.",
                "heading": "Сара любит рисовать",
                "true_false": {"statement": "Сара рисует только цветы.", "correct": False},
                "mcq": {"question": "Что говорит учительница о картинках Сары?", "options": ["они яркие", "они скучные", "они слишком маленькие", "они плохие"], "answer_index": 0},
            },
        ],
        "intermediate": [
            {
                "passage": "Изучение нового языка требует времени и практики. Многие студенты сдаются слишком быстро, потому что ждут быстрых результатов. Однако небольшие ежедневные усилия часто приводят к настоящему прогрессу через несколько месяцев.",
                "heading": "Ключ к изучению языков",
                "true_false": {"statement": "Язык можно выучить быстро без усилий.", "correct": False},
                "mcq": {"question": "Что помогает больше всего согласно тексту?", "options": ["небольшие ежедневные усилия", "быстрая сдача", "ожидание быстрых результатов", "отказ от практики"], "answer_index": 0},
            },
            {
                "passage": "Физические упражнения важны как для тела, так и для разума. Регулярная физическая активность снижает стресс и улучшает сон. Врачи рекомендуют минимум тридцать минут упражнений большинство дней недели.",
                "heading": "Почему важны упражнения",
                "true_false": {"statement": "Врачи рекомендуют заниматься спортом часами каждый день.", "correct": False},
                "mcq": {"question": "Сколько упражнений рекомендуют врачи?", "options": ["тридцать минут большинство дней", "один час каждый день", "десять минут в неделю", "упражнения не нужны"], "answer_index": 0},
            },
            {
                "passage": "Социальные сети изменили способ общения людей. Друзья и семья могут оставаться на связи, даже живя далеко друг от друга. В то же время слишком много времени онлайн может повлиять на настоящие отношения.",
                "heading": "Соцсети и общение",
                "true_false": {"statement": "Социальные сети никак не влияют на отношения.", "correct": False},
                "mcq": {"question": "На что может повлиять слишком много времени онлайн?", "options": ["на настоящие отношения", "на погоду", "на цены на еду", "на школьные здания"], "answer_index": 0},
            },
            {
                "passage": "Переработка отходов помогает защитить окружающую среду, уменьшая количество мусора. Когда люди разделяют бумагу, пластик и стекло, заводы могут повторно использовать эти материалы. Этот процесс экономит природные ресурсы и энергию.",
                "heading": "Польза переработки отходов",
                "true_false": {"statement": "Переработка отходов помогает защитить окружающую среду.", "correct": True},
                "mcq": {"question": "Что можно повторно использовать после переработки?", "options": ["бумагу, пластик и стекло", "только бумагу", "только пластик", "ничего"], "answer_index": 0},
            },
            {
                "passage": "Готовить дома часто полезнее, чем есть в ресторанах. Люди могут выбирать свежие продукты и контролировать количество соли и сахара. Это также может сэкономить много денег со временем.",
                "heading": "Польза домашней готовки",
                "true_false": {"statement": "Готовить дома всегда дороже, чем в ресторане.", "correct": False},
                "mcq": {"question": "Что люди могут контролировать при готовке дома?", "options": ["количество соли и сахара", "цены в ресторане", "погоду", "движение транспорта"], "answer_index": 0},
            },
        ],
        "advanced": [
            {
                "passage": "Искусственный интеллект быстро меняет многие отрасли, от медицины до финансов. Хотя эти технологии дают значительный рост эффективности, они также поднимают важные этические вопросы о приватности и занятости. Политикам необходимо находить баланс между инновациями и разумным регулированием.",
                "heading": "Влияние искусственного интеллекта",
                "true_false": {"statement": "Искусственный интеллект не вызывает этических вопросов.", "correct": False},
                "mcq": {"question": "Что должны балансировать политики?", "options": ["инновации и разумное регулирование", "прибыль и маркетинг", "скорость и цвет", "только приватность"], "answer_index": 0},
            },
            {
                "passage": "Изменение климата — одна из самых серьёзных проблем нашего времени, влияющая на экосистемы и общества по всему миру. Сокращение выбросов углерода требует согласованных международных усилий и значительных изменений в производстве энергии. Индивидуальные действия, хотя и ценны, не могут полностью решить проблему такого масштаба.",
                "heading": "Борьба с изменением климата",
                "true_false": {"statement": "Индивидуальные действия одни могут полностью решить проблему климата.", "correct": False},
                "mcq": {"question": "Что требуется для сокращения выбросов?", "options": ["согласованные международные усилия", "только индивидуальные действия", "игнорирование производства энергии", "ничего"], "answer_index": 0},
            },
            {
                "passage": "Эффективное лидерство требует не только технических знаний, но и эмоционального интеллекта, ясного общения и способности вызывать доверие. Хорошие лидеры часто внимательно слушают перед принятием решений. Такой подход помогает им создавать сильные, мотивированные команды.",
                "heading": "Качества эффективного лидерства",
                "true_false": {"statement": "Хорошие лидеры никогда не слушают других.", "correct": False},
                "mcq": {"question": "Что помогает лидерам создавать сильные команды?", "options": ["внимательно слушать перед решением", "игнорировать команду", "решать в одиночку", "избегать общения"], "answer_index": 0},
            },
            {
                "passage": "Глобализация увеличила экономическую взаимозависимость между странами, создавая как возможности, так и уязвимости. Цепочки поставок теперь охватывают несколько континентов, делая бизнес более эффективным, но и более подверженным сбоям. Последние события заставили многие компании пересмотреть свою зависимость от отдалённых поставщиков.",
                "heading": "Глобализация и цепочки поставок",
                "true_false": {"statement": "Глобальные цепочки поставок находятся только в одной стране.", "correct": False},
                "mcq": {"question": "К чему последние события подтолкнули компании?", "options": ["пересмотреть зависимость от отдалённых поставщиков", "расширяться без ограничений", "игнорировать все риски", "полностью прекратить торговлю"], "answer_index": 0},
            },
            {
                "passage": "Городское планирование играет ключевую роль в создании устойчивых городов для будущих поколений. Продуманный дизайн общественного транспорта, зелёных зон и жилья может значительно снизить экологический след города. Многие города сейчас активно инвестируют в эти области, готовясь к дальнейшему росту населения.",
                "heading": "Важность городского планирования",
                "true_false": {"statement": "Городское планирование не влияет на экологию города.", "correct": False},
                "mcq": {"question": "Во что инвестируют многие города?", "options": ["транспорт, зелёные зоны и жильё", "только развлечения", "ничего нового", "внешнюю торговлю"], "answer_index": 0},
            },
        ],
    },
}

_READING_KINDS = ("heading", "true_false", "mcq")
_NON_READING_TYPES = ("word_match", "word_order", "fill_gap", "mcq")


def _norm_subject(subject: str | None) -> str:
    s = (subject or "").strip().title()
    return s if s in _BANK else "English"


def tier_for_level(level: str | None) -> str:
    """Map a course/CEFR level label to a difficulty tier."""
    lv = (level or "").strip().upper()
    if lv in {"BEGINNER", "ELEMENTARY", "A1", "A2"}:
        return "basic"
    if lv in {"UPPER-INTERMEDIATE", "ADVANCED", "B2", "C1", "C2"}:
        return "advanced"
    # PRE-INTERMEDIATE, INTERMEDIATE, B1 and anything unknown -> intermediate
    return "intermediate"


def _bank_for(subject: str, tier: str) -> list[dict[str, str]]:
    subj = _norm_subject(subject)
    tiers = _BANK[subj]
    return tiers.get(tier) or tiers.get("intermediate") or next(iter(tiers.values()))


def _readings_for(subject: str, tier: str) -> list[dict[str, Any]]:
    subj = _norm_subject(subject)
    tiers = _READINGS[subj]
    return tiers.get(tier) or tiers.get("intermediate") or next(iter(tiers.values()))


def _sample(seq: list, k: int) -> list:
    k = max(0, min(k, len(seq)))
    return random.sample(seq, k) if k else []


def _distractor_translations(bank: list[dict[str, str]], exclude: set[str], k: int) -> list[str]:
    pool = [row["tr"] for row in bank if row["tr"] not in exclude]
    return _sample(pool, k)


def _distractor_words(bank: list[dict[str, str]], exclude: set[str], k: int) -> list[str]:
    pool = [row["word"] for row in bank if row["word"] not in exclude]
    return _sample(pool, k)


def _time_limit_for_question(q: dict[str, Any]) -> int:
    """Per-question time budget scaled by how much the student actually has
    to read/process — a one-word MCQ needs far less time than a full
    reading passage. Clamped to the requested 20s-90s range."""
    qtype = q.get("type")
    if qtype in ("reading_true_false", "reading_mcq"):
        text_len = len(str(q.get("passage") or "")) + len(str(q.get("prompt") or ""))
        # ~90 chars/sec reading speed budget, plus a flat base for deciding.
        return max(20, min(90, 30 + text_len // 6))
    if qtype == "heading_match":
        items = q.get("items") or []
        text_len = sum(len(str(item.get("text") or "")) for item in items)
        return max(20, min(90, 25 + text_len // 5))
    if qtype == "word_match":
        # More pairs to match => more time (each pair is its own unit).
        pairs = len(q.get("_answer") or {}) or 4
        return max(20, min(90, 15 + pairs * 8))
    if qtype == "word_order":
        word_count = len(q.get("words") or [])
        return max(20, min(60, 18 + word_count * 3))
    if qtype == "fill_gap":
        sentence_len = len(str(q.get("sentence") or ""))
        return max(20, min(45, 20 + sentence_len // 8))
    # mcq (single word translation) — quick.
    return 20


def _score_units(q: dict[str, Any]) -> int:
    """How many separately-scored questions a block represents. Matching
    blocks (word_match/heading_match) count each pair/item individually;
    everything else is a single unit."""
    if q.get("type") in ("word_match", "heading_match"):
        return max(1, len(q.get("_answer") or {}))
    return 1


def _make_reading_from_ai(r: dict[str, Any]) -> dict[str, Any] | None:
    """Convert one AI-generated reading passage (passage/question/options/
    answer_index) into a gamified reading_mcq question. Returns None if the
    payload is malformed so the caller can skip it."""
    passage = str(r.get("passage") or "").strip()
    question = str(r.get("question") or "").strip()
    options = [str(o).strip() for o in (r.get("options") or []) if str(o).strip()]
    ai = r.get("answer_index")
    if not passage or not question or len(options) < 4 or ai is None:
        return None
    try:
        ai = int(ai)
    except Exception:
        return None
    options = options[:4]
    if not (0 <= ai < len(options)):
        return None
    correct_option = options[ai]
    shuffled = options[:]
    random.shuffle(shuffled)
    return {
        "index": 0,
        "type": "reading_mcq",
        "prompt": question,
        "passage": passage,
        "options": shuffled,
        "_answer": shuffled.index(correct_option),
    }


def _make_word_match(bank: list[dict[str, str]], idx: int, pairs: int = 4) -> dict[str, Any]:
    """`pairs` words shown against `pairs` shuffled translations (4 of each
    by default). Each individual pairing is scored separately (see
    `_score_units`/`score_session`), so one word_match block counts as
    `pairs` questions toward the test total — that's why the client also
    checks each pair in place and tallies correct/wrong per pair."""
    pairs = max(2, min(pairs, len(bank)))
    picks = _sample(bank, pairs)
    left = [p["word"] for p in picks]
    right = [p["tr"] for p in picks]
    shuffled_right = right[:]
    random.shuffle(shuffled_right)
    return {
        "index": idx,
        "type": "word_match",
        "prompt": "So'zlarni tarjimasi bilan moslang",
        "left": left,
        "right": shuffled_right,
        "_answer": {p["word"]: p["tr"] for p in picks},
    }


def _tokenize(sentence: str) -> list[str]:
    return [w for w in sentence.replace(".", "").replace(",", "").split() if w]


def _make_word_order(bank: list[dict[str, str]], idx: int) -> dict[str, Any]:
    row = random.choice(bank)
    tokens = _tokenize(row["ex"])
    distractors = _distractor_words(bank, {row["word"]}, 2)
    chips = tokens + distractors
    random.shuffle(chips)
    return {
        "index": idx,
        "type": "word_order",
        "prompt": "Gapni to'g'ri tartibda tuzing",
        "words": chips,
        "_answer": tokens,
    }


def _make_fill_gap(bank: list[dict[str, str]], idx: int) -> dict[str, Any]:
    row = random.choice(bank)
    tokens = _tokenize(row["ex"])
    target = row["word"]
    # find the target token (case-insensitive) to blank out
    blank_pos = next((i for i, t in enumerate(tokens) if t.lower() == target.lower()), None)
    if blank_pos is None:
        blank_pos = 0
        target = tokens[0]
    display = tokens[:]
    display[blank_pos] = "____"
    options = [target] + _distractor_words(bank, {row["word"], target}, 3)
    random.shuffle(options)
    return {
        "index": idx,
        "type": "fill_gap",
        "prompt": "Bo'sh joyni to'ldiring",
        "sentence": " ".join(display),
        "options": options,
        "_answer": options.index(target),
    }


def _make_mcq(bank: list[dict[str, str]], idx: int) -> dict[str, Any]:
    row = random.choice(bank)
    options = [row["tr"]] + _distractor_translations(bank, {row["tr"]}, 3)
    random.shuffle(options)
    return {
        "index": idx,
        "type": "mcq",
        "prompt": f"\"{row['word']}\" so'zining tarjimasi qaysi?",
        "options": options,
        "_answer": options.index(row["tr"]),
    }


def _make_reading_heading(passage_row: dict[str, Any], distractor_headings: list[str], idx: int) -> dict[str, Any]:
    """A single reading passage matched against its heading among a few
    distractor headings pulled from other passages in the same pool —
    reuses the exact `items`/`headings` wire shape the old bundled version
    used, just with exactly one item so it's individually scored."""
    headings = [passage_row["heading"]] + distractor_headings
    random.shuffle(headings)
    return {
        "index": idx,
        "type": "heading_match",
        "prompt": "Matnga mos sarlavhani tanlang",
        "items": [{"id": "0", "text": passage_row["passage"]}],
        "headings": headings,
        "_answer": {"0": passage_row["heading"]},
    }


def _make_reading_true_false(passage_row: dict[str, Any], idx: int) -> dict[str, Any]:
    tf = passage_row["true_false"]
    answer_index = 0 if tf["correct"] else 1
    return {
        "index": idx,
        "type": "reading_true_false",
        "prompt": tf["statement"],
        "passage": passage_row["passage"],
        "options": ["To'g'ri", "Noto'g'ri"],
        "_answer": answer_index,
    }


def _make_reading_mcq(passage_row: dict[str, Any], idx: int) -> dict[str, Any]:
    mcq = passage_row["mcq"]
    options = list(mcq["options"])
    correct_option = options[int(mcq["answer_index"])]
    shuffled = options[:]
    random.shuffle(shuffled)
    return {
        "index": idx,
        "type": "reading_mcq",
        "prompt": mcq["question"],
        "passage": passage_row["passage"],
        "options": shuffled,
        "_answer": shuffled.index(correct_option),
    }


def build_questions(
    subject: str | None,
    level: str | None = None,
    count: int = QUESTION_COUNT,
    *,
    vocab: list[dict[str, str]] | None = None,
    ai_readings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Builds a gamified test of `count` scored UNITS (matching blocks count
    each pair as a unit). When `vocab`/`ai_readings` are supplied (freshly
    AI-generated per attempt — see `ai_generator.generate_gamified_material`)
    they're used instead of the static curated bank, so questions don't
    repeat between attempts; if they're missing/insufficient the static bank
    is used as a reliable fallback."""
    subj = _norm_subject(subject)
    tier = tier_for_level(level)
    bank = vocab if (vocab and len(vocab) >= 5) else _bank_for(subj, tier)

    questions: list[dict[str, Any]] = []
    units = 0

    # --- Readings ---
    if ai_readings:
        # Fresh AI passages -> reading_mcq (varied content every attempt).
        for r in ai_readings:
            if units >= count:
                break
            q = _make_reading_from_ai(r)
            if q:
                questions.append(q)
                units += 1
    else:
        readings_pool = _readings_for(subj, tier)
        max_readings = min(len(readings_pool), 5)
        reading_count = random.randint(min(2, max_readings), max_readings) if max_readings else 0
        chosen_readings = random.sample(readings_pool, reading_count) if reading_count else []
        kind_order = list(_READING_KINDS)
        random.shuffle(kind_order)
        for i, passage_row in enumerate(chosen_readings):
            if units >= count:
                break
            kind = kind_order[i % len(kind_order)]
            if kind == "heading":
                other_headings = [r["heading"] for r in readings_pool if r is not passage_row]
                questions.append(_make_reading_heading(passage_row, _sample(other_headings, 3), 0))
            elif kind == "true_false":
                questions.append(_make_reading_true_false(passage_row, 0))
            else:
                questions.append(_make_reading_mcq(passage_row, 0))
            units += 1

    # --- Non-reading, cycling through the types until the unit budget is met ---
    guard = 0
    ni = 0
    while units < count and guard < count * 4:
        guard += 1
        t = _NON_READING_TYPES[ni % len(_NON_READING_TYPES)]
        ni += 1
        if t == "word_match":
            pairs = min(4, len(bank), count - units)
            if pairs < 2:
                questions.append(_make_mcq(bank, 0))
                units += 1
            else:
                q = _make_word_match(bank, 0, pairs=pairs)
                questions.append(q)
                units += _score_units(q)
        elif t == "word_order":
            questions.append(_make_word_order(bank, 0))
            units += 1
        elif t == "fill_gap":
            questions.append(_make_fill_gap(bank, 0))
            units += 1
        else:
            questions.append(_make_mcq(bank, 0))
            units += 1

    random.shuffle(questions)
    # Re-number sequentially after shuffling so `index` always matches the
    # final display order regardless of how the types were interleaved.
    for i, q in enumerate(questions):
        q["index"] = i
    return questions


def public_question(q: dict[str, Any]) -> dict[str, Any]:
    """The client-facing question without the correct answer. Adds a
    per-question `time_limit_sec` sized to the question's actual reading
    load (20s-90s) rather than one flat number for every question."""
    out = {k: v for k, v in q.items() if k != "_answer"}
    out["time_limit_sec"] = _time_limit_for_question(q)
    out["score_units"] = _score_units(q)
    return out


def score_answer(q: dict[str, Any], answer: Any) -> str:
    """Returns 'correct' | 'wrong' | 'skipped' for a single question."""
    if answer is None:
        return "skipped"
    correct = q.get("_answer")
    qtype = q.get("type")
    try:
        if qtype in ("mcq", "fill_gap", "reading_true_false", "reading_mcq"):
            return "correct" if int(answer) == int(correct) else "wrong"
        if qtype == "word_order":
            submitted = [str(w) for w in (answer or [])]
            return "correct" if submitted == list(correct) else "wrong"
        if qtype in ("word_match", "heading_match"):
            if not isinstance(answer, dict) or not answer:
                return "skipped" if not answer else "wrong"
            for key, val in correct.items():
                if str(answer.get(key, "")) != str(val):
                    return "wrong"
            return "correct"
    except Exception:
        return "wrong"
    return "wrong"


def score_session(
    questions: list[dict[str, Any]],
    answers_by_index: dict[int, Any],
    *,
    correct_score: float | None = None,
    wrong_score: float | None = None,
    skip_score: float | None = None,
) -> dict[str, Any]:
    c_val = float(correct_score) if correct_score is not None else SCORE_CORRECT
    w_val = float(wrong_score) if wrong_score is not None else SCORE_WRONG
    s_val = float(skip_score) if skip_score is not None else SCORE_SKIP
    correct = wrong = skipped = 0
    for q in questions:
        ans = answers_by_index.get(int(q.get("index", -1)))
        qtype = q.get("type")
        if qtype in ("word_match", "heading_match"):
            # Each pair/item is its own scored unit (matches the client's
            # per-pair check + the "N correct / M wrong" tally it shows).
            correct_map = q.get("_answer") or {}
            submitted = ans if isinstance(ans, dict) else {}
            for key, val in correct_map.items():
                sub = submitted.get(key)
                if sub is None or str(sub).strip() == "":
                    skipped += 1
                elif str(sub) == str(val):
                    correct += 1
                else:
                    wrong += 1
            continue
        outcome = score_answer(q, ans)
        if outcome == "correct":
            correct += 1
        elif outcome == "wrong":
            wrong += 1
        else:
            skipped += 1
    score = c_val * correct + w_val * wrong + s_val * skipped
    return {
        "correct": correct,
        "wrong": wrong,
        "skipped": skipped,
        "total": correct + wrong + skipped,
        "score": round(score, 1),
    }
