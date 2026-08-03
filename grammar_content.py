"""
Grammar content + quizzes.

For now we ship A1 topics you pasted (1–5). Add more topics later by extending A1_TOPICS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class GrammarQuestion:
    prompt: str
    options: List[str]  # exactly 4
    correct_index: int  # 0..3


@dataclass(frozen=True)
class GrammarTopic:
    topic_id: str        # stable id
    level: str           # A1/A2/B1/B2/C1
    title: str
    rule: str
    questions: List[GrammarQuestion]
    subject: str = "English"


def _q(prompt: str, a: str, b: str, c: str, d: str, correct: str) -> GrammarQuestion:
    correct = correct.strip().upper()
    idx = {"A": 0, "B": 1, "C": 2, "D": 3}[correct]
    options = [a, b, c, d]
    # Auto-disambiguate duplicated options so each poll variant is unique.
    # This keeps old content working while preventing ambiguous answer choices.
    seen: dict[str, int] = {}
    for i, opt in enumerate(options):
        base = (opt or "").strip()
        if base not in seen:
            seen[base] = i
            options[i] = base
            continue
        first_i = seen[base]
        target_i = i
        if i == idx and first_i != idx:
            # Preserve the correct option text and adjust the earlier duplicate instead.
            target_i = first_i
        suffix_n = 2
        candidate = options[target_i]
        while candidate in options[:target_i] + options[target_i + 1:]:
            candidate = f"{base} (alt {suffix_n})"
            suffix_n += 1
        options[target_i] = candidate
        # Refresh seen map after mutation.
        seen = {}
        for k, v in enumerate(options):
            if v not in seen:
                seen[v] = k
    return GrammarQuestion(prompt=prompt, options=options, correct_index=idx)


# ========= A1 =========

A1_TOPICS: List[GrammarTopic] = [
    GrammarTopic(
        topic_id="a1_to_be",
        level="A1",
        title='To be (am/is/are)',
        rule=("🇺🇿 O‘zbekcha:\n"
            "\"To be\" fe’li – bu \"bo‘lmoq\" degani.\n"
            "Hozirgi zamonda 3 xil shakli bor:\n"
            "I → am\n"
            "He / She / It → is\n"
            "You / We / They → are\n\n"
            "🇷🇺 Русский:\n"
            "Глагол \"to be\" означает \"быть\".\n"
            "В настоящем времени имеет 3 формы:\n"
            "I → am\n"
            "He / She / It → is\n"
            "You / We / They → are\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive (Oddiy gap)\n"
            "Formula:\n"
            "Subject + am/is/are\n"
            "Examples:\n"           
            "I am a student\n"
            "She is happy\n"
            "They are teachers\n\n"
            "❌ Negative (Inkor)\n"
            "Formula:\n"
            "Subject + am/is/are + not\n"
            "Short forms:\n"
            "am not\n"           
            "isn’t\n"
            "aren’t\n"
            "Examples:\n"
            "I am not tired\n"
            "He isn’t my friend\n"
            "We aren’t ready\n\n"
            "❓ Question (Savol)\n"
            "Formula:\n"
            "Am/Is/Are + subject ?\n"
            "Examples:\n"
            "Are you ready?\n"        
            "Is she your sister?\n"
            "Am I late?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. \"I\" doim \"am\" bilan ishlaydi\n"
            "❌ I is student\n"          
            "✅ I am student\n\n"
            "🟢 2. He / She / It → doim \"is\"\n"
            "He is tall\n"
            "She is doctor\n"
            "It is big\n\n"
            "🟢 3. Ko‘plik → are\n"
            "They are students\n"
            "We are friends\n\n"
            "🟢 4. Qisqartmalar (Short forms)\n"          
            "I am → I’m\n"
            "He is → He’s\n"
            "They are → They’re\n\n"
            "📌 4. MISOLLAR (Examples)\n"
            "I am 17 years old\n"
            "She is from Uzbekistan\n"
            "We are in school\n"
            "It is cold today\n"
            "You are my friend\n"),
        questions=[
            _q("I ___ a student", "is", "are", "am", "be", "C"),
            _q("She ___ happy", "am", "is", "are", "be", "B"),
            _q("They ___ teachers", "is", "am", "are", "be", "C"),
            _q("We ___ not ready", "is", "am", "are", "be", "C"),
            _q("He ___ my brother", "is", "are", "am", "be", "A"),
            _q("I ___ not tired", "is", "are", "am", "be", "C"),
            _q("___ you a student?", "Is", "Am", "Are", "Be", "C"),
            _q("___ she your friend?", "Am", "Are", "Is", "Be", "C"),
            _q("They ___ not at home", "is", "are", "am", "be", "B"),
            _q("It ___ a dog", "am", "are", "is", "be", "C"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_pronouns",
        level="A1",
        title="Subject Pronouns (I/you/he/she/it/we/they)",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Shaxs olmoshlari – gapda “kim?” yoki “nima?” ni bildiradi va fe’l oldidan keladi. Doim katta harf bilan boshlanadi.\n"
            "I → men\n"
            "You → sen/siz\n"
            "He → u (erkak)\n"
            "She → u (ayol)\n"
            "It → u (narsa/hayvon)\n"
            "We → biz\n"
            "They → ular\n\n"
            "🇷🇺 Русский:\n"
            "Личные местоимения – показывают “кто?” или “что?” в предложении, стоят перед глаголом. Всегда с заглавной буквы.\n"
            "I → я\n"
            "You → ты/вы\n"
            "He → он\n"
            "She → она\n"
            "It → оно/это\n"
            "We → мы\n"
            "They → они\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive (Oddiy gap)\n"
            "Formula: Pronoun + am/is/are + ...\n"
            "Examples:\n"
            "I am a student.\n"
            "You are happy.\n"
            "He is tall.\n\n"
            "❌ Negative (Inkor)\n"
            "Formula: Pronoun + am/is/are + not\n"
            "Examples:\n"
            "I am not tired.\n"
            "She is not here.\n\n"
            "❓ Question (Savol)\n"
            "Formula: Am/Is/Are + pronoun + ...?\n"
            "Examples:\n"
            "Are you from Uzbekistan?\n"
            "Is he your brother?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. “I” doim katta harf va faqat “am” bilan ishlaydi\n"
            "🟢 2. He – faqat erkak uchun, She – faqat ayol uchun\n"
            "🟢 3. It – narsalar va hayvonlar uchun\n"
            "🟢 4. You – bitta yoki ko‘p odam uchun bir xil ishlatiladi\n\n"
            "📌 4. MISOLLAR (Examples)\n"
            "I am 17 years old.\n"
            "She is my teacher.\n"
            "It is a big house.\n"
            "We are friends.\n"
            "They are in Tashkent.\n"
            "You are welcome.\n"),
        questions=[
            _q("___ am a student.", "He", "She", "I", "It", "C"),
            _q("___ is my sister.", "He", "She", "It", "We", "B"),
            _q("___ are teachers.", "He", "She", "They", "It", "C"),
            _q("___ is a book.", "I", "You", "It", "We", "C"),
            _q("___ are from Uzbekistan.", "He", "She", "We", "It", "C"),
            _q("___ is tall.", "He", "She", "It", "They", "A"),
            _q("___ you a doctor?", "Am", "Is", "Are", "Be", "C"),
            _q("___ is my brother.", "She", "He", "It", "We", "B"),
            _q("___ are happy.", "He", "She", "They", "It", "C"),
            _q("___ is cold today.", "I", "You", "It", "We", "C"),
        ],
    ),
    
    GrammarTopic(
        topic_id="a1_possessive_adj",
        level="A1",
        title="Possessive Adjectives (my/your/his/her/its/our/their)",
        rule=("🇺🇿 O‘zbekcha:\n"
        "Egalik sifatlari – “kimning?” degan savolga javob beradi. Ot oldidan keladi va o‘zgarmaydi. \n"
        "my – mening, your – sening/sizning, his – uning (erkak), her – uning (ayol), its – uning (narsa), our – bizning, their – ularning\n\n"
        "🇷🇺 Русский:\n"
        "Притяжательные прилагательные – отвечают на вопрос “чей?”. Стоят перед существительным и не изменяются. \n"
        "my – мой, your – твой/ваш, his – его, her – её, its – его/её, our – наш, their – их\n\n"
        "Formula: Possessive adjective + noun\n"
        "Examples:\n"
        "This is my book.\n"
        "Her name is Anna.\n\n"
        "Formula: Possessive adjective + noun + is/are not\n"
        "Examples:\n"
        "This is not your car.\n\n"
        "Formula: Is/Are + possessive adjective + noun?\n"
        "Examples:\n"
        "Is this your house?\n\n"
        "Maxsus Qoidalar:\n"
        "1. His (erkak), Her (ayol), Its (narsa/hayvon)\n"
        "2. Our va Their ko‘plik uchun\n"
        "3. Possessive adjective + ot (hech qachon “the” bilan birga emas)\n"
        "4. Your – bitta va ko‘p uchun bir xil\n\n"
        "Misol: This is my phone. His car is red. Our teacher is kind. Their house is big. Her eyes are blue.\n\n"
        "📌 2. GAP TUZILISHI\n"
        "✅ Positive\n"
        "Formula: Possessive adjective + noun\n"
        "Examples:\n"
        "This is my book.\n"
        "Her name is Anna.\n\n"
        "❌ Negative\n"
        "Formula: Possessive adjective + noun + is/are not\n"
        "Examples:\n"
        "This is not your car.\n\n"
        "❓ Question\n"
        "Formula: Is/Are + possessive adjective + noun?\n"
        "Examples:\n"
        "Is this your house?\n\n"
        "📌 3. MAXSUS QOIDALAR\n"
        "🟢 1. His (erkak), Her (ayol), Its (narsa/hayvon)\n"
        "🟢 2. Our va Their ko‘plik uchun\n"
        "🟢 3. Possessive adjective + ot (hech qachon “the” bilan birga emas)\n"
        "🟢 4. Your – bitta va ko‘p uchun bir xil\n\n"
        "📌 4. MISOLLAR\n"
        "This is my phone.\n"
        "His car is red.\n"
        "Our teacher is kind.\n"
        "Their house is big.\n"
        "Her eyes are blue.\n"),
        questions=[
            _q("This is ___ book.", "his", "my", "her", "its", "B"),
            _q("___ name is Anna.", "My", "Her", "His", "Our", "B"),
            _q("___ car is new.", "Their", "His", "Her", "Its", "B"),
            _q("Is this ___ house?", "my", "your", "his", "her", "B"),
            _q("___ teacher is from Tashkent.", "Our", "My", "Their", "Its", "A"),
            _q("___ eyes are green.", "They", "Her", "Its", "My", "B"),
            _q("This is not ___ pen.", "your", "my", "his", "her", "A"),
            _q("___ books are on the table.", "My", "Their", "His", "Her", "B"),
            _q("___ dog is small.", "Its", "Their", "Our", "Your", "A"),
            _q("Is ___ brother a student?", "your", "their", "his", "her", "C"),
        ],
    ),

    GrammarTopic(
        topic_id="a1_demonstratives",
        level="A1",
        title="Demonstratives (this/that/these/those)",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Ko‘rsatish olmoshlari – narsani yaqin yoki uzoqda ekanligini bildiradi.\n"
            "This / These → yaqin (bitta/ko‘p)\n"
            "That / Those → uzoq (bitta/ko‘p)\n\n"
            "🇷🇺 Русский:\n"
            "Указательные местоимения – показывают близко или далеко.\n"
            "This / These → близко\n"
            "That / Those → далеко\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: This/That + is + noun / These/Those + are + noun\n"
            "Examples:\n"
            "This is a pen.\n"
            "Those are books.\n\n"
            "❌ Negative\n"
            "Formula: This/That + is not / These/Those + are not\n"
            "Examples:\n"
            "That is not my bag.\n\n"
            "❓ Question\n"
            "Formula: Is this/that ...? / Are these/those ...?\n"
            "Examples:\n"
            "Are these your shoes?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. This/That – bitta narsa uchun\n"
            "🟢 2. These/Those – ko‘p narsa uchun\n"
            "🟢 3. Yaqin uchun “this/these”, uzoq uchun “that/those”\n"
            "🟢 4. “Is” yoki “are” bilan ishlatiladi\n\n"
            "📌 4. MISOLLAR\n"
            "This is my phone.\n"
            "That is a big house.\n"
            "These are apples.\n"
            "Those are cars.\n"
            "This is cold.\n"),
        questions=[
            _q("___ is a book.", "These", "Those", "This", "That", "C"),
            _q("___ are pens.", "This", "That", "These", "Those", "C"),
            _q("___ is your car?", "This", "That", "These", "Those", "B"),
            _q("___ books are on the table.", "This", "That", "These", "Those", "C"),
            _q("Is ___ your bag?", "this", "that", "these", "those", "A"),
            _q("___ are my friends.", "This", "That", "These", "Those", "C"),
            _q("___ is not my phone.", "This", "That", "These", "Those", "B"),
            _q("Are ___ your shoes?", "this", "that", "these", "those", "C"),
            _q("___ house is big.", "This", "That", "These", "Those", "B"),
            _q("___ apples are red.", "This", "That", "These", "Those", "C"),
        ],
    ),

    GrammarTopic(
        topic_id="a1_articles_plurals",
        level="A1",
        title="Articles (a/an) + Plurals",
        rule=("🇺🇿 O‘zbekcha:\n"
            "a – undosh harf oldidan, an – unli harf oldidan (bitta narsa uchun).\n"
            "Ko‘plik: +s, +es, irregular (man → men, child → children).\n\n"
            "🇷🇺 Русский:\n"
            "a – перед согласной, an – перед гласной.\n"
            "Множественное число: +s, +es, неправильные формы.\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: a/an + singular noun / plural noun\n"
            "Examples:\n"
            "I have a dog.\n"
            "They are students.\n\n"
            "❌ Negative\n"
            "Formula: I don’t have a/an ...\n"
            "Examples:\n"
            "I don’t have an apple.\n\n"
            "❓ Question\n"
            "Formula: Do you have a/an ...? / Are they ...?\n"
            "Examples:\n"
            "Is it a cat?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. a – undosh (a book), an – unli (an apple)\n"
            "🟢 2. Ko‘plikda “a/an” ishlatilmaydi\n"
            "🟢 3. Irregular plurals: child-children, man-men\n"
            "🟢 4. “The” A1 da hali to‘liq emas (keyinroq)\n\n"
            "📌 4. MISOLLAR\n"
            "I have a cat.\n"
            "She has an orange.\n"
            "They are children.\n"
            "These are books.\n"
            "We have two dogs.\n\n"),
        questions=[
            _q("I have ___ dog.", "a", "an", "the", "—", "A"),
            _q("This is ___ apple.", "a", "an", "the", "—", "B"),
            _q("They are ___.", "student", "students", "a student", "an student", "B"),
            _q("I don’t have ___ car.", "a", "an", "the", "—", "A"),
            _q("Are they ___?", "child", "children", "a child", "an child", "B"),
            _q("She eats ___ orange.", "a", "an", "the", "—", "B"),
            _q("We have ___ books.", "a", "an", "no article", "the", "C"),
            _q("This is ___ man.", "a", "an", "the", "—", "A"),
            _q("___ women are teachers.", "a", "an", "no article", "the", "C"),
            _q("He has ___ cat.", "a", "an", "the", "—", "A"),
        ],
    ),

    GrammarTopic(
        topic_id="a1_there_is_are",
        level="A1",
        title="There is / There are",
        rule=("🇺🇿 O‘zbekcha:\n"
            "“There is / There are” – “bor” degani.\n"
            "Bitta narsa → There is\n"
            "Ko‘p narsa → There are\n\n"
            "🇷🇺 Русский:\n"
            "“There is / There are” – означает “есть”.\n"
            "Единственное → There is\n"
            "Множественное → There are\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: There is + singular / There are + plural\n"
            "Examples:\n"
            "There is a book on the table.\n"
            "There are two cats.\n\n"
            "Единственное → There is\n"
            "Множественное → There are\n\n"
            "📌 3. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: There is + singular / There are + plural\n"
            "Examples:\n"
            "There is a book on the table.\n"
            "There are two cats.\n\n"
            "❌ Negative\n"
            "Formula: There is not / There are not (isn’t / aren’t)\n"
            "Examples:\n"
            "There isn’t a car.\n"
            "There aren’t any dogs.\n\n"
            "❓ Question\n"
            "Formula: Is there ...? / Are there ...?\n"
            "Examples:\n"
            "Is there a pen? Yes, there is.\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Bitta → is, Ko‘p → are\n"
            "🟢 2. Short forms: There’s, There isn’t, There aren’t\n"
            "🟢 3. “Any” inkor va savolda ko‘plik bilan\n"
            "🟢 4. Javob: Yes, there is. / No, there isn’t.\n\n"
            "📌 4. MISOLLAR\n"
            "There is a phone on the table.\n"
            "There are three books.\n"
            "There isn’t any milk.\n"
            "Are there any students? Yes, there are.\n"
            "There are two dogs in the garden.\n\n"),
        questions=[
            _q("___ a book on the table.", "There are", "There is", "There", "Is there", "B"),
            _q("___ two cats.", "There is", "There are", "There", "Are there", "B"),
            _q("___ any milk?", "There is", "There are", "Is there", "Are there", "C"),
            _q("There ___ a car.", "are", "isn’t", "aren’t", "is not", "D"),
            _q("There ___ students.", "is", "are", "isn’t", "aren’t", "B"),
            _q("___ any dogs? No, there ___.", "Is there / isn’t", "Are there / aren’t", "There is / is", "There are / are", "B"),
            _q("There ___ a pen.", "is", "are", "isn’t", "aren’t", "A"),
            _q("There ___ three apples.", "is", "are", "isn’t", "aren’t", "B"),
            _q("Is there ___ ?", "a book", "books", "any book", "the book", "A"),
            _q("There ___ any water.", "is", "are", "isn’t", "aren’t", "C"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_have_got",
        level="A1",
        title="Have got / Has got",
        rule=("🇺🇿 O‘zbekcha:\n"
            "“Have got” – “ega bo‘lmoq” yoki “bor” degani.\n"
            "I/You/We/They → have got\n"
            "He/She/It → has got\n\n"
            "🇷🇺 Русский:\n"
            "“Have got” означает “иметь” или “есть”.\n"
            "I/You/We/They → have got\n"
            "He/She/It → has got\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive (Oddiy gap)\n"
            "Formula: Subject + have/has got + object\n"
            "Examples:\n"
            "I have got a car.\n"
            "She has got a cat.\n\n"
            "❌ Negative (Inkor)\n"
            "Formula: Subject + haven’t/hasn’t got\n"
            "Examples:\n"
            "I haven’t got a phone.\n"
            "He hasn’t got a brother.\n\n"
            "❓ Question (Savol)\n"
            "Formula: Have/Has + subject + got ...?\n"
            "Examples:\n"
            "Have you got a sister?\n"
            "Has she got blue eyes?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. He/She/It → has got (s qo‘shiladi)\n"
            "🟢 2. Short forms: I’ve got, She’s got, haven’t got, hasn’t got\n"
            "🟢 3. “Any” inkor va savolda ishlatiladi\n"
            "🟢 4. Javob: Yes, I have. / No, I haven’t.\n\n"
            "📌 4. MISOLLAR\n"
            "I have got two brothers.\n"
            "She has got long hair.\n"
            "We haven’t got a dog.\n"
            "Have you got a pen? Yes, I have.\n"
            "It has got big eyes.\n\n"),
        questions=[
            _q("I ___ a car.", "has got", "have got", "has", "have", "B"),
            _q("She ___ a cat.", "have got", "has got", "have", "has", "B"),
            _q("They ___ any money.", "has got", "haven’t got", "hasn’t got", "have", "B"),
            _q("___ you got a sister?", "Has", "Have", "Is", "Are", "B"),
            _q("He ___ blue eyes.", "have got", "has got", "haven’t", "hasn’t", "B"),
            _q("We ___ a big house.", "has got", "have got", "hasn’t", "haven’t", "B"),
            _q("___ she got a phone?", "Has", "Have", "Is", "Are", "A"),
            _q("It ___ four legs.", "have got", "has got", "haven’t", "hasn’t", "B"),
            _q("I ___ any brothers.", "has got", "have got", "haven’t got", "hasn’t got", "C"),
            _q("___ they got a car? Yes, they ___.", "Has / has", "Have / have", "Is / is", "Are / are", "B"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_present_simple",
        level="A1",
        title="Present Simple",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Hozirgi oddiy zamon – odatlar, faktlar va har doim bo‘ladigan ishlar uchun.\n"
            "I/You/We/They → verb (do)\n"
            "He/She/It → verb + s/es\n\n"
            "🇷🇺 Русский:\n"
            "Настоящее простое время – для привычек, фактов и того, что происходит всегда.\n"
            "I/You/We/They → глагол\n"
            "He/She/It → глагол + s/es\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + verb (+s/es)\n"
            "Examples:\n"
            "I play football.\n"
            "She plays tennis.\n\n"
            "❌ Negative\n"
            "Formula: Subject + don’t/doesn’t + verb\n"
            "Examples:\n"
            "I don’t like coffee.\n"
            "He doesn’t work.\n\n"
            "❓ Question\n"
            "Formula: Do/Does + subject + verb?\n"
            "Examples:\n"
            "Do you live in Tashkent?\n"
            "Does she speak English?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. He/She/It → +s (plays), +es (watches, goes)\n"
            "🟢 2. Short forms: don’t, doesn’t\n"
            "🟢 3. Always/usually/sometimes bilan ishlatiladi\n"
            "🟢 4. Javob: Yes, I do. / No, he doesn’t.\n\n"
            "📌 4. MISOLLAR\n"
            "I go to school every day.\n"
            "She works in a bank.\n"
            "We don’t eat meat.\n"
            "Do you speak Uzbek? Yes, I do.\n"
            "It rains a lot here.\n\n"),
        questions=[
            _q("She ___ tennis.", "play", "plays", "plaies", "playing", "B"),
            _q("I ___ coffee.", "don’t like", "doesn’t like", "not like", "no like", "A"),
            _q("___ you live in Tashkent?", "Does", "Do", "Is", "Are", "B"),
            _q("He ___ English.", "speak", "speaks", "speaks", "speakes", "B"),
            _q("They ___ meat.", "doesn’t eat", "don’t eat", "not eat", "eats", "B"),
            _q("___ she work here?", "Does", "Do", "Is", "Are", "A"),
            _q("We ___ to school.", "goes", "go", "going", "goed", "B"),
            _q("It ___ every day.", "rain", "rains", "rains", "raining", "B"),
            _q("I ___ TV in the evening.", "watch", "watch", "watches", "watching", "A"),
            _q("___ he play football? Yes, he ___.", "Do / do", "Does / does", "Is / is", "Are / are", "B"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_present_continuous",
        level="A1",
        title="Present Continuous",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Hozirgi davomiy zamon – hozir sodir bo‘layotgan ishlar uchun.\n"
            "Formula: am/is/are + verb-ing\n\n"
            "🇷🇺 Русский:\n"
            "Настоящее длительное время – для действий, которые происходят сейчас.\n"
            "Formula: am/is/are + глагол-ing\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + am/is/are + verb-ing\n"
            "Examples:\n"
            "I am reading a book.\n"
            "She is cooking.\n\n"
            "❌ Negative\n"
            "Formula: Subject + am/is/are + not + verb-ing\n"
            "Examples:\n"
            "I am not sleeping.\n\n"
            "❓ Question\n"
            "Formula: Am/Is/Are + subject + verb-ing?\n"
            "Examples:\n"
            "Are you studying?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. I → am, He/She/It → is, You/We/They → are\n"
            "🟢 2. Short forms: I’m, He’s, They’re, isn’t, aren’t\n"
            "🟢 3. Now/right now/this moment bilan ishlatiladi\n"
            "🟢 4. -ing qo‘shish: run→running, have→having\n\n"
            "📌 4. MISOLLAR\n"
            "I am eating now.\n"
            "She is watching TV.\n"
            "They are playing football.\n"
            "Are you working? Yes, I am.\n"
            "It is raining today.\n\n"),
        questions=[
            _q("I ___ a book now.", "read", "am reading", "reads", "reading", "B"),
            _q("She ___ TV.", "is watch", "is watching", "watches", "watching", "B"),
            _q("___ you studying?", "Is", "Are", "Am", "Do", "B"),
            _q("They ___ football.", "is playing", "are playing", "plays", "playing", "B"),
            _q("He ___ not sleeping.", "am", "is", "is", "are", "B"),
            _q("We ___ dinner.", "are cooking", "is cooking", "cooks", "cooking", "A"),
            _q("___ it raining?", "Is", "Are", "Am", "Does", "A"),
            _q("I ___ to music.", "am listen", "am listening", "listens", "listening", "B"),
            _q("She ___ a letter.", "is write", "is writing", "writes", "writing", "B"),
            _q("You ___ now.", "are working", "is working", "works", "working", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_simple_vs_continuous",
        level="A1",
        title="Present Simple vs Present Continuous",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Present Simple = har doim / odat\n"
            "Present Continuous = hozir / bir marta\n"
            "Simple: always, usually, every day\n"
            "Continuous: now, right now, at the moment\n\n"
            "🇷🇺 Русский:\n"
            "Present Simple = всегда / привычка\n"
            "Present Continuous = сейчас / один раз\n"
            "Simple: always, usually, every day\n"
            "Continuous: now, right now, at the moment\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Simple: I play football every day.\n"
            "Continuous: I am playing football now.\n\n"
            "❌ Negative\n"
            "Simple: She doesn’t drink tea.\n"
            "Continuous: She isn’t drinking tea now.\n\n"
            "❓ Question\n"
            "Simple: Do you work here?\n"
            "Continuous: Are you working now?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Simple – doimiy faktlar va odatlar\n"
            "🟢 2. Continuous – faqat hozirgi lahzada\n"
            "🟢 3. “Like, love, want, know” faqat Simple bilan\n"
            "🟢 4. I live in Tashkent (Simple) vs I am living with friends now (Continuous)\n\n"
            "📌 4. MISOLLAR\n"
            "I live in Tashkent. (Simple)\n"
            "I am living with my friend now. (Continuous)\n"
            "She works in a bank. (Simple)\n"
            "She is working now. (Continuous)\n"
            "We don’t eat meat. (Simple)\n\n"),
        questions=[
            _q("I ___ in Tashkent. (doimiy)", "am living", "live", "lives", "living", "B"),
            _q("Look! She ___ now.", "cooks", "is cooking", "cook", "cooked", "B"),
            _q("He ___ football every Sunday.", "is playing", "plays", "play", "playing", "B"),
            _q("___ you working now?", "Do", "Are", "Does", "Is", "B"),
            _q("They ___ meat. (odat)", "aren’t eating", "don’t eat", "doesn’t eat", "not eating", "B"),
            _q("I ___ TV at the moment.", "watch", "am watching", "watches", "watching", "B"),
            _q("She ___ English very well. (fakt)", "is speaking", "speaks", "speak", "speaking", "B"),
            _q("We ___ dinner now.", "have", "are having", "has", "having", "B"),
            _q("___ he play tennis? (umumiy savol)", "Is", "Does", "Do", "Are", "B"),
            _q("Right now I ___ a book.", "read", "am reading", "reads", "reading", "B"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_prep_place",
        level="A1",
        title="Prepositions of Place (in/on/under/next to...)",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Joy bildiruvchi predloglar:\n"
            "in – ichida\n"
            "on – ustida\n"
            "under – ostida\n"
            "next to / beside – yonida\n"
            "behind – orqasida\n"
            "in front of – oldida\n\n"
            "🇷🇺 Русский:\n"
            "Предлоги места:\n"
            "in – внутри\n"
            "on – на\n"
            "under – под\n"
            "next to / beside – рядом\n"
            "behind – за\n"
            "in front of – перед\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + verb + preposition + place\n"
            "Examples:\n"
            "The book is on the table.\n"
            "The cat is under the bed.\n\n"
            "❌ Negative\n"
            "Formula: Subject + verb + not + preposition\n"
            "Examples:\n"
            "The keys are not in the bag.\n\n"
            "❓ Question\n"
            "Formula: Is/Are + subject + preposition...?\n"
            "Examples:\n"
            "Is the pen next to the book?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. in – xona, shahar, mamlakat (in the room, in Tashkent)\n"
            "🟢 2. on – yuza (on the table, on the wall)\n"
            "🟢 3. under – pastda\n"
            "🟢 4. next to / beside – yonma-yon\n\n"
            "📌 4. MISOLLAR\n"
            "The book is on the table.\n"
            "My phone is in my bag.\n"
            "The dog is under the chair.\n"
            "She is next to the window.\n"
            "The school is in front of the park.\n\n"),
        questions=[
            _q("The book is ___ the table.", "in", "on", "under", "next to", "B"),
            _q("My keys are ___ the bag.", "on", "in", "under", "behind", "B"),
            _q("The cat is ___ the bed.", "in", "on", "under", "next to", "C"),
            _q("She sits ___ me.", "in", "on", "next to", "under", "C"),
            _q("The car is ___ the house.", "in front of", "behind", "on", "under", "A"),
            _q("The picture is ___ the wall.", "in", "on", "under", "next to", "B"),
            _q("___ the room there is a bed.", "On", "In", "Under", "Next to", "B"),
            _q("The ball is ___ the table.", "in", "on", "under", "behind", "C"),
            _q("He lives ___ Tashkent.", "on", "in", "under", "next to", "B"),
            _q("The chair is ___ the door.", "in", "on", "next to", "under", "C"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_prep_time",
        level="A1",
        title="Prepositions of Time (at/in/on)",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Vaqt bildiruvchi predloglar:\n"
            "at – soat vaqti (at 5 o’clock)\n"
            "in – kunning qismi, oy, yil (in the morning, in March)\n"
            "on – kun va sana (on Monday, on 15th May)\n\n"
            "🇷🇺 Русский:\n"
            "Предлоги времени:\n"
            "at – точное время (at 5 o’clock)\n"
            "in – часть дня, месяц, год (in the morning, in March)\n"
            "on – день недели и дата (on Monday, on 15th May)\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + verb + at/in/on + time\n"
            "Examples:\n"
            "I go to school at 8 o’clock.\n"
            "She works in the morning.\n\n"
            "❌ Negative\n"
            "Formula: Subject + verb + not + at/in/on\n"
            "Examples:\n"
            "We don’t study on Sunday.\n\n"
            "❓ Question\n"
            "Formula: Do/Does + subject + verb + at/in/on...?\n"
            "Examples:\n"
            "Do you wake up at 7?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. at + soat (at 3:30)\n"
            "🟢 2. in + morning/afternoon/evening + month/year\n"
            "🟢 3. on + kun nomi + sana\n"
            "🟢 4. at night (lekin in the morning)\n\n"
            "📌 4. MISOLLAR\n"
            "I eat breakfast at 7 o’clock.\n"
            "We have English in the afternoon.\n"
            "My birthday is on 12th March.\n"
            "She doesn’t work on Sunday.\n"
            "The film starts at 9.\n\n"),
        questions=[
            _q("I wake up ___ 7 o’clock.", "in", "on", "at", "to", "C"),
            _q("She studies ___ the morning.", "at", "in", "on", "for", "B"),
            _q("My birthday is ___ Monday.", "at", "in", "on", "to", "C"),
            _q("The class starts ___ 10.", "at", "in", "on", "for", "A"),
            _q("We don’t go to school ___ Sunday.", "at", "in", "on", "to", "C"),
            _q("It is very cold ___ winter.", "at", "in", "on", "for", "B"),
            _q("The meeting is ___ 15th June.", "at", "in", "on", "to", "C"),
            _q("I watch TV ___ the evening.", "at", "in", "on", "for", "B"),
            _q("___ what time do you eat lunch?", "In", "At", "On", "To", "B"),
            _q("Her party is ___ Friday night.", "at", "in", "on", "for", "C"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_can_cant",
        level="A1",
        title="Can / Can’t",
        rule=("🇺🇿 O‘zbekcha:\n"
            "“Can” – qobiliyat yoki ruxsat bildiradi.\n"
            "Barcha shaxslar uchun bir xil: can / can’t\n"
            "(can’t = cannot)\n\n"
            "🇷🇺 Русский:\n"
            "“Can” – способность или разрешение.\n"
            "Для всех лиц одинаково: can / can’t\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + can + verb\n"
            "Examples:\n"
            "I can swim.\n"
            "She can drive.\n\n"
            "❌ Negative\n"
            "Formula: Subject + can’t + verb\n"
            "Examples:\n"
            "He can’t speak French.\n\n"
            "❓ Question\n"
            "Formula: Can + subject + verb?\n"
            "Examples:\n"
            "Can you help me?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. He/She/It da ham “can” (s qo‘shilmaydi)\n"
            "🟢 2. Short form: can’t\n"
            "🟢 3. Ability (qila olaman) yoki permission (mumkin)\n"
            "🟢 4. Javob: Yes, I can. / No, I can’t.\n\n"
            "📌 4. MISOLLAR\n"
            "I can speak English.\n"
            "You can’t drive a car.\n"
            "Can she cook? Yes, she can.\n"
            "We can play football.\n"
            "It can fly.\n\n"),
        questions=[
            _q("I ___ swim.", "can’t", "can", "cans", "to can", "B"),
            _q("She ___ drive.", "can", "can’t", "cans", "to can", "A"),
            _q("He ___ speak French.", "can", "can’t", "cans", "to can", "B"),
            _q("___ you help me?", "Do", "Can", "Is", "Are", "B"),
            _q("They ___ play tennis.", "can", "can’t", "cans", "to can", "A"),
            _q("We ___ cook very well.", "can", "can", "can’t", "to can", "A"),
            _q("___ she sing? Yes, she ___.", "Can / can", "Can / can", "Does / does", "Is / is", "A"),
            _q("The bird ___ fly.", "can’t", "can", "cans", "to can", "B"),
            _q("I ___ ride a bike.", "can", "can", "can’t", "to can", "A"),
            _q("You ___ open the door.", "can", "can’t", "cans", "to can", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_imperatives",
        level="A1",
        title="Imperatives",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Buyruq va maslahatlar: fe’lning birinchi shakli (infinitive).\n"
            "Positive: verb\n"
            "Negative: Don’t + verb\n\n"
            "🇷🇺 Русский:\n"
            "Повелительное наклонение: глагол в первой форме.\n"
            "Positive: глагол\n"
            "Negative: Don’t + глагол\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Verb + ...\n"
            "Examples:\n"
            "Sit down!\n"
            "Open the book.\n\n"
            "❌ Negative\n"
            "Formula: Don’t + verb\n"
            "Examples:\n"
            "Don’t run!\n"
            "Don’t touch it.\n\n"
            "❓ Question (maslahat)\n"
            "Formula: Let’s + verb (taklif)\n"
            "Examples:\n"
            "Let’s go!\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. “You” ishlatilmaydi\n"
            "🟢 2. Always, never, please qo‘shish mumkin\n"
            "🟢 3. Don’t = Do not (qisqa shakl)\n"
            "🟢 4. Let’s = Let us (taklif)\n\n"
            "📌 4. MISOLLAR\n"
            "Stand up!\n"
            "Don’t be late.\n"
            "Open the door, please.\n"
            "Let’s eat now.\n"
            "Don’t speak loudly.\n\n"),
        questions=[
            _q("___ down!", "Sits", "Sit", "Sitting", "To sit", "B"),
            _q("___ run in the class!", "Run", "Don’t run", "Runs", "Running", "B"),
            _q("___ the window.", "Open", "Opens", "Opening", "To open", "A"),
            _q("___ be late!", "Be", "Don’t be", "Being", "To be", "B"),
            _q("___ go home.", "Let’s", "Let’s", "Let", "Don’t let", "A"),
            _q("___ touch the dog!", "Touch", "Don’t touch", "Touches", "Touching", "B"),
            _q("___ quiet, please.", "Be", "Be", "Being", "To be", "A"),
            _q("___ eat in class!", "Eat", "Don’t eat", "Eats", "Eating", "B"),
            _q("___ the book.", "Read", "Reads", "Reading", "To read", "A"),
            _q("___ talk!", "Talk", "Don’t talk", "Talks", "Talking", "B"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_like_ing",
        level="A1",
        title="Like / Love / Hate + -ing",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Like, love, hate, enjoy fe’llaridan keyin har doim -ing shakli keladi.\n"
            "I like swimming.\n\n"
            "🇷🇺 Русский:\n"
            "После like, love, hate, enjoy всегда глагол + -ing.\n"
            "I like swimming.\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + like/love/hate + verb-ing\n"
            "Examples:\n"
            "I like reading books.\n"
            "She loves dancing.\n\n"
            "❌ Negative\n"
            "Formula: Subject + don’t/doesn’t like + verb-ing\n"
            "Examples:\n"
            "He doesn’t like cooking.\n\n"
            "❓ Question\n"
            "Formula: Do/Does + subject + like + verb-ing?\n"
            "Examples:\n"
            "Do you like swimming?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Faqat -ing (to swim emas)\n"
            "🟢 2. He/She/It → doesn’t like\n"
            "🟢 3. Very much, a lot qo‘shish mumkin\n"
            "🟢 4. Javob: Yes, I do. / No, I don’t.\n\n"
            "📌 4. MISOLLAR\n"
            "I like playing football.\n"
            "She loves cooking.\n"
            "They hate waking up early.\n"
            "Do you like reading? Yes, I do.\n"
            "He doesn’t like watching TV.\n\n"),
        questions=[
            _q("I ___ swimming.", "like", "like", "likes", "to like", "A"),
            _q("She ___ dancing.", "love", "loves", "loveing", "to love", "B"),
            _q("He ___ cooking.", "doesn’t like", "don’t like", "not like", "no like", "A"),
            _q("___ you like reading?", "Does", "Do", "Is", "Are", "B"),
            _q("We ___ playing games.", "like", "likes", "to like", "liking", "A"),
            _q("They ___ getting up early.", "hate", "hate", "hates", "to hate", "A"),
            _q("I ___ very much.", "like swimming", "like to swim", "likes swimming", "like swim", "A"),
            _q("She doesn’t ___ watching films.", "like", "likes", "love", "loves", "A"),
            _q("___ he like tennis?", "Does", "Do", "Is", "Are", "A"),
            _q("We ___ eating ice cream.", "love", "loves", "to love", "loving", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_going_to",
        level="A1",
        title="Going to (Future Plans)",
        rule=("🇺🇿 O‘zbekcha:\n"
            "“Be going to” – kelajakdagi reja va niyatni bildiradi.\n"
            "Formula: am/is/are + going to + verb\n\n"
            "🇷🇺 Русский:\n"
            "“Be going to” – для планов и намерений в будущем.\n"
            "Formula: am/is/are + going to + глагол\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + am/is/are + going to + verb\n"
            "Examples:\n"
            "I am going to buy a car.\n"
            "She is going to study.\n\n"
            "❌ Negative\n"
            "Formula: Subject + am/is/are + not + going to + verb\n"
            "Examples:\n"
            "We aren’t going to travel.\n\n"
            "❓ Question\n"
            "Formula: Am/Is/Are + subject + going to + verb?\n"
            "Examples:\n"
            "Are you going to watch TV?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. I → am, He/She/It → is, You/We/They → are\n"
            "🟢 2. Short forms: I’m going to, He’s going to, isn’t going to\n"
            "🟢 3. Tomorrow, next week, this evening bilan ishlatiladi\n"
            "🟢 4. Javob: Yes, I am. / No, she isn’t.\n\n"
            "📌 4. MISOLLAR\n"
            "I am going to visit my friend tomorrow.\n"
            "She is going to learn English.\n"
            "We aren’t going to eat pizza.\n"
            "Are you going to buy a phone? Yes, I am.\n"
            "It is going to rain.\n\n"),
        questions=[
            _q("I ___ buy a new phone.", "am going to", "am going to", "is going to", "are going to", "A"),
            _q("She ___ study tonight.", "is going to", "am going to", "are going to", "going to", "A"),
            _q("They ___ travel next week.", "am", "is", "are going to", "going to", "C"),
            _q("___ you going to watch the film?", "Is", "Are", "Am", "Do", "B"),
            _q("We ___ not eat fast food.", "aren’t going to", "isn’t going to", "am not going to", "not going to", "A"),
            _q("He ___ play football tomorrow.", "is going to", "am going to", "are going to", "going to", "A"),
            _q("___ it going to rain?", "Is", "Are", "Am", "Does", "A"),
            _q("I ___ visit Tashkent.", "am going to", "is going to", "are going to", "going to", "A"),
            _q("You ___ cook dinner.", "am", "is", "are going to", "going to", "C"),
            _q("She ___ not come.", "isn’t going to", "aren’t going to", "am not going to", "not going to", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_was_were",
        level="A1",
        title="Was / Were (Past of to be)",
        rule=("🇺🇿 O‘zbekcha:\n"
            "“Was / Were” – “to be” fe’lining o‘tgan zamondagi shakli.\n"
            "I/He/She/It → was\n"
            "You/We/They → were\n\n"
            "🇷🇺 Русский:\n"
            "“Was / Were” – прошедшее время глагола “to be”.\n"
            "I/He/She/It → was\n"
            "You/We/They → were\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + was/were + ...\n"
            "Examples:\n"
            "I was happy.\n"
            "They were at school.\n\n"
            "❌ Negative\n"
            "Formula: Subject + was/were + not (wasn’t / weren’t)\n"
            "Examples:\n"
            "She wasn’t tired.\n\n"
            "❓ Question\n"
            "Formula: Was/Were + subject + ...?\n"
            "Examples:\n"
            "Were you at home?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. I/He/She/It → was (singular)\n"
            "🟢 2. You/We/They → were (plural yoki “you”)\n"
            "🟢 3. Short forms: wasn’t, weren’t\n"
            "🟢 4. Javob: Yes, I was. / No, they weren’t.\n\n"
            "📌 4. MISOLLAR\n"
            "I was a student last year.\n"
            "He was in Tashkent.\n"
            "We were happy yesterday.\n"
            "Were they late? Yes, they were.\n"
            "It wasn’t cold.\n\n"),
        questions=[
            _q("I ___ happy yesterday.", "were", "was", "is", "are", "B"),
            _q("She ___ at school.", "was", "were", "is", "are", "A"),
            _q("They ___ teachers.", "was", "were", "is", "are", "B"),
            _q("___ you at home?", "Was", "Were", "Is", "Are", "B"),
            _q("We ___ not tired.", "was", "weren’t", "wasn’t", "isn’t", "B"),
            _q("He ___ late.", "was", "were", "is", "are", "A"),
            _q("___ it cold?", "Was", "Were", "Is", "Are", "A"),
            _q("You ___ my friend.", "was", "were", "is", "are", "B"),
            _q("The children ___ happy.", "were", "was", "is", "are", "A"),
            _q("She ___ not here.", "were", "wasn’t", "wasn’t", "weren’t", "B"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_past_simple_regular",
        level="A1",
        title="Past Simple (Regular Verbs)",
        rule=("🇺🇿 O‘zbekcha:\n"
            "O‘tgan oddiy zamon (regular fe’llar) – kecha, o‘tgan hafta sodir bo‘lgan ishlar uchun.\n"
            "Formula: verb + -ed (played, worked)\n\n"
            "🇷🇺 Русский:\n"
            "Простое прошедшее время (правильные глаголы) – для действий в прошлом.\n"
            "Formula: глагол + -ed\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + verb + -ed\n"
            "Examples:\n"
            "I played football.\n"
            "She worked yesterday.\n\n"
            "❌ Negative\n"
            "Formula: Subject + did not (didn’t) + verb\n"
            "Examples:\n"
            "I didn’t play tennis.\n\n"
            "❓ Question\n"
            "Formula: Did + subject + verb?\n"
            "Examples:\n"
            "Did you watch TV?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. +ed qo‘shiladi (play → played)\n"
            "🟢 2. Short form: didn’t\n"
            "🟢 3. Yesterday, last week, ago bilan ishlatiladi\n"
            "🟢 4. Javob: Yes, I did. / No, she didn’t.\n\n"
            "📌 4. MISOLLAR\n"
            "I walked to school yesterday.\n"
            "She studied English last night.\n"
            "We didn’t visit our friends.\n"
            "Did you call me? Yes, I did.\n"
            "They worked hard.\n\n"),
        questions=[
            _q("I ___ football yesterday.", "play", "played", "plays", "playing", "B"),
            _q("She ___ English.", "studied", "study", "studies", "studying", "A"),
            _q("They ___ to the park.", "walk", "walked", "walks", "walking", "B"),
            _q("___ you watch TV?", "Do", "Did", "Does", "Is", "B"),
            _q("We ___ not call you.", "didn’t", "don’t", "doesn’t", "did", "A"),
            _q("He ___ late last night.", "arrive", "arrived", "arrives", "arriving", "B"),
            _q("___ she work yesterday?", "Did", "Do", "Does", "Is", "A"),
            _q("I ___ my homework.", "finished", "finish", "finishes", "finishing", "A"),
            _q("The dog ___ .", "bark", "barked", "barks", "barking", "B"),
            _q("We ___ the film.", "watched", "watch", "watches", "watching", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_possessive_s",
        level="A1",
        title="Possessive ’s (Mike’s car)",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Egilik ’s – “kimning?” degan ma’noni bildiradi.\n"
            "Name + ’s + noun (Mike’s car = Maykning mashinasi)\n\n"
            "🇷🇺 Русский:\n"
            "Притяжательный ’s – показывает принадлежность.\n"
            "Имя + ’s + существительное\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Person + ’s + noun\n"
            "Examples:\n"
            "This is Anna’s book.\n"
            "My father’s car is new.\n\n"
            "❌ Negative\n"
            "Formula: Person + ’s + noun + is not\n"
            "Examples:\n"
            "It is not John’s phone.\n\n"
            "❓ Question\n"
            "Formula: Is this + Person + ’s + noun?\n"
            "Examples:\n"
            "Is this your friend’s house?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Bitta odam uchun ’s\n"
            "🟢 2. Ko‘plikda faqat ’ (the boys’ room)\n"
            "🟢 3. Irregular: children’s, men’s\n"
            "🟢 4. “of” o‘rniga ishlatiladi (the end of the street emas, street’s end – lekin ko‘pincha ’s)\n\n"
            "📌 4. MISOLLAR\n"
            "This is Sarah’s phone.\n"
            "My brother’s name is Ali.\n"
            "The teacher’s book is on the table.\n"
            "Is this Anna’s bag? Yes, it is.\n"
            "The children’s toys are new.\n\n"),
        questions=[
            _q("This is ___ car.", "Mike", "Mike’s", "Mikes", "Mike is", "B"),
            _q("___ name is Anna.", "Sarah", "Sarah’s", "Sarahs", "Sarah is", "B"),
            _q("My ___ book is here.", "father", "father’s", "fathers", "father is", "B"),
            _q("Is this ___ house?", "your friend’s", "your friends", "your friend is", "your friends’", "A"),
            _q("The ___ toys are big.", "childrens", "children’s", "childrens’", "children is", "B"),
            _q("___ car is red.", "John", "John’s", "Johns", "John is", "B"),
            _q("This is not ___ pen.", "the teacher’s", "the teacher", "the teachers", "teacher’s", "A"),
            _q("___ bag is on the table.", "My sister", "My sister’s", "My sisters", "My sister is", "B"),
            _q("The ___ room is clean.", "boys", "boys’", "boys’s", "boy’s", "B"),
            _q("___ phone is new.", "Anna’s", "Anna", "Annas", "Anna is", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_adjectives",
        level="A1",
        title="Adjectives (big, small, beautiful)",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Sifatlar – narsaning xususiyatini bildiradi va ot oldidan keladi. O‘zgarmaydi (big house, big houses, beautiful girl, interesting book).\n\n"
            "🇷🇺 Русский:\n"
            "Прилагательные – описывают качество предмета, стоят перед существительным и не изменяются (big house, big houses, beautiful girl, interesting book).\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Adjective + noun (big house, beautiful girl)\n"
            "Examples:\n"
            "It is a big house.\n"
            "She is beautiful.\n\n"
            "❌ Negative\n"
            "Formula: Subject + is/are + not + adjective\n"
            "Examples:\n"
            "The car is not small.\n\n"
            "❓ Question\n"
            "Formula: Is/Are + subject + adjective?\n"
            "Examples:\n"
            "Is the book interesting?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Har doim ot oldidan\n"
            "🟢 2. “Very, quite, really” bilan ishlatiladi\n"
            "🟢 3. Bitta sifat yoki bir nechta (a big red car)\n"
            "🟢 4. A1 da oddiy sifatlar: big, small, happy, sad, old, new, beautiful, ugly\n\n"
            "📌 4. MISOLLAR\n"
            "This is a big city.\n"
            "She is a happy girl.\n"
            "The book is interesting.\n"
            "Are you tired? Yes, I am.\n"
            "It is a beautiful day.\n\n"),
        questions=[
            _q("It is a ___ house.", "big", "big", "bigger", "biggest", "A"),
            _q("She is a ___ teacher.", "kind", "kindly", "kindness", "kindest", "A"),
            _q("The car is ___ .", "new", "newly", "news", "newer", "A"),
            _q("___ you happy?", "Is", "Are", "Am", "Do", "B"),
            _q("This is not a ___ book.", "boring", "bore", "bores", "boringly", "A"),
            _q("He is a ___ boy.", "tall", "taller", "tallest", "tallness", "A"),
            _q("The film is very ___ .", "interesting", "interest", "interests", "interested", "A"),
            _q("They are ___ students.", "good", "well", "goods", "goodness", "A"),
            _q("Is the room ___ ?", "clean", "cleanly", "cleans", "cleaner", "A"),
            _q("My phone is ___ .", "old", "older", "oldest", "oldness", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_adv_frequency",
        level="A1",
        title="Adverbs of Frequency (always/never/sometimes)",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Chastota ravishlari – qanchalik tez-tez bo‘lishini bildiradi.\n"
            "Always (100%), usually, often, sometimes, rarely, never (0%)\n\n"
            "🇷🇺 Русский:\n"
            "Наречия частотности – показывают как часто происходит действие.\n"
            "Always (100%), usually, often, sometimes, rarely, never (0%)\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + adverb + verb / Subject + be + adverb\n"
            "Examples:\n"
            "I always drink coffee.\n"
            "She is never late.\n\n"
            "❌ Negative\n"
            "Formula: Subject + don’t/doesn’t + adverb + verb\n"
            "Examples:\n"
            "He doesn’t often play.\n\n"
            "❓ Question\n"
            "Formula: Do/Does + subject + adverb + verb?\n"
            "Examples:\n"
            "Do you sometimes go to the cinema?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Oddiy fe’llar bilan: adverb + verb (I always go)\n"
            "🟢 2. “Be” fe’li bilan: be + adverb (I am always happy)\n"
            "🟢 3. Sometimes va often gap boshida yoki oxirida ham bo‘lishi mumkin\n"
            "🟢 4. Never va always bilan inkor ishlatilmaydi\n\n"
            "📌 4. MISOLLAR\n"
            "I always wake up early.\n"
            "She is sometimes late.\n"
            "We never eat fast food.\n"
            "Do you often watch films? Yes, I do.\n"
            "He rarely plays games.\n\n"),
        questions=[
            _q("I ___ drink tea.", "always", "never", "sometimes", "often", "A"),
            _q("She is ___ late.", "always", "never", "sometimes", "often", "B"),
            _q("We ___ go to the park.", "sometimes", "always", "never", "rarely", "A"),
            _q("He ___ plays football.", "often", "often", "sometimes", "always", "A"),
            _q("They ___ eat meat.", "never", "always", "sometimes", "often", "A"),
            _q("___ you usually study?", "Do", "Do", "Does", "Is", "A"),
            _q("I am ___ happy.", "always", "never", "sometimes", "often", "A"),
            _q("She ___ watches TV.", "rarely", "rarely", "never", "always", "A"),
            _q("We ___ go to school.", "always", "never", "sometimes", "often", "A"),
            _q("Do you ___ eat pizza?", "sometimes", "always", "never", "often", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_comparative_adj",
        level="A1",
        title="Comparative Adjectives (bigger/more expensive)",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Qiyosiy sifatlar – ikki narsani solishtirish uchun.\n"
            "Qisqa sifatlar (1-2 bo‘g‘in): +er (big → bigger)\n"
            "Uzun sifatlar (3+ bo‘g‘in): more + sifat (beautiful → more beautiful)\n\n"
            "🇷🇺 Русский:\n"
            "Сравнительная степень прилагательных – для сравнения двух вещей.\n"
            "Короткие (1-2 слога): +er\n"
            "Длинные (3+ слога): more + прилагательное\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + be + comparative + than + object\n"
            "Examples:\n"
            "This book is bigger than that one.\n"
            "She is more beautiful than her sister.\n\n"
            "❌ Negative\n"
            "Formula: Subject + be + not + comparative + than\n"
            "Examples:\n"
            "This car is not faster than mine.\n\n"
            "❓ Question\n"
            "Formula: Is/Are + subject + comparative + than ...?\n"
            "Examples:\n"
            "Is Tashkent bigger than Samarkand?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Qisqa: big → bigger, small → smaller, hot → hotter\n"
            "🟢 2. Uzun: expensive → more expensive, interesting → more interesting\n"
            "🟢 3. Irregular: good → better, bad → worse\n"
            "🟢 4. Har doim “than” bilan\n\n"
            "📌 4. MISOLLAR\n"
            "My phone is newer than yours.\n"
            "This bag is more expensive than that one.\n"
            "He is taller than me.\n"
            "English is easier than math.\n"
            "The weather is better today than yesterday.\n\n"),
        questions=[
            _q("This house is ___ than that one.", "big", "bigger", "more big", "biggest", "B"),
            _q("She is ___ than her brother.", "tall", "taller", "more tall", "tallest", "B"),
            _q("This film is ___ than the last one.", "more interesting", "interestinger", "interesting", "most interesting", "A"),
            _q("My car is ___ than yours.", "fast", "faster", "more fast", "fastest", "B"),
            _q("Tashkent is ___ than Bukhara.", "bigger", "big", "more big", "biggest", "A"),
            _q("This test is ___ than yesterday’s.", "easy", "easier", "easier", "more easy", "B"),
            _q("Coffee is ___ than tea for me.", "good", "better", "more good", "best", "B"),
            _q("This phone is ___ than that one.", "expensive", "more expensive", "expensiver", "most expensive", "B"),
            _q("He runs ___ than me.", "fast", "faster", "more fast", "fastest", "B"),
            _q("Math is ___ than English.", "worse", "bad", "more bad", "badder", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_superlative_adj",
        level="A1",
        title="Superlative Adjectives (the biggest)",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Eng yuqori daraja sifatlari – guruhdagi eng ... narsani bildiradi.\n"
            "Qisqa: the + sifat + est (big → the biggest)\n"
            "Uzun: the most + sifat (beautiful → the most beautiful)\n\n"
            "🇷🇺 Русский:\n"
            "Превосходная степень прилагательных – самый ... в группе.\n"
            "Короткие: the + прилагательное + est\n"
            "Длинные: the most + прилагательное\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + be + the superlative\n"
            "Examples:\n"
            "This is the biggest house.\n"
            "She is the most beautiful girl.\n\n"
            "❌ Negative\n"
            "Formula: Subject + be + not + the superlative\n"
            "Examples:\n"
            "It is not the most expensive car.\n\n"
            "❓ Question\n"
            "Formula: Is/Are + subject + the superlative?\n"
            "Examples:\n"
            "Is Everest the highest mountain?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Har doim “the” bilan\n"
            "🟢 2. Qisqa: big → the biggest, small → the smallest\n"
            "🟢 3. Uzun: interesting → the most interesting\n"
            "🟢 4. Irregular: good → the best, bad → the worst\n\n"
            "📌 4. MISOLLAR\n"
            "Tashkent is the biggest city in Uzbekistan.\n"
            "This is the most expensive phone.\n"
            "He is the best student.\n"
            "Mount Everest is the highest mountain.\n"
            "She has the longest hair.\n\n"),
        questions=[
            _q("This is ___ house in the street.", "big", "bigger", "the biggest", "more big", "C"),
            _q("She is ___ girl in the class.", "beautiful", "more beautiful", "the most beautiful", "beautifullest", "C"),
            _q("Everest is ___ mountain in the world.", "high", "higher", "the highest", "most high", "C"),
            _q("This is ___ book I have read.", "interesting", "more interesting", "the most interesting", "interestinger", "C"),
            _q("He is ___ player on the team.", "good", "better", "the best", "most good", "C"),
            _q("This car is ___ in the shop.", "expensive", "more expensive", "the most expensive", "expensivest", "C"),
            _q("Math is ___ subject for me.", "bad", "worse", "the worst", "baddest", "C"),
            _q("Tashkent is ___ city in Uzbekistan.", "big", "bigger", "the biggest", "most big", "C"),
            _q("This is ___ day of my life.", "happy", "happier", "the happiest", "most happy", "C"),
            _q("She is ___ student in the school.", "smart", "smarter", "the smartest", "most smart", "C"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_conjunctions",
        level="A1",
        title="Conjunctions (and/but/or/because/so)",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Bog‘lovchilar – ikki gapni birlashtiradi.\n"
            "and – va (qo‘shimcha)\n"
            "but – lekin (qarama-qarshi)\n"
            "or – yoki (tanlov)\n"
            "because – chunki (sababi)\n"
            "so – shuning uchun (natija)\n\n"
            "🇷🇺 Русский:\n"
            "Союзы – соединяют предложения.\n"
            "and – и\n"
            "but – но\n"
            "or – или\n"
            "because – потому что\n"
            "so – поэтому\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Sentence1 + conjunction + Sentence2\n"
            "Examples:\n"
            "I like tea and coffee.\n"
            "She is tired but happy.\n\n"
            "❌ Negative\n"
            "Formula: Sentence1 + conjunction + negative sentence\n"
            "Examples:\n"
            "He doesn’t like tea but he likes coffee.\n\n"
            "❓ Question\n"
            "Formula: Savol + conjunction + javob\n"
            "Examples:\n"
            "Why are you late? Because I missed the bus.\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. And – ikkita narsani qo‘shadi\n"
            "🟢 2. But – farqni bildiradi\n"
            "🟢 3. Or – tanlov\n"
            "🟢 4. Because – sabab oldidan, so – natija oldidan\n\n"
            "📌 4. MISOLLAR\n"
            "I am happy and tired.\n"
            "It is cold but sunny.\n"
            "Do you want tea or coffee?\n"
            "I stayed home because I was sick.\n"
            "She studied hard so she passed the test.\n\n"),
        questions=[
            _q("I like apples ___ oranges.", "but", "and", "or", "because", "B"),
            _q("He is rich ___ not happy.", "and", "but", "or", "so", "B"),
            _q("Do you want pizza ___ sushi?", "and", "but", "or", "because", "C"),
            _q("I can’t go ___ I am sick.", "and", "but", "because", "so", "C"),
            _q("She ran fast ___ she won.", "and", "but", "or", "so", "D"),
            _q("It is raining ___ we stay home.", "and", "so", "or", "because", "B"),
            _q("He speaks English ___ Uzbek.", "and", "but", "or", "because", "A"),
            _q("The test was hard ___ I passed.", "and", "but", "or", "so", "B"),
            _q("Why are you late? ___ traffic.", "And", "But", "Because", "So", "C"),
            _q("Study hard ___ you will succeed.", "and", "but", "or", "so", "D"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_wh_questions",
        level="A1",
        title="Questions & Wh-questions",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Savollar – so‘z tartibi: yordamchi fe’l (am/is/are/do/does/can) oldinga chiqadi.\n"
            "Wh-questions: What, Where, When, Who, Why, How + yordamchi fe’l + subject + verb\n\n"
            "🇷🇺 Русский:\n"
            "Вопросы – порядок слов: вспомогательный глагол (am/is/are/do/does/can) выходит вперёд.\n"
            "Wh-вопросы: What, Where, When, Who, Why, How + вспомогательный + подлежащее + глагол\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Yes/No questions\n"
            "Formula: Am/Is/Are/Do/Does/Can + subject + verb?\n"
            "Examples:\n"
            "Are you a student?\n"
            "Do you like tea?\n\n"
            "✅ Wh-questions\n"
            "Formula: Wh-word + am/is/are/do/does/can + subject + verb?\n"
            "Examples:\n"
            "Where do you live?\n"
            "What is your name?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Yes/No savollarda yordamchi fe’l oldinga\n"
            "🟢 2. Wh-savollarda Wh-word eng oldinda\n"
            "🟢 3. Who – “kim?” (subject sifatida ishlatilsa yordamchi kerak emas: Who lives here?)\n"
            "🟢 4. Short answers: Yes, I do. / No, he isn’t.\n\n"
            "📌 4. MISOLLAR\n"
            "What is your name?\n"
            "Where are you from?\n"
            "When do you wake up?\n"
            "Who is your teacher?\n"
            "Why are you happy?\n"
            "How old are you?\n"
            "Can you swim? Yes, I can.\n"
            "Do you speak English? No, I don’t.\n\n"),
        questions=[
            _q("___ is your name?", "What", "What", "Where", "When", "A"),
            _q("___ do you live?", "What", "Where", "Who", "Why", "B"),
            _q("___ are you happy?", "What", "Where", "Why", "When", "C"),
            _q("___ old are you?", "How", "What", "Where", "Who", "A"),
            _q("___ is your teacher?", "What", "Where", "Who", "Why", "C"),
            _q("___ do you go to school?", "What", "When", "Who", "How", "B"),
            _q("___ you a student?", "Are", "Do", "Does", "Can", "A"),
            _q("___ you like coffee?", "Are", "Do", "Is", "Can", "B"),
            _q("___ she speak Uzbek?", "Do", "Does", "Is", "Are", "B"),
            _q("___ you swim? Yes, I ___.", "Do / do", "Can / can", "Are / am", "Is / is", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_ru_adj_gender",
        level="A1",
        subject="Russian",
        title="Согласование прилагательных с родом существительных",
        rule=(
            "🔺 Sifatlarni otlarning rodiga qarab moslashtirish kerak.\n\n"
            "М.р -> новЫЙ ученик\n"
            "Ж.р -> новАЯ работа\n"
            "С.р -> новОЕ задание\n"
            "Ko'plik -> новЫЕ ученики\n\n"
            "М.р otlari bilan sifat asosan -ЫЙ (ba'zan -ИЙ):\n"
            "КрасивЫЙ город, ДобрЫЙ человек\n\n"
            "Ж.р otlari bilan asosan -АЯ (ba'zan -ЯЯ):\n"
            "КрасивАЯ улица, ДобрАЯ девочка\n\n"
            "С.р otlari bilan asosan -ОЕ (ba'zan -ЕЕ):\n"
            "КрасивОЕ платье, СтарОЕ пальто\n\n"
            "Ko'plikda sifat -ЫЕ (-ИЕ) bo'ladi:\n"
            "КрасивЫЕ люди, ДобрЫЕ дети"
        ),
        questions=[
            _q("Пальто … ?", "красивАЯ", "красивОЕ", "красивЫЙ", "красивЫЕ", "B"),
            _q("Книга … ?", "интереснОЕ", "интереснАЯ", "интереснЫЕ", "интереснЫЙ", "B"),
            _q("Дом … ?", "большИЕ", "большАЯ", "большОЕ", "большОЙ", "D"),
            _q("Окно … ?", "чистЫЙ", "чистАЯ", "чистОЕ", "чистЫЕ", "C"),
            _q("Друзья … ?", "хорошИЙ", "хорошАЯ", "хорошОЕ", "хорошИЕ", "D"),
            _q("Машина … ?", "новЫЙ", "новАЯ", "новОЕ", "новЫЕ", "B"),
            _q("Стол … ?", "старАЯ", "старЫЙ", "старОЕ", "старЫЕ", "B"),
            _q("Класс … ?", "чистАЯ", "чистЫЙ", "чистОЕ", "чистЫЕ", "B"),
            _q("Море … ?", "синЯЯ", "синЕЕ", "синИЙ", "синИЕ", "B"),
            _q("Ученики … ?", "умнЫЙ", "умнАЯ", "умнОЕ", "умнЫЕ", "D"),
            _q("Телефон … ?", "дорогИЕ", "дорогАЯ", "дорогОЕ", "дорогОЙ", "D"),
            _q("Сумка … ?", "маленькАЯ", "маленькИЙ", "маленькОЕ", "маленькИЕ", "A"),
            _q("Письмо … ?", "важнЫЙ", "важнАЯ", "важнОЕ", "важнЫЕ", "C"),
            _q("Книги … ?", "интереснЫЙ", "интереснАЯ", "интереснОЕ", "интереснЫЕ", "D"),
            _q("Кошка … ?", "чёрнЫЙ", "чёрнАЯ", "чёрнОЕ", "чёрнЫЕ", "B"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_ru_possessive_gender",
        level="A1",
        subject="Russian",
        title="Мой/моя/моё/мои и другие притяжательные местоимения",
        rule=(
            "🔺 Bu olmoshlarni so'zni rodiga qarab moslashtirish kerak.\n\n"
            "Мой (м.р), Моя (ж.р), Моё (с.р), Мои (ko'plik)\n"
            "Твой, Твоя, Твоё, Твои\n"
            "Наш, Наша, Наше, Наши\n"
            "Ваш, Ваша, Ваше, Ваши\n\n"
            "Misollar:\n"
            "МОЙ дом\n"
            "МОЯ машина\n"
            "МОЁ задание\n"
            "МОИ деньги"
        ),
        questions=[
            _q("___ дом", "моя", "мой", "моё", "мои", "B"),
            _q("___ брат", "мой", "моя", "моё", "мои", "A"),
            _q("___ стол", "мой", "моя", "моё", "мои", "A"),
            _q("___ телефон", "мой", "моя", "моё", "мои", "A"),
            _q("___ друг", "мой", "моя", "моё", "мои", "A"),
            _q("___ рюкзак", "мой", "моя", "моё", "мои", "A"),
            _q("___ кот", "мой", "моя", "моё", "мои", "A"),
            _q("___ компьютер", "мой", "моя", "моё", "мои", "A"),
            _q("___ словарь", "мой", "моя", "моё", "мои", "A"),
            _q("___ город", "мой", "моя", "моё", "мои", "A"),
            _q("___ книга", "моя", "мой", "моё", "мои", "A"),
            _q("___ ручка", "моя", "мой", "моё", "мои", "A"),
            _q("___ сестра", "моя", "мой", "моё", "мои", "A"),
            _q("___ тетрадь", "моя", "мой", "моё", "мои", "A"),
            _q("___ сумка", "моя", "мой", "моё", "мои", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a1_ru_noun_gender",
        level="A1",
        subject="Russian",
        title="Род существительных: ж.р / с.р / м.р",
        rule=(
            "❗️ Rus tilida 3 ta rod bor.\n"
            "(so'zlarni guruhlarga bo'lish)\n\n"
            "Rod oxirgi harfga qarab aniqlanadi:\n"
            "Ж.р: -а, -я (работА, машинА)\n"
            "С.р: -о, -е, -мя (числО, морЕ, иМЯ)\n"
            "М.р: undosh (бизнеС, друГ)\n\n"
            "Istisno m.r so'zlar: Папа, Дядя, Братишка, Дедушка, Мужчина, Юноша\n"
            "('Ь' bilan tugaydigan so'zlar uchun alohida qoida bor)."
        ),
        questions=[
            _q("Буква", "С.р", "Ж.р", "М.р", "—", "B"),
            _q("Кошка", "С.р", "М.р", "Ж.р", "—", "C"),
            _q("Папа", "М.р", "С.р", "Ж.р", "—", "A"),
            _q("Телефон", "Ж.р", "М.р", "С.р", "—", "B"),
            _q("Пенал", "М.р", "С.р", "Ж.р", "—", "A"),
            _q("Вишня", "Ж.р", "С.р", "М.р", "—", "A"),
            _q("Доска", "С.р", "Ж.р", "М.р", "—", "B"),
            _q("Окно", "С.р", "М.р", "Ж.р", "—", "A"),
            _q("Работа", "Ж.р", "С.р", "М.р", "—", "A"),
            _q("Задание", "С.р", "М.р", "Ж.р", "—", "A"),
            _q("Карандаш", "М.р", "Ж.р", "С.р", "—", "A"),
            _q("Школа", "Ж.р", "С.р", "М.р", "—", "A"),
            _q("Слово", "С.р", "М.р", "Ж.р", "—", "A"),
            _q("Дядя", "М.р", "Ж.р", "С.р", "—", "A"),
            _q("Имя", "С.р", "Ж.р", "М.р", "—", "A"),
        ],
    ),
]


# ========= A2 =========

A2_TOPICS: List[GrammarTopic] = [
    GrammarTopic(
        topic_id="a2_present_perfect",
        level="A2",
        title="Present Perfect Simple",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Hozirgi mukammal zamon – o‘tmishda sodir bo‘lgan ishning hozirgi natijasi yoki hayot tajribasi uchun ishlatiladi.\n"
            "Formula: I/You/We/They + have + V3 | He/She/It + has + V3\n\n"
            "🇷🇺 Русский:\n"
            "Present Perfect – для действий в прошлом, которые имеют связь с настоящим, или для жизненного опыта.\n"
            "Formula: I/You/We/They + have + V3 | He/She/It + has + V3\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive: Subject + have/has + past participle (Ex: I have visited Tashkent.)\n"
            "❌ Negative: Subject + haven’t/hasn’t + past participle (Ex: I haven’t eaten yet.)\n"
            "❓ Question: Have/Has + subject + past participle? (Ex: Have you ever been to London?)\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Ever (tajriba savoli), Never (hech qachon), Already (allaqachon), Yet (hali)\n"
            "🟢 2. Just (endi), So far, Today/This week bilan ishlatiladi\n"
            "🟢 3. Short forms: I’ve, She’s, haven’t, hasn’t\n"
            "🟢 4. Javob: Yes, I have. / No, she hasn’t.\n\n"
            "📌 4. MISOLLAR (Examples)\n"
            "I have lost my keys. / She has never flown before.\n"
            "We haven’t finished homework yet. / Have you ever eaten sushi? Yes, I have.\n"
            "It has just started raining.\n"
        ),
        questions=[
            _q("I ___ my homework.", "has finished", "have finished", "finished", "finish", "B"),
            _q("She ___ this film.", "have seen", "has seen", "saw", "sees", "B"),
            _q("They ___ to London.", "has been", "have been", "was", "were", "B"),
            _q("___ you ever eaten sushi?", "Has", "Have", "Did", "Do", "B"),
            _q("He ___ his keys.", "has lost", "have lost", "lost", "loses", "A"),
            _q("We ___ yet.", "hasn’t eaten", "haven’t eaten", "didn’t eat", "don’t eat", "B"),
            _q("___ she arrived?", "Has", "Have", "Did", "Do", "A"),
            _q("It ___ just started.", "have", "has", "had", "is", "B"),
            _q("I ___ never been to Paris.", "have", "has", "did", "do", "A"),
            _q("___ they finished? Yes, they ___.", "Has / has", "Have / have", "Did / did", "Do / do", "B"),
            ],
    ),
    GrammarTopic(
        topic_id="a2_perf_vs_past",
        level="A2",
        title="Present Perfect vs Past Simple",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Present Perfect = hozirgi natija yoki tajriba (ever, never, already, yet)\n"
            "Past Simple = aniq o‘tmish vaqti (yesterday, last week, in 2020)\n\n"
            "🇷🇺 Русский:\n"
            "Present Perfect = связь с настоящим или опыт\n"
            "Past Simple = конкретное время в прошлом\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Present Perfect: I have seen this film.\n"
            "Past Simple: I saw this film yesterday.\n\n"
            "❌ Negative\n"
            "Present Perfect: I haven’t seen it.\n"
            "Past Simple: I didn’t see it last night.\n\n"
            "❓ Question\n"
            "Present Perfect: Have you seen it?\n"
            "Past Simple: Did you see it yesterday?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Present Perfect – aniq vaqt yo‘q (I have lived here for 5 years)\n"
            "🟢 2. Past Simple – aniq vaqt bor (I lived there in 2020)\n"
            "🟢 3. Ever/Never/Already/Yet → faqat Present Perfect\n"
            "🟢 4. Yesterday/Last week/Ago → faqat Past Simple\n\n"
            "📌 4. MISOLLAR\n"
            "I have visited Paris. (tajriba)\n"
            "I visited Paris last year. (aniq vaqt)\n"
            "She hasn’t eaten yet.\n"
            "She didn’t eat breakfast.\n"
            "Have you ever been to Samarkand?\n"),
        questions=[
            _q("I ___ Paris last year.", "visited", "have visited", "visit", "visiting", "A"),
            _q("She ___ this film before.", "saw", "has seen", "sees", "see", "B"),
            _q("___ you ever been to London?", "Did", "Have", "Do", "Are", "B"),
            _q("They ___ yesterday.", "arrived", "have arrived", "arrive", "arriving", "A"),
            _q("We ___ yet.", "didn’t finish", "haven’t finished", "not finish", "doesn’t finish", "B"),
            _q("He ___ in 2020.", "lived", "has lived", "lives", "living", "A"),
            _q("___ she call you last night?", "Has", "Did", "Have", "Do", "B"),
            _q("I ___ never seen snow.", "have", "did", "has", "do", "A"),
            _q("They ___ the test already.", "passed", "have passed", "pass", "passing", "B"),
            _q("She ___ to Tashkent last week.", "went", "has gone", "go", "going", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_past_irregular",
        level="A2",
        title="Past Simple – Irregular Verbs",
        rule=("🇺🇿 O‘zbekcha:\n"
            "O‘tgan oddiy zamon (irregular fe’llar) – kecha, o‘tgan hafta sodir bo‘lgan ishlar uchun.\n"
            "Oddiy qoida yo‘q – har biri alohida o‘rganiladi (go → went, eat → ate).\n\n"
            "🇷🇺 Русский:\n"
            "Простое прошедшее время (неправильные глаголы) – форма меняется не по правилу.\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + irregular past form (Ex: I went to school.)\n\n"
            "❌ Negative\n"
            "Formula: Subject + didn’t + base verb (Ex: I didn’t go home.)\n\n"
            "❓ Question\n"
            "Formula: Did + subject + base verb? (Ex: Did you eat breakfast?)\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Common irregular: go-went, eat-ate, see-saw, buy-bought, come-came\n"
            "🟢 2. Short form: didn’t\n"
            "🟢 3. Yesterday, last week, ago bilan\n"
            "🟢 4. Javob: Yes, I did. / No, I didn’t.\n\n"
            "📌 4. MISOLLAR\n"
            "I saw my friend yesterday.\n"
            "She bought a new phone.\n"
            "We didn’t eat meat.\n"
            "Did you come to the party? Yes, I did.\n"
            "He went to Tashkent last month.\n"),
        questions=[
            _q("I ___ to school yesterday.", "go", "went", "goes", "going", "B"),
            _q("She ___ a cake.", "ate", "eat", "eats", "eating", "A"),
            _q("They ___ the film.", "see", "saw", "sees", "seeing", "B"),
            _q("___ you buy milk?", "Do", "Did", "Does", "Have", "B"),
            _q("He ___ his keys.", "lost", "lose", "loses", "losing", "A"),
            _q("We ___ home early.", "came", "come", "comes", "coming", "A"),
            _q("___ she speak English?", "Did", "Do", "Does", "Has", "A"),
            _q("I ___ a new car.", "bought", "buy", "buys", "buying", "A"),
            _q("The dog ___ .", "ran", "run", "runs", "running", "A"),
            _q("They ___ to the party.", "went", "go", "goes", "going", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_past_continuous",
        level="A2",
        title="Past Continuous",
        rule=("🇺🇿 O‘zbekcha:\n"
            "O‘tgan davomiy zamon – o‘tmishda ma’lum bir vaqtda sodir bo‘layotgan ish uchun.\n"
            "Formula: was/were + verb-ing\n\n"
            "🇷🇺 Русский:\n"
            "Прошедшее длительное время – для действий, которые происходили в определённый момент в прошлом.\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + was/were + verb-ing (Ex: I was reading a book.)\n\n"
            "❌ Negative\n"
            "Formula: Subject + wasn’t/weren’t + verb-ing (Ex: She wasn’t sleeping.)\n\n"
            "❓ Question\n"
            "Formula: Was/Were + subject + verb-ing? (Ex: Were you working?)\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. I/He/She/It → was, You/We/They → were\n"
            "🟢 2. Short forms: wasn’t, weren’t\n"
            "🟢 3. At 5 o’clock yesterday, while, when bilan ishlatiladi\n"
            "🟢 4. Background action (orqa fondagi harakat) uchun ishlatiladi\n\n"
            "📌 4. MISOLLAR\n"
            "I was eating when you called.\n"
            "She was watching TV at 8 pm.\n"
            "They weren’t listening.\n"
            "Were you sleeping? Yes, I was.\n"
            "It was raining all day.\n"),
        questions=[
            _q("I ___ a book yesterday.", "was reading", "read", "reads", "reading", "A"),
            _q("She ___ TV at 7.", "was watching", "watched", "watches", "watching", "A"),
            _q("___ you working?", "Were", "Was", "Are", "Is", "A"),
            _q("They ___ football.", "was playing", "were playing", "played", "playing", "B"),
            _q("He ___ not sleeping.", "were", "wasn’t", "isn’t", "aren’t", "B"),
            _q("We ___ dinner.", "were cooking", "was cooking", "cooked", "cooking", "A"),
            _q("___ it raining?", "Was", "Were", "Is", "Are", "A"),
            _q("I ___ to music.", "was listening", "listened", "listens", "listening", "A"),
            _q("She ___ a letter.", "was writing", "wrote", "writes", "writing", "A"),
            _q("You ___ now. (o‘tgan)", "were working", "was working", "worked", "working", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_past_simple_vs_cont",
        level="A2",
        title="Past Simple vs Past Continuous",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Past Simple = qisqa, tugallangan harakat.\n"
            "Past Continuous = davomiy, fon harakati.\n"
            "When + Past Simple (qisqa) | While + Past Continuous (davomiy).\n\n"
            "🇷🇺 Русский:\n"
            "Past Simple = короткое, завершённое действие.\n"
            "Past Continuous = длительное действие (фон).\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Past Simple: I ate dinner.\n"
            "Past Continuous: I was eating dinner when...\n\n"
            "❌ Negative\n"
            "Past Simple: I didn’t eat.\n"
            "Past Continuous: I wasn’t eating.\n\n"
            "❓ Question\n"
            "Past Simple: Did you eat?\n"
            "Past Continuous: Were you eating?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. When + Past Simple (to‘satdan sodir bo‘lgan harakat)\n"
            "🟢 2. While + Past Continuous (davom etayotgan harakat)\n"
            "🟢 3. Background (fon) + interruption (to‘xtatish)\n"
            "🟢 4. I was walking when I saw... (Men ketayotgan edim, ko‘rib qoldim)\n\n"
            "📌 4. MISOLLAR\n"
            "I was sleeping when the phone rang.\n"
            "She was cooking while I was watching TV.\n"
            "It was raining when we left.\n"
            "Did you see the accident? Yes, I was driving.\n"
            "We weren’t listening when the teacher spoke.\n"),
        questions=[
            _q("I ___ when the phone rang.", "was sleeping", "slept", "sleep", "sleeps", "A"),
            _q("She ___ dinner when I arrived.", "cooked", "was cooking", "cooks", "cooking", "B"),
            _q("It ___ when we left.", "rained", "was raining", "rains", "raining", "B"),
            _q("___ you driving when you saw the accident?", "Were", "Was", "Did", "Do", "A"),
            _q("He ___ the book when I called.", "read", "was reading", "reads", "reading", "B"),
            _q("We ___ TV while she was cooking.", "were watching", "watched", "watch", "watching", "A"),
            _q("___ it raining? Yes, it ___.", "Was / was", "Were / were", "Did / did", "Is / is", "A"),
            _q("I ___ home when it started.", "was walking", "walked", "walk", "walks", "A"),
            _q("They ___ when the teacher came.", "were talking", "talked", "talk", "talks", "A"),
            _q("She ___ a letter while I was sleeping.", "wrote", "was writing", "writes", "writing", "B"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_will",
        level="A2",
        title="Will (future predictions & promises)",
        rule=("🇺🇿 O‘zbekcha:\n"
            "“Will” – kelajakdagi bashoratlar, va'dalar, qarorlar (o‘sha lahzada) uchun ishlatiladi.\n"
            "Formula: Subject + will + verb (I will go)\n\n"
            "🇷🇺 Русский:\n"
            "“Will” – для предсказаний, обещаний, спонтанных решений в будущем.\n"
            "Formula: Subject + will + глагол\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + will + verb (Ex: It will rain tomorrow.)\n\n"
            "❌ Negative\n"
            "Formula: Subject + will not (won’t) + verb (Ex: She won’t come.)\n\n"
            "❓ Question\n"
            "Formula: Will + subject + verb? (Ex: Will you call me?)\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Bashorat (Prediction): I think it will snow.\n"
            "🟢 2. Va’da (Promise): I will love you forever.\n"
            "🟢 3. Spontan qaror (Spontaneous decision): I’m hungry. I will make food.\n"
            "🟢 4. Short form: I’ll, you’ll, won’t\n\n"
            "📌 4. MISOLLAR\n"
            "I will call you later.\n"
            "It will be sunny tomorrow.\n"
            "She won’t forget your birthday.\n"
            "Will you marry me? Yes, I will.\n"
            "We will win the game!\n"),
        questions=[
            _q("I ___ call you tomorrow.", "will", "am going to", "going to", "will to", "A"),
            _q("It ___ rain soon.", "is going to", "will", "goes to", "will to", "B"),
            _q("She ___ not come to the party.", "is going to", "won’t", "doesn’t", "isn’t", "B"),
            _q("___ you help me?", "Are", "Do", "Will", "Can", "C"),
            _q("We ___ win!", "will", "are going to", "going to", "will to", "A"),
            _q("He ___ buy a new phone.", "will", "will", "is going to", "goes to", "A"),
            _q("___ it be cold?", "Will", "Is", "Does", "Are", "A"),
            _q("I ___ love you forever.", "will", "am going to", "going to", "will to", "A"),
            _q("They ___ not forget.", "will", "won’t", "don’t", "aren’t", "B"),
            _q("___ you come? Yes, I ___.", "Will / will", "Will / will", "Are / am", "Do / do", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_will_vs_going_to",
        level="A2",
        title="Will vs Going to vs Present Continuous (future)",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Will = bashorat yoki spontan qaror.\n"
            "Going to = reja yoki dalil bor (Look! It is going to rain.)\n"
            "Present Continuous = kelajakdagi tasdiqlangan reja (I am meeting her tomorrow.)\n\n"
            "🇷🇺 Русский:\n"
            "Will = предсказание или спонтанное решение.\n"
            "Going to = план или очевидное будущее.\n"
            "Present Continuous = фиксированный план в будущем.\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Will: I will help you.\n"
            "Going to: I am going to study tonight.\n"
            "Present Continuous: I am flying to London tomorrow.\n\n"
            "❌ Negative\n"
            "Will: I won’t tell.\n"
            "Going to: She isn’t going to come.\n\n"
            "❓ Question\n"
            "Will you...? / Are you going to...? / Are you meeting...?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Will – aniq reja yo‘q (I think...)\n"
            "🟢 2. Going to – niyat yoki aniq belgilar borligida\n"
            "🟢 3. Present Continuous – vaqt va joy belgilangan (Diary future)\n"
            "🟢 4. Arrangements (kelishuvlar) uchun Present Continuous ko‘p ishlatiladi\n\n"
            "📌 4. MISOLLAR\n"
            "I will call you. (spontan)\n"
            "I am going to call you. (reja)\n"
            "I am calling you at 5. (tasdiqlangan kelishuv)\n"
            "It will rain. (shunchaki bashorat)\n"
            "Look at the clouds! It is going to rain. (dalil bor)\n"),
        questions=[
            _q("I think it ___ rain. (bashorat)", "is going to", "will", "is raining", "rains", "B"),
            _q("I ___ study tonight. (reja)", "am going to", "will", "am studying", "study", "A"),
            _q("We ___ meet at 7 tomorrow. (tasdiqlangan)", "will", "are going to", "are meeting", "meet", "C"),
            _q("Look! The baby ___ fall.", "will", "is going to", "is falling", "falls", "B"),
            _q("She ___ not tell anyone. (va’da)", "is going to", "won’t", "isn’t going to", "doesn’t", "B"),
            _q("___ you come to the party? (taklif)", "Are going to", "Will", "Are", "Do", "B"),
            _q("I ___ buy tickets tomorrow. (reja)", "will", "am going to", "buy", "buying", "B"),
            _q("He ___ fly to Tashkent next week. (chipta olingan)", "will", "is going to", "is flying", "flies", "C"),
            _q("It ___ be difficult. (fikr)", "will", "is going to", "is being", "is", "A"),
            _q("We ___ not eat out tonight. (qaror)", "are going to", "won’t", "aren’t going to", "don’t", "B"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_first_conditional",
        level="A2",
        title="First Conditional",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Birinchi shartli gap – real kelajakdagi shart va natija.\n"
            "Formula: If + Present Simple, will + verb\n\n"
            "🇷🇺 Русский:\n"
            "Условное предложение первого типа – реальное будущее условие и результат.\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: If + Present Simple, Subject + will + verb (Ex: If it rains, we will stay home.)\n\n"
            "❌ Negative\n"
            "Formula: If + Present Simple negative, Subject + won't + verb (Ex: If you don’t study, you won’t pass.)\n\n"
            "❓ Question\n"
            "Formula: What will + subject + do if...? (Ex: What will happen if I fail?)\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. If-gap (shart) oldinda kelsa, vergul (,) qo‘yiladi.\n"
            "🟢 2. Unless = If not (agar ... -masa).\n"
            "🟢 3. If qismida hech qachon 'will' ishlatilmaydi, faqat Present Simple.\n"
            "🟢 4. Kelajakdagi real imkoniyatlar (Real possibility) uchun ishlatiladi.\n\n"
            "📌 4. MISOLLAR\n"
            "If you study hard, you will pass the exam.\n"
            "We will go out if the weather is good.\n"
            "If she doesn’t come, I will be sad.\n"
            "Call me if you have time.\n"
            "You won’t succeed unless you try.\n"),
        questions=[
            _q("If it ___ , we will stay home.", "rains", "rain", "rained", "raining", "A"),
            _q("I ___ call you if I need help.", "will", "am going to", "call", "calls", "A"),
            _q("If you ___ hard, you will pass.", "study", "study", "studied", "studying", "A"),
            _q("We ___ not go if it rains.", "will", "won’t", "don’t", "isn’t", "B"),
            _q("___ you come if I invite you?", "Will", "Will", "Do", "Are", "A"),
            _q("If she ___ late, we will start without her.", "is", "be", "was", "being", "A"),
            _q("You ___ succeed unless you try.", "will", "won’t", "don’t", "isn’t", "B"),
            _q("If I ___ money, I will buy a car.", "have", "has", "had", "having", "A"),
            _q("What ___ if you win the lottery?", "will you do", "do you do", "did you do", "are you doing", "A"),
            _q("If he ___ , tell him to call me.", "calls", "call", "called", "calling", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_zero_conditional",
        level="A2",
        title="Zero Conditional",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Nol shartli gap – umumiy haqiqatlar, ilmiy faktlar yoki odatlar uchun.\n"
            "Formula: If + Present Simple, Present Simple\n\n"
            "🇷🇺 Русский:\n"
            "Условное предложение нулевого типа – для общих истин, фактов, привычек.\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: If + Present Simple, Present Simple (Ex: If you heat water, it boils.)\n\n"
            "❌ Negative\n"
            "Formula: If + Present Simple negative, Present Simple negative (Ex: If it doesn’t rain, plants die.)\n\n"
            "❓ Question\n"
            "Formula: What happens if + subject + Present Simple? (Ex: What happens if you mix blue and yellow?)\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Ikkala gapda ham har doim Present Simple ishlatiladi.\n"
            "🟢 2. 'If' o'rniga 'When' (qachonki) so'zini ham ishlatish mumkin.\n"
            "🟢 3. Umumiy qonuniyatlar va ilmiy faktlar uchun qo'llaniladi.\n"
            "🟢 4. Agar 'If' gapning boshida kelsa, vergul (,) qo‘yiladi.\n\n"
            "📌 4. MISOLLAR\n"
            "If you mix red and blue, you get purple.\n"
            "Water freezes if the temperature is zero.\n"
            "I go to bed early if I am tired.\n"
            "If people eat too much, they get fat.\n""Plants die if they don’t get water.\n"),
        questions=[
            _q("If you ___ water, it boils.", "heat", "heats", "heated", "heating", "A"),
            _q("Ice ___ if you heat it.", "melts", "melt", "melted", "melting", "A"),
            _q("If it ___ , we stay inside.", "rains", "rains", "rained", "raining", "A"),
            _q("Plants ___ if they don’t get sun.", "die", "die", "died", "dying", "A"),
            _q("If I ___ hungry, I eat.", "am", "is", "was", "be", "A"),
            _q("What ___ if you drop glass?", "happens", "happen", "happened", "happening", "A"),
            _q("People ___ tired if they don’t sleep.", "get", "gets", "got", "getting", "A"),
            _q("If you ___ exercise, you stay healthy.", "do", "does", "did", "doing", "A"),
            _q("Water ___ at 100 degrees.", "boils", "boil", "boiled", "boiling", "A"),
            _q("If babies ___ , they cry.", "are hungry", "is hungry", "was hungry", "be hungry", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_modals_must_have_to_should",
        level="A2",
        title="Must / Have to / Should",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Must = kuchli majburiyat (o‘zim yoki qonun).\n"
            "Have to = tashqi majburiyat (boshqalar talabi, qoidalar).\n"
            "Should = maslahat, tavsiya.\n\n"
            "🇷🇺 Русский:\n"
            "Must = сильное внутреннее обязательство или закон.\n"
            "Have to = внешнее обязательство (требование других).\n"
            "Should = совет, рекомендация.\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Must: You must stop. | Have to: I have to work. | Should: You should study.\n\n"
            "❌ Negative\n"
            "Mustn’t = taqiqlangan (Forbidden).\n"
            "Don’t have to = shart emas (Not necessary).\n"
            "Shouldn’t = maslahat emas (Advice against).\n\n"
            "❓ Question\n"
            "Must I...? / Do I have to...? / Should I...?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Must – faqat hozirgi va kelajak zamonda ishlatiladi, o‘tgan zamon shakli yo‘q (had to ishlatiladi).\n"
            "🟢 2. Mustn’t = qilish qat'iyan taqiqlanganligini bildiradi.\n"
            "🟢 3. Don’t have to = majburiyat yo‘q, xohlasangiz qilishingiz mumkin degani.\n"
            "🟢 4. Should – maslahat berish uchun (I think you should...).\n\n"
            "📌 4. MISOLLAR\n"
            "You must wear a helmet. (qonun)\n"
            "I have to finish this today. (boshliq buyrug'i)\n"
            "You should see a doctor. (maslahat)\n"
            "You mustn’t smoke here. (taqiq)\n"
            "You don’t have to come early. (shart emas)\n"),
        questions=[
            _q("You ___ stop when the light is red.", "must", "have to", "should", "can", "A"),
            _q("I ___ go to work tomorrow.", "must", "have to", "should", "can", "B"),
            _q("You ___ eat more vegetables.", "must", "have to", "should", "can", "C"),
            _q("We ___ not park here.", "have to", "mustn’t", "shouldn’t", "don’t have to", "B"),
            _q("___ I wear a tie?", "Must", "Must", "Have to", "Should", "A"),
            _q("She ___ study harder.", "must", "have to", "should", "can", "C"),
            _q("You ___ come if you don’t want.", "mustn’t", "don’t have to", "shouldn’t", "must", "B"),
            _q("Students ___ be quiet in class.", "must", "have to", "should", "can", "A"),
            _q("I ___ visit my grandma.", "must", "have to", "should", "can", "A"),
            _q("You ___ touch that!", "mustn’t", "don’t have to", "shouldn’t", "must", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_can_could",
        level="A2",
        title="Can / Could (requests & permission)",
        rule=("🇺🇿 O‘zbekcha:\n"
            "“Can” – hozirgi qobiliyat, ruxsat yoki iltimos.\n"
            "“Could” – o‘tmishdagi qobiliyat yoki muloyim iltimos (hozirgi uchun ham ishlatiladi).\n\n"
            "🇷🇺 Русский:\n"
            "“Can” – способность, разрешение или просьба сейчас.\n"
            "“Could” – способность в прошлом или вежливая просьба.\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + can/could + verb (Ex: I can swim. | Could you help me?)\n\n"
            "❌ Negative\n""Formula: Subject + can’t / couldn’t + verb (Ex: I can’t drive. | I couldn’t swim when I was five.)\n\n"
            "❓ Question\n"
            "Formula: Can/Could + subject + verb? (Ex: Can I open the window? | Could you tell me the time?)\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Can – norasmiy (informal) ruxsat yoki iltimos uchun.\n"
            "🟢 2. Could – muloyimroq (more polite) so'rovlar (requests) uchun.\n"
            "🟢 3. Ability (Qobiliyat): hozir → can, o'tmish → could.\n"
            "🟢 4. Javob: Yes, you can. / No, I couldn’t.\n\n"
            "📌 4. MISOLLAR\n"
            "Can I borrow your pen? Yes, you can.\n"
            "Could you speak louder?\n"
            "She can speak three languages.\n"
            "I couldn’t find my keys yesterday.\n"
            "Can we go now?\n"),
        questions=[
            _q("___ I use your phone?", "Can", "Could", "Must", "Should", "A"),
            _q("___ you help me, please? (muloyim)", "Can", "Could", "Must", "Should", "B"),
            _q("I ___ swim when I was a child.", "can", "could", "can’t", "couldn’t", "B"),
            _q("She ___ speak English fluently.", "can", "could", "must", "should", "A"),
            _q("___ we leave early today?", "Can", "Can", "Could", "Must", "A"),
            _q("He ___ drive a car last year.", "can", "could", "can’t", "couldn’t", "B"),
            _q("___ you open the door?", "Could", "Can", "Must", "Should", "B"),
            _q("I ___ hear you. Speak louder!", "can’t", "can’t", "couldn’t", "could", "A"),
            _q("___ I sit here?", "Can", "Could", "Must", "Should", "A"),
            _q("They ___ play tennis very well now.", "can", "could", "must", "should", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_countable_uncountable",
        level="A2",
        title="Countable & Uncountable Nouns",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Countable (sanab bo‘ladigan): bitta/ko‘p – a book, books\n"
            "Uncountable (sanab bo‘lmaydigan): suv, pul – water, money (a/an ishlatilmaydi)\n\n"
            "🇷🇺 Русский:\n"
            "Исчисляемые (countable): можно посчитать – a book, books\n"
            "Неисчисляемые (uncountable): нельзя посчитать – water, money\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Countable: I have a cat / three cats. | Uncountable: I need some water.\n\n"
            "❌ Negative\n"
            "Countable: I don’t have any apples. | Uncountable: There isn’t any milk.\n\n"
            "❓ Question\n"
            "Countable: How many books? | Uncountable: How much sugar?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Countable: a/an (singular), some/any (plural)\n"
            "🟢 2. Uncountable: some/any (hech qachon a/an emas)\n"
            "🟢 3. Irregular: hair (unc), news (unc), advice (unc)\n"
            "🟢 4. How many (countable), How much (uncountable)\n\n"
            "📌 4. MISOLLAR\n"
            "I have two apples. (countable)\n"
            "There is some milk in the fridge. (uncountable)\n"
            "How many chairs are there?\n"
            "How much money do you have?\n"
            "She gave me good advice.\n"),
        questions=[
            _q("I need ___ water.", "a", "some", "an", "many", "B"),
            _q("How ___ books do you have?", "many", "much", "some", "any", "A"),
            _q("There isn’t ___ sugar.", "many", "any", "a", "an", "B"),
            _q("She has ___ hair.", "a lot of", "many", "a", "an", "A"),
            _q("How ___ money is there?", "many", "much", "some", "any", "B"),
            _q("I bought ___ apples.", "some", "much", "a", "an", "A"),
            _q("There are ___ chairs in the room.", "some", "much", "a", "an", "A"),
            _q("He gave me ___ advice.", "some", "many", "a", "an", "A"),
            _q("How ___ rice do we need?", "much", "many", "some", "any", "A"),
            _q("We don’t have ___ friends here.", "much", "any", "a", "an", "B"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_some_any_no",
        level="A2",
        title="Some / Any / No",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Some – darak (positive) gapda (ba’zi, bir oz).\n"
            "Any – so‘roq va inkor gapda (biror, hech qanday).\n"
            "No = not any (hech qanday).\n\n"
            "🇷🇺 Русский:\n"
            "Some – в утвердительных предложениях.\n"
            "Any – в вопросах и отрицаниях.\n"
            "No = not any.\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Some: There is some bread. (Bir oz non bor.)\n\n"
            "❌ Negative\n"
            "Any/No: There isn’t any bread. / There is no bread. (Hech qanday non yo'q.)\n\n"
            "❓ Question\n"
            "Any: Is there any milk? (Sut bormi?)\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Some – taklif (offer) yoki so‘rovda (request) ham ishlatiladi (Ex: Would you like some tea?)\n"
            "🟢 2. Any – shartli gaplarda (If you have any questions...)\n"
            "🟢 3. No = not any (inkor ma'nosini kuchliroq bildiradi)\n"
            "🟢 4. Someone/anyone/no one, something/anything/nothing kabi birikmalar ham shu qoidaga bo'ysunadi.\n\n"
            "📌 4. MISOLLAR\n"
            "I have some friends in Tashkent.\n"
            "Is there any water?\n"
            "There is no time left.\n"
            "Would you like some coffee?\n"
            "I don’t have any money.\n"),
        questions=[
            _q("There is ___ milk in the fridge.", "some", "any", "no", "many", "A"),
            _q("Is there ___ sugar?", "some", "any", "no", "much", "B"),
            _q("We have ___ time.", "some", "any", "no", "many", "A"),
            _q("Do you have ___ questions?", "some", "any", "no", "much", "B"),
            _q("There isn’t ___ bread.", "some", "any", "no", "many", "B"),
            _q("Would you like ___ tea?", "some", "any", "no", "much", "A"),
            _q("I don’t need ___ help.", "some", "any", "no", "many", "B"),
            _q("There is ___ problem.", "some", "any", "no", "much", "C"),
            _q("Have you got ___ friends here?", "some", "any", "no", "much", "A"),
            _q("She has ___ money left.", "some", "any", "no", "many", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_much_many_lot",
        level="A2",
        title="Much / Many / A lot of / A little / A few",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Much – uncountable savol/inkor (ko‘pmi? ko‘p emas).\n"
            "Many – countable savol/inkor.\n"
            "A lot of – darak (positive) gaplarda (ko‘p).\n"
            "A little – uncountable (bir oz, yetarli).\n"
            "A few – countable (bir necha, yetarli).\n\n"
            "🇷🇺 Русский:\n"
            "Much – неисчисляемые в вопросах/отрицаниях.\n"
            "Many – исчисляемые в вопросах/отрицаниях.\n"
            "A lot of – много в утвердительных.\n"
            "A little – немного (неисчисляемые).\n"
            "A few – несколько (исчисляемые).\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "A lot of: There are a lot of people.\n\n"
            "❌ Negative\n"
            "Much/Many: I don’t have much time. / many friends.\n\n"
            "❓ Question\n"
            "How much / How many?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Positive gaplarda 'a lot of' yoki 'lots of' ishlatish afzal.\n"
            "🟢 2. Savol va inkorlarda 'much' (sanalmaydigan) va 'many' (saniladigan) ishlatiladi.\n"
            "🟢 3. A little / A few = ozgina bo'lsa ham yetarli (ijobiy).\n"
            "🟢 4. Little / Few = deyarli yo'q, juda kam (salbiy).\n\n"
            "📌 4. MISOLLAR\n"
            "There are many students in the class.\n"
            "I don’t have much money.\n"
            "She has a lot of books.\n"
            "There is a little water left.\n""I have a few friends here.\n"),
        questions=[
            _q("How ___ water do you drink?", "much", "many", "a lot", "a few", "A"),
            _q("There are ___ people here.", "much", "a lot of", "a little", "a few", "B"),
            _q("I have ___ friends in this city.", "much", "many", "a few", "a little", "C"),
            _q("She doesn’t eat ___ sugar.", "much", "many", "a lot", "a few", "A"),
            _q("How ___ books do you read?", "much", "many", "a lot", "a little", "B"),
            _q("There is ___ milk left.", "much", "many", "a little", "a few", "C"),
            _q("We have ___ time before the exam.", "a little", "a few", "much", "many", "A"),
            _q("He doesn’t have ___ money.", "much", "many", "a lot", "a few", "A"),
            _q("There are ___ apples on the table.", "much", "a few", "a little", "much", "B"),
            _q("I don’t know ___ people here.", "much", "many", "a lot", "a little", "B"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_too_enough",
        level="A2",
        title="Too / Enough",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Too – ortiqcha (salbiy: juda ko‘p) – too + adjective.\n"
            "Enough – yetarli (positive yoki negative) – adjective + enough / enough + noun.\n\n"
            "🇷🇺 Русский:\n"
            "Too – слишком (отрицательно).\n"
            "Enough – достаточно.\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Enough: This bag is big enough. | Too: The coffee is too hot.\n\n"
            "❌ Negative\n"
            "Not enough: There isn’t enough time.\n\n"
            "❓ Question\n"
            "Is it big enough? / Is it too heavy?\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Too + adjective + to + verb (too heavy to carry – ko'tarish uchun juda og'ir).\n"
            "🟢 2. Adjective + enough + to + verb (old enough to drive – haydash uchun yetarli darajada katta).\n"
            "🟢 3. Enough + noun (enough money – yetarli pul).\n"
            "🟢 4. Not too... = juda emas.\n\n"
            "📌 4. MISOLLAR\n"
            "The soup is too salty.\n"
            "She is old enough to vote.\n"
            "There isn’t enough food for everyone.\n"
            "This box is too heavy to lift.\n"
            "Is it warm enough to go out?\n"),
        questions=[
            _q("This tea is ___ hot.", "too", "enough", "very", "quite", "A"),
            _q("He is ___ tall to play basketball.", "too", "enough", "very", "quite", "A"),
            _q("There isn’t ___ time.", "too", "enough", "many", "much", "B"),
            _q("The bag is ___ heavy to carry.", "too", "enough", "very", "quite", "A"),
            _q("She speaks English ___ well.", "too", "enough", "very", "quite", "B"),
            _q("Is the coffee ___ sweet?", "too", "enough", "very", "quite", "A"),
            _q("We don’t have ___ money.", "too", "enough", "many", "much", "B"),
            _q("This dress is ___ small for me.", "too", "enough", "very", "quite", "A"),
            _q("He isn’t ___ old to drive.", "too", "enough", "very", "quite", "B"),
            _q("The room is ___ big for us.", "too", "enough", "very", "quite", "B"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_adv_manner",
        level="A2",
        title="Adverbs of Manner",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Harakat tarzini bildiruvchi ravishlar – qanday? degan savolga javob beradi.\n"
            "Sifat + ly (quick → quickly)\n"
            "Irregular (noto‘g‘ri): good → well, fast → fast, hard → hard\n\n"
            "🇷🇺 Русский:\n"
            "Наречия образа действия – отвечают на вопрос “как?”.\n"
            "Прилагательное + ly\n"
            "Неправильные: good → well, fast → fast, hard → hard\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + verb + adverb (Ex: She speaks English fluently.)\n\n"
            "❌ Negative\n"
            "Formula: Subject + doesn't/don't + verb + adverb (Ex: They don’t work hard.)\n\n"
            "❓ Question\n"
            "Formula: How + do/does + subject + verb? (Ex: How does she sing?)\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Ko'pincha -ly qo‘shiladi: slow → slowly, beautiful → beautifully.\n"
            "🟢 2. Agar sifat -y bilan tugasa: y → i bo'ladi (happy → happily).\n"
            "🟢 3. Irregular shakllar o'zgarmaydi yoki butunlay o'zgaradi: well, fast, hard, early, late.\n"
            "🟢 4. Odatda fe'ldan keyin yoki gap oxirida keladi.\n\n"
            "📌 4. MISOLLAR\n"
            "He runs quickly.\n"
            "She sings beautifully.\n"
            "They work hard every day.\n"
            "The child speaks English well.\n"
            "Drive slowly in the rain.\n"),
        questions=[
            _q("She speaks English ___.", "fluent", "fluently", "fluency", "fluents", "B"),
            _q("He drives ___.", "careful", "carefully", "care", "cares", "B"),
            _q("They play football ___.", "good", "well", "goods", "welly", "B"),
            _q("She dances ___.", "beautiful", "beautifully", "beauty", "beautifull", "B"),
            _q("Work ___ or you will fail.", "hardly", "hard", "harder", "hardest", "B"),
            _q("He arrived ___.", "late", "late", "lately", "later", "A"),
            _q("The baby sleeps ___.", "quiet", "quietly", "quietness", "quiets", "B"),
            _q("She answered the question ___.", "correct", "correctly", "correction", "corrects", "B"),
            _q("They run ___.", "fast", "fast", "faster", "fastest", "A"),
            _q("He writes ___.", "clear", "clearly", "clarity", "clears", "B"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_as_not_as",
        level="A2",
        title="As ... as / Not as ... as",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Tenglik solishtirish: as + adjective + as (xuddi ...dek, ... kabi).\n"
            "Inkor: not as + adjective + as (...chalik emas).\n\n"
            "🇷🇺 Русский:\n"
            "Сравнение равенства: as + прилагательное + as (такой же как).\n"
            "Отрицание: not as + прилагательное + as (не такой как).\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + be + as + adjective + as + object (Ex: She is as tall as her brother.)\n\n"
            "❌ Negative\n"
            "Formula: Subject + be + not as + adjective + as (Ex: This phone is not as expensive as that one.)\n\n"
            "❓ Question\n"
            "Formula: Is/Are + subject + as + adjective + as ...? (Ex: Is Tashkent as big as Almaty?)\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. As ... as – ikki narsaning sifati tengligini bildiradi.\n"
            "🟢 2. Not as ... as = kamroq (less than) ma'nosini beradi.\n"
            "🟢 3. Ravish (adverb) bilan ham ishlatish mumkin: He doesn’t run as fast as me.\n"
            "🟢 4. Darak gaplarda doimo 'as ... as' ishlatiladi ('so ... as' asosan inkorlarda uchrashi mumkin, lekin 'as ... as' universal).\n\n"
            "📌 4. MISOLLAR\n"
            "My car is as fast as yours.\n"
            "English is not as difficult as math.\n"
            "She sings as beautifully as a professional.\n"
            "Is this bag as heavy as that one?\n"
            "He isn’t as tall as his father.\n"),
        questions=[
            _q("She is ___ tall ___ her sister.", "as / as", "so / as", "than / as", "more / than", "A"),
            _q("This book is ___ interesting ___ that one.", "as / as", "not as / as", "more / than", "than / as", "A"),
            _q("He runs ___ fast ___ me.", "as / as", "not as / as", "more / than", "than / as", "A"),
            _q("Tashkent is ___ big ___ Samarkand.", "as / as", "not as / as", "more / than", "than / as", "A"),
            _q("The film was ___ good ___ I expected.", "not as / as", "as / as", "more / than", "than / as", "B"),
            _q("Is your phone ___ expensive ___ mine?", "as / as", "as / as", "more / than", "than / as", "A"),
            _q("She doesn’t speak ___ fluently ___ her teacher.", "as / as", "as / as", "more / than", "than / as", "A"),
            _q("This coffee is ___ hot ___ that one.", "not as / as", "as / as", "more / than", "than / as", "A"),
            _q("He is ___ strong ___ his brother.", "as / as", "not as / as", "more / than", "than / as", "A"),
            _q("Math is ___ easy ___ English for me.", "not as / as", "as / as", "more / than", "than / as", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_object_pronouns",
        level="A2",
        title="Object Pronouns",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Ob'ekt olmoshlari – gapda fe’l yoki predlogdan keyin keladi (menga, unga, bizga).\n"
            "me, you, him, her, it, us, them\n\n"
            "🇷🇺 Русский:\n"
            "Объектные местоимения – после глагола или предлога.\n"
            "me, you, him, her, it, us, them\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + verb + object pronoun (Ex: She loves him. | Give it to me.)\n\n"
            "❌ Negative\n""Formula: Subject + don't/doesn't + verb + object pronoun (Ex: I don’t know them.)\n\n"
            "❓ Question\n"
            "Formula: Do/Does + subject + verb + object pronoun? (Ex: Do you see her?)\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. 'You' va 'it' shakllari o‘zgarmaydi (ham ega, ham to'ldiruvchi bir xil).\n"
            "🟢 2. Predloglardan keyin faqat ob'ekt olmoshi keladi: with me, for us, to them.\n"
            "🟢 3. Ega (I, you, he...) bilan adashtirmang – bular faqat harakat qabul qiluvchi.\n"
            "🟢 4. Tell, show, give, send fe'llari bilan juda ko‘p ishlatiladi.\n\n"
            "📌 4. MISOLLAR\n"
            "Call me tomorrow.\n"
            "I saw her yesterday.\n"
            "They helped us a lot.\n"
            "This gift is for you.\n"
            "Don’t tell him the secret.\n"),
        questions=[
            _q("She loves ___.", "he", "him", "his", "himself", "B"),
            _q("Give ___ the book.", "me", "I", "my", "mine", "A"),
            _q("I don’t know ___.", "they", "them", "their", "theirs", "B"),
            _q("He called ___ yesterday.", "she", "her", "hers", "herself", "B"),
            _q("This is for ___.", "us", "we", "our", "ours", "A"),
            _q("Do you see ___?", "it", "it", "its", "itself", "A"),
            _q("Tell ___ the truth.", "me", "I", "my", "mine", "A"),
            _q("They invited ___ to the party.", "us", "we", "our", "ours", "A"),
            _q("She doesn’t like ___.", "he", "him", "his", "himself", "B"),
            _q("Send ___ a message.", "me", "I", "my", "mine", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_reflexive_pronouns",
        level="A2",
        title="Reflexive Pronouns",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Qaytma olmoshlar – harakat eganing o‘ziga qaytganida (o‘zimni, o‘zini) ishlatiladi.\n"
            "myself, yourself, himself, herself, itself, ourselves, yourselves, themselves\n\n"
            "🇷🇺 Русский:\n"
            "Возвратные местоимения – используются, когда действие возвращается к самому субъекту.\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + verb + reflexive pronoun (Ex: I hurt myself. | She talks to herself.)\n\n"
            "❌ Negative\n"
            "Formula: Subject + didn't + verb + reflexive pronoun (Ex: We didn’t enjoy ourselves.)\n\n"
            "❓ Question\n"
            "Formula: Did + subject + verb + reflexive pronoun? (Ex: Did you cut yourself?)\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. By + reflexive = yolg‘iz, yordamsiz (Ex: by myself = o'zim mustaqil).\n"
            "🟢 2. Enjoy, hurt, cut, teach, introduce kabi fe'llar bilan ko‘p keladi.\n"
            "🟢 3. Each other / one another – 'bir-birini' degan ma'noni beradi (ikki yoki undan ortiq shaxs).\n"
            "🟢 4. Birlikda -self, ko‘plikda -selves qo'shimchasi qo'shiladi.\n\n"
            "📌 4. MISOLLAR\n"
            "I made this cake myself.\n"
            "He cut himself while cooking.\n"
            "They enjoyed themselves at the party.\n"
            "She lives by herself.\n"
            "We taught ourselves English.\n"),
        questions=[
            _q("I hurt ___.", "me", "myself", "mine", "my", "B"),
            _q("She talks to ___.", "her", "herself", "hers", "she", "B"),
            _q("They enjoyed ___ at the beach.", "them", "themselves", "their", "theirs", "B"),
            _q("He lives by ___.", "him", "himself", "his", "he", "B"),
            _q("We cut ___ while playing.", "us", "ourselves", "our", "ours", "B"),
            _q("Did you teach ___ English?", "you", "yourself", "your", "yours", "B"),
            _q("The cat cleans ___.", "it", "itself", "its", "itself", "B"),
            _q("You should believe in ___.", "you", "yourself", "your", "yours", "B"),
            _q("They introduced ___ to us.", "them", "themselves", "their", "theirs", "B"),
            _q("I did it by ___.", "me", "myself", "mine", "my", "B"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_possessive_pronouns",
        level="A2",
        title="Possessive Pronouns",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Egilik olmoshlari – otning o‘rnida keladi va egalikni bildiradi (meningki, seningki).\n"
            "mine, yours, his, hers, its, ours, yours, theirs\n\n"
            "🇷🇺 Русский:\n"
            "Притяжательные местоимения – заменяют существительное и указывают на принадлежность.\n"
            "mine, yours, his, hers, its, ours, yours, theirs\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + be + possessive pronoun (Ex: This book is mine. | The car is hers.)\n\n"
            "❌ Negative\n"
            "Formula: Subject + be + not + possessive pronoun (Ex: This phone is not yours.)\n\n"
            "❓ Question\n"
            "Formula: Is/Are + subject + possessive pronoun? (Ex: Is this yours?)\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Ot (noun) oldidan ishlatilmaydi – mustaqil gap oxirida yoki ega vazifasida keladi.\n"
            "🟢 2. 'Its' shakli egilik olmoshi sifatida juda kam ishlatiladi.\n"
            "🟢 3. 'Yours' ham birlik, ham ko‘plik uchun bir xil.\n"
            "🟢 4. Egilik sifatlari (my, your...) + ot birikmasini bitta egilik olmoshi (mine, yours...) bilan almashtirish mumkin.\n\n"
            "📌 4. MISOLLAR\n"
            "This pen is mine.\n"
            "That house is theirs.\n"
            "Is this bag yours? Yes, it is.\n"
            "Her phone is broken, so she uses mine.\n"
            "The idea was ours.\n"),
        questions=[
            _q("This book is ___.", "my", "mine", "me", "myself", "B"),
            _q("That car is ___.", "her", "hers", "she", "herself", "B"),
            _q("Is this phone ___?", "your", "yours", "you", "yourself", "B"),
            _q("The house is ___.", "their", "theirs", "them", "themselves", "B"),
            _q("This gift is ___.", "our", "ours", "us", "ourselves", "B"),
            _q("His idea is better than ___.", "my", "mine", "me", "myself", "B"),
            _q("The cat is ___.", "its", "its", "it", "itself", "A"),
            _q("These shoes are not ___.", "your", "yours", "you", "yourself", "B"),
            _q("That decision was ___.", "our", "ours", "us", "ourselves", "B"),
            _q("Is the mistake ___ or ___?", "your / mine", "yours / mine", "you / me", "yourself / myself", "B"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_there_was_were",
        level="A2",
        title="There was / There were",
        rule=("🇺🇿 O‘zbekcha:\n"
            "O‘tmishdagi “bor edi” (mavjud edi) – There was / There were.\n"
            "Bitta narsa (Singular) → There was\n"
            "Ko‘p narsa (Plural) → There were\n\n"
            "🇷🇺 Русский:\n"
            "Прошедшее время “было / имелось” – There was / There were.\n"
            "Единственное число → There was\n"
            "Множественное число → There were\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: There was + singular / There were + plural (Ex: There was a book on the table.)\n\n"
            "❌ Negative\n"
            "Formula: There wasn’t / There weren’t (Ex: There wasn’t any milk.)\n\n"
            "❓ Question\n"
            "Formula: Was there ...? / Were there ...? (Ex: Was there a party? Yes, there was.)\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Was – birlik (Singular) va sanalmaydigan otlar bilan; Were – ko'plik (Plural) bilan.\n"
            "🟢 2. Qisqartma shakllar: wasn’t, weren’t.\n"
            "🟢 3. Any – ko'pincha inkor va so'roq gaplarda ko'plikdagi otlar bilan keladi.\n"
            "🟢 4. Javob: Yes, there was. / No, there weren’t.\n\n"
            "📌 4. MISOLLAR\n"
            "There was a big tree in the garden.\n"
            "There were two cats outside.\n"
            "There wasn’t any water left.\n"
            "Were there many guests? Yes, there were.\n"
            "There was no internet yesterday.\n"),
        questions=[
            _q("___ a pen on the desk yesterday.", "There were", "There was", "There is", "There are", "B"),
            _q("___ many students in the class.", "There was", "There were", "There is", "There are", "B"),
            _q("___ any food left?", "Was there", "Were there", "Is there", "Are there", "A"),
            _q("There ___ a problem last week.", "was", "were", "is", "are", "A"),
            _q("There ___ any chairs.", "was", "weren’t", "wasn’t", "isn’t", "B"),
            _q("___ there a meeting? Yes, there ___.", "Was / was", "Was / was", "Were / were", "Are / are", "A"),
            _q("There ___ three books.", "was", "were", "is", "are", "B"),
            _q("There ___ no time.", "was", "were", "is", "are", "A"),
            _q("Were there ___ people?", "some", "any", "a", "an", "B"),
            _q("There ___ any rain yesterday.", "was", "wasn’t", "were", "weren’t", "B"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_used_to",
        level="A2",
        title="Used to (past habits & states)",
        rule=("🇺🇿 O‘zbekcha:\n"
            "“Used to” – o‘tmishdagi (hozirda to‘xtagan) odatlar yoki holatlar uchun ishlatiladi.\n"
            "Formula: Subject + used to + verb\n\n"
            "🇷🇺 Русский:\n"
            "“Used to” – привычки или состояния в прошлом, которых больше нет.\n"
            "Formula: Subject + used to + глагол\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + used to + verb (Ex: I used to play football.)\n\n"
            "❌ Negative\n"
            "Formula: Subject + didn’t use to + verb (Ex: He didn’t use to smoke.)\n\n"
            "❓ Question\n"
            "Formula: Did + subject + use to + verb? (Ex: Did you use to have long hair?)\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Faqat o‘tmishdagi, hozirda mavjud bo'lmagan odat yoki holat uchun.\n"
            "🟢 2. Inkor va so'roq gaplarda 'd' harfi tushib qoladi (didn't use to / Did you use to).\n"
            "🟢 3. 'Be used to + -ing' (ko‘nikkan bo‘lmoq) bilan adashtirmang, bu boshqa struktura.\n"
            "🟢 4. Qisqa javob: Yes, I did. / No, I didn’t.\n\n"
            "📌 4. MISOLLAR\n"
            "I used to live in a village.\n"
            "We used to visit grandparents every weekend.\n"
            "She didn’t use to like coffee.\n"
            "Did you use to watch cartoons? Yes, I did.\n"
            "There used to be a park here.\n"),
        questions=[
            _q("I ___ play video games a lot.", "use to", "used to", "uses to", "using to", "B"),
            _q("She ___ live in Tashkent.", "use to", "used to", "uses to", "using to", "B"),
            _q("He ___ not smoke.", "use to", "didn’t use to", "doesn’t use to", "using to", "B"),
            _q("___ you use to have a dog?", "Do", "Did", "Does", "Are", "B"),
            _q("We ___ go swimming every summer.", "used to", "use to", "uses to", "using to", "A"),
            _q("There ___ be a cinema here.", "used to", "use to", "uses to", "using to", "A"),
            _q("She ___ like vegetables.", "use to", "didn’t use to", "doesn’t use to", "using to", "B"),
            _q("Did they ___ travel a lot?", "use to", "use to", "uses to", "using to", "A"),
            _q("I ___ be very shy.", "used to", "use to", "uses to", "using to", "A"),
            _q("He ___ not eat fast food.", "use to", "didn’t use to", "doesn’t use to", "using to", "B"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_prep_movement",
        level="A2",
        title="Prepositions of Movement",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Harakat predloglari – qayerga? savoliga javob berib, harakat yo‘nalishini bildiradi.\n"
            "to – tomon (yo'nalish), into – ichiga kirish, across – kesib o‘tish (yuzadan), through – ichidan o‘tish.\n\n"
            "🇷🇺 Русский:\n"
            "Предлоги движения – показывают направление движения.\n"
            "to – к/в (направление), into – внутрь, across – через (поверхность), through – сквозь.\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + verb + preposition + place (Ex: I went to school.)\n\n"
            "❌ Negative\n"
            "Formula: Subject + didn't + verb + preposition (Ex: He didn’t go into the room.)\n\n"
            "❓ Question\n"
            "Formula: Where + did + subject + verb? (Ex: Where did you go?)\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. to – biror joyga qarab yo‘nalish (to the park).\n"
            "🟢 2. into – harakat bilan biror narsaning ichkarisiga kirish (into the house).\n"
            "🟢 3. across – bir tomondan ikkinchi tomonga yuzadan o‘tish (across the river).\n"
            "🟢 4. through – uch o'lchamli bo'shliq yoki to'siq ichidan o‘tish (through the tunnel).\n\n"
            "📌 4. MISOLLAR\n"
            "We drove to Tashkent.\n"
            "The cat jumped into the box.\n"
            "She walked across the bridge.\n"
            "He ran through the park.\n"
            "They came out of the building.\n"),
        questions=[
            _q("I went ___ school.", "to", "into", "across", "through", "A"),
            _q("She walked ___ the street.", "to", "across", "into", "through", "B"),
            _q("He jumped ___ the pool.", "to", "into", "across", "through", "B"),
            _q("We drove ___ the tunnel.", "to", "into", "through", "across", "C"),
            _q("They came ___ the room.", "to", "into", "out of", "across", "C"),
            _q("The bird flew ___ the window.", "through", "to", "into", "across", "A"),
            _q("I ran ___ the park.", "to", "across", "into", "through", "D"),
            _q("She went ___ home.", "to", "into", "across", "through", "A"),
            _q("He climbed ___ the wall.", "to", "over", "into", "through", "B"),
            _q("We walked ___ the forest.", "to", "into", "through", "across", "C"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_basic_phrasal_verbs",
        level="A2",
        title="Basic Phrasal Verbs",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Asosiy phrasal verbs (iborali fe'llar) – fe’l + yuklama (zarf/predlog) birikmasi bo'lib, yangi ma’no hosil qiladi.\n"
            "Misol: turn on (yoqish), turn off (o'chirish), look for (qidirish), get up (o'rindan turish).\n\n"
            "🇷🇺 Русский:\n"
            "Основные фразовые глаголы – сочетание глагола + частица (наречие/предлог), меняющее значение.\n"
            "Пример: turn on (включить), look for (искать), get up (вставать).\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Subject + phrasal verb (+ object) (Ex: Turn on the light. | I got up early.)\n\n"
            "❌ Negative\n"
            "Formula: Subject + don’t/doesn’t + phrasal verb (Ex: Don’t turn off the TV.)\n\n"
            "❓ Question\n"
            "Formula: Do/Does + subject + phrasal verb? (Ex: Did you look for your keys?)\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Ajraladigan (Separable): to'ldiruvchi fe'l va yuklama o'rtasida kelishi mumkin (Ex: turn it on).\n"
            "🟢 2. Ajralmaydigan (Inseparable): to'ldiruvchi har doim yuklamadan keyin keladi (Ex: look for it).\n"
            "🟢 3. Eng ko'p ishlatiladiganlar: get up, wake up, put on, take off, look after, give up.\n"
            "🟢 4. Ma’no butunlay o'zgarishi mumkin (Ex: give - bermoq, give up - taslim bo'lmoq).\n\n"
            "📌 4. MISOLLAR\n"
            "Turn on the computer.\n"
            "I woke up at 7.\n"
            "She put on her jacket.\n"
            "He looked after the baby.\n"
            "Don’t give up!\n"),
        questions=[
            _q("Please ___ the light.", "turn on", "turn on", "turn off", "turn up", "A"),
            _q("I ___ early every day.", "get up", "get up", "get on", "get in", "A"),
            _q("She ___ her shoes.", "put on", "put on", "put off", "put up", "A"),
            _q("Can you ___ the kids?", "look for", "look after", "look at", "look up", "B"),
            _q("Don’t ___ now!", "give up", "give up", "give in", "give out", "A"),
            _q("Turn ___ the music, it’s loud.", "on", "off", "up", "down", "D"),
            _q("He ___ his hat.", "take off", "took off", "take on", "take up", "B"),
            _q("We need to ___ the truth.", "look for", "look for", "look after", "look at", "A"),
            _q("Wake ___ at 6, please.", "up", "up", "on", "off", "A"),
            _q("She ___ smoking last year.", "gave up", "gave up", "gave in", "gave out", "A"),
        ],
    ),
    GrammarTopic(
        topic_id="a2_defining_relative",
        level="A2",
        title="Defining Relative Clauses",
        rule=("🇺🇿 O‘zbekcha:\n"
            "Aniqlovchi ergash gaplar (Relative Clauses) – shaxs, narsa yoki joy haqida aniqlashtiruvchi ma’lumot beradi.\n"
            "who – odamlar uchun, which – narsalar uchun, that – ikkalasi uchun (norasmiy), where – joy uchun.\n\n"
            "🇷🇺 Русский:\n"
            "Определительные придаточные предложения – дают важную информацию о человеке, предмете или месте.\n"
            "who – люди, which – неодушевленные предметы, that – оба варианта, where – место.\n\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula: Noun + who/which/that/where + clause (Ex: The man who lives next door is kind.)\n\n"
            "❌ Negative\n"
            "Formula: Noun + who/which/that + negative clause (Ex: I don’t like people who are rude.)\n\n"
            "❓ Question\n"
            "Formula: Do you know the place where...? (Ex: Do you know the city where she was born?)\n\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. That – asosan so'zlashuvda 'who' yoki 'which' o'rnida ishlatilishi mumkin.\n"
            "🟢 2. Agar olmosh to'ldiruvchi vazifasida kelsa, uni tashlab ketish mumkin (Ex: The book [that] I read...).\n"
            "🟢 3. Where – har doim joy ma'nosidagi otlardan keyin keladi (Ex: the school where I studied).\n"
            "🟢 4. Defining clause gapning ma'nosi uchun zarur bo'lgani uchun vergul (comma) bilan ajratilmaydi.\n\n"
            "📌 4. MISOLLAR\n"
            "The girl who won the prize is my sister.\n"
            "This is the house where I grew up.\n"
            "I like films that are funny.\n"
            "The teacher (who/that) helped me is great.\n"
            "Tashkent is the city where I live.\n"),
        questions=[
            _q("The man ___ lives next door is nice.", "who", "which", "where", "whose", "A"),
            _q("This is the book ___ I bought.", "who", "that", "where", "whose", "B"),
            _q("The school ___ I studied is old.", "who", "which", "where", "whose", "C"),
            _q("People ___ are kind help others.", "who", "which", "where", "whose", "A"),
            _q("The car ___ is red is mine.", "who", "which", "where", "whose", "B"),
            _q("Do you know the place ___ we met?", "who", "which", "where", "whose", "C"),
            _q("The boy ___ won is happy.", "who", "which", "where", "whose", "A"),
            _q("I lost the phone ___ I bought yesterday.", "who", "that", "where", "whose", "B"),
            _q("This is the restaurant ___ serves Uzbek food.", "who", "which", "where", "whose", "B"),
            _q("The teacher ___ helped me is great.", "who", "which", "where", "whose", "A"),
        ],
    ),
]

# ========= B1 =========
# Part 1: Topics 1–5

B1_TOPICS: List[GrammarTopic] = [
    GrammarTopic(
        topic_id='b1_present_perfect_continuous',
        level="B1",
        title='Present Perfect Continuous (have/has been + verb-ing)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Hozirgi mukammal davomiy zamon – o‘tmishda boshlangan va hozir davom etayotgan yoki yaqinda tugagan (natijasi ko‘rinib turgan) harakatlar uchun.Formula: I/You/We/They + have been + V-ingHe/She/It + has been + V-ing\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Present Perfect Continuous – для действий, которые начались в прошлом и продолжаются сейчас или недавно закончились (с видимым результатом).\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "Subject + have/has been + verb-ing\n"
            "Examples:\n"
            "I have been studying English for three hours.She has been running, that's why she's tired.\n"
            "❌ Negative\n"
            "Formula:\n"
            "Subject + haven’t/hasn’t been + verb-ing\n"
            "Examples:\n"
            "We haven’t been sleeping well lately.\n"
            "❓ Question\n"
            "Formula:\n"
            "Have/Has + subject + been + verb-ing?\n"
            "Examples:\n"
            "How long have you been waiting?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. For / since bilan ko‘p ishlatiladi (for two weeks, since 2020)\n"
            "🟢 2. Natija ko‘rinib tursa (wet clothes → has been raining)\n"
            "🟢 3. How long...? savollarda eng yaxshi\n"
            "🟢 4. Stative fe’llar bilan kam (know, like – Present Perfect Simple ishlatiladi)\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "have been working here since 2019.\n"
            "Why are your eyes red? – I have been crying.\n"
            "She hasn’t been feeling well recently.\n"
            "Have you been exercising?\n"
            "You look fit!\n"
            "It has been snowing all night.\n"
        ),
        questions=[
            _q('I ___ English for two years.', 'have studied', 'have been studying', 'studied', 'study', 'B'),
            _q("She ___ , that's why she's wet.", 'has walked', 'has been walking', 'walked', 'walks', 'B'),
            _q('How long ___ you ___ here?', 'have / waited', 'have / been waiting', 'did / wait', 'are / waiting', 'B'),
            _q('We ___ TV all evening.', 'have watched', 'have been watching', 'watched', 'watch', 'B'),
            _q('He ___ not ___ well lately.', 'has / felt', 'has / been feeling', 'felt', 'feels', 'B'),
            _q('Why are your hands dirty? – I ___ the car.', 'repaired', 'have been repairing', 'repair', 'repairing', 'B'),
            _q('___ they ___ long?', 'Have / waited', 'Have / been waiting', 'Did / wait', 'Are / waiting', 'B'),
            _q('It ___ raining since morning.', 'has rained', 'has been raining', 'rained', 'rains', 'B'),
            _q('I ___ not ___ enough sleep.', 'have / got', 'have / been getting', 'got', 'get', 'B'),
            _q('How long ___ she ___ Spanish?', 'has / learned', 'has / been learning', 'learned', 'learns', 'B'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_past_perfect_simple',
        level="B1",
        title='Past Perfect Simple (had + V3)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "O‘tmishda o‘tmish – bir harakat boshqasidan oldin sodir bo‘lganini bildiradi.Formula: Subject + had + past participle\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Прошедшее совершенное время – действие, завершённое до другого действия в прошлом.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "Subject + had + V3\n"
            "Examples:\n"
            "I had finished my homework before dinner.She had left when I arrived.\n"
            "❌ Negative\n"
            "Formula:\n"
            "Subject + hadn’t + V3\n"
            "Examples:\n"
            "They hadn’t eaten before the meeting.\n"
            "❓ Question\n"
            "Formula:\n"
            "Had + subject + V3?\n"
            "Examples:\n"
            "Had you seen the film before?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Before / after / by the time / when bilan ishlatiladi\n"
            "🟢 2. Birinchi harakat Past Perfect, ikkinchisi Past Simple\n"
            "🟢 3. Short form: I’d, she’d, hadn’t\n"
            "🟢 4. Narrative hikoyalarda (storytelling) ko‘p\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "When I got home, my family had already eaten.\n"
            "She hadn’t studied, so she failed the test.\n"
            "Had you visited Uzbekistan before 2020?\n"
            "By the time we arrived, the film had started.\n"
            "He was tired because he had worked all night.\n"
        ),
        questions=[
            _q('I ___ my homework before I went out.', 'finished', 'had finished', 'have finished', 'finish', 'B'),
            _q('She ___ when we arrived.', 'left', 'had left', 'has left', 'leaves', 'B'),
            _q('___ you ___ the news before?', 'Have / heard', 'Had / heard', 'Did / hear', 'Do / hear', 'B'),
            _q('They ___ eaten before the party started.', 'hadn’t', 'haven’t', 'didn’t', 'don’t', 'A'),
            _q('By the time he came, we ___ .', 'left', 'had left', 'have left', 'leave', 'B'),
            _q('He was angry because she ___ his message.', 'didn’t read', 'hadn’t read', 'hasn’t read', 'doesn’t read', 'B'),
            _q('___ the train ___ before you got to the station?', 'Has / left', 'Had / left', 'Did / leave', 'Does / leave', 'B'),
            _q('We ___ the film, so we knew the ending.', 'saw', 'had seen', 'have seen', 'see', 'B'),
            _q('She ___ tired because she ___ all day.', 'was / worked', 'was / had worked', 'is / worked', 'has / worked', 'B'),
            _q('Had they ___ before the rain started?', 'finished', 'finish', 'finishes', 'finishing', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_narrative_tenses',
        level="B1",
        title='Narrative Tenses (Past Simple, Past Continuous, Past Perfect)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Hikoya zamonlari – o‘tmishdagi voqealarni hikoya qilish uchun.Past Simple – ketma-ket qisqa harakatlarPast Continuous – fon (davomiy harakat)Past Perfect – oldingi harakat (birinchisi)\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Повествовательные времена – для рассказывания истории в прошлом.Past Simple – последовательные действияPast Continuous – фонPast Perfect – действие раньше другого\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Past Simple: I went to the party.Past Continuous: I was dancing when...Past Perfect: I had eaten before I went.\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Past Simple: I didn’t go.Past Continuous: I wasn’t dancing.Past Perfect: I hadn’t eaten.\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Past Simple: Did you go?Past Continuous: Were you dancing?Past Perfect: Had you eaten?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. When + Past Simple (qisqa harakat) + Past Continuous (fon)\n"
            "🟢 2. Before/By the time + Past Perfect\n"
            "🟢 3. While + Past Continuous\n"
            "🟢 4. Hikoyada Past Perfect birinchi harakatni ko‘rsatadi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "was walking in the park when it started to rain.\n"
            "She had already left when I arrived.\n"
            "While I was cooking, the phone rang.\n"
            "By the time we got there, the film had finished.\n"
            "He didn’t see the accident because he was looking at his phone.\n"
        ),
        questions=[
            _q('I ___ in the park when it ___ to rain.', 'walked / started', 'was walking / started', 'had walked / started', 'walk / starts', 'B'),
            _q('She ___ the house before I ___.', 'left / arrived', 'had left / arrived', 'was leaving / arrived', 'leaves / arrive', 'B'),
            _q('While I ___ dinner, the phone ___.', 'cooked / rang', 'was cooking / rang', 'had cooked / rang', 'cook / rings', 'B'),
            _q('By the time we ___, the meeting ___.', 'arrived / started', 'arrived / had started', 'were arriving / started', 'arrive / starts', 'B'),
            _q('He ___ the accident because he ___ at his phone.', 'didn’t see / looked', 'didn’t see / was looking', 'hadn’t seen / looked', 'doesn’t see / looks', 'B'),
            _q('___ you ___ when the teacher came?', 'Were / talking', 'Were / talking (alt 2)', 'Had / talked', 'Did / talk', 'A'),
            _q('They ___ tired because they ___ all day.', 'were / worked', 'were / had worked', 'had been / worked', 'was / working', 'B'),
            _q('I ___ the film before, so I knew the ending.', 'saw', 'had seen', 'was seeing', 'have seen', 'B'),
            _q('She ___ when the lights went out.', 'cooked', 'was cooking', 'had cooked', 'cooks', 'B'),
            _q('___ the train ___ before you got to the station?', 'Had / left', 'Did / leave', 'Was / leaving', 'Has / left', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_future_continuous_perfect',
        level="B1",
        title='Future Continuous & Future Perfect',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Future Continuous – kelajakda bir vaqtda davom etayotgan harakat (will be + V-ing)Future Perfect – kelajakda bir vaqtga qadar tugallangan harakat (will have + V3)\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Future Continuous – действие в процессе в будущемFuture Perfect – действие, завершённое к определённому моменту в будущем\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Future Continuous: I will be working at 5 pm.Future Perfect: I will have finished by tomorrow.\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Future Continuous: I won’t be working.Future Perfect: I won’t have finished.\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Future Continuous: Will you be working?Future Perfect: Will you have finished?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Future Continuous – at 5 o’clock, this time tomorrow\n"
            "🟢 2. Future Perfect – by 2027, by the time, by next week\n"
            "🟢 3. Both forms polite so‘rovlar uchun ishlatiladi (Will you be using...?)\n"
            "🟢 4. Stative fe’llar bilan kamroq\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "This time tomorrow I will be flying to London.\n"
            "By the end of the year I will have learned 500 words.\n"
            "Will you be using the car this evening?\n"
            "She won’t have arrived by 8 o’clock.\n"
            "I will be sleeping when you call.\n"
        ),
        questions=[
            _q('This time tomorrow I ___ to London.', 'will be flying', 'will fly', 'will have flown', 'fly', 'A'),
            _q('By next week I ___ the book.', 'will read', 'will have read', 'will be reading', 'read', 'B'),
            _q('___ you ___ the car tonight?', 'Will / use', 'Will / be using', 'Will / have used', 'Do / use', 'B'),
            _q('By 2030 we ___ on Mars.', 'will live', 'will have lived', 'will be living', 'live', 'C'),
            _q('She ___ when you arrive.', 'will sleep', 'will be sleeping', 'will have slept', 'sleeps', 'B'),
            _q('I ___ the report by Friday.', 'will have finished', 'will finish', 'will be finishing', 'finish', 'A'),
            _q('___ they ___ at 10 pm?', 'Will / work', 'Will / be working', 'Will / have worked', 'Do / work', 'B'),
            _q('By the time you come, I ___ dinner.', 'will have cooked', 'will cook', 'will be cooking', 'cook', 'A'),
            _q('We ___ the match at 7.', 'will watch', 'will be watching', 'will have watched', 'watch', 'B'),
            _q('She ___ the exam by next month.', 'will pass', 'will have passed', 'will be passing', 'passes', 'B'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_present_vs_past_perfect',
        level="B1",
        title='Present Perfect vs Past Perfect',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Present Perfect – o‘tmish bilan hozir bog‘liq (ever, never, already, yet)Past Perfect – ikkala harakat ham o‘tmishda (before, when, by the time)\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Present Perfect – связь прошлого с настоящимPast Perfect – оба действия в прошлом (одно раньше другого)\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Present Perfect: I have visited Paris.Past Perfect: I had visited Paris before I went to London.\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Present Perfect: I haven’t seen it.Past Perfect: I hadn’t seen it before.\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Present Perfect: Have you seen it?Past Perfect: Had you seen it before?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Present Perfect – today, this week, so far\n"
            "🟢 2. Past Perfect – before, after, when (o‘tmish hikoyasida)\n"
            "🟢 3. Present Perfect – natija hozir ko‘rinadi\n"
            "🟢 4. Past Perfect – ikkinchi harakat Past Simple\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "have lost my keys.\n"
            "(hozir topa olmayapman)I had lost my keys before I left home.\n"
            "(o‘tmishda)She has never been to London.\n"
            "She had never been to London before 2020.\n"
            "Had you eaten before the meeting started?\n"
        ),
        questions=[
            _q('I ___ my keys. (hozir)', 'have lost', 'had lost', 'lost', 'lose', 'A'),
            _q('I ___ my keys before I left. (o‘tmish)', 'have lost', 'had lost', 'lost', 'lose', 'B'),
            _q('She ___ never been to Paris.', 'had', 'has', 'have', 'was', 'B'),
            _q('___ you eaten before the film started?', 'Have', 'Had', 'Did', 'Do', 'B'),
            _q('They ___ the news yet. (hozir)', 'haven’t heard', 'hadn’t heard', 'didn’t hear', 'don’t hear', 'A'),
            _q('By the time I arrived, they ___ .', 'have left', 'had left', 'left', 'leave', 'B'),
            _q('I ___ this film before. (tajriba)', 'have seen', 'had seen', 'saw', 'see', 'A'),
            _q('She ___ tired because she ___ all day.', 'was / has worked', 'was / had worked', 'is / worked', 'has / worked', 'B'),
            _q('___ you visited Tashkent before 2023?', 'Have', 'Had', 'Did', 'Do', 'B'),
            _q('We ___ the test, so we were happy.', 'have passed', 'had passed', 'passed', 'pass', 'B'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_second_conditional',
        level="B1",
        title='Second Conditional',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Ikkinchi shartli gap – hozirgi yoki kelajakdagi hayoliy / kam ehtimol holatlar.Formula: If + Past Simple, would + verb\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Условное предложение второго типа – нереальные или маловероятные ситуации сейчас или в будущем.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "If + Past Simple, Subject + would + verb\n"
            "Examples:\n"
            "If I won the lottery, I would travel the world.\n"
            "❌ Negative\n"
            "Formula:\n"
            "If + Past Simple negative, wouldn’t + verb\n"
            "Examples:\n"
            "If I didn’t have money, I wouldn’t buy a car.\n"
            "❓ Question\n"
            "Formula:\n"
            "What would you do if...?\n"
            "Examples:\n"
            "What would you do if you were rich?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. If gapda Past Simple (real emas!)\n"
            "🟢 2. Would – barcha shaxslar uchun bir xil\n"
            "🟢 3. Were – barcha shaxslar uchun (If I were you...)\n"
            "🟢 4. Unless = if not\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "f I were the president, I would help poor people.\n"
            "She would buy a house if she had enough money.\n"
            "If it didn’t rain, we would go to the park.\n"
            "What would you do if you saw a ghost?\n"
            "I wouldn’t tell anyone if I knew the secret.\n"
        ),
        questions=[
            _q('If I ___ the lottery, I ___ the world.', 'win / will travel', 'won / would travel', 'won / will travel', 'win / would travel', 'B'),
            _q('She ___ a car if she ___ money.', 'would buy / has', 'would buy / had', 'buys / had', 'would buy / has (alt 2)', 'B'),
            _q('If it ___ , we ___ to the beach.', 'doesn’t rain / would go', 'didn’t rain / would go', 'didn’t rain / will go', 'doesn’t rain / go', 'B'),
            _q('What ___ you do if you ___ rich?', 'will / were', 'would / were', 'would / was', 'will / was', 'B'),
            _q('I ___ anyone if I ___ the secret.', 'wouldn’t tell / know', 'wouldn’t tell / knew', 'won’t tell / knew', 'wouldn’t tell / know (alt 2)', 'B'),
            _q('If I ___ you, I ___ that job.', 'were / would take', 'was / would take', 'were / will take', 'am / would take', 'A'),
            _q('He ___ happier if he ___ more.', 'would be / exercised', 'would be / exercised (alt 2)', 'will be / exercises', 'would be / exercises', 'A'),
            _q('If she ___ English better, she ___ a better job.', 'spoke / would get', 'spoke / would get (alt 2)', 'speaks / would get', 'spoke / will get', 'A'),
            _q('What ___ happen if the world ___ ?', 'would / stopped', 'would / stopped (alt 2)', 'will / stops', 'would / stops', 'A'),
            _q('I ___ the party if I ___ time.', 'would come / had', 'will come / had', 'would come / have', 'come / had', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_third_conditional',
        level="B1",
        title='Third Conditional',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Uchinchi shartli gap – o‘tmishdagi hayoliy / amalga oshmagan holatlar.Formula: If + Past Perfect, would have + V3\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Условное предложение третьего типа – нереальные ситуации в прошлом.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "If + Past Perfect, Subject + would have + V3\n"
            "Examples:\n"
            "If I had studied, I would have passed the exam.\n"
            "❌ Negative\n"
            "Formula:\n"
            "If + Past Perfect negative, wouldn’t have + V3\n"
            "Examples:\n"
            "If she hadn’t been late, she wouldn’t have missed the train.\n"
            "❓ Question\n"
            "Formula:\n"
            "What would you have done if...?\n"
            "Examples:\n"
            "What would you have done if you had won?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. If gapda Past Perfect\n"
            "🟢 2. Would have – natija o‘tmishda\n"
            "🟢 3. Real holatda bo‘lmagan narsa haqida pushaymon\n"
            "🟢 4. Unless + Past Perfect ham ishlatiladi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "f I had known, I would have helped you.\n"
            "She wouldn’t have fallen if she had been careful.\n"
            "What would you have done if you had seen the accident?\n"
            "We would have won if we had played better.\n"
            "If he hadn’t missed the bus, he would have arrived on time.\n"
        ),
        questions=[
            _q('If I ___ , I ___ you.', 'had known / would have helped', 'knew / would help', 'had known / would help', 'know / will help', 'A'),
            _q('She ___ if she ___ careful.', 'wouldn’t fall / had been', 'wouldn’t have fallen / had been', 'wouldn’t have fallen / was', 'wouldn’t fall / was', 'B'),
            _q('What ___ you ___ if you ___ the lottery?', 'would / have done / had won', 'would / do / won', 'will / do / win', 'would / have done / won', 'A'),
            _q('We ___ if we ___ better.', 'would have won / had played', 'would win / played', 'will win / play', 'would have won / played', 'A'),
            _q('If he ___ the bus, he ___ on time.', 'hadn’t missed / would arrive', 'hadn’t missed / would have arrived', 'didn’t miss / would have arrived', 'hadn’t missed / will arrive', 'B'),
            _q('I ___ the job if I ___ the interview.', 'would have got / had passed', 'would get / passed', 'will get / pass', 'would have got / passed', 'A'),
            _q('They ___ happier if they ___ earlier.', 'would be / had left', 'would have been / had left', 'will be / leave', 'would have been / left', 'B'),
            _q('If you ___ me, I ___ the secret.', 'had told / wouldn’t have told', 'told / wouldn’t tell', 'had told / wouldn’t tell', 'tell / wouldn’t have told', 'A'),
            _q('What ___ happen if she ___ ?', 'would / have happened / had known', 'would / happen / knew', 'will / happen / knows', 'would / have happened / knew', 'A'),
            _q('He ___ the accident if he ___ faster.', 'wouldn’t have had / had driven', 'wouldn’t have / drove', 'won’t have / drives', 'wouldn’t have had / drove', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_mixed_conditionals',
        level="B1",
        title='Mixed Conditionals',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Aralash shartli gaplar – ikkinchi va uchinchi conditionalni birlashtirish.Type 2 + Type 3: If + Past Simple (hozirgi holat), would have + V3 (o‘tmish natija)Type 3 + Type 2: If + Past Perfect (o‘tmish), would + verb (hozirgi natija)\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Смешанные условные предложения – комбинация второго и третьего типа.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Type 2+3: If I were rich, I would have bought a house last year.Type 3+2: If I had studied, I would be a doctor now.\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "If I didn’t like coffee, I wouldn’t have drunk it yesterday.\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "What would you have done if you were me?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Type 2+3: hozirgi holat → o‘tmish natija\n"
            "🟢 2. Type 3+2: o‘tmish harakat → hozirgi natija\n"
            "🟢 3. Were – barcha shaxslar uchun (formal)\n"
            "🟢 4. Real hayotdagi pushaymonlik uchun ishlatiladi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "f I spoke English better, I would have got the job last month.\n"
            "If she had won the lottery, she would be happy now.\n"
            "If I hadn’t missed the bus, I would be at work now.\n"
            "What would you do if you had more time?\n"
            "If he were taller, he would have played basketball professionally.\n"
        ),
        questions=[
            _q('If I ___ English better, I ___ the job.', 'spoke / would get', 'spoke / would have got', 'had spoken / would get', 'speak / will get', 'B'),
            _q('If she ___ the lottery, she ___ happy now.', 'won / would be', 'had won / would be', 'wins / would be', 'had won / will be', 'B'),
            _q('If I ___ the bus, I ___ at work now.', 'hadn’t missed / would be', 'didn’t miss / would be', 'hadn’t missed / will be', 'don’t miss / would be', 'A'),
            _q('What ___ you ___ if you ___ more money?', 'would / have done / had', 'would / do / had', 'will / do / have', 'would / do / had (alt 2)', 'B'),
            _q('If he ___ taller, he ___ basketball.', 'were / would play', 'were / would have played', 'was / would play', 'had been / would play', 'A'),
            _q('If I ___ you, I ___ that mistake.', 'were / wouldn’t have made', 'was / wouldn’t make', 'had been / wouldn’t make', 'were / wouldn’t make', 'A'),
            _q('She ___ happier if she ___ harder last year.', 'would be / studied', 'would be / had studied', 'will be / had studied', 'would have been / studied', 'B'),
            _q('If we ___ earlier, we ___ the concert now.', 'had left / would enjoy', 'had left / would be enjoying', 'left / would enjoy', 'had left / will enjoy', 'B'),
            _q('What ___ happen if you ___ the exam?', 'would / have happened / had failed', 'would / happen / failed', 'will / happen / fail', 'would / have happened / failed', 'A'),
            _q('If she ___ the truth, she ___ worried now.', 'had known / wouldn’t be', 'knew / wouldn’t be', 'had known / wouldn’t have been', 'knows / wouldn’t be', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_wish_if_only',
        level="B1",
        title='Wish / If only',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Wish / If only – pushaymonlik, xohish yoki afsus bildiradi.Hozirgi uchun: wish + Past SimpleO‘tmish uchun: wish + Past PerfectKelajak uchun: wish + would/could\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Wish / If only – сожаление, желание или упрёк.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Wish + Past Simple: I wish I were rich.Wish + Past Perfect: I wish I had studied harder.If only + would: If only it would stop raining!\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "I wish I didn’t have to work.\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "What do you wish you could do?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. I wish I were (formal) / I wish I was (informal)\n"
            "🟢 2. If only – kuchliroq afsus\n"
            "🟢 3. Would – boshqa odamlarning xatti-harakatiga nisbatan\n"
            "🟢 4. Could – qobiliyat uchun\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "wish I spoke English fluently.\n"
            "She wishes she had bought the house last year.\n"
            "If only I had listened to my parents!\n"
            "I wish it would stop raining.\n"
            "He wishes he could play the guitar.\n"
        ),
        questions=[
            _q('I wish I ___ rich.', 'were', 'am', 'was', 'would be', 'A'),
            _q('She wishes she ___ harder last year.', 'studied', 'had studied', 'would study', 'studies', 'B'),
            _q('If only I ___ the truth!', 'knew', 'had known', 'know', 'would know', 'B'),
            _q('I wish it ___ raining.', 'would stop', 'stops', 'stopped', 'had stopped', 'A'),
            _q('He wishes he ___ play the piano.', 'could', 'can', 'would', 'had', 'A'),
            _q('I wish I ___ to work today.', 'didn’t have', 'don’t have', 'hadn’t had', 'wouldn’t have', 'A'),
            _q('If only you ___ me earlier!', 'told', 'had told', 'tell', 'would tell', 'B'),
            _q('She wishes she ___ taller.', 'were', 'is', 'was', 'would be', 'A'),
            _q('I wish you ___ smoking.', 'would stop', 'stop', 'stopped', 'had stopped', 'A'),
            _q('If only we ___ more time!', 'had', 'have', 'would have', 'had had', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_modals_deduction',
        level="B1",
        title='Modals of Deduction (must, might, can’t)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Deduksiya modallari – hozirgi holat haqida taxmin qilish.Must – 90-100% ishonch (albatta)Might / May / Could – 30-70% (ehtimol)Can’t – 100% inkor (mumkin emas)\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Модальные глаголы дедукции – предположения о настоящем.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Must: He must be tired.Might: She might be at home.\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Can’t: It can’t be true.\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Must he be...? / Can it be...?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Must – kuchli ishonch\n"
            "🟢 2. Can’t – kuchli inkor\n"
            "🟢 3. Might/Could – zaifroq taxmin\n"
            "🟢 4. Be + V-ing bilan ham ishlatiladi (must be working)\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "You must be hungry after the long trip.\n"
            "She can’t be at school – it’s Sunday.\n"
            "He might be stuck in traffic.\n"
            "That can’t be John – he’s in London.\n"
            "It must be raining – the streets are wet.\n"
        ),
        questions=[
            _q('He ___ be tired after the exam. (100%)', 'must', 'might', 'can’t', 'may', 'A'),
            _q('She ___ be at home – all lights are off. (100% yo‘q)', 'must', 'might', 'can’t', 'could', 'C'),
            _q('It ___ rain tomorrow. (ehtimol)', 'must', 'might', 'can’t', 'mustn’t', 'B'),
            _q('That ___ be true! It’s impossible.', 'must', 'might', 'can’t', 'may', 'C'),
            _q('They ___ be playing football now.', 'must', 'can’t', 'might', 'couldn’t', 'C'),
            _q('She ___ be the winner – she’s the best.', 'must', 'might', 'can’t', 'may', 'A'),
            _q('He ___ be sick – he looks healthy.', 'must', 'might', 'can’t', 'could', 'C'),
            _q('The phone ___ be broken.', 'might', 'must', 'can’t', 'mustn’t', 'A'),
            _q('It ___ be 5 o’clock already.', 'must', 'might', 'can’t', 'may', 'A'),
            _q('They ___ be at the cinema.', 'might', 'must', 'can’t', 'couldn’t', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_passive_voice',
        level="B1",
        title='Passive Voice (all tenses)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Passiv voz – harakat ob'ektga qaratilganida.Formula: be + V3 (zamonga qarab be o‘zgaradi)\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Пассивный залог – действие направлено на объект.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Present Simple: The book is read by students.Past Simple: The book was read yesterday.Present Perfect: The book has been read.\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "The book hasn’t been read yet.\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Has the book been read?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Agent (by + kim) – muhim bo‘lsa qo‘yiladi\n"
            "🟢 2. Barcha zamonlarda qo‘llaniladi\n"
            "🟢 3. Modallar: must be done, can be done\n"
            "🟢 4. Future: will be done\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "English is spoken all over the world.\n"
            "The car was repaired yesterday.\n"
            "The homework has been done.\n"
            "The meeting will be held next week.\n"
            "The cake must be eaten carefully.\n"
        ),
        questions=[
            _q('English ___ all over the world.', 'speaks', 'is spoken', 'spoke', 'has spoken', 'B'),
            _q('The car ___ yesterday.', 'repaired', 'was repaired', 'has repaired', 'repairs', 'B'),
            _q('The homework ___ yet.', 'hasn’t done', 'hasn’t been done', 'didn’t do', 'wasn’t done', 'B'),
            _q('The meeting ___ next week.', 'will hold', 'will be held', 'holds', 'is holding', 'B'),
            _q('The cake ___ by my mother.', 'was baked', 'baked', 'has baked', 'bakes', 'A'),
            _q('Books ___ in this library.', 'are kept', 'keep', 'kept', 'have kept', 'A'),
            _q('The letter ___ tomorrow.', 'will be sent', 'will send', 'sends', 'sent', 'A'),
            _q('The film ___ by millions.', 'has watched', 'has been watched', 'watched', 'watches', 'B'),
            _q('This house ___ in 1990.', 'was built', 'built', 'has built', 'builds', 'A'),
            _q('The problem ___ now.', 'is being solved', 'is solving', 'solves', 'solved', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_reported_speech_statements',
        level="B1",
        title='Reported Speech (statements & questions)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Indirect speech – gapni boshqa odamdan eshitganda o‘zgartirish.Backshift: Present → Past, will → would, now → then, this → that\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Косвенная речь – пересказ чужих слов с изменением времён.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "StatementsHe said (that) he was tired.\n"
            "QuestionsHe asked if I was tired. / He asked where I lived.\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "She said she didn’t like it.\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "—\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Say + that, Ask + if/whether (yes/no) yoki wh-word\n"
            "🟢 2. Backshift: am/is → was, do → did, will → would\n"
            "🟢 3. Time words: today → that day, tomorrow → the next day\n"
            "🟢 4. Universal truths da backshift bo‘lmaydi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "“I am tired,” he said. → He said he was tired.“Where do you live?” she asked. → She asked where I lived.“I will call you,” he said. → He said he would call me.“Do you like coffee?” → She asked if I liked coffee.“The earth is round,” he said. → He said the earth is round.\n"
        ),
        questions=[
            _q('“I am tired.” → He said he ___.', 'was tired', 'is tired', 'tired', 'has tired', 'A'),
            _q('“Where do you live?” → She asked where ___.', 'I live', 'I lived', 'do I live', 'did I live', 'B'),
            _q('“I will call you.” → He said he ___.', 'would call', 'will call', 'calls', 'called', 'A'),
            _q('“Do you like coffee?” → She asked if I ___.', 'like', 'liked', 'likes', 'had liked', 'B'),
            _q('“The earth is round.” → He said the earth ___.', 'was', 'is', 'has been', 'had been', 'B'),
            _q('“I am going home.” → She said she ___.', 'was going', 'is going', 'goes', 'went', 'A'),
            _q('“Have you finished?” → He asked if I ___.', 'finished', 'had finished', 'have finished', 'finish', 'B'),
            _q('“Don’t be late!” → He told me ___ late.', 'not to be (alt 2)', 'not to be', 'don’t be', 'to not be', 'B'),
            _q('“I can help you.” → She said she ___.', 'could help', 'can help', 'helps', 'helped', 'A'),
            _q('“What is your name?” → He asked what ___.', 'my name is', 'my name was', 'is my name', 'was my name', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_reported_speech_commands',
        level="B1",
        title='Reported Speech (commands, requests, suggestions)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Buyruq, iltimos va taklifni indirect speechda o‘zgartirish.Tell / order / ask + (not) to + infinitiveSuggest + gerund yoki that + should\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Косвенная речь для приказов, просьб и предложений.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Command: “Sit down!” → He told me to sit down.Request: “Please help me.” → She asked me to help her.Suggestion: “Let’s go.” → He suggested going / that we should go.\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "“Don’t touch it!” → He told me not to touch it.\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "He asked if I could help.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Tell / order / advise / warn + to + infinitive\n"
            "🟢 2. Ask / beg / request + to + infinitive\n"
            "🟢 3. Suggest + -ing yoki that + should\n"
            "🟢 4. Backshift qo‘llaniladi (present → past)\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "“Be quiet!” → The teacher told us to be quiet.“Please open the window.” → She asked me to open the window.“Let’s eat out.” → He suggested eating out.“Don’t be late!” → My mother warned me not to be late.“You should study more.” → She advised me to study more.\n"
        ),
        questions=[
            _q('“Sit down!” → He told me ___ down.', 'sit', 'to sit', 'sitting', 'sat', 'B'),
            _q('“Please help me.” → She asked me ___ her.', 'help', 'to help', 'helping', 'helped', 'B'),
            _q('“Let’s go to the cinema.” → He suggested ___.', 'to go', 'going', 'go', 'we go', 'B'),
            _q('“Don’t touch it!” → He told me ___ it.', 'not touch', 'not to touch', 'don’t touch', 'touching', 'B'),
            _q('“You should rest.” → She advised me ___.', 'rest', 'to rest', 'resting', 'rested', 'B'),
            _q('“Open the door, please.” → He asked me ___ the door.', 'open', 'to open', 'opening', 'opened', 'B'),
            _q('“Let’s not argue.” → She suggested ___.', 'not to argue', 'not arguing', 'don’t argue', 'not argue', 'B'),
            _q('“Be careful!” → The doctor warned me ___ careful.', 'be', 'to be', 'being', 'was', 'B'),
            _q('“Could you lend me money?” → He asked me ___ him money.', 'lend', 'to lend', 'lending', 'lent', 'B'),
            _q('“Why don’t we eat pizza?” → She suggested ___ pizza.', 'to eat', 'eating', 'eat', 'we eat', 'B'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_relative_clauses',
        level="B1",
        title='Relative Clauses (defining & non-defining)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Defining – muhim ma’lumot (who, which, that, where)Non-defining – qo‘shimcha ma’lumot (who, which, where) – vergul bilan ajratiladi\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Определяющие (defining) и неопределяющие (non-defining) придаточные.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "DefiningThe man who lives next door is my teacher.\n"
            "Non-definingMy brother, who lives in Tashkent, is a doctor.\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "The book which I read wasn’t interesting.\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "—\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Defining: that ishlatilishi mumkin, vergul yo‘q\n"
            "🟢 2. Non-defining: which/who, vergul majburiy, that ishlatilmaydi\n"
            "🟢 3. Object bo‘lsa who/which/that ni tashlab qoldirish mumkin (defining da)\n"
            "🟢 4. Where – joy, whose – egilik\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "The woman who won the prize is my aunt.\n"
            "(defining)My aunt, who won the prize, is a teacher.\n"
            "(non-defining)This is the house where I grew up.\n"
            "The film, which I saw yesterday, was boring.\n"
            "The boy whose father is a doctor is my friend.\n"
        ),
        questions=[
            _q('The man ___ lives next door is my teacher. (defining)', 'who', 'which', ', who', 'whose', 'A'),
            _q('My brother, ___ lives in London, is a doctor. (non-defining)', 'who', 'who (alt 2)', 'that', 'which', 'A'),
            _q('This is the book ___ I read yesterday.', 'which', ', which', 'who', 'whose', 'A'),
            _q('The city ___ I was born is Tashkent.', 'which', 'where', 'who', 'that', 'B'),
            _q('The film, ___ was very long, was boring.', 'which', 'which (alt 2)', 'that', 'who', 'A'),
            _q('The girl ___ bag is red is my sister.', 'who', 'which', 'whose', 'where', 'C'),
            _q('People ___ are kind help others.', 'who', ', who', 'which', 'whose', 'A'),
            _q('My phone, ___ I bought last week, is broken.', 'which', 'which (alt 2)', 'that', 'who', 'A'),
            _q('The restaurant ___ we ate was excellent.', 'where', 'which', 'who', 'that', 'A'),
            _q('The teacher ___ helped me is great. (defining)', 'who', ', who', 'which', 'whose', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_gerunds_infinitives',
        level="B1",
        title='Gerunds & Infinitives (verb patterns)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Gerund (-ing) yoki Infinitive (to + verb) – fe’llardan keyin keladigan shakl.Enjoy + gerund, want + infinitive, stop + gerund vs stop + infinitive (ma’no o‘zgaradi)\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Герундий и инфинитив – после определённых глаголов.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "GerundI enjoy reading books.\n"
            "InfinitiveI want to read a book.\n"
            "Both (ma’no farq)I stopped smoking. (to’xtatdim)I stopped to smoke. (to’xtab, sigaret chekdim)\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "—\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "—\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Gerund: enjoy, like, hate, finish, suggest, mind\n"
            "🟢 2. Infinitive: want, decide, hope, promise, learn\n"
            "🟢 3. Both: start, begin, continue (ma’no bir xil)\n"
            "🟢 4. Remember / forget / regret / stop / try – ma’no farq qiladi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "enjoy swimming in the sea.\n"
            "She decided to study abroad.\n"
            "I stopped to buy some milk.\n"
            "He forgot to lock the door.\n"
            "I regret telling her the secret.\n"
        ),
        questions=[
            _q('I enjoy ___ books.', 'to read', 'reading', 'read', 'reads', 'B'),
            _q('She wants ___ a doctor.', 'to become', 'becoming', 'become', 'becomes', 'A'),
            _q('He stopped ___ when he saw me.', 'to talk', 'to talk (alt 2)', 'talking', 'talk', 'C'),
            _q('I regret ___ you the truth.', 'to tell', 'telling', 'tell', 'told', 'B'),
            _q('We decided ___ early.', 'to leave', 'leaving', 'leave', 'left', 'A'),
            _q('Do you mind ___ the window?', 'to open', 'opening', 'open', 'opened', 'B'),
            _q('I forgot ___ the lights.', 'to turn off', 'turning off', 'turn off', 'turned off', 'A'),
            _q('She promised ___ me.', 'helping', 'to help', 'help', 'helped', 'B'),
            _q('I tried ___ the door, but it was locked.', 'to open', 'opening', 'open', 'opened', 'A'),
            _q('He suggested ___ to the cinema.', 'going', 'to go', 'go', 'went', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_used_to_be_get_used_to',
        level="B1",
        title='Used to / Be used to / Get used to',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Used to – o‘tmishdagi odat (endi yo‘q)Be used to – hozirgi ko‘nikkan holatGet used to – ko‘nikish jarayoni\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Used to – прошлая привычкаBe used to – привыкнуть (сейчас)Get used to – привыкать\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Used toI used to smoke.\n"
            "Be used toI am used to waking up early.\n"
            "Get used toI am getting used to the cold weather.\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "—\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "—\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Used to + infinitive (o‘tmish)\n"
            "🟢 2. Be / get used to + gerund yoki noun\n"
            "🟢 3. Negative: didn’t use to\n"
            "🟢 4. Question: Did you use to...?\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "used to live in a small village.\n"
            "I am used to driving on the right.\n"
            "She is getting used to living alone.\n"
            "He didn’t use to like coffee.\n"
            "Are you used to the new job yet?\n"
        ),
        questions=[
            _q('I ___ play football every day. (o‘tmish)', 'used to', 'am used to', 'get used to', 'use to', 'A'),
            _q('I ___ waking up at 5 am. (hozir)', 'used to', 'am used to', 'get used to', 'used', 'B'),
            _q('She ___ the cold weather. (jarayon)', 'used to', 'is used to', 'is getting used to', 'used', 'C'),
            _q('He ___ not ___ like tea.', 'didn’t / use to', 'isn’t / used to', 'doesn’t / get used to', 'didn’t / used to', 'A'),
            _q('Are you ___ the new school?', 'used to (alt 2)', 'used to', 'get used to', 'using to', 'B'),
            _q('We ___ live in Tashkent.', 'used to', 'are used to', 'get used to', 'using', 'A'),
            _q('I ___ speaking English every day.', 'am getting used to', 'am getting used to (alt 2)', 'used to', 'am used to', 'A'),
            _q('They ___ eat spicy food. (o‘tmish)', 'used to', 'are used to', 'get used to', 'didn’t used to', 'A'),
            _q('She ___ driving on the left now.', 'used to', 'is used to', 'get used to', 'used', 'B'),
            _q('Did you ___ have long hair?', 'use to', 'used to', 'be used to', 'get used to', 'B'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_advanced_phrasal_verbs',
        level="B1",
        title='Phrasal Verbs (more advanced)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Murakkab phrasal verbs – fe’l + zarf/predlog (ma’no butunlay o‘zgaradi).look forward to, put up with, get along with, break down, turn down\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Продвинутые фразовые глаголы.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "I look forward to seeing you.She put up with the noise.\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "I can’t put up with it anymore.\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "—\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Separable: turn down the music / turn the music down\n"
            "🟢 2. Inseparable: look forward to, get along with\n"
            "🟢 3. Common B1: break down, give up, take after, run out of, come across\n"
            "🟢 4. Contextdan ma’no aniqlanadi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "am looking forward to the holidays.\n"
            "My car broke down on the way to work.\n"
            "She takes after her mother.\n"
            "We ran out of milk.\n"
            "He turned down the job offer.\n"
        ),
        questions=[
            _q('I am looking forward ___ you.', 'to see', 'to seeing', 'see', 'seeing', 'B'),
            _q('My car ___ on the highway.', 'broke up', 'broke down', 'broke out', 'broke off', 'B'),
            _q('She ___ her mother.', 'takes after', 'takes after (alt 2)', 'takes up', 'takes off', 'A'),
            _q('We ___ milk. Can you buy some?', 'ran out of', 'ran out of (alt 2)', 'ran away', 'ran into', 'A'),
            _q('He ___ the job offer.', 'turned up', 'turned down', 'turned on', 'turned off', 'B'),
            _q('I can’t ___ this noise anymore.', 'put off', 'put up with', 'put away', 'put on', 'B'),
            _q('She ___ an old friend yesterday.', 'came across', 'came across (alt 2)', 'came up', 'came out', 'A'),
            _q('Don’t ___ now, you can do it!', 'give in', 'give up', 'give out', 'give away', 'B'),
            _q('The meeting ___ because of rain.', 'was called off', 'called off', 'called up', 'called in', 'A'),
            _q('I ___ with my new colleagues.', 'get along', 'get up', 'get out', 'get over', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_question_tags',
        level="B1",
        title='Question Tags',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Savol qo‘shimchalari – gap oxirida qo‘yiladi va tasdiqlash yoki rad etish uchun ishlatiladi.Positive gap + negative tag, negative gap + positive tag.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Вопросительные хвостики – добавляются в конец предложения для подтверждения.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "Positive statement + negative tag\n"
            "Examples:\n"
            "You are a student, aren’t you?\n"
            "❌ Negative\n"
            "Formula:\n"
            "Negative statement + positive tag\n"
            "Examples:\n"
            "You aren’t tired, are you?\n"
            "❓ Question\n"
            "Formula:\n"
            "Tag bilan savol\n"
            "Examples:\n"
            "It’s cold today, isn’t it?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Gapdagi fe’lga mos tag (am/is/are → aren’t you? / isn’t it?)\n"
            "🟢 2. “I am” uchun “aren’t I?”\n"
            "🟢 3. Imperative: “Let’s go, shall we?”\n"
            "🟢 4. “Have got” da “haven’t you?”\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "You like coffee, don’t you?\n"
            "She didn’t come, did she?\n"
            "Let’s eat out, shall we?\n"
            "I am right, aren’t I?\n"
            "They have finished, haven’t they?\n"
        ),
        questions=[
            _q('You are a teacher, ___?', 'aren’t you', 'aren’t you (alt 2)', 'don’t you', 'isn’t you', 'A'),
            _q('She doesn’t speak French, ___?', 'does she', 'does she (alt 2)', 'doesn’t she', 'is she', 'A'),
            _q('It’s raining, ___?', 'isn’t it', 'isn’t it (alt 2)', 'doesn’t it', 'is it', 'A'),
            _q('Let’s go home, ___?', 'shall we', 'shall we (alt 2)', 'will we', 'won’t we', 'A'),
            _q('You have seen this film, ___?', 'haven’t you', 'haven’t you (alt 2)', 'don’t you', 'have you', 'A'),
            _q('I am late, ___?', 'aren’t I', 'aren’t I (alt 2)', 'am I', 'isn’t I', 'A'),
            _q('They won’t come, ___?', 'will they', 'will they (alt 2)', 'won’t they', 'do they', 'A'),
            _q('He can swim, ___?', 'can’t he', 'can’t he (alt 2)', 'doesn’t he', 'can he', 'A'),
            _q('We should leave now, ___?', 'shouldn’t we', 'shouldn’t we (alt 2)', 'should we', 'don’t we', 'A'),
            _q('You didn’t call me, ___?', 'did you', 'did you (alt 2)', 'didn’t you', 'do you', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_so_such_too_enough',
        level="B1",
        title='So / Such / Too / Enough (advanced use)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "So + adjective/adverbSuch + (a/an) + adjective + nounToo + adjective (ortiqcha)Enough + adjective/noun (yetarli)\n"
            "\n"
            "🇷🇺 Русский:\n"
            "So / Such / Too / Enough – усиление и достаточность.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "So: It is so cold.Such: It is such a cold day.Enough: It is warm enough.\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Too: It is too cold to go out.\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "—\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. So + adj/adv (without noun)\n"
            "🟢 2. Such + a/an + adj + noun\n"
            "🟢 3. Too + adj + to + infinitive\n"
            "🟢 4. Adjective + enough / enough + noun\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "The film was so interesting that I watched it twice.\n"
            "It was such a beautiful day that we went for a picnic.\n"
            "She is too young to drive.\n"
            "We don’t have enough time to finish.\n"
            "The box is heavy enough to carry alone.\n"
        ),
        questions=[
            _q('The test was ___ difficult.', 'so', 'such', 'too', 'enough', 'A'),
            _q('It was ___ a difficult test.', 'so', 'such', 'too', 'enough', 'B'),
            _q('She is ___ young to vote.', 'too', 'so', 'such', 'enough', 'A'),
            _q('We have ___ money.', 'enough', 'too', 'so', 'such', 'A'),
            _q('The weather is ___ nice.', 'so', 'such', 'too', 'enough', 'A'),
            _q('It was ___ beautiful weather.', 'so', 'such', 'too', 'enough', 'B'),
            _q('The bag is ___ heavy for me.', 'too', 'so', 'such', 'enough', 'A'),
            _q('She speaks ___ quickly.', 'so', 'such', 'too', 'enough', 'A'),
            _q('Is the room ___ big?', 'enough', 'too', 'so', 'such', 'A'),
            _q('He is ___ tired to work.', 'too', 'so', 'such', 'enough', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_although_despite',
        level="B1",
        title='Although / Though / Even though / In spite of / Despite',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Qarama-qarshi bog‘lovchilar – “garchi ... bo‘lsa ham”.Although / Though / Even though + gapIn spite of / Despite + noun / gerund\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Союзы контраста – хотя / несмотря на.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Although: Although it rained, we went out.Despite: Despite the rain, we went out.\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Even though: Even though I studied, I failed.\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "—\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Although / Even though + to‘liq gap\n"
            "🟢 2. In spite of / Despite + noun / -ing\n"
            "🟢 3. Even though – kuchliroq qarama-qarshi\n"
            "🟢 4. Vergul gap boshida bo‘lsa qo‘yiladi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "Although it was cold, we went for a walk.\n"
            "Despite being tired, she finished the work.\n"
            "Even though he is rich, he is not happy.\n"
            "In spite of the traffic, we arrived on time.\n"
            "Though I tried hard, I didn’t win.\n"
        ),
        questions=[
            _q('___ it rained, we went out.', 'Although', 'Despite', 'In spite', 'Even', 'A'),
            _q('___ the rain, we went out.', 'Although', 'Despite', 'Even though', 'Though', 'B'),
            _q('___ he studied, he failed.', 'Even though', 'Despite', 'In spite', 'Although', 'A'),
            _q('___ being sick, he came to work.', 'Although', 'In spite of', 'Even though', 'Though', 'B'),
            _q('___ I like him, I don’t trust him.', 'Although', 'Despite', 'In spite', 'Though', 'A'),
            _q('___ the bad weather, the match continued.', 'Although', 'Despite', 'Even though', 'Though', 'B'),
            _q('___ she is young, she is very smart.', 'Though', 'Despite', 'In spite', 'Even', 'A'),
            _q('___ working hard, he didn’t get promoted.', 'Although', 'In spite of', 'Even though', 'Though', 'B'),
            _q('___ it was expensive, I bought it.', 'Even though', 'Despite', 'In spite', 'Although', 'A'),
            _q('___ the problem, we solved it.', 'Although', 'Despite', 'Even though', 'Though', 'B'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_clauses_of_purpose',
        level="B1",
        title='Clauses of Purpose (to, in order to, so that, so as to)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Maqsad bog‘lovchilari – “... uchun”.To / In order to + infinitiveSo that + gap (modal bilan)So as to + infinitive (formal)\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Придаточные цели – для того чтобы.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "To: I study to pass the exam.So that: I study so that I can pass the exam.\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "So as not to: I left early so as not to be late.\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "—\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. To / In order to – oddiy maqsad\n"
            "🟢 2. So that – modal (can, could, will) bilan\n"
            "🟢 3. So as to – formal, so as not to (inkor)\n"
            "🟢 4. In order not to – inkor uchun\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "went to the bank to withdraw money.\n"
            "She studies hard in order to get a good job.\n"
            "I took a taxi so that I wouldn’t be late.\n"
            "He spoke quietly so as not to wake the baby.\n"
            "We left early so as to avoid traffic.\n"
        ),
        questions=[
            _q('I study ___ pass the exam.', 'to', 'so that', 'in order', 'so as', 'A'),
            _q('She works hard ___ get promoted.', 'to', 'in order to', 'so that', 'so as', 'B'),
            _q('I called him ___ I could tell the news.', 'to', 'in order to', 'so that', 'so as', 'C'),
            _q('He spoke slowly ___ be understood.', 'to', 'so as to', 'so that', 'in order', 'B'),
            _q('We left early ___ miss the train.', 'so as not to', 'to not', 'in order not', 'so that not', 'A'),
            _q('She saved money ___ buy a car.', 'to', 'so that', 'in order', 'so as', 'A'),
            _q('I took notes ___ forget anything.', 'so as not to', 'to not', 'in order not', 'so that not', 'A'),
            _q('He studies English ___ work abroad.', 'to', 'in order to', 'so that', 'so as', 'B'),
            _q('Turn on the light ___ see better.', 'so that', 'to', 'in order to', 'so as', 'B'),
            _q('I bought a map ___ get lost.', 'so as not to', 'to not', 'in order not', 'so that not', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_causative_have_get',
        level="B1",
        title='Causative Have / Get (have something done)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Causative – o‘zing qilmay, boshqaga qildirish.Have + object + V3 (professional xizmat)Get + object + V3 (ko‘proq informal)\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Каузатив – заставить кого-то сделать что-то.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Have: I had my car repaired.Get: I got my hair cut.\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "I didn’t have my phone fixed.\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "—\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Have – professional (mechanic, doctor, hairdresser)\n"
            "🟢 2. Get – informal yoki o‘zing qilishga majbur qilish\n"
            "🟢 3. Past: had / got\n"
            "🟢 4. Future: will have / will get\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "have my hair cut every month.\n"
            "She got her car washed yesterday.\n"
            "We had the house painted last year.\n"
            "He is having his teeth checked today.\n"
            "I need to get my passport renewed.\n"
        ),
        questions=[
            _q('I ___ my car repaired last week.', 'had', 'get', 'got', 'have', 'A'),
            _q('She ___ her hair cut yesterday.', 'had', 'got', 'have', 'gets', 'B'),
            _q('We ___ the house painted next month.', 'will have', 'will get', 'have', 'get', 'A'),
            _q('He is ___ his teeth checked.', 'having', 'getting', 'had', 'got', 'A'),
            _q('I need to ___ my passport renewed.', 'had', 'get', 'have', 'getting', 'B'),
            _q('They ___ the windows cleaned.', 'had', 'get', 'got', 'have', 'A'),
            _q('She ___ her phone fixed.', 'had', 'got', 'have', 'getting', 'B'),
            _q('I ___ my suit ironed for the meeting.', 'had', 'get', 'got', 'have', 'A'),
            _q('We will ___ the garden redesigned.', 'have', 'get', 'had', 'getting', 'A'),
            _q('He ___ his bike repaired.', 'had', 'got', 'have', 'getting', 'B'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_clauses_of_contrast',
        level="B1",
        title='Clauses of Contrast (however, nevertheless, whereas, on the other hand)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Qarama-qarshi bog‘lovchilar – ikkita fikrni solishtirish yoki qarama-qarshi qilish uchun.However / Nevertheless – gap boshida yoki o‘rtada (vergul bilan)Whereas / On the other hand – ikki narsani solishtirish\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Союзы контраста – для противопоставления двух идей.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "However: It was raining.\n"
            "However, we went out.Whereas: I like tea, whereas my sister likes coffee.\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "Nevertheless: He was tired.\n"
            "Nevertheless, he finished the work.\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "—\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. However / Nevertheless – vergul bilan ajratiladi\n"
            "🟢 2. Whereas – ikki gapni solishtirish uchun\n"
            "🟢 3. On the other hand – ikkinchi fikrni kiritish\n"
            "🟢 4. Gap boshida bo‘lsa katta harf bilan boshlanadi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "The weather was bad.\n"
            "However, we enjoyed the trip.\n"
            "I love summer, whereas my brother prefers winter.\n"
            "He studied hard.\n"
            "Nevertheless, he failed the exam.\n"
            "She is very shy.\n"
            "On the other hand, her sister is outgoing.\n"
            "The book is interesting.\n"
            "However, it is too long.\n"
        ),
        questions=[
            _q('It was expensive. ___, I bought it.', 'However', 'Whereas', 'On the other', 'Nevertheless', 'A'),
            _q('I like dogs, ___ my sister likes cats.', 'however', 'whereas', 'nevertheless', 'on the other hand', 'B'),
            _q('He was ill. ___, he went to work.', 'Whereas', 'Nevertheless', 'On the other', 'However', 'B'),
            _q('She is rich. ___, she is not happy.', 'On the other hand', 'Whereas', 'However', 'Nevertheless', 'A'),
            _q('The test was hard. ___, everyone passed.', 'However', 'Whereas', 'On the other', 'Nevertheless', 'A'),
            _q('I am tall, ___ my brother is short.', 'however', 'whereas', 'nevertheless', 'on the other hand', 'B'),
            _q('It rained all day. ___, the match continued.', 'Whereas', 'Nevertheless', 'On the other', 'However', 'B'),
            _q('He works hard. ___, he earns little.', 'On the other hand', 'Whereas', 'However', 'Nevertheless', 'A'),
            _q('The film was long. ___, it was boring.', 'However', 'Whereas', 'On the other', 'Nevertheless', 'A'),
            _q('Summer is hot, ___ winter is cold.', 'however', 'whereas', 'nevertheless', 'on the other hand', 'B'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_inversion_negative_adverbials',
        level="B1",
        title='Inversion (with negative adverbials)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Inversion – gap boshida salbiy so‘z bo‘lsa yordamchi fe’l oldinga chiqadi.Never, Rarely, Seldom, Only when, No sooner...than, Hardly...when\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Инверсия – при отрицательных наречиях вспомогательный глагол выходит вперёд.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "Negative adverbial + auxiliary + subject + verb\n"
            "Examples:\n"
            "Never have I seen such a beautiful place.\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "No sooner had I arrived than it started raining.\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "—\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Never / Rarely / Seldom + have/has/had\n"
            "🟢 2. Only when / Only after + auxiliary\n"
            "🟢 3. No sooner...than / Hardly...when\n"
            "🟢 4. Formal va dramatik uslubda ishlatiladi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "Never have I felt so happy.\n"
            "Only when I arrived did I realise the mistake.\n"
            "No sooner had she left than the phone rang.\n"
            "Rarely do we see such talent.\n"
            "Hardly had I sat down when the bell rang.\n"
        ),
        questions=[
            _q('___ have I seen such a beautiful view.', 'Never', 'Only', 'No sooner', 'Hardly', 'A'),
            _q('Only when the teacher came ___ the students quiet.', 'did', 'do', 'does', 'had', 'A'),
            _q('No sooner ___ I arrived ___ it started to rain.', 'had / than', 'have / than', 'did / when', 'had / when', 'A'),
            _q('___ do we eat fast food.', 'Rarely', 'Never', 'Only', 'Hardly', 'A'),
            _q('Hardly ___ she finished speaking ___ the audience clapped.', 'had / when', 'have / than', 'did / when', 'had / than', 'A'),
            _q('Only after the exam ___ I relax.', 'did', 'do', 'does', 'had', 'A'),
            _q('___ had I left the house ___ I remembered my keys.', 'No sooner / than', 'Never / when', 'Hardly / than', 'Only / when', 'A'),
            _q('Seldom ___ she complain about her work.', 'does', 'do', 'did', 'has', 'A'),
            _q('Never before ___ such a big crowd.', 'have I seen', 'I have seen', 'did I see', 'I saw', 'A'),
            _q('Only when it is quiet ___ I study well.', 'can', 'do', 'does', 'will', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b1_advanced_articles_determiners',
        level="B1",
        title='Advanced Articles & Determiners (the, zero article, a/an rules)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Advanced artikllar – qachon “the”, qachon “a/an” yoki hech qanday artikl ishlatilmaydi.The – ma’lum narsa, unique narsalar, musiqa asarlariZero article – umumiy ma’no, kasblar, sport, ovqatlar\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Продвинутые правила артиклей – когда использовать the, a/an или нулевой артикль.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "The: The sun rises in the east.Zero: I love playing tennis. / She is a doctor.\n"
            "❌ Negative\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "A: I have a car. (bitta narsa)\n"
            "❓ Question\n"
            "Formula:\n"
            "—\n"
            "Examples:\n"
            "—\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. The – unique (the sun, the president), superlative, rivers, oceans\n"
            "🟢 2. Zero – kasblar (She is doctor), sport (play football), meals (have breakfast)\n"
            "🟢 3. A/An – birinchi marta tilga olinganda\n"
            "🟢 4. The with musical instruments (play the piano)\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "The Pacific Ocean is the largest ocean.\n"
            "She plays the guitar very well.\n"
            "I have breakfast at 7 o’clock.\n"
            "The more you study, the better you get.\n"
            "Mount Everest is the highest mountain.\n"
        ),
        questions=[
            _q('___ sun is very hot today.', 'The', 'A', 'An', '–', 'A'),
            _q('She is ___ doctor.', 'the', 'a', '–', 'an', 'C'),
            _q('I play ___ piano every evening.', 'the', 'a', 'an', '–', 'A'),
            _q('___ Mount Everest is the highest mountain.', 'The', 'A', '–', 'An', 'C'),
            _q('We have ___ dinner at 8.', 'the', 'a', '–', 'an', 'C'),
            _q('___ more you practise, ___ better you become.', 'The / the', 'The / the (alt 2)', 'A / a', '– / –', 'A'),
            _q('___ Pacific Ocean is very deep.', 'The', 'A', 'An', '–', 'A'),
            _q('He is ___ best player in the team.', 'the', 'a', 'an', '–', 'A'),
            _q('I love ___ tennis.', 'the', 'a', '–', 'an', 'C'),
            _q('___ Nile is the longest river in the world.', 'The', 'A', 'An', '–', 'A'),
        ],
    ),
]
# ========= B2 =========

B2_TOPICS: List[GrammarTopic] = [
    GrammarTopic(
        topic_id='b2_01_past_perfect_continuous_had_been_verb_ing',
        level="B2",
        title='Past Perfect Continuous (had been + verb-ing)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "O‘tmishda davom etgan va keyingi o‘tmish harakati bilan bog‘liq bo‘lgan harakat.\n"
            "Natija (charchagan ko‘rinish, ho‘l kiyim) ko‘rinib turadi.\n"
            "Formula: Subject + had been + V-ing\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Прошедшее совершенное длительное время – действие в прошлом, которое продолжалось до другого момента в прошлом (с видимым результатом).\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "Subject + had been + verb-ing\n"
            "Examples:\n"
            "I had been working for 10 hours when you called.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "Subject + hadn’t been + verb-ing\n"
            "Examples:\n"
            "She hadn’t been sleeping well.\n"
            "\n"
            "❓ Question\n"
            "Formula:\n"
            "Had + subject + been + verb-ing?\n"
            "Examples:\n"
            "How long had you been waiting?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. For / since bilan (for 3 hours, since morning)\n"
            "🟢 2. Natija ko‘rinib tursa ishlatiladi (wet clothes → had been raining)\n"
            "🟢 3. Stative verbs bilan kam (know, like)\n"
            "🟢 4. “How long...?” savollarida eng yaxshi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "She was tired because she had been studying all night.\n"
            "How long had you been living in Tashkent before you moved?\n"
            "It had been raining for hours, so the streets were flooded.\n"
            "He hadn’t been feeling well for weeks.\n"
            "We had been waiting for two hours when the train finally arrived."
        ),
        questions=[
            _q('I ___ for three hours when the phone rang.', 'had worked', 'had been working', 'worked', 'was working', 'A'),
            _q('She was wet because it ___ .', 'had rained', 'had been raining', 'rained', 'was raining', 'A'),
            _q('How long ___ you ___ English before you came here?', 'had / learned', 'had / been learning', 'have / been learning', 'did / learn', 'A'),
            _q('They ___ TV for hours before the power went out.', 'had watched', 'had been watching', 'watched', 'were watching', 'A'),
            _q('He looked exhausted. He ___ all day.', 'had run', 'had been running', 'ran', 'was running', 'A'),
            _q('We ___ not ___ well for weeks.', 'had / been sleeping', 'had / slept', 'were / sleeping', 'have / been sleeping', 'A'),
            _q('___ they ___ long when the bus came?', 'Had / waited', 'Had / been waiting', 'Were / waiting', 'Have / been waiting', 'A'),
            _q('The ground was wet. It ___ .', 'had rained', 'had been raining', 'rained', 'was raining', 'A'),
            _q('I ___ the car for two hours before I found it.', 'had searched', 'had been searching', 'searched', 'was searching', 'A'),
            _q('How long ___ she ___ before the accident?', 'had / driven', 'had / been driving', 'has / been driving', 'was / driving', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_02_future_perfect_continuous_will_have_been_verb_ing',
        level="B2",
        title='Future Perfect Continuous (will have been + verb-ing)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Kelajakda bir vaqtga qadar davom etgan va natijasi bo‘ladigan harakat.\n"
            "Formula: Subject + will have been + V-ing\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Будущее совершенное длительное время – действие, которое будет продолжаться до определённого момента в будущем.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "Subject + will have been + verb-ing\n"
            "Examples:\n"
            "By 2028 I will have been living here for 10 years.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "Subject + won’t have been + verb-ing\n"
            "Examples:\n"
            "She won’t have been working long enough.\n"
            "\n"
            "❓ Question\n"
            "Formula:\n"
            "Will + subject + have been + verb-ing?\n"
            "Examples:\n"
            "How long will you have been studying by then?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. By + future time (by 2030, by the time)\n"
            "🟢 2. Duration (for 5 years) bilan\n"
            "🟢 3. Natija yoki tajriba uchun\n"
            "🟢 4. Stative verbs bilan kam ishlatiladi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "By next June I will have been teaching English for 8 years.\n"
            "How long will you have been waiting when the plane lands?\n"
            "She will have been working here for 20 years by retirement.\n"
            "We won’t have been living in this city very long.\n"
            "In 2030 they will have been married for 25 years."
        ),
        questions=[
            _q('By 2030 I ___ English for 15 years.', 'will have been teaching', 'will teach', 'will have taught', 'will be teaching', 'A'),
            _q('How long ___ you ___ when the film starts?', 'will / have been waiting', 'will / wait', 'will / have waited', 'will / be waiting', 'A'),
            _q('She ___ here for 10 years by next month.', 'will have been living', 'will live', 'will have lived', 'will be living', 'A'),
            _q('They ___ not ___ long enough to get a promotion.', 'will / have been working', 'will / work', 'will / have worked', 'will / be working', 'A'),
            _q('In 2027 we ___ married for 20 years.', 'will have been', 'will be', 'will have', 'will', 'A'),
            _q('___ you ___ the project by Friday?', 'Will / have been finishing', 'Will / finish', 'Will / have finished', 'Will / be finishing', 'A'),
            _q('By the time you arrive, I ___ for hours.', 'will have been waiting', 'will wait', 'will have waited', 'will be waiting', 'A'),
            _q('She ___ not ___ enough by the exam.', 'will / have been studying', 'will / study', 'will / have studied', 'will / be studying', 'A'),
            _q('How long ___ they ___ in Tashkent by 2030?', 'will / have been living', 'will / live', 'will / have lived', 'will / be living', 'A'),
            _q('We ___ the company for 5 years by then.', 'will have been running', 'will run', 'will have run', 'will be running', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_03_modals_in_the_past_must_have_could_have_might_have',
        level="B2",
        title='Modals in the Past (must have, could have, might have, can’t have)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "O‘tmishdagi taxminlar va deduksiya.\n"
            "Must have – 90-100% ishonchMight/Could have – ehtimolCan’t have – 100% inkor\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Модальные глаголы в прошедшем времени – предположения о прошлом.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Must have: He must have forgotten.\n"
            "Might have: She might have missed the bus.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Can’t have: It can’t have been easy.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Modal + have + V3\n"
            "🟢 2. Must have – kuchli ishonch\n"
            "🟢 3. Can’t have – kuchli inkor\n"
            "🟢 4. Could have – imkoniyat bo‘lgan, lekin ishlatilmagan\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "You must have been very tired after the flight.\n"
            "She can’t have seen me – she didn’t wave.\n"
            "He might have left his phone at home.\n"
            "They could have won if they had played better.\n"
            "It must have rained heavily last night."
        ),
        questions=[
            _q('He ___ the meeting – he looks relaxed.', 'must have forgotten', 'might forget', 'can’t have forgotten', 'could forget', 'A'),
            _q('She ___ the bus – she’s never late.', 'can’t have missed', 'must have missed', 'might miss', 'could miss', 'A'),
            _q('You ___ very hungry – you ate everything.', 'must have been', 'might be', 'can’t have been', 'could be', 'A'),
            _q('They ___ the news already.', 'might have heard', 'must hear', 'can’t hear', 'could hear', 'A'),
            _q('It ___ easy to pass the exam.', 'can’t have been', 'must have been', 'might be', 'could be', 'A'),
            _q('He ___ the keys in the car.', 'could have left', 'must leave', 'can’t leave', 'might leave', 'A'),
            _q('She ___ all night – her eyes are red.', 'must have cried', 'might cry', 'can’t cry', 'could cry', 'A'),
            _q('We ___ the wrong train.', 'might have taken', 'must take', 'can’t take', 'could take', 'A'),
            _q('You ___ very cold without a coat.', 'must have been', 'might be', 'can’t have been', 'could be', 'A'),
            _q('It ___ a difficult decision.', 'must have been', 'might be', 'can’t have been', 'could be', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_04_inversion_advanced_structures',
        level="B2",
        title='Inversion (advanced structures)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Inversion – salbiy yoki shartli so‘z gap boshida bo‘lsa yordamchi fe’l oldinga chiqadi.\n"
            "Never, Only, No sooner, Not only, So + adj, Had I known, Were I...\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Инверсия в продвинутых структурах.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Never have I seen...\n"
            "Only when... did I realise...\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Not only is she beautiful, but she is also clever.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Never / Rarely / Seldom + auxiliary + subject\n"
            "🟢 2. No sooner...than / Hardly...when\n"
            "🟢 3. So + adj + auxiliary + subject\n"
            "🟢 4. Conditionalsda: Had I known, Were I rich...\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "Never have I felt so embarrassed.\n"
            "No sooner had I arrived than the phone rang.\n"
            "So tired was I that I fell asleep immediately.\n"
            "Had I known the truth, I would have helped you.\n"
            "Not only did she win, but she also broke the record."
        ),
        questions=[
            _q('___ have I seen such beauty.', 'Never', 'Only', 'So', 'Had', 'A'),
            _q('No sooner ___ I left ___ it started raining.', 'had / than', 'have / than', 'did / when', 'had / when', 'A'),
            _q('So beautiful ___ the view that I took a photo.', 'was', 'is', 'were', 'be', 'A'),
            _q('___ I known, I would have called you.', 'Had', 'Have', 'If', 'Were', 'A'),
            _q('Not only ___ she beautiful, but she is also intelligent.', 'is', 'was', 'be', 'does', 'A'),
            _q('Rarely ___ we see such talent.', 'do', 'does', 'did', 'have', 'A'),
            _q('Hardly ___ she finished speaking ___ everyone clapped.', 'had / when', 'have / than', 'did / when', 'had / than', 'A'),
            _q('Only after the exam ___ I relax.', 'did', 'do', 'does', 'had', 'A'),
            _q('Were I ___ , I would travel the world.', 'rich', 'richer', 'richest', 'the rich', 'A'),
            _q('So angry ___ he that he shouted at everyone.', 'was', 'is', 'were', 'be', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_05_subjunctive_mood_i_wish_if_only_it_s_time_as_if',
        level="B2",
        title='Subjunctive Mood (I wish, If only, It’s time, as if)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Subjunctive – hayoliy, tavsiya, talab holatlari.\n"
            "I wish / If only + Past Simple (hozir) yoki Past Perfect (o‘tmish)It’s time + subject + Past SimpleAs if / As though + Past Simple / Past Perfect\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Сослагательное наклонение – для нереальных желаний и рекомендаций.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "I wish I were rich.\n"
            "It’s time you went to bed.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "If only I hadn’t said that.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Were – barcha shaxslar uchun (formal)\n"
            "🟢 2. It’s (high) time + Past Simple (tavsiya)\n"
            "🟢 3. As if / As though – Past Perfect (o‘tmish kabi)\n"
            "🟢 4. Suggest / Demand / Insist + that + base verb (American English)\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "I wish I could speak French fluently.\n"
            "If only I had studied harder!\n"
            "It’s time we left.\n"
            "She looks as if she had seen a ghost.\n"
            "I suggest that he see a doctor."
        ),
        questions=[
            _q('I wish I ___ rich.', 'were', 'am', 'was', 'would be', 'A'),
            _q('If only I ___ the exam!', 'had passed', 'passed', 'pass', 'would pass', 'A'),
            _q('It’s time you ___ to bed.', 'went', 'go', 'goes', 'going', 'A'),
            _q('She speaks as if she ___ a native speaker.', 'were', 'is', 'was', 'would be', 'A'),
            _q('I suggest that he ___ a doctor.', 'see', 'sees', 'saw', 'to see', 'A'),
            _q('If only it ___ raining!', 'would stop', 'stops', 'stopped', 'had stopped', 'A'),
            _q('It’s high time we ___ this problem.', 'solved', 'solve', 'solving', 'to solve', 'A'),
            _q('He looks as though he ___ all night.', 'hadn’t slept', 'hasn’t slept', 'didn’t sleep', 'not sleep', 'A'),
            _q('I wish you ___ smoking.', 'would stop', 'stop', 'stopped', 'had stopped', 'A'),
            _q('She insisted that I ___ the truth.', 'tell', 'tells', 'told', 'to tell', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_06_advanced_passive_voice_modals_gerunds_infinitives',
        level="B2",
        title='Advanced Passive Voice (modals, gerunds, infinitives)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Passivning murakkab shakllari – modal fe’llar, gerund va infinitive bilan.\n"
            "Formula: modal + be + V3 / having been + V3 / to be + V3\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Продвинутый пассивный залог – с модальными глаголами, герундием и инфинитивом.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "The report must be finished by Friday.\n"
            "I hate being told what to do.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "The car can’t have been repaired yet.\n"
            "\n"
            "❓ Question\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Has the house been painted?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Modal + be + V3 (must be done, should have been done)\n"
            "🟢 2. Gerund: being + V3 (hate being asked)\n"
            "🟢 3. Infinitive: to be + V3 (want to be promoted)\n"
            "🟢 4. Perfect: having been + V3 (after having been warned)\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "The meeting should have been cancelled.\n"
            "I remember being taken to the zoo as a child.\n"
            "The building is going to be demolished next year.\n"
            "She hates being interrupted.\n"
            "The thief is believed to have been caught."
        ),
        questions=[
            _q('The report ___ by Friday.', 'must be finished', 'must finish', 'must have finished', 'must be finishing', 'A'),
            _q('I hate ___ what to do.', 'being told', 'to tell', 'telling', 'told', 'A'),
            _q('The car ___ yet.', 'can’t have been repaired', 'can’t repair', 'can’t be repaired', 'can’t have repaired', 'A'),
            _q('The house is going ___ next year.', 'to be demolished', 'to demolish', 'demolishing', 'demolished', 'A'),
            _q('She wants ___ a manager.', 'to be promoted', 'promoting', 'promote', 'promoted', 'A'),
            _q('After ___ , he felt better.', 'having been warned', 'to be warned', 'warning', 'warned', 'A'),
            _q('The film is expected ___ soon.', 'to be released', 'releasing', 'release', 'released', 'A'),
            _q('I don’t like ___ in public.', 'being criticised', 'to criticise', 'criticising', 'criticised', 'A'),
            _q('The thief ___ by the police.', 'is believed to have been caught', 'is believed catching', 'believed caught', 'is believed to catch', 'A'),
            _q('The work ___ before the deadline.', 'should have been completed', 'should complete', 'should have completed', 'should be completing', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_07_reported_speech_advanced_hypothetical_suggestions',
        level="B2",
        title='Reported Speech (advanced: hypothetical & suggestions)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Indirect speechning murakkab shakllari – hypothetical (would), suggestions (should), commands (to + infinitive).\n"
            "Backshift + modal o‘zgarishi.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Продвинутая косвенная речь – гипотетические ситуации и предложения.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "“If I were you, I would apologise,” he said. → He said that if he were me, he would apologise.\n"
            "“Let’s go,” she suggested. → She suggested going / that we should go.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "“Don’t be late,” he warned. → He warned me not to be late.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Hypothetical: would / could / might o‘zgarmaydi\n"
            "🟢 2. Suggest + -ing yoki that + should\n"
            "🟢 3. Insist / demand + that + base verb (AmE) yoki should\n"
            "🟢 4. Time words: tomorrow → the next day\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "“If I won the lottery, I would travel,” he said. → He said that if he won the lottery, he would travel.\n"
            "“You should see a doctor,” she advised. → She advised me to see a doctor.\n"
            "“Let’s meet at 8,” he suggested. → He suggested meeting at 8.\n"
            "“Don’t forget your keys,” she reminded. → She reminded me not to forget my keys.\n"
            "“I wish I had studied,” he said. → He said he wished he had studied."
        ),
        questions=[
            _q('“If I were rich, I would buy a house.” → He said if he ___ rich, he ___ a house.', 'were / would buy', 'was / will buy', 'had been / would buy', 'is / would buy', 'A'),
            _q('“You should rest.” → She advised me ___ .', 'to rest', 'rest', 'resting', 'should rest', 'A'),
            _q('“Let’s eat out.” → He suggested ___ .', 'eating out', 'to eat out', 'we eat out', 'eat out', 'A'),
            _q('“Don’t be late!” → He warned me ___ late.', 'not to be', 'don’t be', 'not be', 'to not be', 'A'),
            _q('“I wish I had studied.” → He said he wished he ___ .', 'had studied', 'studied', 'would study', 'studies', 'A'),
            _q('“You must finish the report.” → She insisted that I ___ the report.', 'finish', 'finished', 'to finish', 'should finish', 'A'),
            _q('“If only I had known!” → She said if only she ___ .', 'had known', 'knew', 'would know', 'knows', 'A'),
            _q('“Why don’t we go to the cinema?” → He suggested ___ to the cinema.', 'going', 'to go', 'we go', 'go', 'A'),
            _q('“You could have told me.” → He said I ___ him.', 'could have told', 'could tell', 'had told', 'told', 'A'),
            _q('“I would apologise if I were you.” → He said he would apologise if he ___ me.', 'were', 'was', 'is', 'had been', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_08_relative_clauses_non_defining_prepositions',
        level="B2",
        title='Relative Clauses (non-defining + prepositions)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Non-defining relative clauses – qo‘shimcha ma’lumot (vergul bilan).\n"
            "Preposition + which/whom (formal).\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Непределяющие придаточные + предлоги.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "My brother, who lives in London, is a doctor.\n"
            "The house in which I grew up is for sale.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "The film, which I didn’t like, was very long.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Non-defining: vergul majburiy, that ishlatilmaydi\n"
            "🟢 2. Preposition + which/whom (formal)\n"
            "🟢 3. Whose – egilik uchun\n"
            "🟢 4. Where / when – joy va vaqt uchun\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "Tashkent, which is the capital of Uzbekistan, is a big city.\n"
            "The man with whom I spoke is my teacher.\n"
            "My sister, whose husband is a pilot, lives in Samarkand.\n"
            "The book, which I read last week, was amazing.\n"
            "The hotel where we stayed was excellent."
        ),
        questions=[
            _q('My brother, ___ lives in London, is a doctor.', 'who', 'which', 'that', 'whose', 'A'),
            _q('The house ___ I grew up is for sale.', 'in which', 'which in', 'where', 'that', 'A'),
            _q('Tashkent, ___ is the capital, is very old.', 'which', 'who', 'that', 'whose', 'A'),
            _q('The man ___ I spoke is my boss.', 'with whom', 'whom with', 'who', 'whose', 'A'),
            _q('My sister, ___ husband is a pilot, lives abroad.', 'whose', 'who', 'which', 'that', 'A'),
            _q('The film, ___ I didn’t like, was too long.', 'which', 'who', 'that', 'whose', 'A'),
            _q('The hotel ___ we stayed was excellent.', 'where', 'which', 'that', 'in which', 'A'),
            _q('The teacher, ___ we all respect, is retiring.', 'whom', 'who', 'which', 'whose', 'A'),
            _q('The day ___ I met her was the best day of my life.', 'when', 'which', 'that', 'where', 'A'),
            _q('This is the reason ___ I left.', 'for which', 'which for', 'why', 'that', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_09_gerunds_infinitives_advanced_patterns_meaning_chan',
        level="B2",
        title='Gerunds & Infinitives (advanced patterns + meaning change)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Murakkab verb patterns – gerund va infinitive ma’no farqi bilan.\n"
            "Remember / forget / stop / try / regret / mean – ma’no o‘zgaradi.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Продвинутые конструкции герундия и инфинитива с изменением смысла.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "I remember locking the door.\n"
            "(eslayman)I remember to lock the door.\n"
            "(eslataman)\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "I stopped to smoke.\n"
            "(to‘xtab chekdim)\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Remember + gerund = o‘tmishdagi harakatni eslash\n"
            "🟢 2. Remember + infinitive = kelajakdagi vazifani eslatish\n"
            "🟢 3. Stop + gerund = to‘xtatish\n"
            "🟢 4. Stop + infinitive = to‘xtab boshqa ish qilish\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "I regret telling her the secret.\n"
            "(pushaymonman)I regret to tell you that...\n"
            "(rasmiy xabar)She tried to open the door.\n"
            "(urinib ko‘rdi)She tried opening the window.\n"
            "(tajriba qildi)I mean to finish this today.\n"
            "(niyat)"
        ),
        questions=[
            _q('I remember ___ the door last night.', 'locking', 'to lock', 'lock', 'locked', 'A'),
            _q('Remember ___ the lights before you leave.', 'to turn off', 'turning off', 'turn off', 'turned off', 'A'),
            _q('I stopped ___ when I saw the doctor.', 'smoking', 'to smoke', 'smoke', 'smoked', 'A'),
            _q('She stopped ___ a cigarette.', 'to smoke', 'smoking', 'smoke', 'smoked', 'A'),
            _q('I regret ___ you the bad news.', 'to tell', 'telling', 'tell', 'told', 'A'),
            _q('I tried ___ the door, but it was locked.', 'to open', 'opening', 'open', 'opened', 'A'),
            _q('Try ___ the window – it might be cooler.', 'opening', 'to open', 'open', 'opened', 'A'),
            _q('I mean ___ this report today.', 'to finish', 'finishing', 'finish', 'finished', 'A'),
            _q('She forgot ___ me the money.', 'to give', 'giving', 'give', 'gave', 'A'),
            _q('I’ll never forget ___ the President.', 'meeting', 'to meet', 'meet', 'met', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_10_cleft_sentences_it_is_that_what',
        level="B2",
        title='Cleft Sentences (It is ... that / What ...)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Cleft sentences – ma’lumotni ta’kidlab ko‘rsatish uchun.\n"
            "It is/was + ta’kidlanayotgan qism + that/whoWhat ... is/was ...\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Расщеплённые предложения – для выделения информации.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "It was John who broke the window.\n"
            "What I need is a good rest.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "It isn’t money that makes you happy.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. It is/was ... that/who (odam uchun who)\n"
            "🟢 2. What ... is/was ... (nima kerakligini ta’kidlash)\n"
            "🟢 3. All / The only thing ... is ...\n"
            "🟢 4. Ta’kid uchun ishlatiladi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "It was my sister who helped me.\n"
            "What I want is to travel the world.\n"
            "It isn’t the money that matters.\n"
            "The only thing I remember is his smile.\n"
            "What surprised me was her reaction."
        ),
        questions=[
            _q('___ John who broke the window.', 'It was', 'It is', 'Was it', 'Is it', 'A'),
            _q('___ I need is a good rest.', 'What', 'It is', 'That', 'Which', 'A'),
            _q('___ my sister who helped me.', 'It was', 'It is', 'Was it', 'Who', 'A'),
            _q('___ surprised me was her reaction.', 'What', 'It was', 'That', 'Which', 'A'),
            _q('It isn’t ___ that makes you happy.', 'money', 'the money', 'that money', 'a money', 'A'),
            _q('The only thing I remember ___ his smile.', 'is', 'was', 'it is', 'what is', 'A'),
            _q('___ she said that shocked everyone.', 'It was', 'What', 'That', 'Which', 'A'),
            _q('___ I want to do is travel.', 'What', 'It is', 'That', 'All', 'A'),
            _q('It was in Tashkent ___ I met her.', 'that', 'where', 'which', 'who', 'A'),
            _q('___ makes me angry is the traffic.', 'What', 'It is', 'That', 'The thing', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_11_ellipsis_substitution',
        level="B2",
        title='Ellipsis & Substitution',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Ellipsis – takrorlanadigan so‘zlarni tashlab qoldirish (qisqartirish).\n"
            "Substitution – so‘z o‘rniga one, ones, do, so, neither, not...either ishlatish.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Эллипсис и субституция – сокращение повторяющихся частей и замена слов.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Ellipsis: I can swim and so can my brother.\n"
            "Substitution: I like this book.\n"
            "Do you like this one?\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "I don’t like coffee and neither does she.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Ellipsis: auxiliary + subject (so do I, neither do I)\n"
            "🟢 2. Substitution: one/ones (for nouns), do/so (for verbs)\n"
            "🟢 3. Neither / not...either – inkor uchun\n"
            "🟢 4. To avoid repetition in conversation\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "I love pizza and so does my sister.\n"
            "She has a red car.\n"
            "I have a blue one.\n"
            "He can speak French.\n"
            "So can I.\n"
            "I don’t eat meat and neither does my husband.\n"
            "She studied hard and so did her friend."
        ),
        questions=[
            _q('I love pizza and ___ my sister.', 'so does', 'so do', 'does so', 'so is', 'A'),
            _q('I have a red car. She has a blue ___.', 'one', 'ones', 'car', 'it', 'A'),
            _q('He can swim. ___ I.', 'So can', 'So do', 'Can so', 'So is', 'A'),
            _q('I don’t like coffee and ___ she.', 'neither does', 'neither do', 'so does', 'either does', 'A'),
            _q('She studied hard and ___ her brother.', 'so did', 'so does', 'did so', 'so is', 'A'),
            _q('This book is good. Have you read this ___?', 'one', 'ones', 'it', 'book', 'A'),
            _q('I can’t dance and ___ my friend.', 'neither can', 'neither does', 'so can', 'either can', 'A'),
            _q('He went to Paris. ___ I.', 'So did', 'So do', 'Did so', 'So is', 'A'),
            _q('These shoes are nice. I want those ___.', 'ones', 'one', 'it', 'shoes', 'A'),
            _q('She doesn’t smoke and ___ her husband.', 'neither does', 'neither do', 'so does', 'either does', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_12_advanced_conditionals_inverted_mixed_unless',
        level="B2",
        title='Advanced Conditionals (inverted, mixed, unless)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Murakkab shartli gaplar:Inverted: Had I known... / Were I rich... / Should you need...\n"
            "Unless = if notMixed conditionals (2+3 va 3+2)\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Продвинутые условные предложения – инверсия, unless, смешанные типы.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Inverted: Had I known, I would have helped.\n"
            "Unless: I’ll go unless it rains.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Mixed: If I were rich, I would have bought it.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Inverted conditionals (formal): Had + subject + V3\n"
            "🟢 2. Should + subject + infinitive (future possibility)\n"
            "🟢 3. Unless = if not\n"
            "🟢 4. Mixed: Type 2 + Type 3 va Type 3 + Type 2\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "Had I known the truth, I would have told you.\n"
            "Should you need help, call me.\n"
            "I won’t go unless you come with me.\n"
            "If I were taller, I would have played basketball.\n"
            "If she had studied, she would be a doctor now."
        ),
        questions=[
            _q('___ I known, I would have helped.', 'Had', 'If', 'Were', 'Should', 'A'),
            _q('I’ll go ___ it rains.', 'unless', 'if', 'when', 'because', 'A'),
            _q('___ you need help, call me.', 'Should', 'Had', 'Were', 'If', 'A'),
            _q('If I ___ rich, I would have bought a car.', 'were', 'had been', 'am', 'was', 'A'),
            _q('If she ___ harder, she would be successful now.', 'had studied', 'studied', 'studies', 'would study', 'A'),
            _q('___ I rich, I would travel the world.', 'Were', 'Had', 'Should', 'If', 'A'),
            _q('We won’t win ___ we practise more.', 'unless', 'if', 'when', 'because', 'A'),
            _q('___ you arrive early, we can start on time.', 'Should', 'Had', 'Were', 'If', 'A'),
            _q('If I ___ the lottery, I would have bought a house.', 'had won', 'won', 'win', 'would win', 'A'),
            _q('___ I known the answer, I would have passed.', 'Had', 'Were', 'Should', 'If', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_13_causative_have_get_advanced_forms',
        level="B2",
        title='Causative Have/Get (advanced forms)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Causative ning murakkab shakllari – have/get something done + modal, perfect, continuous.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Продвинутый каузатив – have/get something done с модалами и временами.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "I have my car serviced every year.\n"
            "She is having her hair done right now.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "I haven’t had my passport renewed yet.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Have + object + V3 (professional)\n"
            "🟢 2. Get + object + V3 (informal)\n"
            "🟢 3. Modal + have/get + V3\n"
            "🟢 4. Continuous: is having / has been having\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "I need to have my computer repaired.\n"
            "She got her teeth whitened last month.\n"
            "We are having the house painted at the moment.\n"
            "You should have your eyes checked.\n"
            "He had his wallet stolen yesterday."
        ),
        questions=[
            _q('I need to ___ my computer repaired.', 'have', 'get', 'had', 'getting', 'A'),
            _q('She ___ her hair done yesterday.', 'got', 'have', 'had', 'getting', 'A'),
            _q('We ___ the house painted now.', 'are having', 'have', 'got', 'had', 'A'),
            _q('You should ___ your eyes checked.', 'have', 'get', 'had', 'getting', 'A'),
            _q('He ___ his wallet stolen.', 'had', 'got', 'have', 'getting', 'A'),
            _q('She is ___ her passport renewed.', 'having', 'getting', 'had', 'get', 'A'),
            _q('I haven’t ___ my car serviced yet.', 'had', 'get', 'have', 'getting', 'A'),
            _q('We will ___ the garden redesigned.', 'have', 'get', 'had', 'getting', 'A'),
            _q('They ___ their photos taken professionally.', 'had', 'get', 'have', 'getting', 'A'),
            _q('She got her nails ___.', 'done', 'do', 'doing', 'did', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_14_phrasal_verbs_separable_inseparable_multi_word',
        level="B2",
        title='Phrasal Verbs (separable/inseparable + multi-word)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Murakkab phrasal verbs – separable (object o‘rtada), inseparable va multi-word (3 so‘zli).\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Продвинутые фразовые глаголы – разделяемые, неразделяемые и многословные.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Separable: Turn the light off. / Turn off the light.\n"
            "Inseparable: Look after the children.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "I can’t put up with the noise anymore.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Separable: turn on/off, pick up, give back\n"
            "🟢 2. Inseparable: look after, run into, come across\n"
            "🟢 3. Multi-word: look forward to, put up with, get along with\n"
            "🟢 4. Object pronoun – separable da o‘rtada\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "Please turn the TV off.\n"
            "I ran into an old friend yesterday.\n"
            "I am looking forward to seeing you.\n"
            "She put up with the bad weather.\n"
            "Can you pick me up at 7?"
        ),
        questions=[
            _q('Turn ___ the light, please.', 'off', 'on', 'up', 'down', 'A'),
            _q('I ran ___ an old friend yesterday.', 'into', 'after', 'across', 'up', 'A'),
            _q('I am looking forward ___ the holidays.', 'to', 'for', 'at', 'on', 'A'),
            _q('She can’t put ___ with the noise.', 'up', 'down', 'off', 'on', 'A'),
            _q('Can you pick ___ at 7?', 'me up', 'up me', 'me', 'up', 'A'),
            _q('Give ___ the money, please.', 'me back', 'back me', 'me', 'back', 'A'),
            _q('We get ___ very well.', 'along', 'on', 'up', 'off', 'A'),
            _q('Look ___ the children while I’m away.', 'after', 'for', 'at', 'into', 'A'),
            _q('The meeting was called ___.', 'off', 'on', 'up', 'down', 'A'),
            _q('I came ___ an old photo yesterday.', 'across', 'into', 'after', 'up', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_15_discourse_markers_linking_words_advanced',
        level="B2",
        title='Discourse Markers & Linking Words (advanced)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Diskurs markerlar – gaplarni bog‘lash va fikrni aniq ifodalash uchun (however, moreover, in addition, on the contrary, as a result va h.k.).\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Дискурсивные маркеры и связующие слова продвинутого уровня.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "However: It was expensive.\n"
            "However, I bought it.\n"
            "Moreover: She is beautiful.\n"
            "Moreover, she is clever.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "On the contrary: I don’t like it.\n"
            "On the contrary, I love it.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Addition: moreover, furthermore, in addition\n"
            "🟢 2. Contrast: however, nevertheless, on the other hand\n"
            "🟢 3. Result: as a result, therefore, consequently\n"
            "🟢 4. Example: for instance, such as\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "The film was long.\n"
            "However, it was very interesting.\n"
            "She studied hard.\n"
            "As a result, she passed the exam.\n"
            "He is rich.\n"
            "Moreover, he is very generous.\n"
            "I don’t like coffee.\n"
            "On the contrary, I love it.\n"
            "The weather was bad.\n"
            "Nevertheless, we went out."
        ),
        questions=[
            _q('It was expensive. ___, I bought it.', 'However', 'Moreover', 'As a result', 'On the contrary', 'A'),
            _q('She is beautiful. ___, she is very clever.', 'Moreover', 'However', 'As a result', 'On the contrary', 'A'),
            _q('He studied hard. ___, he passed the exam.', 'As a result', 'However', 'Moreover', 'On the contrary', 'A'),
            _q('I don’t like tea. ___, I love it.', 'On the contrary', 'However', 'Moreover', 'As a result', 'A'),
            _q('The test was difficult. ___, everyone passed.', 'Nevertheless', 'Moreover', 'As a result', 'On the contrary', 'A'),
            _q('He is tired. ___, he continues working.', 'Nevertheless', 'Moreover', 'As a result', 'On the contrary', 'A'),
            _q('She is smart. ___, she is kind.', 'Furthermore', 'However', 'As a result', 'On the contrary', 'A'),
            _q('It rained all day. ___, the match was cancelled.', 'As a result', 'However', 'Moreover', 'On the contrary', 'A'),
            _q('I like apples. ___, I like oranges.', 'In addition', 'However', 'As a result', 'On the contrary', 'A'),
            _q('The book is long. ___, it is boring.', 'However', 'Moreover', 'As a result', 'On the contrary', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_16_noun_clauses_reported_questions',
        level="B2",
        title='Noun Clauses & Reported Questions',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Noun clauses – gap ichida ot o‘rnida turadi (what, that, if/whether, wh-questions).\n"
            "Reported questions – savol so‘z tartibi o‘zgaradi (if/whether + statement).\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Существительные придаточные предложения и косвенные вопросы.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Noun clause: I know what you did.\n"
            "Reported question: She asked if I was ready.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "I don’t know whether he will come.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. That-clauses: I think that he is right (that tashlab qoldirilishi mumkin)\n"
            "🟢 2. Wh-clauses: I wonder where she lives\n"
            "🟢 3. Yes/No questions: if/whether (whether formalroq)\n"
            "🟢 4. Backshift: do → did, will → would\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "I don’t know what time it is.\n"
            "She asked whether I had finished the report.\n"
            "Tell me where you are going.\n"
            "I wonder if he will arrive on time.\n"
            "The problem is that we don’t have enough time."
        ),
        questions=[
            _q('I don’t know ___ he lives.', 'where', 'what', 'if', 'that', 'A'),
            _q('She asked ___ I was ready.', 'if', 'what', 'where', 'that', 'A'),
            _q('Tell me ___ you are going.', 'where', 'if', 'that', 'whether', 'A'),
            _q('I wonder ___ he will come.', 'if', 'what', 'where', 'that', 'A'),
            _q('The problem is ___ we don’t have time.', 'that', 'if', 'whether', 'what', 'A'),
            _q('I know ___ you mean.', 'what', 'where', 'if', 'that', 'A'),
            _q('He asked ___ I had seen the film.', 'whether', 'what', 'where', 'that', 'A'),
            _q('Do you know ___ time it is?', 'what', 'where', 'if', 'whether', 'A'),
            _q('She told me ___ she was tired.', 'that', 'what', 'where', 'if', 'A'),
            _q('I can’t remember ___ I put the keys.', 'where', 'what', 'if', 'that', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_17_adverbial_clauses_purpose_result_concession_advanc',
        level="B2",
        title='Adverbial Clauses (purpose, result, concession advanced)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Murakkab adverbial clauses – maqsad (so that, in order that), natija (so...that, such...that), qarama-qarshi (even if, whereas).\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Продвинутые придаточные обстоятельственные – цели, результата, уступки.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "So that: I studied so that I could pass.\n"
            "So...that: It was so cold that we stayed home.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Even if: I’ll go even if it rains.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Purpose: so that + modal (can/could/will/would)\n"
            "🟢 2. Result: so + adj/adv + that / such + noun + that\n"
            "🟢 3. Concession: even if / even though / whereas\n"
            "🟢 4. In case / lest (kam ishlatiladi)\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "I left early so that I wouldn’t be late.\n"
            "It was such a difficult test that no one passed.\n"
            "Even if you try, you might not succeed.\n"
            "She studied hard so that she could get a scholarship.\n"
            "The film was so boring that I fell asleep."
        ),
        questions=[
            _q('I left early ___ I wouldn’t be late.', 'so that', 'even if', 'such that', 'whereas', 'A'),
            _q('It was ___ cold ___ we stayed home.', 'so / that', 'such / that', 'even if', 'whereas', 'A'),
            _q('I’ll go ___ it rains.', 'even if', 'so that', 'such that', 'whereas', 'A'),
            _q('She studied hard ___ she could get a scholarship.', 'so that', 'even if', 'such that', 'whereas', 'A'),
            _q('The test was ___ difficult ___ no one passed.', 'such / that', 'so / that', 'even if', 'whereas', 'A'),
            _q('He is rich ___ his brother is poor.', 'whereas', 'so that', 'even if', 'such that', 'A'),
            _q('Take an umbrella ___ it rains.', 'in case', 'so that', 'even if', 'whereas', 'A'),
            _q('The film was ___ boring ___ I left early.', 'so / that', 'such / that', 'even if', 'whereas', 'A'),
            _q('Even ___ he is tired, he continues working.', 'though', 'if', 'such', 'so', 'A'),
            _q('It was ___ a nice day ___ we went for a picnic.', 'such / that', 'so / that', 'even if', 'whereas', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_18_emphasis_structures',
        level="B2",
        title='Emphasis Structures',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Ta’kidlash tuzilmalari – ma’lumotni kuchaytirish uchun.\n"
            "What...is..., It is...that..., All...is..., The thing is...\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Структуры для выделения и подчёркивания.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "What I need is more time.\n"
            "It was the teacher who helped me.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "The thing that worries me is the price.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. What + clause + is/was...\n"
            "🟢 2. It is/was + ta’kidlanayotgan qism + that/who\n"
            "🟢 3. All/The only thing + clause + is...\n"
            "🟢 4. The reason why... is...\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "What I love about Tashkent is the food.\n"
            "It was my friend who called me.\n"
            "The only thing I want is peace.\n"
            "All she did was cry.\n"
            "The reason I left early was the traffic."
        ),
        questions=[
            _q('___ I need is more time.', 'What', 'It is', 'All', 'The thing', 'A'),
            _q('It was my friend ___ called me.', 'who', 'what', 'that', 'which', 'A'),
            _q('The only thing I want ___ peace.', 'is', 'was', 'it is', 'what is', 'A'),
            _q('All she did ___ cry.', 'was', 'is', 'it was', 'what was', 'A'),
            _q('The reason I left ___ the traffic.', 'was', 'is', 'it was', 'what was', 'A'),
            _q('___ worries me is the price.', 'The thing that', 'What', 'It is', 'All', 'A'),
            _q('It is the teacher ___ helped me.', 'who', 'what', 'that', 'which', 'A'),
            _q('What I love about the city ___ the people.', 'is', 'was', 'it is', 'what is', 'A'),
            _q('The thing ___ surprises me is her decision.', 'that', 'what', 'who', 'which', 'A'),
            _q('All we need ___ a little luck.', 'is', 'was', 'it is', 'what is', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_19_wish_if_only_suppose_past_future_advanced',
        level="B2",
        title='Wish / If only / Suppose (past & future advanced)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Wish / If only ning murakkab shakllari – o‘tmish va kelajak xohishlari.\n"
            "Suppose / Supposing – taxminiy savollar.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Продвинутые конструкции wish, if only и suppose.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "I wish I had gone to university.\n"
            "If only you would listen to me!\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Suppose you won the lottery, what would you do?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Wish + Past Perfect (o‘tmish pushaymon)\n"
            "🟢 2. Wish + would (boshqa odamning xatti-harakatiga)\n"
            "🟢 3. Suppose / Supposing + Past Simple (hozirgi taxmin)\n"
            "🟢 4. If only – kuchliroq afsus\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "I wish I hadn’t quit my job.\n"
            "If only it would stop raining!\n"
            "Suppose you were president, what would you change?\n"
            "I wish you would stop smoking.\n"
            "If only I had listened to my parents!"
        ),
        questions=[
            _q('I wish I ___ to university.', 'had gone', 'went', 'go', 'would go', 'A'),
            _q('If only it ___ raining!', 'would stop', 'stops', 'stopped', 'had stopped', 'A'),
            _q('Suppose you ___ the lottery, what would you do?', 'won', 'win', 'had won', 'would win', 'A'),
            _q('I wish you ___ smoking.', 'would stop', 'stop', 'stopped', 'had stopped', 'A'),
            _q('If only I ___ to my parents!', 'had listened', 'listened', 'listen', 'would listen', 'A'),
            _q('Suppose it ___ tomorrow, what will we do?', 'rained', 'rains', 'had rained', 'would rain', 'A'),
            _q('I wish I ___ more time.', 'had', 'have', 'would have', 'had had', 'A'),
            _q('If only he ___ the truth!', 'would tell', 'tells', 'told', 'had told', 'A'),
            _q('Suppose you ___ rich, where would you live?', 'were', 'are', 'had been', 'would be', 'A'),
            _q('I wish it ___ warmer today.', 'were', 'is', 'was', 'would be', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_20_hypothetical_past_future_would_have_be_to_were_to',
        level="B2",
        title='Hypothetical Past & Future (would have, be to, were to)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Hypothetical shartlar – o‘tmish va kelajakda bo‘lmagan yoki kam ehtimol holatlar.\n"
            "Would have + V3 (o‘tmish)Were to / Be to + infinitive (kelajak taxmin)\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Гипотетическое прошедшее и будущее – would have, were to, be to.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "If I had known, I would have helped.\n"
            "If he were to arrive late, we would start without him.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "I wouldn’t have gone if I had known.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Would have – o‘tmishda bo‘lmagan natija\n"
            "🟢 2. Were to – kam ehtimol kelajak (formal)\n"
            "🟢 3. Be to – rasmiy kelajak reja yoki taqdir\n"
            "🟢 4. Inverted: Were he to come...\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "If she had called, I would have answered.\n"
            "If you were to ask him, he might help.\n"
            "The president is to visit Tashkent next week.\n"
            "Were I to win the lottery, I would retire.\n"
            "I would have travelled more if I had had money."
        ),
        questions=[
            _q('If I ___ , I would have helped.', 'had known', 'knew', 'know', 'would know', 'A'),
            _q('If he ___ late, we would start without him.', 'were to arrive', 'arrives', 'arrived', 'would arrive', 'A'),
            _q('The president ___ visit next week.', 'is to', 'was to', 'were to', 'would', 'A'),
            _q('Were I ___ win, I would retire.', 'to', 'would', 'had', 'will', 'A'),
            _q('I would have travelled more if I ___ money.', 'had had', 'have', 'had', 'would have', 'A'),
            _q('If she ___ called, I would have answered.', 'had', 'has', 'would have', 'were to', 'A'),
            _q('Be to + infinitive – rasmiy kelajak reja.', 'is', 'was', 'were', 'would', 'A'),
            _q('If you ___ ask, he might help.', 'were to', 'are to', 'was to', 'would', 'A'),
            _q('I wouldn’t have gone if I ___ .', 'had known', 'knew', 'know', 'would know', 'A'),
            _q('Were she ___ come, we would be happy.', 'to', 'would', 'had', 'will', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_21_collocations_verb_patterns_advanced',
        level="B2",
        title='Collocations & Verb Patterns (advanced)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Collocations – so‘z birikmalari (make a decision, take a risk).\n"
            "Verb patterns – murakkab fe’l tuzilmalari (accuse sb of doing, prevent sb from doing).\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Коллокации и продвинутые глагольные конструкции.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Make: make a mistake / make progressAccuse: He accused me of lying.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Prevent: They prevented us from entering.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Common collocations: make an effort, take responsibility, pay attention\n"
            "🟢 2. Verb + preposition + gerund: accuse of, apologise for, insist on\n"
            "🟢 3. Verb + object + preposition + gerund: blame sb for, congratulate sb on\n"
            "🟢 4. Verb + infinitive / gerund farqi (advanced)\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "You should make an effort to learn English.\n"
            "She accused him of stealing the money.\n"
            "They prevented the children from playing outside.\n"
            "I apologise for being late.\n"
            "He insisted on paying the bill."
        ),
        questions=[
            _q('You should ___ an effort to improve.', 'make', 'do', 'take', 'have', 'A'),
            _q('He ___ me of lying.', 'accused', 'blamed', 'charged', 'criticised', 'A'),
            _q('They prevented us ___ the room.', 'from entering', 'to enter', 'enter', 'entering', 'A'),
            _q('I apologise ___ late.', 'for being', 'to be', 'being', 'for be', 'A'),
            _q('She insisted ___ the truth.', 'on telling', 'to tell', 'telling', 'tell', 'A'),
            _q('He takes ___ for his mistakes.', 'responsibility', 'care', 'attention', 'part', 'A'),
            _q('Pay ___ to the details.', 'attention', 'care', 'notice', 'mind', 'A'),
            _q('She congratulated me ___ passing the exam.', 'on', 'for', 'about', 'at', 'A'),
            _q('They blamed the weather ___ the delay.', 'for', 'on', 'about', 'at', 'A'),
            _q('I look forward ___ you soon.', 'to seeing', 'to see', 'seeing', 'see', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_22_question_tags_echo_questions_advanced',
        level="B2",
        title='Question Tags & Echo Questions (advanced)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Murakkab question tags – modal, perfect, imperative, there is bilan.\n"
            "Echo questions – tasdiqlash yoki ajablanish uchun (Really? / Did you?).\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Продвинутые хвостики и эхо-вопросы.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "You have been there, haven’t you?\n"
            "There is no milk left, is there?\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Don’t forget, will you?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. There is/are → isn’t/aren’t there?\n"
            "🟢 2. Imperative: positive → will you?, negative → won’t you?\n"
            "🟢 3. Let’s → shall we?\n"
            "🟢 4. Echo: Really? / Did you? / Isn’t it?\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "You’ve finished, haven’t you?\n"
            "There isn’t any time left, is there?\n"
            "Let’s start now, shall we?\n"
            "Don’t touch it, will you?– I passed the exam. – Did you?\n"
            "Congratulations!"
        ),
        questions=[
            _q('You’ve been to Paris, ___?', 'haven’t you', 'have you', 'didn’t you', 'don’t you', 'A'),
            _q('There is no milk, ___?', 'is there', 'isn’t there', 'has there', 'hasn’t there', 'A'),
            _q('Let’s go home, ___?', 'shall we', 'will we', 'shan’t we', 'won’t we', 'A'),
            _q('Don’t be late, ___?', 'will you', 'won’t you', 'do you', 'don’t you', 'A'),
            _q('– She is coming. – ___? Great!', 'Is she', 'Isn’t she', 'Does she', 'Doesn’t she', 'A'),
            _q('You can help me, ___?', 'can’t you', 'can you', 'couldn’t you', 'could you', 'A'),
            _q('There are many people, ___?', 'aren’t there', 'are there', 'isn’t there', 'is there', 'A'),
            _q('– I won the prize. – ___? Amazing!', 'Did you', 'Didn’t you', 'Do you', 'Don’t you', 'A'),
            _q('Don’t forget your keys, ___?', 'will you', 'won’t you', 'do you', 'don’t you', 'A'),
            _q('Let’s not argue, ___?', 'shall we', 'will we', 'shan’t we', 'won’t we', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_23_prepositions_of_time_place_advanced',
        level="B2",
        title='Prepositions of Time & Place (advanced)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Murakkab predloglar – time: by, during, throughout, in time / on timePlace: at / in / on, by / near / next to, across / through / over\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Продвинутые предлоги времени и места.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "By: I’ll finish by 5 pm.\n"
            "In time: We arrived in time for the meeting.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Throughout: It rained throughout the day.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. By = latest time (by Friday)\n"
            "🟢 2. In time = yetarli vaqtda, on time = aniq vaqtda\n"
            "🟢 3. During / throughout = davomida\n"
            "🟢 4. Place: across (yuzadan), through (ichidan), over (ustidan)\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "I need the report by tomorrow.\n"
            "We arrived in time to see the beginning.\n"
            "The concert was delayed, but we got there on time.\n"
            "It rained throughout the night.\n"
            "She walked across the street carefully."
        ),
        questions=[
            _q('I need it ___ Friday.', 'by', 'until', 'till', 'to', 'A'),
            _q('We arrived ___ time for the film.', 'in', 'on', 'at', 'by', 'A'),
            _q('The train was ___ time.', 'on', 'in', 'at', 'by', 'A'),
            _q('It rained ___ the day.', 'throughout', 'during', 'in', 'on', 'A'),
            _q('She walked ___ the bridge.', 'across', 'through', 'over', 'along', 'A'),
            _q('He drove ___ the tunnel.', 'through', 'across', 'over', 'under', 'A'),
            _q('The plane flew ___ the mountains.', 'over', 'through', 'across', 'above', 'A'),
            _q('Finish the task ___ the end of the week.', 'by', 'until', 'till', 'to', 'A'),
            _q('We were late ___ the meeting.', 'for', 'to', 'at', 'in', 'A'),
            _q('The shop is open ___ 9 am ___ 8 pm.', 'from / to', 'from / till', 'at / to', 'in / until', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_24_formal_vs_informal_grammar',
        level="B2",
        title='Formal vs Informal Grammar',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Formal va informal grammatika farqlari – passiv, inversion, subjunctive, formal linking words.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Формальная и неформальная грамматика.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Formal: passiv, subjunctive (suggest that he be...), inversion\n"
            "🟢 2. Informal: contractions (I’m, don’t), phrasal verbs\n"
            "🟢 3. Linking: furthermore (formal), also (informal)\n"
            "🟢 4. No contractions in formal writing\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "It is essential that all documents be submitted on time.\n"
            "(formal)You must submit all documents on time.\n"
            "(informal)Should any problems arise, contact us immediately.\n"
            "I think it’s a good idea.\n"
            "(informal)It is believed to be true.\n"
            "(formal)"
        ),
        questions=[
            _q('It is recommended that you ___ early.', 'arrive', 'arrives', 'arriving', 'arrived', 'A'),
            _q('Should you ___ help, call us.', 'need', 'needs', 'needing', 'needed', 'A'),
            _q('I think it’s ___ good idea. (informal)', 'a', 'the', '–', 'an', 'A'),
            _q('It is believed ___ true. (formal)', 'to be', 'be', 'being', 'been', 'A'),
            _q('Furthermore, the results ___ positive. (formal)', 'are', 'is', 'be', 'being', 'A'),
            _q('You should ___ the form. (informal)', 'fill in', 'fill in', 'filling in', 'filled in', 'A'),
            _q('It is essential that he ___ present.', 'be', 'is', 'being', 'been', 'A'),
            _q('I’m sorry, I ___ late. (informal)', '’m', 'am', 'was', 'be', 'A'),
            _q('In conclusion, the project ___ successful. (formal)', 'was', 'is', 'be', 'being', 'A'),
            _q('If any issues arise, please ___ us. (formal)', 'inform', 'tell', 'say', 'speak', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='b2_25_final_review_b2_key_structures',
        level="B2",
        title='Final Review – B2 Key Structures',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "B2 darajasining asosiy tuzilmalari – inversion, cleft, subjunctive, advanced passiv, hypothetical, discourse markers.\n"
            "Bu mavzu – umumiy takrorlash va test uchun.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Итоговый обзор ключевых структур B2 уровня.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Never have I seen...\n"
            "It was the best day that...\n"
            "I wish I had known...\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Not only did she win, but...\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Inversion bilan ta’kidlash\n"
            "🟢 2. Cleft bilan ajratib ko‘rsatish\n"
            "🟢 3. Subjunctive bilan xohish va tavsiya\n"
            "🟢 4. Discourse markers bilan bog‘lash\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "Not only is she intelligent, but she is also kind.\n"
            "What surprised me was his decision.\n"
            "It’s high time we started.\n"
            "Had I known earlier, I would have joined.\n"
            "All things considered, it was a success."
        ),
        questions=[
            _q('___ have I felt so happy.', 'Never', 'Only', 'So', 'Had', 'A'),
            _q('It was the teacher ___ helped me most.', 'who', 'what', 'that', 'which', 'A'),
            _q('It’s high time we ___ .', 'left', 'leave', 'leaving', 'to leave', 'A'),
            _q('Had I ___ , I would have helped.', 'known', 'know', 'knows', 'knowing', 'A'),
            _q('Not only ___ she win, but she also broke the record.', 'did', 'does', 'do', 'has', 'A'),
            _q('What I need ___ more practice.', 'is', 'was', 'it is', 'what is', 'A'),
            _q('I wish I ___ more time last year.', 'had had', 'have', 'had', 'would have', 'A'),
            _q('All things ___ , it was a good decision.', 'considered', 'considering', 'consider', 'to consider', 'A'),
            _q('The reason ___ I left is the salary.', 'why', 'that', 'which', 'what', 'A'),
            _q('It is essential that he ___ on time.', 'be', 'is', 'being', 'been', 'A'),
        ],
    ),
]

# ========= C1 =========

C1_TOPICS: List[GrammarTopic] = [
    GrammarTopic(
        topic_id='c1_01_modals_in_the_past',
        level="C1",
        title='Modals in the Past (must have, might have, could have, should have, etc.)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "O‘tmishdagi taxmin, pushaymonlik, tanqid yoki imkoniyatni bildirish uchun modal fe’l + have + V3 ishlatiladi.\n"
            "Must have → kuchli ishonch (albatta bo‘lgan)Might / Could / May have → zaif taxmin (ehtimol)Should have → pushaymonlik yoki tanqid (qilishi kerak edi, lekin qilmagan)Could have → o‘tmishdagi imkoniyat (lekin ishlatilmagan)\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Модальные глаголы в прошедшем времени для предположений, сожалений, критики или упущенных возможностей: modal + have + V3.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "Subject + modal + have + past participle\n"
            "Examples:\n"
            "You must have been very tired.\n"
            "She should have told me the truth.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "Subject + modal + not + have + past participle\n"
            "Examples:\n"
            "He couldn’t have known about the problem.\n"
            "\n"
            "❓ Question\n"
            "Formula:\n"
            "Modal + subject + have + past participle?\n"
            "Examples:\n"
            "Could she have forgotten the meeting?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Must have – 90-100% deduksiya (kuchli taxmin)\n"
            "🟢 2. Should have – regret (pushaymonlik) yoki criticism (tanqid)\n"
            "🟢 3. Might / Could have – possibility (ehtimol)\n"
            "🟢 4. Could have – unrealised past ability or opportunity\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "You must have left your phone in the taxi.\n"
            "I should have studied harder for the C1 exam.\n"
            "She might have missed the train because of the traffic.\n"
            "We could have won the match if we had trained more.\n"
            "He couldn’t have done all this work alone."
        ),
        questions=[
            _q('You ___ very hungry – you ate everything!', 'should have been', 'must have been', 'might have been', 'could have been', 'A'),
            _q('I ___ you the news earlier. Now it’s too late.', 'must have told', 'should have told', 'might have told', 'could have told', 'A'),
            _q('She ___ the message – she never replied.', 'must have received', 'might not have received', 'should have received', 'could have received', 'A'),
            _q('They ___ the prize. They played terribly.', 'must have won', 'couldn’t have won', 'should have won', 'might have won', 'A'),
            _q('___ she ___ the keys? The door is still locked.', 'Must / have lost', 'Could / have lost', 'Should / have lost', 'Might / have lost', 'A'),
            _q('You ___ more careful with your money last month.', 'must have been', 'should have been', 'might have been', 'could have been', 'A'),
            _q('It ___ raining all night – the streets are flooded.', 'should have been', 'must have been', 'could have been', 'might have been', 'A'),
            _q('We ___ invited them. They looked disappointed.', 'must have', 'should have', 'might have', 'could have', 'A'),
            _q('He ___ the accident. He was in another city at that time.', 'must have caused', 'couldn’t have caused', 'should have caused', 'might have caused', 'A'),
            _q('She ___ forgotten her passport again.', 'must have', 'should have', 'could have', 'might have', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_02_mixed_conditionals',
        level="C1",
        title='Mixed Conditionals',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Aralash shartli gaplar – hozirgi holat bilan o‘tmish natijasini yoki o‘tmish harakat bilan hozirgi natijani birlashtirish.\n"
            "If + Past Perfect, would + verb (o‘tmish → hozir)If + Past Simple, would have + V3 (hozir → o‘tmish)\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Смешанные условные предложения – комбинация второго и третьего типа.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "If I had studied medicine (o‘tmish), I would be a doctor now (hozir).\n"
            "If I were rich (hozir), I would have bought that house last year (o‘tmish).\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "If she hadn’t missed the flight, she wouldn’t be stuck here now.\n"
            "\n"
            "❓ Question\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "What would you do if you had more time last week?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. If + Past Perfect → would + infinitive (o‘tmish sabab → hozirgi natija)\n"
            "🟢 2. If + Past Simple → would have + V3 (hozirgi holat → o‘tmish natija)\n"
            "🟢 3. Were – barcha shaxslar uchun (formal uslubda)\n"
            "🟢 4. Real hayotdagi pushaymonlik va “agar ... bo‘lganida edi” uchun ishlatiladi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "If I had saved more money, I would be travelling the world now.\n"
            "If she spoke better English, she would have got the job last month.\n"
            "If I were you, I would have accepted the offer immediately.\n"
            "What would you have done if you were in my position?"
        ),
        questions=[
            _q('If I ___ harder at university, I ___ a doctor now.', 'studied / would have', 'had studied / would be', 'had studied / would have', 'studied / would', 'A'),
            _q('If she ___ English fluently, she ___ the promotion last year.', 'spoke / would get', 'spoke / would have got', 'had spoken / would get', 'speaks / would have got', 'A'),
            _q('If I ___ the bus this morning, I ___ at work now.', 'hadn’t missed / would be', 'didn’t miss / would be', 'hadn’t missed / will be', 'don’t miss / would be', 'A'),
            _q('What ___ you ___ if you ___ more time yesterday?', 'would / have done / had', 'would / do / had', 'will / do / have', 'would / have done / were', 'A'),
            _q('If he ___ taller, he ___ professional basketball.', 'were / would play', 'were / would have played', 'was / would play', 'had been / would play', 'A'),
            _q('If I ___ you, I ___ that mistake last week.', 'were / wouldn’t have made', 'were / wouldn’t make', 'had been / wouldn’t make', 'was / wouldn’t have made', 'A'),
            _q('She ___ happier now if she ___ harder last year.', 'would be / studied', 'would be / had studied', 'will be / had studied', 'would have been / studied', 'A'),
            _q('If we ___ earlier, we ___ the concert now.', 'had left / would enjoy', 'had left / would be enjoying', 'left / would enjoy', 'had left / will enjoy', 'A'),
            _q('What ___ happen if you ___ the exam last month?', 'would / have happened / had failed', 'would / happen / had failed', 'will / happen / fail', 'would / have happened / failed', 'A'),
            _q('If she ___ the truth, she ___ worried now.', 'had known / wouldn’t be', 'knew / wouldn’t be', 'had known / wouldn’t have been', 'knows / wouldn’t be', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_03_inversion_with_negative_adverbials',
        level="C1",
        title='Inversion with Negative Adverbials',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Inversion – gap boshida salbiy yoki cheklovchi so‘z (never, rarely, seldom, hardly, no sooner, only when va h.k.) bo‘lsa, yordamchi fe’l subjectdan oldinga chiqadi.\n"
            "Bu formal va dramatik uslubda ishlatiladi.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Инверсия – когда в начале предложения стоит отрицательное или ограничивающее наречие, вспомогательный глагол выходит перед подлежащим.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "Negative adverbial + auxiliary + subject + main verb\n"
            "Examples:\n"
            "Never have I seen such a beautiful view.\n"
            "No sooner had she arrived than the phone rang.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Hardly had I sat down when the lights went out.\n"
            "\n"
            "❓ Question\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Seldom do we have the chance to meet such talented people.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Never, Rarely, Seldom, Hardly, Scarcely + have/has/had\n"
            "🟢 2. No sooner ... than / Hardly ... when\n"
            "🟢 3. Only when / Only after / Not until + auxiliary\n"
            "🟢 4. Formal yozuv va nutqda kuchli ta’sir berish uchun ishlatiladi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "Never have I felt so happy in my life.\n"
            "Only when I arrived did I realise my mistake.\n"
            "No sooner had we left the house than it started raining.\n"
            "Rarely do we see such talent in young players.\n"
            "Hardly had she finished speaking when the audience stood up."
        ),
        questions=[
            _q('___ have I seen such a beautiful view.', 'Only', 'Never', 'No sooner', 'Hardly', 'A'),
            _q('Only when the teacher came ___ the students quiet.', 'do', 'did', 'does', 'had', 'A'),
            _q('No sooner ___ I arrived ___ it started to rain.', 'have / than', 'had / than', 'did / when', 'had / when', 'A'),
            _q('___ do we eat fast food.', 'Only', 'Rarely', 'Never', 'Hardly', 'A'),
            _q('Hardly ___ she finished speaking ___ the audience clapped.', 'had / when', 'have / than', 'did / when', 'had / than', 'A'),
            _q('Only after the exam ___ I relax.', 'do', 'did', 'does', 'had', 'A'),
            _q('___ had I left the house ___ I remembered my keys.', 'No sooner / than', 'Hardly / when', 'Never / when', 'Only / when', 'A'),
            _q('Seldom ___ she complain about her work.', 'does', 'do', 'did', 'has', 'A'),
            _q('Never before ___ such a big crowd.', 'have I seen', 'I have seen', 'did I see', 'I saw', 'A'),
            _q('Only when it is completely quiet ___ I study well.', 'can', 'can', 'do', 'will', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_04_cleft_sentences',
        level="C1",
        title='Cleft Sentences (It is / was ... that / who / which)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Cleft sentences – gapdagi muhim qismni ta’kidlab ko‘rsatish uchun ishlatiladi.\n"
            "Formula: It is / was + emphasized part + that / who / which + rest of the sentence\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Расщеплённые предложения – для выделения важной части высказывания.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "It was the weather that ruined the picnic.\n"
            "It is English that I find most difficult.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "It wasn’t me who broke the window.\n"
            "\n"
            "❓ Question\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Was it you who called me last night?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. It is / was + ta’kidlanayotgan qism + that/who/which\n"
            "🟢 2. Who – odamlar uchun, which/that – narsalar va hodisalar uchun\n"
            "🟢 3. Hozirgi zamon uchun “It is”, o‘tmish uchun “It was”\n"
            "🟢 4. Kuchli ta’kid va formal uslubda ishlatiladi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "It was my sister who helped me with the homework.\n"
            "It is hard work that leads to success.\n"
            "It wasn’t the price that surprised me, it was the quality.\n"
            "It is in Tashkent that I was born.\n"
            "Was it you who sent me this message?"
        ),
        questions=[
            _q('___ my brother who won the competition.', 'It is', 'It was', 'It has', 'There is', 'A'),
            _q('It is English ___ I find most difficult.', 'who', 'that', 'which', 'where', 'A'),
            _q('___ you who called me yesterday?', 'Was it', 'Was it', 'Is it', 'Did it', 'A'),
            _q('It wasn’t the rain ___ ruined the match.', 'who', 'that', 'which', 'where', 'A'),
            _q('It is hard work ___ brings success.', 'who', 'that', 'which', 'where', 'A'),
            _q('___ in London that they first met.', 'It was', 'It was', 'It is', 'There was', 'A'),
            _q('It is the manager ___ makes all the decisions.', 'that', 'who', 'which', 'where', 'A'),
            _q('It wasn’t me ___ broke the glass.', 'who', 'who', 'that', 'which', 'A'),
            _q('___ the price that surprised me the most.', 'It is', 'It was', 'It has', 'There is', 'A'),
            _q('It is patience ___ you need most in this job.', 'who', 'that', 'which', 'where', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_05_participle_clauses',
        level="C1",
        title='Participle Clauses (Advanced use)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Participle clauses – gapni qisqartirish va murakkab ma’noni ifodalash uchun -ing (present participle) yoki -ed (past participle) shakllari ishlatiladi.\n"
            "Vaqt, sabab, shart, natija bildirishi mumkin.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Причастные обороты – для сокращения предложений и выражения времени, причины, условия или результата.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Having finished the exam, she felt relieved.\n"
            "Seen from the top, the city looks beautiful.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Not knowing what to do, he called his friend.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Present participle (-ing) – bir vaqtda yoki sabab\n"
            "🟢 2. Past participle (-ed) – passiv ma’no\n"
            "🟢 3. Perfect participle (having + V3) – oldin sodir bo‘lgan harakat\n"
            "🟢 4. Subject bir xil bo‘lishi kerak (agar farqli bo‘lsa, to‘liq gap ishlatiladi)\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "Having lived in Tashkent for 10 years, he knows the city very well.\n"
            "Encouraged by her teacher, she decided to take the C1 exam.\n"
            "Not understanding the question, I asked for help.\n"
            "Seen from the mountain, the lake was breathtaking.\n"
            "Having finished all her work, she went home early."
        ),
        questions=[
            _q('___ the exam, she felt very relieved.', 'Finished', 'Having finished', 'Finishing', 'To finish', 'A'),
            _q('___ from the top of the tower, the view is amazing.', 'Seen', 'Seen', 'Seeing', 'To see', 'A'),
            _q('___ what to say, he remained silent.', 'Not knowing', 'Not knowing', 'Not known', 'Not to know', 'A'),
            _q('___ by his parents, he worked even harder.', 'Encouraged', 'Encouraged', 'Encouraging', 'To encourage', 'A'),
            _q('___ in London for many years, she speaks English fluently.', 'Lived', 'Having lived', 'Living', 'To live', 'A'),
            _q('___ the bad weather, we still went out.', 'Despite', 'Despite', 'In spite', 'Although', 'A'),
            _q('The book, ___ last year, became a bestseller.', 'published', 'published', 'publishing', 'to publish', 'A'),
            _q('___ tired after the long journey, he went straight to bed.', 'Feeling', 'Feeling', 'Felt', 'To feel', 'A'),
            _q('___ all the preparations, the team was ready for the match.', 'Made', 'Having made', 'Making', 'To make', 'A'),
            _q('The girl, ___ by the news, started crying.', 'shocked', 'shocked', 'shocking', 'to shock', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_06_advanced_inversion',
        level="C1",
        title='Advanced Inversion (with negative adverbials and other structures)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Inversion – gap boshida salbiy yoki cheklovchi so‘z (never, rarely, seldom, hardly, no sooner, only when, little, not only va h.k.) bo‘lsa, yordamchi fe’l subjectdan oldinga chiqadi.\n"
            "Bu formal va dramatik uslubda kuchli ta’sir beradi.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Инверсия – когда в начале предложения стоит отрицательное или ограничивающее наречие, вспомогательный глагол выходит перед подлежащим.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "Negative adverbial + auxiliary + subject + main verb\n"
            "Examples:\n"
            "Never have I seen such a beautiful city.\n"
            "No sooner had we arrived than the meeting started.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Hardly had she finished when the phone rang.\n"
            "\n"
            "❓ Question\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Seldom do we have the opportunity to meet such talented people.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Never / Rarely / Seldom + have/has/had\n"
            "🟢 2. No sooner ... than / Hardly / Scarcely ... when\n"
            "🟢 3. Only when / Only after / Not until + auxiliary\n"
            "🟢 4. Little / Not only / At no time + inversion\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "Never before had I felt so nervous.\n"
            "Only when I arrived did I realise my mistake.\n"
            "No sooner had she left than the storm began.\n"
            "Little did I know that this would change my life.\n"
            "Not only did she pass the exam, but she also got the highest score."
        ),
        questions=[
            _q('___ have I seen such a beautiful view.', 'Only', 'Never', 'No sooner', 'Hardly', 'A'),
            _q('Only when the teacher came ___ the students become quiet.', 'do', 'did', 'does', 'had', 'A'),
            _q('No sooner ___ I arrived ___ it started to rain.', 'have / than', 'had / than', 'did / when', 'had / when', 'A'),
            _q('___ do we eat fast food.', 'Only', 'Rarely', 'Never', 'Hardly', 'A'),
            _q('Hardly ___ she finished speaking ___ the audience clapped.', 'had / when', 'have / than', 'did / when', 'had / than', 'A'),
            _q('Only after the exam ___ I finally relax.', 'do', 'did', 'does', 'had', 'A'),
            _q('___ had I left the house ___ I remembered my keys.', 'No sooner / than', 'Hardly / when', 'Never / when', 'Only / when', 'A'),
            _q('Seldom ___ she complain about her work.', 'does', 'do', 'did', 'has', 'A'),
            _q('Never before ___ such a big crowd at the concert.', 'have I seen', 'I have seen', 'did I see', 'I saw', 'A'),
            _q('Only when it is completely quiet ___ I study well.', 'can', 'can', 'do', 'will', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_07_cleft_sentences',
        level="C1",
        title='Cleft Sentences (It is / was ... that / who / which)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Cleft sentences – gapdagi muhim qismni kuchli ta’kidlab ko‘rsatish uchun ishlatiladi.\n"
            "Formula: It is / was + emphasized part + that / who / which + qolgan qism\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Расщеплённые предложения – для сильного выделения важной части высказывания.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "It was the weather that ruined our plans.\n"
            "It is hard work that leads to success.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "It wasn’t me who broke the window.\n"
            "\n"
            "❓ Question\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Was it you who called me last night?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. It is (hozir) / It was (o‘tmish)\n"
            "🟢 2. Who – odamlar uchun, that / which – narsalar va hodisalar uchun\n"
            "🟢 3. Kuchli ta’kid va formal yozuvda ishlatiladi\n"
            "🟢 4. What-cleft ham mumkin: What I need is more time.\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "It was my sister who helped me prepare for the C1 exam.\n"
            "It is patience that you need most in this job.\n"
            "It wasn’t the price that surprised me, it was the quality.\n"
            "It is in Tashkent that I feel most at home.\n"
            "What I really want is a long holiday."
        ),
        questions=[
            _q('___ my brother who won the competition.', 'It is', 'It was', 'It has', 'There is', 'A'),
            _q('It is English ___ I find most difficult.', 'who', 'that', 'which', 'where', 'A'),
            _q('___ you who called me yesterday?', 'Was it', 'Was it', 'Is it', 'Did it', 'A'),
            _q('It wasn’t the rain ___ ruined the match.', 'who', 'that', 'which', 'where', 'A'),
            _q('It is hard work ___ brings real success.', 'who', 'that', 'which', 'where', 'A'),
            _q('___ in London that they first met each other.', 'It was', 'It was', 'It is', 'There was', 'A'),
            _q('It is the manager ___ makes all the important decisions.', 'that', 'who', 'which', 'where', 'A'),
            _q('It wasn’t me ___ broke the glass.', 'who', 'who', 'that', 'which', 'A'),
            _q('___ the price that surprised me the most.', 'It is', 'It was', 'It has', 'There is', 'A'),
            _q('It is patience ___ you need most in language learning.', 'who', 'that', 'which', 'where', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_08_participle_clauses',
        level="C1",
        title='Participle Clauses (Advanced)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Participle clauses – gapni qisqartirish va murakkab ma’noni (vaqt, sabab, shart, natija) ifodalash uchun -ing yoki -ed shakllari ishlatiladi.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Причастные обороты – для сокращения предложений и выражения времени, причины, условия или результата.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Having finished the report, she went home early.\n"
            "Seen from the mountain, the view was breathtaking.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Not knowing what to do, he asked for help.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Present participle (-ing) – bir vaqtda yoki sabab\n"
            "🟢 2. Past participle (-ed) – passiv ma’no\n"
            "🟢 3. Perfect participle (having + V3) – oldin sodir bo‘lgan harakat\n"
            "🟢 4. Subject bir xil bo‘lishi shart (agar farqli bo‘lsa, to‘liq gap ishlatiladi)\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "Having lived in Uzbekistan for ten years, he speaks Uzbek fluently.\n"
            "Encouraged by her results, she decided to take the C1 exam.\n"
            "Not understanding the question, I asked the teacher to repeat it.\n"
            "Seen from above, the city looks like a painting.\n"
            "Having completed all the tasks, the team celebrated their success."
        ),
        questions=[
            _q('___ the exam, she felt very relieved.', 'Finished', 'Having finished', 'Finishing', 'To finish', 'A'),
            _q('___ from the top of the tower, the view is amazing.', 'Seen', 'Seen', 'Seeing', 'To see', 'A'),
            _q('___ what to say, he remained silent.', 'Not knowing', 'Not known', 'Not to know', 'Knowing not', 'A'),
            _q('___ by her teacher, she decided to take the C1 exam.', 'Encouraged', 'Encouraged', 'Encouraging', 'To encourage', 'A'),
            _q('___ in Tashkent for many years, she knows the city very well.', 'Lived', 'Having lived', 'Living', 'To live', 'A'),
            _q('The book, ___ last year, became a bestseller.', 'published', 'published', 'publishing', 'to publish', 'A'),
            _q('___ tired after the long journey, he went straight to bed.', 'Feeling', 'Feeling', 'Felt', 'To feel', 'A'),
            _q('___ all the preparations, the team was ready.', 'Made', 'Having made', 'Making', 'To make', 'A'),
            _q('The girl, ___ by the news, started crying.', 'shocked', 'shocked', 'shocking', 'to shock', 'A'),
            _q('___ the bad weather, we still went hiking.', 'Despite', 'Despite', 'In spite', 'Although', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_09_hedging_and_boosting',
        level="C1",
        title='Hedging and Boosting (Softening & Strengthening Language)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Hedging – fikrni yumshatish (maybe, perhaps, tend to, seem to, rather)Boosting – fikrni kuchaytirish (definitely, absolutely, clearly, undoubtedly)C1 darajasida bu ikkalasini muvozanatli ishlatish juda muhim.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Hedging – смягчение высказывания, Boosting – усиление.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "It seems to me that the solution is rather complicated.\n"
            "This is undoubtedly the best option.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "I wouldn’t say that the film was particularly interesting.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Hedging: seem, appear, tend to, rather, quite, somewhat, possibly\n"
            "🟢 2. Boosting: definitely, absolutely, clearly, undoubtedly, certainly\n"
            "🟢 3. Academic va formal nutqda hedging ko‘proq ishlatiladi\n"
            "🟢 4. Boosting – kuchli ishonch bildirish uchun\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "It appears that the economy is improving slightly.\n"
            "This method is undoubtedly more effective than the previous one.\n"
            "I tend to agree with your point of view.\n"
            "The results seem to suggest that more research is needed.\n"
            "We are clearly making progress in this area."
        ),
        questions=[
            _q('___ the results suggest that the theory is correct.', 'Clearly', 'It appears that', 'Definitely', 'Absolutely', 'A'),
            _q('This solution is ___ complicated.', 'definitely', 'rather', 'undoubtedly', 'absolutely', 'A'),
            _q('I ___ agree with your opinion.', 'tend to', 'definitely', 'absolutely', 'clearly', 'A'),
            _q('The experiment was ___ a success.', 'somewhat', 'undoubtedly', 'rather', 'possibly', 'A'),
            _q('It ___ that we need more time.', 'seems', 'seems', 'definitely', 'absolutely', 'A'),
            _q('She is ___ the best candidate for the job.', 'rather', 'undoubtedly', 'somewhat', 'possibly', 'A'),
            _q('The data ___ indicate a positive trend.', 'tend to', 'absolutely', 'definitely', 'clearly', 'A'),
            _q('This is ___ the most difficult exam I have ever taken.', 'somewhat', 'by far', 'rather', 'possibly', 'A'),
            _q('___ we should consider other options.', 'It seems that', 'It seems that', 'Definitely', 'Absolutely', 'A'),
            _q('The problem is ___ more serious than we thought.', 'rather', 'somewhat', 'undoubtedly', 'absolutely', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_10_advanced_passive_structures',
        level="C1",
        title='Advanced Passive Structures',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Advanced passive – murakkab zamonlarda, modal bilan va causative bilan birga qo‘llaniladi.get + V3 (informal), be + V3 (formal), have something done.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Продвинутый пассивный залог – в сложных временах, с модальными глаголами и causative.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "The report is being prepared at the moment.\n"
            "The house had been painted before we moved in.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "The problem hasn’t been solved yet.\n"
            "\n"
            "❓ Question\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Has the document been checked by the manager?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Continuous passive: is/are being + V3\n"
            "🟢 2. Perfect passive: have/has been + V3\n"
            "🟢 3. Modal passive: must be done, should have been done\n"
            "🟢 4. Causative passive: have/get something done\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "The new policy is being discussed by the government.\n"
            "All the work had been completed before the deadline.\n"
            "The car must be serviced regularly.\n"
            "She has had her hair cut short.\n"
            "The mistake should have been noticed earlier."
        ),
        questions=[
            _q('The report ___ at the moment.', 'is prepared', 'is being prepared', 'has prepared', 'was prepared', 'A'),
            _q('All the work ___ before we arrived.', 'had completed', 'had been completed', 'has been completed', 'was completing', 'A'),
            _q('The car ___ regularly.', 'must service', 'must be serviced', 'must have serviced', 'must serviced', 'A'),
            _q('She ___ her hair cut short last week.', 'has', 'has had', 'had', 'have', 'A'),
            _q('The mistake ___ earlier.', 'should notice', 'should have been noticed', 'should be noticed', 'should noticed', 'A'),
            _q('The new bridge ___ by next year.', 'will complete', 'will have been completed', 'will be completing', 'will completed', 'A'),
            _q('The documents ___ by the lawyer.', 'are checking', 'are being checked', 'have checked', 'checked', 'A'),
            _q('The problem ___ yet.', 'hasn’t solved', 'hasn’t been solved', 'didn’t solve', 'wasn’t solved', 'A'),
            _q('The house ___ before we moved in.', 'had painted', 'had been painted', 'has painted', 'was painting', 'A'),
            _q('The meeting ___ tomorrow at 10 a.m.', 'is holding', 'is to be held', 'holds', 'will hold', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_11_reduced_relative_clauses',
        level="C1",
        title='Reduced Relative Clauses',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Reduced relative clauses – to‘liq relative clause ni qisqartirish orqali gapni ixchamlashtirish.\n"
            "Active: who/which/that + verb → -ingPassive: who/which/that + be + V3 → V3 (past participle)\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Сокращённые придаточные определительные – для сокращения предложений с who/which/that.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "The man standing at the door is my teacher.\n"
            "The book written by Orwell is a classic.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "The students not having finished the test were asked to stay.\n"
            "\n"
            "❓ Question\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Is this the report sent yesterday?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Active reduced: -ing form (the girl wearing red)\n"
            "🟢 2. Passive reduced: past participle (the car repaired last week)\n"
            "🟢 3. Perfect reduced: having + V3 (students having passed the exam)\n"
            "🟢 4. Faqat defining relative clauses da qisqartiriladi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "The woman sitting next to me is a famous writer.\n"
            "All the documents signed by the manager are valid.\n"
            "Students not understanding the question should ask for help.\n"
            "The film directed by Nolan won many awards.\n"
            "Having completed the course, she received her certificate."
        ),
        questions=[
            _q('The man ___ at the door is my boss.', 'who stands', 'standing', 'stood', 'who standing', 'A'),
            _q('The book ___ by Orwell is a classic.', 'written', 'written', 'who wrote', 'writing', 'A'),
            _q('Students ___ the test were asked to stay.', 'not finishing', 'not having finished', 'not finished', 'who not finish', 'A'),
            _q('The car ___ last week is now for sale.', 'repaired', 'repaired', 'repairing', 'who repaired', 'A'),
            _q('The girl ___ a red dress is my sister.', 'wearing', 'wearing', 'wore', 'who wears', 'A'),
            _q('All applicants ___ the exam will be contacted.', 'passing', 'having passed', 'passed', 'who pass', 'A'),
            _q('The report ___ yesterday is on your desk.', 'sent', 'sent', 'sending', 'who sent', 'A'),
            _q('People ___ in big cities often feel stressed.', 'living', 'living', 'lived', 'who live', 'A'),
            _q('The house ___ in 1990 is now a museum.', 'built', 'built', 'building', 'who built', 'A'),
            _q('The team ___ the championship celebrated all night.', 'winning', 'having won', 'won', 'who win', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_12_the_subjunctive_mood',
        level="C1",
        title='The Subjunctive Mood',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Subjunctive – formal va rasmiy uslubda “agar ... bo‘lsa” yoki talab, taklif, istak bildirish uchun ishlatiladi.\n"
            "Present subjunctive: base form (I suggest he go)Past subjunctive: were (If I were you...)\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Сослагательное наклонение – для формальных предложений, требований, пожеланий и гипотетических ситуаций.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "I suggest that he apologize immediately.\n"
            "It is essential that she be informed.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "It is important that we not make the same mistake.\n"
            "\n"
            "❓ Question\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Is it necessary that everyone attend the meeting?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. After suggest, recommend, insist, demand, require → base form\n"
            "🟢 2. After It is important/essential/vital → base form\n"
            "🟢 3. Past subjunctive: If I were / If he were (barcha shaxslar uchun were)\n"
            "🟢 4. Formal yozuv va rasmiy nutqda ko‘p uchraydi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "The doctor recommended that she rest for two weeks.\n"
            "It is crucial that the report be finished by Friday.\n"
            "If I were the manager, I would change the policy.\n"
            "We insist that he tell the truth.\n"
            "It is vital that everyone be present at the conference."
        ),
        questions=[
            _q('I suggest that he ___ immediately.', 'leaves', 'leave', 'left', 'leaving', 'A'),
            _q('It is essential that she ___ informed.', 'is', 'be', 'was', 'been', 'A'),
            _q('If I ___ you, I would accept the offer.', 'was', 'were', 'am', 'be', 'A'),
            _q('The committee recommended that the project ___ postponed.', 'is', 'be', 'was', 'been', 'A'),
            _q('It is important that we ___ the same mistake again.', 'not make', 'not make', 'not making', 'don’t make', 'A'),
            _q('We demand that the manager ___ the truth.', 'tells', 'tell', 'told', 'telling', 'A'),
            _q('If she ___ here, she would know what to do.', 'was', 'were', 'is', 'be', 'A'),
            _q('It is vital that everyone ___ the deadline.', 'meets', 'meet', 'met', 'meeting', 'A'),
            _q('The teacher insisted that the students ___ quiet.', 'are', 'be', 'were', 'been', 'A'),
            _q('It is necessary that the document ___ signed today.', 'is', 'be', 'was', 'been', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_13_advanced_reported_speech_reporting_verbs',
        level="C1",
        title='Advanced Reported Speech & Reporting Verbs',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Advanced reported speech – oddiy “said” o‘rniga reporting verbs (admit, deny, suggest, claim, warn, accuse va h.k.) bilan birga ishlatiladi.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Продвинутая косвенная речь с различными reporting verbs.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "She admitted that she had made a mistake.\n"
            "He suggested going out for dinner.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "The manager denied having seen the report.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. admit/deny + -ing / that-clause\n"
            "🟢 2. suggest + -ing / that + should\n"
            "🟢 3. accuse sb of + -ing\n"
            "🟢 4. warn sb (not) to + infinitive\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "She denied stealing the money.\n"
            "He accused me of lying.\n"
            "The teacher warned the students not to be late.\n"
            "They claimed to have seen a UFO.\n"
            "I recommend that you book the tickets early."
        ),
        questions=[
            _q('She ___ stealing the money.', 'denied', 'denied', 'denied to', 'denied that', 'A'),
            _q('He ___ me of lying to the boss.', 'accused', 'accused', 'suggested', 'warned', 'A'),
            _q('The teacher ___ the students not to be late.', 'suggested', 'warned', 'admitted', 'claimed', 'A'),
            _q('They ___ to have seen a UFO.', 'admitted', 'claimed', 'denied', 'suggested', 'A'),
            _q('I ___ booking the tickets early.', 'suggest', 'suggest', 'recommend', 'warn', 'A'),
            _q('She ___ having made a mistake.', 'admitted', 'admitted', 'denied', 'claimed', 'A'),
            _q('The manager ___ seeing the report.', 'denied', 'denied', 'admitted', 'suggested', 'A'),
            _q('He ___ going out for dinner.', 'suggested', 'suggested', 'warned', 'accused', 'A'),
            _q('They ___ us to leave immediately.', 'warned', 'warned', 'suggested', 'denied', 'A'),
            _q('She ___ that she had forgotten the meeting.', 'admitted', 'admitted', 'denied', 'accused', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_14_nominalisation',
        level="C1",
        title='Nominalisation',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Nominalisation – fe’l yoki sifatni otga aylantirish orqali gapni ixcham va formal qilish.\n"
            "Bu akademik va rasmiy matnlarda juda ko‘p ishlatiladi.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Номинализация – превращение глагола или прилагательного в существительное для более формального стиля.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "The company made a decision to expand. → The company’s decision to expand...\n"
            "People are worried about climate change. → There is growing concern about climate change.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Common endings: -tion, -ment, -ness, -ity, -ance\n"
            "🟢 2. Fe’l → ot: decide → decision, improve → improvement\n"
            "🟢 3. Sifat → ot: important → importance\n"
            "🟢 4. Natijada gap qisqaradi va formal bo‘ladi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "The government is investigating the problem. → The government is carrying out an investigation into the problem.\n"
            "She succeeded because she worked hard. → Her success was due to hard work.\n"
            "It is important to protect the environment. → The protection of the environment is important.\n"
            "The team improved rapidly. → There was a rapid improvement in the team’s performance."
        ),
        questions=[
            _q('The company made a ___ to expand.', 'decide', 'decision', 'deciding', 'decided', 'A'),
            _q('There is growing ___ about climate change.', 'worry', 'concern', 'worrying', 'worried', 'A'),
            _q('Her ___ was due to hard work.', 'succeed', 'success', 'successful', 'succeeding', 'A'),
            _q('The ___ of the environment is very important.', 'protect', 'protection', 'protecting', 'protected', 'A'),
            _q('There was a rapid ___ in the team’s performance.', 'improve', 'improvement', 'improving', 'improved', 'A'),
            _q('The government is carrying out an ___ into the problem.', 'investigate', 'investigation', 'investigating', 'investigated', 'A'),
            _q('The ___ of the new policy caused a lot of debate.', 'introduce', 'introduction', 'introducing', 'introduced', 'A'),
            _q('His ___ to help was greatly appreciated.', 'willing', 'willingness', 'willing', 'will', 'A'),
            _q('The ___ in sales was unexpected.', 'increase', 'increase', 'increasing', 'increased', 'A'),
            _q('The report highlighted the ___ of the situation.', 'serious', 'seriousness', 'seriously', 'serious', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_15_fronting_for_emphasis',
        level="C1",
        title='Fronting for Emphasis',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Fronting – gap boshiga muhim so‘z yoki iborani chiqarib, uni kuchli ta’kid qilish.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Фронтинг – вынесение важной части предложения в начало для усиления.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "What I need most is more time.\n"
            "The one thing I regret is not studying harder.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Never in my life have I seen such beauty.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. What / The thing / The one thing + clause\n"
            "🟢 2. Negative adverbials bilan inversion birga ishlatiladi\n"
            "🟢 3. As for / Regarding / As far as ... is concerned\n"
            "🟢 4. Kuchli emphasis va formal nutqda ishlatiladi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "What I really want is a quiet holiday.\n"
            "The one thing I will never forget is her kindness.\n"
            "As for the price, it is quite reasonable.\n"
            "Never before have I been so impressed.\n"
            "The person I admire most is my grandmother."
        ),
        questions=[
            _q('___ I need most is more time.', 'What', 'What', 'The thing', 'The one thing', 'A'),
            _q('___ I regret is not studying harder.', 'The one thing', 'The one thing', 'What', 'As for', 'A'),
            _q('___ the price, it is quite reasonable.', 'As for', 'As for', 'What', 'The thing', 'A'),
            _q('___ in my life have I seen such beauty.', 'Never', 'Never', 'What', 'The one thing', 'A'),
            _q('___ I admire most is my grandmother.', 'The person', 'The person', 'What', 'As for', 'A'),
            _q('___ we need to do is start again.', 'All', 'All', 'What', 'The thing', 'A'),
            _q('___ the weather, it was perfect.', 'As for', 'As for', 'What', 'Never', 'A'),
            _q('___ I will never forget is her smile.', 'The one thing', 'The one thing', 'What', 'As for', 'A'),
            _q('___ before have I been so impressed.', 'Never', 'Never', 'What', 'The thing', 'A'),
            _q('___ really matters is your health.', 'What', 'What', 'The one thing', 'As for', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_16_advanced_relative_clauses',
        level="C1",
        title='Advanced Relative Clauses (non-defining, reduced, with prepositions)',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Advanced relative clauses – non-defining (qo‘shimcha ma’lumot, vergul bilan), reduced (qisqartirilgan) va preposition bilan (to whom, in which va h.k.).\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Продвинутые придаточные определительные – неопределяющие, сокращённые и с предлогами.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "My brother, who lives in London, is a doctor.\n"
            "This is the book in which I found the answer.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "The manager, whom I respect greatly, has retired.\n"
            "\n"
            "❓ Question\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Is this the hotel where you stayed last year?\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Non-defining – vergul bilan, that ishlatilmaydi\n"
            "🟢 2. Reduced – who/which + be + V3 → V3 yoki -ing\n"
            "🟢 3. Preposition + relative pronoun (to whom, in which, for which)\n"
            "🟢 4. Formal uslubda ko‘p ishlatiladi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "Tashkent, which is the capital of Uzbekistan, is a very modern city.\n"
            "The scientist, whose theory changed the world, won the Nobel Prize.\n"
            "This is the house in which I grew up.\n"
            "The problem, having been discussed for hours, was finally solved.\n"
            "She is the only person to whom I can talk openly."
        ),
        questions=[
            _q('My brother, ___ lives in London, is a doctor.', 'who', 'who', 'which', 'that', 'A'),
            _q('This is the book ___ I found the answer.', 'in which', 'in which', 'which in', 'that in', 'A'),
            _q('Tashkent, ___ is the capital, is very modern.', 'which', 'which', 'that', 'who', 'A'),
            _q('The scientist, ___ theory changed the world, won the prize.', 'whose', 'whose', 'who', 'which', 'A'),
            _q('The problem, ___ for hours, was finally solved.', 'having discussed', 'having been discussed', 'discussed', 'discussing', 'A'),
            _q('She is the only person ___ I can talk openly.', 'to whom', 'to whom', 'who to', 'whom to', 'A'),
            _q('The hotel ___ we stayed last year is now closed.', 'where', 'where', 'which', 'that', 'A'),
            _q('The report, ___ yesterday, is on your desk.', 'sent', 'sent', 'sending', 'who sent', 'A'),
            _q('This is the reason ___ I left the company.', 'for which', 'for which', 'which for', 'that for', 'A'),
            _q('The man ___ I borrowed the money has moved to another city.', 'from whom', 'from whom', 'who from', 'whom from', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_17_emphasis_with_do_does_did_and_other_structures',
        level="C1",
        title='Emphasis with "do/does/did" and Other Structures',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Emphasis – oddiy gapni kuchaytirish uchun do/does/did yoki boshqa strukturalar (what, all, the only thing va h.k.) ishlatiladi.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Усиление высказывания с помощью do/does/did и других структур.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "I do understand your point.\n"
            "What I need is more time.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "She didn’t like the film at all.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. do/does/did – kuchli ta’kid uchun\n"
            "🟢 2. What / All / The only thing + clause\n"
            "🟢 3. Indeed, certainly, absolutely bilan birga ishlatiladi\n"
            "🟢 4. Formal va nutqda juda kuchli ta’sir beradi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "I do appreciate your help.\n"
            "What really matters is your health.\n"
            "She did warn us about the danger.\n"
            "The only thing I want is peace and quiet.\n"
            "He certainly knows what he is doing."
        ),
        questions=[
            _q('I ___ understand your point of view.', 'do', 'do', 'did', 'does', 'A'),
            _q('___ I really want is a long holiday.', 'What', 'What', 'All', 'The only thing', 'A'),
            _q('She ___ warn us about the danger.', 'do', 'did', 'does', 'doing', 'A'),
            _q('The only thing ___ is peace and quiet.', 'I want', 'I want', 'what I want', 'all I want', 'A'),
            _q('He ___ knows what he is doing.', 'certainly', 'certainly', 'does', 'did', 'A'),
            _q('___ really matters is your health.', 'What', 'What', 'All', 'The only thing', 'A'),
            _q('I ___ appreciate your help very much.', 'do', 'do', 'did', 'does', 'A'),
            _q('___ she told me was completely wrong.', 'What', 'What', 'All', 'The only thing', 'A'),
            _q('They ___ finish the project on time.', 'did', 'did', 'do', 'does', 'A'),
            _q('The one thing ___ I regret is not studying harder.', 'what', 'that', 'which', 'who', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_18_discourse_markers_advanced_linking_words',
        level="C1",
        title='Discourse Markers & Advanced Linking Words',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Discourse markers – gaplar o‘rtasidagi munosabatni ko‘rsatuvchi so‘zlar (however, nevertheless, furthermore, as a result, on the other hand va h.k.).\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Дискурсивные маркеры – слова, показывающие связь между идеями.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "The weather was bad.\n"
            "Nevertheless, we enjoyed the trip.\n"
            "Furthermore, the price is very reasonable.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "He studied hard.\n"
            "However, he failed the exam.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Contrast: however, nevertheless, on the other hand\n"
            "🟢 2. Addition: furthermore, moreover, in addition\n"
            "🟢 3. Result: as a result, consequently, therefore\n"
            "🟢 4. Formal matnlarda juda muhim\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "The exam was extremely difficult.\n"
            "Nevertheless, most students passed.\n"
            "The new policy is expensive.\n"
            "Furthermore, it is not very popular.\n"
            "He missed the train.\n"
            "As a result, he arrived late.\n"
            "On the other hand, the job offers a good salary.\n"
            "Moreover, the company provides excellent training."
        ),
        questions=[
            _q('The weather was bad. ___, we enjoyed the trip.', 'However', 'Nevertheless', 'Furthermore', 'As a result', 'A'),
            _q('The new policy is expensive. ___, it is not popular.', 'However', 'Nevertheless', 'Furthermore', 'Therefore', 'A'),
            _q('He missed the train. ___, he arrived late.', 'However', 'Nevertheless', 'As a result', 'Furthermore', 'A'),
            _q('The job is stressful. ___, it offers a good salary.', 'However', 'On the other hand', 'Furthermore', 'As a result', 'A'),
            _q('The product is high quality. ___, it is quite expensive.', 'Nevertheless', 'However', 'Furthermore', 'Moreover', 'A'),
            _q('She studied hard. ___, she passed with flying colours.', 'However', 'Nevertheless', 'As a result', 'On the other hand', 'A'),
            _q('The plan is good. ___, we need more time.', 'However', 'However', 'Furthermore', 'As a result', 'A'),
            _q('The company is growing fast. ___, it needs more staff.', 'Nevertheless', 'Moreover', 'However', 'As a result', 'A'),
            _q('He is very talented. ___, he is quite modest.', 'However', 'On the other hand', 'Furthermore', 'Therefore', 'A'),
            _q('The meeting was long. ___, it was very productive.', 'Nevertheless', 'Nevertheless', 'Furthermore', 'As a result', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_19_advanced_conditionals_review_inverted_conditionals',
        level="C1",
        title='Advanced Conditionals Review & Inverted Conditionals',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Advanced conditionals – inverted shakllar (Were I you..., Had I known..., Should you need...).\n"
            "Bu formal va adabiy uslubda ishlatiladi.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Продвинутые условные предложения и инвертированные формы.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Were I you, I would accept the offer.\n"
            "Had I known the truth, I would have acted differently.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Should you not arrive on time, please call me.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Were + subject (If I were → Were I)\n"
            "🟢 2. Had + subject + V3 (If I had known → Had I known)\n"
            "🟢 3. Should + subject (If you should need → Should you need)\n"
            "🟢 4. Formal va yozma nutqda juda kuchli ta’sir beradi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "Were I in your position, I would take the job.\n"
            "Had she known the risks, she would never have invested.\n"
            "Should you require any assistance, do not hesitate to contact me.\n"
            "Were it not for your help, I would have failed the exam.\n"
            "Had we arrived earlier, we would have seen the show."
        ),
        questions=[
            _q('___ I you, I would accept the offer.', 'Were', 'Were', 'If', 'Had', 'A'),
            _q('___ I known the truth, I would have acted differently.', 'Were', 'Had', 'If', 'Should', 'A'),
            _q('___ you require any help, please call me.', 'Were', 'Had', 'Should', 'If', 'A'),
            _q('___ it not for your support, I would have given up.', 'Were', 'Were', 'Had', 'Should', 'A'),
            _q('___ we arrived earlier, we would have seen the beginning.', 'Were', 'Had', 'Should', 'If', 'A'),
            _q('___ you not pass the test, you can retake it next month.', 'Were', 'Had', 'Should', 'If', 'A'),
            _q('___ I the manager, I would change the policy.', 'Were', 'Had', 'Should', 'If', 'A'),
            _q('___ she studied harder, she would have passed.', 'Were', 'Had', 'Should', 'If', 'A'),
            _q('___ you need more information, let me know.', 'Were', 'Had', 'Should', 'If', 'A'),
            _q('___ it not for the rain, the match would have continued.', 'Were', 'Had', 'Should', 'If', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_20_advanced_passive_with_reporting_verbs',
        level="C1",
        title='Advanced Passive with Reporting Verbs',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Reporting verbs bilan passive – “It is said that...”, “He is believed to have...”, “The company is reported to be...” kabi strukturalar.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Пассив с глаголами сообщения – It is said that..., He is believed to..., The company is reported to...\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "It is said that the president will resign.\n"
            "The company is reported to be losing money.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "The minister is not thought to have known about the scandal.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. It is said/believed/reported/thought + that-clause\n"
            "🟢 2. Subject + is said/believed + to + infinitive / to have + V3\n"
            "🟢 3. Formal yangiliklar va rasmiy matnlarda juda ko‘p ishlatiladi\n"
            "🟢 4. Present → to + infinitive, Past → to have + V3\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "It is believed that the thief escaped through the window.\n"
            "The president is expected to make a statement tomorrow.\n"
            "The company is reported to have lost millions.\n"
            "She is thought to be one of the best writers of her generation.\n"
            "The new vaccine is said to be very effective."
        ),
        questions=[
            _q('It ___ that the president will resign soon.', 'is said', 'is said', 'was said', 'has said', 'A'),
            _q('The company ___ to be losing money.', 'is reported', 'is reported', 'was reported', 'has reported', 'A'),
            _q('The minister ___ to have known about the scandal.', 'is not thought', 'is not thought', 'was not thought', 'has not thought', 'A'),
            _q('She ___ to be one of the best writers alive.', 'is believed', 'is believed', 'was believed', 'has believed', 'A'),
            _q('The new drug ___ to have serious side effects.', 'is said', 'is said', 'was said', 'has said', 'A'),
            _q('It ___ that the meeting will be postponed.', 'is expected', 'is expected', 'was expected', 'has expected', 'A'),
            _q('The team ___ to have won the championship.', 'is reported', 'is reported', 'was reported', 'has reported', 'A'),
            _q('He ___ to be the richest man in the country.', 'is thought', 'is thought', 'was thought', 'has thought', 'A'),
            _q('The building ___ to have been damaged in the fire.', 'is believed', 'is believed', 'was believed', 'has believed', 'A'),
            _q('It ___ that the price will rise next month.', 'is predicted', 'is predicted', 'was predicted', 'has predicted', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_21_gerunds_and_infinitives_advanced_patterns',
        level="C1",
        title='Gerunds and Infinitives – Advanced Patterns',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Advanced gerund va infinitive – ma’no farqi va murakkab fe’llar bilan qo‘llanish (remember, regret, stop, try, mean, go on va boshqalar).\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Продвинутые случаи употребления герундия и инфинитива с изменением смысла.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "I remember locking the door.\n"
            "(xotirlayman)I remember to lock the door.\n"
            "(eslatib qo‘yaman)\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "She stopped to smoke.\n"
            "(to‘xtab, chekdi)She stopped smoking.\n"
            "(cheklashni tashladi)\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Remember / regret / forget + -ing (o‘tmish harakat)\n"
            "🟢 2. Remember / forget / regret + to + infinitive (kelajak / eslatish)\n"
            "🟢 3. Stop + -ing (to‘xtatish), stop + to + infinitive (to‘xtab, boshqa ish qilish)\n"
            "🟢 4. Try + -ing (sinab ko‘rish), try + to + infinitive (harakat qilish)\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "I regret telling her the secret.\n"
            "I regret to inform you that the flight is cancelled.\n"
            "She tried to open the door, but it was locked.\n"
            "She tried opening the window instead.\n"
            "He went on talking even though everyone was bored."
        ),
        questions=[
            _q('I remember ___ the door before I left. (xotira)', 'to lock', 'locking', 'lock', 'locked', 'A'),
            _q('I regret ___ you that the meeting is cancelled. (rasmiy)', 'telling', 'to tell', 'tell', 'told', 'A'),
            _q('She stopped ___ when she saw me. (to‘xtab)', 'talking', 'to talk', 'talk', 'talked', 'A'),
            _q('Try ___ the window if the door is locked. (sinab ko‘rish)', 'to open', 'opening', 'open', 'opened', 'A'),
            _q('He went on ___ even after the bell rang.', 'to speak', 'speaking', 'speak', 'spoken', 'A'),
            _q('I forgot ___ the lights when I left. (esdan chiqarish)', 'to turn off', 'turning off', 'turn off', 'turned off', 'A'),
            _q('She tried ___ the problem differently.', 'to solve', 'solving', 'solve', 'solved', 'A'),
            _q('I regret ___ so rude to her yesterday.', 'to be', 'being', 'be', 'been', 'A'),
            _q('Remember ___ the report by Friday. (eslatish)', 'submitting', 'to submit', 'submit', 'submitted', 'A'),
            _q('He stopped ___ after the doctor’s warning.', 'to smoke', 'smoking', 'smoke', 'smoked', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_22_advanced_articles_and_determiners',
        level="C1",
        title='Advanced Articles and Determiners',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Advanced artikllar – the, a/an va zero article ning murakkab qoidalari (abstract nouns, institutions, unique items, generalizations).\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Продвинутые правила употребления артиклей и детерминативов.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "The more you practise, the better you get.\n"
            "She plays the piano beautifully.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "He went to hospital.\n"
            "(British English – kasalxonaga)\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. The + comparative (the more..., the better...)\n"
            "🟢 2. Musical instruments: play the piano / the guitar\n"
            "🟢 3. Institutions: go to hospital / school (British – zero article)\n"
            "🟢 4. Abstract nouns: love, happiness – odatda zero article\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "The richer he became, the more unhappy he felt.\n"
            "She is learning to play the violin.\n"
            "He was taken to hospital after the accident.\n"
            "Happiness cannot be bought with money.\n"
            "The United Nations was founded in 1945."
        ),
        questions=[
            _q('___ more you practise, ___ better you become.', 'The / the', 'The / the', 'A / a', '– / –', 'A'),
            _q('She plays ___ piano every evening.', 'a', 'the', '–', 'an', 'A'),
            _q('He was taken to ___ hospital after the accident.', 'the', 'a', '–', 'an', 'A'),
            _q('___ happiness cannot be bought.', 'The', 'A', '–', 'An', 'A'),
            _q('___ United Nations was founded in 1945.', 'A', 'The', '–', 'An', 'A'),
            _q('She went to ___ school at the age of 6.', 'the', 'a', '–', 'an', 'A'),
            _q('___ love is a complicated emotion.', 'The', 'A', '–', 'An', 'A'),
            _q('The ___ older he gets, the ___ wiser he becomes.', '– / –', 'the / the', 'a / a', 'more / more', 'A'),
            _q('He is learning to play ___ guitar.', 'a', 'the', '–', 'an', 'A'),
            _q('___ knowledge is power.', 'The', 'A', '–', 'An', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_23_ellipsis_and_substitution',
        level="C1",
        title='Ellipsis and Substitution',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Ellipsis – takrorlanadigan so‘zlarni tashlab qoldirish, Substitution – so‘zlarni boshqa so‘zlar bilan almashtirish (one, ones, do, so, neither, nor).\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Эллипсис и субституция – пропуск повторяющихся элементов и их замена.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "She can speak French and so can I.\n"
            "I like the red car, but I prefer the blue one.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "He didn’t pass, neither did I.\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. So / neither / nor – qisqa javoblar\n"
            "🟢 2. One / ones – countable nouns o‘rnida\n"
            "🟢 3. Do / does / did – fe’l o‘rnida\n"
            "🟢 4. Formal va tabiiy nutqda juda ko‘p ishlatiladi\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "She wants to go to Spain and so do I.\n"
            "I don’t like black coffee, but I love the white one.\n"
            "He passed the exam and so did his brother.\n"
            "I haven’t finished yet, but I will have by tomorrow.\n"
            "She can play the piano, and her sister can too."
        ),
        questions=[
            _q('She can speak French and ___ can I.', 'so', 'so', 'neither', 'nor', 'A'),
            _q('I like the red car, but I prefer the blue ___.', 'car', 'one', 'ones', 'it', 'A'),
            _q('He didn’t pass the test, and ___ did I.', 'so', 'neither', 'neither', 'nor', 'A'),
            _q('I haven’t seen the film yet, but I ___ soon.', 'will', 'will', 'do', 'have', 'A'),
            _q('She loves classical music and her brother ___ too.', 'does', 'does', 'is', 'has', 'A'),
            _q('I don’t like black coffee, but I love the white ___.', 'it', 'one', 'ones', 'coffee', 'A'),
            _q('They arrived late and ___ did we.', 'so', 'so', 'neither', 'nor', 'A'),
            _q('He can swim and his sister ___ .', 'can too', 'can too', 'does', 'is', 'A'),
            _q('I haven’t finished the report, but I ___ by Friday.', 'will', 'will', 'have', 'do', 'A'),
            _q('She passed the exam and ___ did her best friend.', 'so', 'so', 'neither', 'nor', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_24_collocation_and_lexical_cohesion',
        level="C1",
        title='Collocation and Lexical Cohesion',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Collocation – so‘zlarning tabiiy birikmasi (make a decision, take responsibility, heavy rain).\n"
            "Lexical cohesion – matnni bog‘lash uchun sinonimlar, antonimlar va shunga o‘xshash so‘zlardan foydalanish.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Коллокации и лексическая связность – естественные сочетания слов и связывание текста.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "She made a big decision last week.\n"
            "The heavy rain caused serious flooding.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "She did a big decision.\n"
            "(xato)\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Common collocations: make a mistake, take a photo, pay attention\n"
            "🟢 2. Strong collocations: heavy rain, strong wind, bitter disappointment\n"
            "🟢 3. Lexical chains – sinonimlar bilan matnni bog‘lash\n"
            "🟢 4. C1 darajasida tabiiy va boy lug‘at ko‘rsatish uchun muhim\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "She took full responsibility for the mistake.\n"
            "The government is paying close attention to the issue.\n"
            "There was a sharp increase in prices last month.\n"
            "He gave a detailed explanation of the problem.\n"
            "The team achieved remarkable success despite difficulties."
        ),
        questions=[
            _q('She ___ a big decision last week.', 'did', 'made', 'took', 'gave', 'A'),
            _q('The ___ rain caused serious flooding.', 'strong', 'heavy', 'big', 'hard', 'A'),
            _q('He ___ full responsibility for the error.', 'made', 'took', 'did', 'gave', 'A'),
            _q('Please ___ close attention to the instructions.', 'make', 'pay', 'take', 'give', 'A'),
            _q('There was a ___ increase in prices.', 'heavy', 'sharp', 'strong', 'big', 'A'),
            _q('She gave a ___ explanation of the problem.', 'heavy', 'detailed', 'sharp', 'strong', 'A'),
            _q('The team achieved ___ success.', 'heavy', 'remarkable', 'sharp', 'strong', 'A'),
            _q('He ___ a lot of effort into the project.', 'made', 'put', 'took', 'gave', 'A'),
            _q('We need to ___ the problem seriously.', 'make', 'take', 'do', 'give', 'A'),
            _q('The news caused a ___ disappointment.', 'heavy', 'bitter', 'sharp', 'strong', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='c1_25_complex_sentence_structures_final_review',
        level="C1",
        title='Complex Sentence Structures & Final Review',
        rule=(
            "📌 1. QOIDA (RULE)\n"
            "🇺🇿 O‘zbekcha:\n"
            "Complex sentences – bir nechta clause larni birlashtirish, participle clauses, cleft sentences, inversion va boshqa advanced strukturalarni birga ishlatish.\n"
            "Bu C1 darajasining eng muhim ko‘nikmasi.\n"
            "\n"
            "🇷🇺 Русский:\n"
            "Сложные предложения – комбинирование нескольких структур для естественного и продвинутого стиля.\n"
            "\n"
            "📌 2. GAP TUZILISHI\n"
            "✅ Positive\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Having studied hard all year, not only did she pass the exam, but she also got the highest score.\n"
            "\n"
            "❌ Negative\n"
            "Formula:\n"
            "\n"
            "Examples:\n"
            "Not only she passed the exam, but she also got the highest score.\n"
            "(xato)\n"
            "\n"
            "📌 3. MAXSUS QOIDALAR\n"
            "🟢 1. Participle clause + inversion + cleft\n"
            "🟢 2. Not only ... but also ... bilan inversion\n"
            "🟢 3. Although / despite + reduced clause\n"
            "🟢 4. C1 darajasida tabiiy va murakkab gaplar qurish uchun asosiy ko‘nikma\n"
            "\n"
            "📌 4. MISOLLAR\n"
            "Having worked in the company for ten years, not only did he receive a promotion, but he was also given a substantial bonus.\n"
            "Although exhausted after the long journey, she still managed to finish the report.\n"
            "What surprised me most was how quickly she adapted to the new environment.\n"
            "Were it not for your constant support, I would never have achieved this level."
        ),
        questions=[
            _q('___ hard all year, she passed with flying colours.', 'Having studied', 'Having studied', 'Studied', 'To study', 'A'),
            _q('Not only ___ she pass the exam, but she also got the highest score.', 'did', 'did', 'does', 'has', 'A'),
            _q('___ exhausted after the journey, she finished the report.', 'Although', 'Although', 'Despite', 'Having', 'A'),
            _q('What surprised me most ___ how quickly she adapted.', 'is', 'was', 'were', 'has been', 'A'),
            _q('___ it not for your help, I would have failed.', 'Were', 'Were', 'Had', 'Should', 'A'),
            _q('Having lived abroad for years, ___ he speaks several languages fluently.', 'not only', 'not only', 'although', 'despite', 'A'),
            _q('Although ___ the problem for hours, we still couldn’t solve it.', 'discussed', 'having discussed', 'discussing', 'to discuss', 'A'),
            _q('The one thing I regret ___ not taking the opportunity earlier.', 'is', 'is', 'was', 'were', 'A'),
            _q('Not only ___ the price high, but the quality was also poor.', 'was', 'was', 'is', 'were', 'A'),
            _q('___ the bad weather, we still enjoyed the trip.', 'Despite', 'Despite', 'Although', 'Having', 'A'),
        ],
    ),
]


# ========= Russian ODT supplement =========
# Imported from /home/xumoyun-maxkamov/Documents/rus tili grammar.odt

RUSSIAN_ODT_TOPICS: List[GrammarTopic] = [
    GrammarTopic(
        topic_id='ru_odt_past_tense',
        level='A1',
        subject="Russian",
        title='Прошедшее время',
        rule=(
            "🔻 Прошедшее время - o'tgan zamon bo'lib, allaqachon sodir bo'lgan voqea - hodisalarni ifodalash uchun ishlatiladi.\\n"
            "🔻 Fe'l o'tgan zamonda rodlarga qarab turlicha qo'shimcha oladi.\\n"
            'Masalan "читать", ya\'ni "o\'qimoq" fe\'lini olsak, bunda fe\'l rodlarga quyidagicha o\'zgaradi:\\n'
            '➡️ мужской род - читать → читаЛ\\n'
            '➡️ женский род - читать → читаЛА\\n'
            '➡️ средний род - читать → читаЛО\\n'
            "➡️ множественное число (ko'plik) - читать → читаЛИ\\n"
            '🔻 Misollar:\\n'
            '🔹 Мужской род\\n'
            'Он писаЛ. - U yozdi.\\n'
            "Друг отправиЛ- Do'st jo'natdi.\\n"
            'Я кушаЛ- Men yedim.\\n'
            '🔹 Женский род\\n'
            "Она видеЛА. - U ko'rdi.\\n"
            'Сестра сказаЛА. - Opa aytdi.\\n'
            'Мама говориЛА. - Ona gapirdi.\\n'
            '🔹 Средний род\\n'
            'Оно пришЛО. - U keldi.\\n'
            'Оно ушЛО. - U ketdi.\\n'
            "Оно прошЛО. - U o'tdi.\\n"
            '🔹 Множественное число\\n'
            'Они готовиЛИ. - Ular tayyorlashdi.\\n'
            'Мы смотреЛИ. - Biz tomosha qildik.\\n'
            'Вы рисоваЛИ. - Siz chizdingiz.'
        ),
        questions=[
            _q('Men kitob o‘qidim (я … книгу [м.р])', 'читала', 'читал', 'читали', '—', 'B'),
            _q('U kitob o‘qidi (она … книгу)', 'читал', 'читала', 'читали', '—', 'B'),
            _q('U xatni o‘qidi (он … письмо)', 'читал', 'читала', 'читали', '—', 'A'),
            _q('Biz gazeta o‘qidik (мы … газету)', 'читали', 'читал', 'читало', '—', 'A'),
            _q('Siz xat yozdingiz (вы … письмо)', 'писали', 'писал', 'писала', '—', 'A'),
            _q('Men yozdim (я … , [ж.р])', 'написала', 'написал', 'написали', '—', 'A'),
            _q("U so'zlarni yodladi (он … слова)", 'выучил', 'выучила', 'выучили', '—', 'A'),
            _q('Ular kitob o‘qidi (они … книгу)', 'читали', 'читало', 'читала', '—', 'A'),
            _q('Men bordim (я … в магазин [м.р])', 'пошёл', 'пошла', 'пошли', '—', 'A'),
            _q('U ketdi (она … домой)', 'пошла', 'пошёл', 'пошли', '—', 'A'),
            _q('Biz kechikdik (мы …)', 'опоздали', 'опоздала', 'опоздал', '—', 'A'),
            _q('U yozdi (он … письмо)', 'написал', 'написала', 'написали', '—', 'A'),
            _q('U xonaga kirdi (она … в комнату)', 'вошла', 'вошёл', 'вошли', '—', 'A'),
            _q('Biz o‘qidik (мы … )', 'читали', 'читал', 'читала', '—', 'A'),
            _q('Men tushdim (я … , [ж.р])', 'спустилась', 'спустился', 'спустились', '—', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='ru_odt_present_tense',
        level='A1',
        subject="Russian",
        title='Настоящее время',
        rule=(
            "🔻 Настоящее время - hozirgi zamon bo'lib, ayni damda bo'layotgan va kundalik davomiy sodir bo'layotgan ish-harakatlarni ifodalash uchun ishlatiladi.\\n"
            "🔻 Hozirgi zamonda fe'l harakat egasiga bog'liq holda turli qo'shimchalarni oladi.\\n"
            'Masalan "читать", ya\'ni "o\'qimoq" fe\'lini olsak, bunda fe\'l quyidagicha qo\'shimcha oladi:\\n'
            "Я читаЮ - Men o'qiyapman.\\n"
            "Ты читаЕШЬ - Sen o'qiyapsan.\\n"
            "Мы читаЕМ - Biz o'qiyapmiz.\\n"
            "Вы читаЕТЕ - Siz o'qiyapsiz.\\n"
            "Он(а) читаЕТ - U o'qiyapti.\\n"
            "Они читаЮТ - Ular o'qishyapti.\\n"
            '💡 Qisqa tushuncha\\n'
            'Я + "-ю"\\n'
            'Ты + "-ешь"\\n'
            'Мы + "-ем"\\n'
            'Вы + "-ете"\\n'
            'Он(а) + "-ет"\\n'
            'Они + "-ют"\\n'
            '🔻Eslab qoling!!!\\n'
            'Rus tilida, shuningdek, "ить" ga tugaydigan fe\'llar ham bor. Masalan, "говорить" fe\'li, keling bunday fe\'l qanday tarzda o\'zgarishini ko\'rib chiqamiz.\\n'
            'Я говорЮ - Men gapiryapman.\\n'
            'Ты говорИШЬ - Sen gapiryapsan.\\n'
            'Мы говорИМ - Biz gapiryapmiz.\\n'
            'Вы говорИТЕ - Siz gapiryapsiz.\\n'
            'Он(а) говорИТ - U gapiryapti.\\n'
            'Они говорЯТ - Ular gapirishyapti\\n'
            "🔻Va yana bir nechta istisno sanaluvchi fe'llar ham bor, ular ham hozirgi zamon qo'shimchalarini turlicha oladi.\\n"
            '🔻 Qo‘shimcha tushuncha ⚡️\\n'
            'Kundalik va ayni damda bajarilayotgan ishlar uchun misollar:\\n'
            'Я читаю книгу каждый день.\\n'
            "[ Men har kuni kitob o'qiyman. ]\\n"
            'Он сейчас читает книгу.\\n'
            "[ U hozir kitob o'qiyapti. ]"
        ),
        questions=[
            _q('Я ... книгу.', 'читаю', 'читаешь', 'читают', 'читает', 'A'),
            _q('Ты ... домашнее дело?', 'делаю', 'делаешь', 'делает', 'делают', 'B'),
            _q('Собака ... мясо.', 'кушает', 'кушаешь', 'кушают', 'кушаю', 'A'),
            _q('Мы ... футбол.', 'играю', 'играешь', 'играем', 'играют', 'C'),
            _q('Они ... передачу.', 'смотрят', 'смотрит', 'смотрите', 'смотришь', 'A'),
            _q('Она ... письмо.', 'отправляет', 'отправляют', 'отправляете', 'отправляешь', 'A'),
            _q('Вы ... по-русски.', 'говорю', 'говоришь', 'говорите', 'говорят', 'C'),
            _q('Я ... музыку.', 'слушает', 'слушаю', 'слушаешь', 'слушают', 'B'),
            _q('Мы ... в парке.', 'гуляю', 'гуляешь', 'гуляем', 'гуляю', 'C'),
            _q('Ты ... телевизор.', 'смотрю', 'смотришь', 'смотрит', 'смотрим', 'B'),
            _q('Они ... в школу.', 'ходит', 'ходите', 'ходишь', 'ходят', 'D'),
            _q('Он ... каждый день.', 'работает', 'работаю', 'работаешь', 'работают', 'A'),
            _q('Мы ... книгу.', 'читаешь', 'читаем', 'читают', 'читаю', 'B'),
            _q('Она ... обед.', 'готовит', 'готовят', 'готовите', 'готовишь', 'A'),
            _q('Вы ... домашнее задание.', 'делаю', 'делаешь', 'делают', 'делаете', 'D'),
        ],
    ),
    GrammarTopic(
        topic_id='ru_odt_future_budu',
        level='A1',
        subject="Russian",
        title='Будущее время: буду + инфинитив',
        rule=(
            "🔻 Будущее время - kelasi zamon bo'lib, kelajakda sodir bo'ladigan va bajariladigan ish-harakatlarni ifodalash uchun ishlatiladi.\\n"
            "🔻 Kelasi zamon ikki shaklga bo'linadi: murakkab (jarayon) va oddiy (natija) shakli.\\n"
            "Quyida kelasi zamonning murakkab shaklini ko'rib chiqamiz⚡️\\n"
            "Kelasi zamonning bu shaklida fe'ldan oldin quyidagi kabi yordamchi so'zlardan foydalanamiz:\\n"
            'я БУДУ делать - Men qilaman.(davomiy)\\n'
            'ты БУДЕШЬ делать - Sen qilasan.\\n'
            'мы БУДЕМ делать - Biz qilamiz.\\n'
            'вы БУДЕТЕ делать - Siz qilasiz.\\n'
            'он(а) БУДЕТ делать - U qiladi.\\n'
            'они БУДУТ делать - Ular qilishadi.\\n'
            '🔻 ESLAB QOLING!!!\\n'
            "➡️ Yordamchi so'zdan keyin keladigan fe'l infinitiv shaklida, ya'ni hech qanday qo'shimcha olmagan holda qoladi.\\n"
            "➡️ Kelasi zamonda yordamchi so'zdan keyin keladigan fe'lning tugallanmagan shakli ishlatiladi.\\n"
            'Masalan\\n'
            'я буду ДЕЛАТЬ.\\n'
            "Quyidagi gaplarni grammatik jihatdan to'g'irlang."
        ),
        questions=[
            _q('Я ... читать книгу.', 'буду', 'будешь', 'будет', 'будут', 'A'),
            _q('Ты ... делать домашнее задание.', 'буду', 'будешь', 'будет', 'будем', 'B'),
            _q('Он ... смотреть фильм.', 'буду', 'будешь', 'будет', 'будут', 'C'),
            _q('Мы ... писать тест завтра.', 'будете', 'буду', 'будем', 'будет', 'C'),
            _q('Они ... играть в футбол.', 'будет', 'будешь', 'буду', 'будут', 'D'),
            _q('Вы ... читать текст.', 'будет', 'будете', 'буду', 'будешь', 'B'),
            _q('Я ... делать это задание вечером.', 'буду', 'будет', 'будешь', 'будем', 'A'),
            _q('Он ... учиться завтра.', 'буду', 'будешь', 'будет', 'будут', 'C'),
            _q('Мы ... смотреть фильм вечером.', 'буду', 'будут', 'будете', 'будем', 'D'),
            _q('Ты ... писать письмо.', 'буду', 'будешь', 'будет', 'будем', 'B'),
            _q('Они ... готовить ужин.', 'будет', 'буду', 'будут', 'будешь', 'C'),
            _q('Я не ... делать это.', 'будет', 'буду', 'будешь', 'будут', 'B'),
            _q('Он не ... работать завтра.', 'буду', 'будешь', 'будет', 'будут', 'C'),
            _q('Мы ... читать эту книгу.', 'буду', 'будут', 'будете', 'будем', 'D'),
            _q('Вы ... учить новые слова.', 'буду', 'будут', 'будете', 'будешь', 'C'),
        ],
    ),
    GrammarTopic(
        topic_id='ru_odt_plural_cases',
        level='A2',
        subject="Russian",
        title='Падежи существительных во множественном числе',
        rule=(
            'Падеж - bu nima?\\n'
            'Падеж - bu kelishik bo’lib, bizga qo’shimcha qo’shishda yordamlashuvchi vosita hisoblanadi.\\n'
            'Bu kelishiklar gaplarimizni to’g’ri ifodalashimiz uchun xizmat qiladi.\\n'
            'Rus tilida 6 ta kelishik (падеж) bor.\\n'
            'Rus tilidagi rodlarga qarab, bu “падеж”larning qo’shimchalari o’zgaradi.\\n'
            'Quyida “падеж”larning ko’plik shaklida otlar qanday qo’shimchalar olishini ko’rib chiqamiz.\\n'
            'Birinchi navbatda, ko’plikda “падеж” qo’shimchalari qanday ma’noni anglatishini ko’rib olamiz:\\n'
            '1) -lar\\n'
            '2) -larning\\n'
            '3) -larga\\n'
            '4) -larni\\n'
            '5) -lar bilan/bo’lib\\n'
            '6) -lar haqida\\n'
            'Rus tilida:\\n'
            '1)-- (so’zning ko’plik shakli)\\n'
            '2 - падеж qo’shimchalari biroz murakkab, ularni alohida ko’rib chiqamiz:\\n'
            '2) Agar so’z “a” yoki”o” harfi bilan tugasa - bu harflar shunchaki tushib qoladi.\\n'
            'shu tariqa:\\n'
            'undosh - “-ов”/”-ев”;\\n'
            '“ь” - “-ей”;\\n'
            '“ие” - “-ий”;\\n'
            '“-ч”, “-ж”, “-ш”, “-щ” - “-ей”;\\n'
            '“я” - “-ь”\\n'
            '3) -ам, -ям\\n'
            '4) jonli bo’lsa - 2-падеж qo’shimchasini oladi/ jonsiz bo’lsa hech qanday qo’shimcha olmay, o’z holida qoladi.\\n'
            '5) -ами, -ями\\n'
            '6) (о) -ах, ях\\n'
            'ESLAB QOLING!!!\\n'
            'Qo’shimcha qo’shayotganda, so’zning birligiga qaraladi, ya’ni:\\n'
            'машинЫ emas, машинА so’ziga qo’shimcha qo’shiladi.\\n'
            "Quyidagi so'zlarning rus tilidagi to'g'ri tarjimasi berilgan javobni toping."
        ),
        questions=[
            _q('"kitoblarning"', 'книг', 'книги', 'книгам', 'книгами', 'A'),
            _q('"stollarga"', 'столов', 'столам', 'столами', 'столах', 'B'),
            _q('"derazalarga"', 'окна', 'окон', 'окнам', 'окнами', 'C'),
            _q('"o\'qituvchilar bilan"', 'учителей', 'учителями', 'учителям', 'учителях', 'B'),
            _q('"qizlarga"', 'девочек', 'девочкам', 'девочками', 'девочках', 'B'),
            _q('"shaharlar haqida"', 'городах', 'городами', 'городов', 'городам', 'A'),
            _q('"dengizlarning"', 'морей', 'моря', 'морям', 'морями', 'A'),
            _q('"akalarni"', 'братья', 'братьев', 'братьям', 'братьями', 'B'),
            _q('"stullarni"', 'стулья', 'стульев', 'стульям', 'стульями', 'A'),
            _q('"mashinalar bilan"', 'машин', 'машинам', 'машинами', 'машинах', 'C'),
            _q('"qahramonlarning"', 'герои', 'героев', 'героям', 'героями', 'B'),
            _q('"olmalarga"', 'яблок', 'яблокам', 'яблоками', 'яблоках', 'B'),
            _q('"do\'stlarni"', 'друзья', 'друзей', 'друзьям', 'друзьями', 'B'),
            _q('"derazalar haqida"', 'окнам', 'окнах', 'окнами', 'окон', 'B'),
            _q('"o\'quvchilarga"', 'учеников', 'ученикам', 'учениками', 'учениках', 'B'),
        ],
    ),
    GrammarTopic(
        topic_id='ru_odt_adjectives_masculine_cases',
        level='A2',
        subject="Russian",
        title='Прилагательные мужского рода в падежах',
        rule=(
            '🔻 Rus tilida sifatlar o\'zbek tilidagi kabi otlarga bog\'liq bo\'ladi va sifatlar ham "падеж", ya\'ni kelishik qo\'shimchalarini oladi. Biroq sifat qo\'shimchalari ot qo\'shimchalaridan biroz farq qiladi.\\n'
            '🔻 Quyida "мужской род" ga tegishli otlarga bog\'lanadigan sifatlar qo\'shimchalarini ko\'rib chiqamiz.\\n'
            "1) --(hech qanday qo'shimcha olmaydi)❌\\n"
            '2) -ого/-его\\n'
            '3) -ому/-ему\\n'
            "4) -jonli bo'lsa, 2-падеж qo'shimchasi/jonsiz bo'lsa, hech qanday qo'shimcha olmaydi❌\\n"
            '5) -ым/-им\\n'
            '6) (о) -ом/-ем\\n'
            '🔻 Masalan:\\n'
            '➡️ "хороший мальчик"\\n'
            '1) хороший мальчик\\n'
            '2) хорошЕГО мальчика\\n'
            '3) хорошЕМУ мальчику\\n'
            '4) хорошЕГО мальчика\\n'
            '5) хорошИМ мальчиком\\n'
            '6) (о) хорошЕМ мальчике\\n'
            '➡️ "новый телефон"\\n'
            '1) новый телефон\\n'
            '2) новОГО телефона\\n'
            '3) новОМУ телефону\\n'
            '4) новЫЙ телефон\\n'
            '5) новЫМ телефоном\\n'
            '6) (о) новОМ телефоне\\n'
            '❗️ESLAB QOLING!!!\\n'
            'O\'zbek tilida biz "yaxshi bolaning/bolaga"(va hokazo) deb aytamiz, ammo rus tilida bu "yaxshining bolaning/yaxshiga bolaga" (va hokazo) deb aytiladi.\\n'
            "Quyidagi so'z birikmalarning rus tilidagi to'g'ri tarjimasi berilgan javobni toping."
        ),
        questions=[
            _q('"yosh do\'stimga\'', 'молодой друг', 'молодого друга', 'молодому другу', 'молодым другом', 'C'),
            _q('"yangi telefonning"', 'новый телефон', 'нового телефона', 'новому телефону', 'новым телефоном', 'B'),
            _q('"yaxshi do‘stga"', 'хороший друг', 'хорошего друга', 'хорошему другу', 'хорошим другом', 'C'),
            _q('"katta stolning"', 'большой стол', 'большого стола', 'большому столу', 'большим столом', 'B'),
            _q('"aqlli talabaning"', 'умный студент', 'умного студента', 'умному студенту', 'умным студентом', 'B'),
            _q('"qiziqarli filmga"', 'интересный фильм', 'интересного фильма', 'интересному фильму', 'интересным фильмом', 'C'),
            _q('"yangi kompyuter bilan"', 'новый компьютер', 'нового компьютера', 'новому компьютеру', 'новым компьютером', 'D'),
            _q('"katta bog‘ning"', 'большой парк', 'большого парка', 'большому парку', 'большим парком', 'B'),
            _q('"yaxshi ustozga"', 'хороший учитель', 'хорошего учителя', 'хорошему учителю', 'хорошим учителем', 'C'),
            _q('"eski telefon bilan"', 'старый телефон', 'старого телефона', 'старому телефону', 'старым телефоном', 'D'),
            _q('"aqlli bola bilan"', 'умный мальчик', 'умного мальчика', 'умному мальчику', 'умным мальчиком', 'D'),
            _q('"yangi do‘stning"', 'новый друг', 'нового друга', 'новому другу', 'новым другом', 'B'),
            _q('"katta shaharga"', 'большой город', 'большого города', 'большому городу', 'большим городом', 'C'),
            _q('"yaxshi natija bilan"', 'хороший результат', 'хорошего результата', 'хорошему результату', 'хорошим результатом', 'D'),
            _q('"kuchli akamga"', 'сильный брат', 'сильному брату', 'сильным братом', 'сильного брата', 'B'),
        ],
    ),
    GrammarTopic(
        topic_id='ru_odt_adjectives_feminine_cases',
        level='A2',
        subject="Russian",
        title='Прилагательные женского рода в падежах',
        rule=(
            '🔻 Rus tilida sifatlar o‘zbek tilidagi kabi otlarga bog‘liq bo‘ladi va sifatlar ham "падеж" qo‘shimchalarini oladi.\\n'
            '🔻 Quyida женский род ga tegishli sifat qo‘shimchalari:\\n'
            '1. -ая / -яя\\n'
            '2. -ой / -ей\\n'
            '3. -ой / -ей\\n'
            '4. -ую / -юю\\n'
            '5. -ой / -ей\\n'
            '6. (о) -ой / -ей\\n'
            '🔻 Masalan:\\n'
            '➡️ "хорошая девочка"\\n'
            '1. хорошАЯ девочка\\n'
            '2. хорошЕЙ девочки\\n'
            '3. хорошЕЙ девочке\\n'
            '4. хорошУЮ девочку\\n'
            '5. хорошЕЙ девочкой\\n'
            '6. (о) хорошЕЙ девочке\\n'
            '➡️ "новая книга"\\n'
            '1. новАЯ книга\\n'
            '2. новОЙ книги\\n'
            '3. новОЙ книге\\n'
            '4. новУЮ книгу\\n'
            '5. новОЙ книгой\\n'
            '6. (о) новОЙ книге\\n'
            '❗️ ESLAB QOLING!!!\\n'
            'O‘zbek tilida biz:\\n'
            '👉 *yangi kitobning / kitobga / kitobni* deymiz\\n'
            'Rus tilida esa:\\n'
            '👉 *yangiNING kitobning / yangiGA kitobga / yangiNI kitobni* bo‘ladi\\n'
            'ya’ni sifat ham ot bilan birga o‘zgaradi🔥'
        ),
        questions=[
            _q('"yangi kitobning"', 'новая книга', 'новой книги', 'новой книге', 'новую книгу', 'B'),
            _q('"yaxshi qizga"', 'хорошая девочка', 'хорошей девочки', 'хорошей девочке', 'хорошую девочку', 'C'),
            _q('"katta xonaning"', 'большая комната', 'большой комнаты', 'большой комнате', 'большую комнату', 'B'),
            _q('"qiziqarli kitobni"', 'интересная книга', 'интересной книги', 'интересной книге', 'интересную книгу', 'D'),
            _q('"yangi sumka bilan"', 'новая сумка', 'новой сумки', 'новой сумке', 'новой сумкой', 'D'),
            _q('"chiroyli qizning"', 'красивая девушка', 'красивой девушки', 'красивой девушке', 'красивую девушку', 'B'),
            _q('"yaxshi o‘qituvchiga"', 'хорошая учительница', 'хорошей учительницы', 'хорошей учительнице', 'хорошую учительницу', 'C'),
            _q('"katta ko‘chani"', 'большая улица', 'большой улицы', 'большой улице', 'большую улицу', 'D'),
            _q('"yangi mashina bilan"', 'новая машина', 'новой машины', 'новой машине', 'новой машиной', 'D'),
            _q('"qiziqarli hikoyaning"', 'интересная история', 'интересной истории', 'интересной истории', 'интересную историю', 'B'),
            _q('"yaxshi dugonaga"', 'хорошая подруга', 'хорошей подруги', 'хорошей подруге', 'хорошую подругу', 'C'),
            _q('"qizil mashinaning"', 'красную машину', 'красной машине', 'красной машины', '(о) красной машине', 'C'),
            _q('"yangi ishning"', 'новая работа', 'новой работы', 'новой работе', 'новую работу', 'B'),
            _q('"chiroyli atirgulni"', 'красивая роза', 'красивой розой', 'красивой розе', 'красивую розу', 'D'),
            _q('"yangi kitobga"', 'новая книга', 'новой книги', 'новой книге', 'новую книгу', 'C'),
        ],
    ),
    GrammarTopic(
        topic_id='ru_odt_adjectives_plural_cases',
        level='A2',
        subject="Russian",
        title='Прилагательные во множественном числе в падежах',
        rule=(
            '🔻 Rus tilida sifatlar ko‘plikda ham otlarga bog‘liq bo‘ladi va kelishiklarga qarab o‘zgaradi.\\n'
            '🔻 Quyida ko‘plik (мн.ч) uchun sifat qo‘shimchalari:\\n'
            '1. -ые / -ие\\n'
            '2. -ых / -их\\n'
            '3. -ым / -им\\n'
            '4. -jonli bo‘lsa: -ых / -их\\n'
            '-jonsiz bo‘lsa: 1-padej (ya’ni -ые / -ие) ❌\\n'
            '5. -ыми / -ими\\n'
            '6. (о) -ых / -их\\n'
            '🔻 Masalan:\\n'
            '➡️ "хорошие ученики" (jonli)\\n'
            '1. хорошИЕ ученики\\n'
            '2. хорошИХ учеников\\n'
            '3. хорошИМ ученикам\\n'
            '4. хорошИХ учеников\\n'
            '5. хорошИМИ учениками\\n'
            '6. (о) хорошИХ учениках\\n'
            '➡️ "новые телефоны" (jonsiz)\\n'
            '1. новЫЕ телефоны\\n'
            '2. новЫХ телефонов\\n'
            '3. новЫМ телефонам\\n'
            '4. новЫЕ телефоны\\n'
            '5. новЫМИ телефонами\\n'
            '6. (о) новЫХ телефонах\\n'
            '## ❗️ ESLAB QOLING!!!\\n'
            'O‘zbek tilida:\\n'
            '👉 *yangi telefonlar / telefonlarning / telefonlarga*\\n'
            'Rus tilida esa:\\n'
            '👉 "yangiLAR telefonlar / yangiLARNING telefonlarning / yangiLARGA telefonlarga"\\n'
            'ya’ni ko‘plikda ham sifat ot bilan birga o‘zgaradi 🔥'
        ),
        questions=[
            _q('"yangi telefonlarning"', 'новые телефоны', 'новых телефонов', 'новым телефонам', 'новыми телефонами', 'B'),
            _q('"yaxshi o‘quvchilarga"', 'хорошие ученики', 'хороших учеников', 'хорошим ученикам', 'хорошими учениками', 'C'),
            _q('"katta uylarni"', 'большие дома', 'больших домов', 'большим домам', 'большими домами', 'A'),
            _q('"aqlli bolalarni"', 'умные мальчики', 'умных мальчиков', 'умным мальчикам', 'умными мальчиками', 'B'),
            _q('"yangi kitoblar bilan"', 'новые книги', 'новых книг', 'новым книгам', 'новыми книгами', 'D'),
            _q('"qiziqarli filmlarning"', 'интересные фильмы', 'интересных фильмов', 'интересным фильмам', 'интересными фильмами', 'B'),
            _q('"yaxshi do‘stlarga"', 'хорошие друзья', 'хороших друзей', 'хорошим друзьям', 'хорошими друзьями', 'C'),
            _q('"katta bog‘larni"', 'большие парки', 'больших парков', 'большим паркам', 'большими парками', 'A'),
            _q('"yangi kompyuterlar bilan"', 'новые компьютеры', 'новых компьютеров', 'новым компьютерам', 'новыми компьютерами', 'D'),
            _q('"aqlli talabalarni"', 'умные студенты', 'умных студентов', 'умным студентам', 'умными студентами', 'B'),
            _q('"yaxshi natijalarning"', 'хорошие результаты', 'хороших результатов', 'хорошим результатам', 'хорошими результатами', 'B'),
            _q('"katta shaharlarga"', 'большие города', 'больших городов', 'большим городам', 'большими городами', 'C'),
            _q('"yangi mashinalarni"', 'новые машины', 'новых машин', 'новым машинам', 'новыми машинами', 'A'),
            _q('"yaxshi ustozlarni"', 'хорошие учителя', 'хороших учителей', 'хорошим учителям', 'хорошими учителями', 'B'),
            _q('"qiziqarli hikoyalar bilan"', 'интересные истории', 'интересных историй', 'интересным историям', 'интересными историями', 'D'),
        ],
    ),
    GrammarTopic(
        topic_id='ru_odt_age_years',
        level='A1',
        subject="Russian",
        title='Возраст: год / года / лет',
        rule=(
            "Rus tilida yoshni (возраст) aytishni ko'rib chiqamiz.\\n"
            '✅ 1) 1 yosh (1)\\n'
            '👉 “год” ishlatiladi\\n'
            'Men 1 yoshdaman → Мне 1 год\\n'
            '✅ 2) 2, 3, 4 yosh\\n'
            '👉 “года” ishlatiladi\\n'
            'Men 2 yoshdaman → Мне 2 года\\n'
            'U 4 yoshda → Ему 4 года\\n'
            '⚠️ 3) 5 dan boshlab hamma sonlar\\n'
            '👉 “лет” ishlatiladi\\n'
            'Men 5 yoshdaman → Мне 5 лет\\n'
            'U 10 yoshda → Ему 10 лет\\n'
            'U 20 yoshda → Ему 20 лет\\n'
            '❗️ MUHIM (11–14)\\n'
            '11, 12, 13, 14 bo‘lsa hamma vaqt “лет” ishlatiladi:\\n'
            '* 11 yosh → 11 лет\\n'
            '* 12 yosh → 12 лет\\n'
            '* 13 yosh → 13 лет\\n'
            '* 14 yosh → 14 лет\\n'
            '🧠 Qisqa eslab qolish:\\n'
            '* 1 → год\\n'
            '* 2–4 → года\\n'
            '* 5+ → лет\\n'
            '* 11–14 → лет (har doim)\\n'
            '📌 Misollar:\\n'
            '* Мне 15 лет. (Men 15 yoshdaman)\\n'
            '* Моей сестре 3 года. (Singlim 3 yoshda)\\n'
            '* Моему брату 11 лет. (Ukam 11 yoshda)'
        ),
        questions=[
            _q('2 yosh', '2 год', '2 года', '2 лет', '—', 'B'),
            _q('1 yosh', '1 год', '1 года', '1 лет', '—', 'A'),
            _q('4 yosh', '4 лет', '4 года', '4 год', '—', 'B'),
            _q('5 yosh', '5 год', '5 года', '5 лет', '—', 'C'),
            _q('10 yosh', '10 год', '10 года', '10 лет', '—', 'C'),
            _q('11 yosh', '11 год', '11 года', '11 лет', '—', 'C'),
            _q('12 yosh', '12 год', '12 года', '12 лет', '—', 'C'),
            _q('13 yosh', '13 года', '13 лет', '13 год', '—', 'B'),
            _q('14 yosh', '14 год', '14 года', '14 лет', '—', 'C'),
            _q('3 yosh', '3 год', '3 года', '3 лет', '—', 'B'),
            _q('7 yosh', '7 год', '7 года', '7 лет', '—', 'C'),
            _q('9 yosh', '9 лет', '9 год', '9 года', '—', 'A'),
            _q('15 yosh', '15 год', '15 года', '15 лет', '—', 'C'),
            _q('20 yosh', '20 год', '20 года', '20 лет', '—', 'C'),
            _q('18 yosh', '18 год', '18 года', '18 лет', '—', 'C'),
        ],
    ),
    GrammarTopic(
        topic_id='ru_odt_time_telling',
        level='A1',
        subject="Russian",
        title='Как говорить время',
        rule=(
            "➡️ Vaqtni (время) aytishni ko'rib chiqamiz.\\n"
            '🔹 Soat aytish (oddiy shakl):\\n'
            '1:00 — час\\n'
            '2:00 — два часа\\n'
            '3:00 — три часа\\n'
            '4:00 — четыре часа\\n'
            '5:00 — пять часов\\n'
            '6:00 — шесть часов\\n'
            '7:00 — семь часов\\n'
            '8:00 — восемь часов\\n'
            '9:00 — девять часов\\n'
            '10:00 — десять часов\\n'
            '11:00 — одиннадцать часов\\n'
            '12:00 — двенадцать часов\\n'
            '🔹 Yarim va minutlar:\\n'
            '1:30 — пол второго\\n'
            '2:15 — пятнадцать минут третьего\\n'
            '2:45 — без пятнадцати три\\n'
            '2:20 — двадцать минут третьего\\n'
            '🔹 Misollar:\\n'
            'Сейчас 3 часа.\\n'
            '[ Hozir 3:00 ]\\n'
            'Сейчас пол шестого.\\n'
            '[ Hozir 5:30 ]\\n'
            'Сейчас без пятнадцати восемь\\n'
            '[ Hozir 7:45 ]\\n'
            "Quyidagi vaqtlar to'g'ri berilgan variantni toping."
        ),
        questions=[
            _q('2:15', 'пятнадцать минут третьего', 'без пятнадцати третьего', 'половина третьего', '—', 'A'),
            _q('3:30', 'пол четвёртого', 'без пятнадцати четвёртого', 'пятнадцать минут четвёртого', '—', 'A'),
            _q('4:45', 'пятнадцать минут пятого', 'без пятнадцати пять', 'половина пятого', '—', 'B'),
            _q('1:15', 'пятнадцать минут второго', 'без пятнадцати второго', 'пол второго', '—', 'A'),
            _q('5:30', 'пол шестого', 'без пятнадцати шестого', 'пятнадцать минут шестого', '—', 'A'),
            _q('6:45', 'пятнадцать минут седьмого', 'без пятнадцати семь', 'пол седьмого', '—', 'B'),
            _q('7:15', 'пятнадцать минут восьмого', 'без пятнадцати восьмого', 'пол восьмого', '—', 'A'),
            _q('8:30', 'пол девятого', 'без пятнадцати девятого', 'пятнадцать минут девятого', '—', 'A'),
            _q('9:45', 'пятнадцать минут десятого', 'без пятнадцати десять', 'пол десятого', '—', 'B'),
            _q('10:15', 'пятнадцать минут одиннадцатого', 'без пятнадцати одиннадцатого', 'пол одиннадцатого', '—', 'A'),
            _q('11:30', 'пол двенадцатого', 'без пятнадцати двенадцатого', 'пятнадцать минут двенадцатого', '—', 'A'),
            _q('12:45', 'пятнадцать минут первого', 'без пятнадцати один', 'пол первого', '—', 'B'),
            _q('2:30', 'пол третьего', 'пятнадцать минут третьего', 'без пятнадцати третьего', '—', 'A'),
            _q('3:45', 'без пятнадцати четыре', 'пятнадцать минут четвёртого', 'пол четвёртого', '—', 'A'),
            _q('5:15', 'пятнадцать минут шестого', 'без пятнадцати шестого', 'пол шестого', '—', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='ru_odt_years_ordinals',
        level='A2',
        subject="Russian",
        title='Годы и порядковые числительные',
        rule=(
            '🔹 RUS TILIDA YILLARNI AYTISH (ENG OSON QOIDA)\\n'
            'Rus tilida yil aytish 2 qismga bo‘linadi:\\n'
            '✅ 1) 1000–1999 yillar\\n'
            '👉 Tuzilishi:\\n'
            'ming + yuz + o‘n + birlik\\n'
            '📌 Misol:\\n'
            '* 1987\\n'
            '👉 тысяча девятьсот восемьдесят семь\\n'
            '(1000 + 900 + 80 + 7)\\n'
            '* 1950\\n'
            '👉 тысяча девятьсот пятьдесят\\n'
            '🧠 Oson eslab qolish:\\n'
            '👉 “bir ming + yuzlik + qolgan son”\\n'
            '✅ 2) 2000 va undan keyingi yillar\\n'
            '👉 Tuzilishi:\\n'
            'ikki ming + qolgan son\\n'
            '📌 Misol:\\n'
            '* 2001\\n'
            '👉 две тысячи один\\n'
            '* 2010\\n'
            '👉 две тысячи десять\\n'
            '* 2023\\n'
            '👉 две тысячи двадцать три\\n'
            '🔥 SUPER OSON QOIDA\\n'
            '## ✳️ 1000–1999:\\n'
            '👉 тысяча + ...\\n'
            '✳️ 2000+:\\n'
            '👉 две тысячи + ...\\n'
            '⚠️ MUHIM NARSA\\n'
            'Yillarni aytganda:\\n'
            '👉 oddiy son ishlatilmaydi\\n'
            '👉 har doim so‘z bilan to‘liq o‘qiladi\\n'
            '📌 MISOLLAR BIR JOYDA:\\n'
            '* 1987 → тысяча девятьсот восемьдесят семь\\n'
            '* 1950 → тысяча девятьсот пятьдесят\\n'
            '* 2001 → две тысячи один\\n'
            '* 2010 → две тысячи десять\\n'
            '* 2023 → две тысячи двадцать три\\n'
            '📌 🔹 “-INCHI” = TARTIB SONLAR (порядковые числительные)\\n'
            'O‘zbekchadagi 1-inchi, 2-inchi, 3-inchi…rus tilida:\\n'
            '👉 первый, второй, третий, четвёртый…\\n'
            '🔹 YILLARDA “-INCHI” QANDAY ISHLAYDI?\\n'
            'Yil aytilganda rus tilida oxirgi son "-inchi shaklga o‘tadi", ya’ni:\\n'
            '👉 год = “-inchi yil”\\n'
            '🔥 1) 1000–1999 yillar\\n'
            '📌 QOIDA:\\n'
            '👉 тысяча + yuzlik + tartib son\\n'
            'Misollar:\\n'
            '1987 yil\\n'
            '👉 тысяча девятьсот восемьдесят седьмой год\\n'
            '(1987-inchi yil)\\n'
            '* 1950 yil\\n'
            '👉 тысяча девятьсот пятидесятый год\\n'
            '(1950-inchi yil)\\n'
            '🔥 2) 2000+ yillar\\n'
            '📌 QOIDA:\\n'
            '👉 две тысячи + tartib son\\n'
            'Misollar:\\n'
            '2001 yil\\n'
            '👉 две тысячи первый год\\n'
            '2010 yil\\n'
            '👉 две тысячи десятый год\\n'
            '2023 yil\\n'
            '👉 две тысячи двадцать третий год\\n'
            '⚠️ MUHIM FARQ\\n'
            '❌ Oddiy sanash:\\n'
            '2023 → две тысячи двадцать три\\n'
            '✅ “-inchi yil”:\\n'
            '2023 yil → две тысячи двадцать третий год\\n'
            '💡 XULOSA\\n'
            '👉 Yil aytganda:\\n'
            '*son + so‘z emas ❌\\n'
            '*tartib son + год ✅'
        ),
        questions=[
            _q('2001-yil', 'две тысячи один', 'две тысячи первый год', 'две тысячи один год', '—', 'B'),
            _q('2010-yil', 'две тысячи десятый год', 'две тысячи десять год', 'две тысячи десять', '—', 'A'),
            _q('2023', 'две тысячи двадцать три', 'две тысячи двадцать третий год', 'две тысячи двадцать третья', '—', 'A'),
            _q('1987-yil', 'тысяча девятьсот восемьдесят седьмой год', 'тысяча девятьсот восемьдесят семь', 'тысяча девятьсот восемьдесят седьмая', '—', 'A'),
            _q('1950-yil', 'тысяча девятьсот пятьдесят', 'тысяча девятьсот пятидесятый год', 'тысяча девятьсот пятьдесят год', '—', 'B'),
            _q('2005', 'две тысячи пятый год', 'две тысячи пять', 'две тысячи пятая', '—', 'B'),
            _q('2015-yil', 'две тысячи пятнадцать', 'две тысячи пятнадцатый год', 'две тысячи пятнадцатая', '—', 'B'),
            _q('1999-yil', 'тысяча девятьсот девяносто девятый год', 'тысяча девятьсот девяносто девять', 'тысяча девятьсот девяносто девятое', '—', 'A'),
            _q('2000', 'две тысячи год', 'две тысячи', 'две тысячи год', '—', 'B'),
            _q('2020-yil', 'две тысячи двадцать', 'две тысячи двадцатый год', 'две тысячи двадцать год', '—', 'B'),
            _q('1965-yil', 'тысяча девятьсот шестьдесят пять', 'тысяча девятьсот шестьдесят пятый год', 'тысяча девятьсот шестьдесят пятое', '—', 'B'),
            _q('2012-yil', 'две тысячи двенадцать год', 'две тысячи двенадцатый год', 'две тысячи двенадцатая', '—', 'B'),
            _q('1980 yil', 'тысяча девятьсот восемьдесят', 'тысяча девятьсот восьмидесятый год', 'тысяча девятьсот восьмидесятая', '—', 'B'),
            _q('2008-yil', 'две тысячи восемь', 'две тысячи восьмой год', 'две тысячи восьмая', '—', 'B'),
            _q('1973', 'тысяча девятьсот семьдесят третий год', 'тысяча девятьсот семьдесят три', 'тысяча девятьсот семьдесят третье', '—', 'B'),
        ],
    ),
    GrammarTopic(
        topic_id='ru_odt_genitive_prepositions',
        level='B1',
        subject="Russian",
        title='Предлоги с родительным падежом',
        rule=(
            "🔻 Predlog - bu ko'makchi so'z bo'lib, u boshqa so'zlar (odatda, otlar bilan) birga ishlatiladi.\\n"
            "🔻 Ko'makchilar (predloglarning) vazifasi - ot bilan birikib, ularning munosabatini aniqlash.\\n"
            "Quyida 2-kelishik (падеж) qo'shimchasi bilan ishlatiladigan ko'makchilarni ko'rib chiqamiz.\\n"
            '➡️ Около / возле-yonida\\n'
            'около дома\\n'
            'около школы\\n'
            'возле университета\\n'
            'возле машины\\n'
            'около компьютера\\n'
            'около офиса\\n'
            '➡️ Напротив - ro’parasida\\n'
            'напротив завода\\n'
            'напротив магазина\\n'
            'напротив базара\\n'
            'напротив школы\\n'
            'напротив больницы\\n'
            '➡️ До - ...gacha\\n'
            'до школы\\n'
            'до дома\\n'
            'до Ташкента\\n'
            'до Москвы\\n'
            'до офиса\\n'
            '➡️ У - …nikida /… da (shahslar bilan)\\n'
            'У сестры\\n'
            'у тети\\n'
            'у дяди\\n'
            'у брата\\n'
            'у Шахнозы\\n'
            'у Сарвара\\n'
            '➡️ После - keyin\\n'
            'после урока\\n'
            'После школы\\n'
            'после института\\n'
            'после работы\\n'
            'после футбола\\n'
            '➡️ Для - uchun\\n'
            'для мамы\\n'
            'для брата\\n'
            'для Шахзоды\\n'
            'для Шахзода\\n'
            'для друга\\n'
            '➡️ Из-за - sababli\\n'
            'из-за урока\\n'
            'из-за работы\\n'
            'из-за брата\\n'
            'из-за Асрора\\n'
            'из-за Умиды\\n'
            '➡️ Без - ….siz\\n'
            'без интернета\\n'
            'без переводчика\\n'
            'без работы\\n'
            'без друга\\n'
            'без лимона\\n'
            '➡️ Вместо - o’rniga\\n'
            'вместо друга\\n'
            'вместо урока\\n'
            'вместо брата\\n'
            'вместо сестры\\n'
            'вместо работы\\n'
            '➡️ Кроме - tashqari\\n'
            'Кроме Расула\\n'
            'кроме умиды\\n'
            'кроме умида\\n'
            'кроме папы\\n'
            'кроме мамы\\n'
            '➡️ Насчёт - bo’yicha\\n'
            "По поводу - bo'yicha\\n"
            'насчет работы\\n'
            'насчет урока\\n'
            'по поводу вакансии\\n'
            '➡️ Посередине-o’rtasida\\n'
            'посередине зала\\n'
            'посередине офиса\\n'
            'посередине урока\\n'
            'посередине комнаты\\n'
            'посередине двора\\n'
            '➡️ Из - …dan\\n'
            'С - ...dan\\n'
            'Из - ichidan\\n'
            'с - ustidan\\n'
            'из дома\\n'
            'из комнаты\\n'
            'из Ташкента\\n'
            'из России\\n'
            'с крыши\\n'
            'с парты\\n'
            'с урока\\n'
            'с работы\\n'
            '(jarayonlar bilan ham qo’llaniladi)\\n'
            '➡️ От-… dan / …nikidan\\n'
            'от друга\\n'
            'от брата\\n'
            'от Анвара\\n'
            'от гриппа\\n'
            '🔻 ESLATMA!!!\\n'
            "2 - kelishik (падеж) qo'shimchasi ko'makchi (предлог) dan keyingi otga qo'shiladi.\\n"
            "Quyidagi so'z birikmalarning rus tilidagi ma'nosini ko'makchilar yordamida aniqlang."
        ),
        questions=[
            _q("Do'konning yonida - ... магазина", 'НАПРОТИВ', 'ВОЗЛЕ', 'ДО', '—', 'B'),
            _q('Do‘stimdan - ... друга', 'С', 'ИЗ', 'ОТ', '—', 'C'),
            _q('Maktabgacha – … школы', 'ДО', 'ОКОЛО', 'ПОСЕРЕДИНЕ', '—', 'A'),
            _q('Ukam sababli - ... братишки', 'БЕЗ', 'ИЗ-ЗА', 'ДЛЯ', '—', 'B'),
            _q('Uyning qarshisida – … дома', 'НАПРОТИВ', 'ВМЕСТО', 'КРОМЕ', '—', 'A'),
            _q("Telefon o'rniga – … телефона", 'ВМЕСТО', 'С', 'У', '—', 'A'),
            _q('Do‘stlardan tashqari – … друзей', 'ПОСЕРЕДИНЕ', 'КРОМЕ', 'НАСЧЁТ', '—', 'B'),
            _q('Uy ichidan – … дома', 'ИЗ', 'С', 'ОКОЛО', '—', 'A'),
            _q('Stulgacha – … стула', 'С', 'ОТ', 'ДО', '—', 'C'),
            _q('Ota-onadan – … родителей', 'ОТ', 'ИЗ', 'В', '—', 'A'),
            _q('Uy uchun – … дома', 'С', 'ДЛЯ', 'НАСЧЁТ', '—', 'B'),
            _q('Maktabgacha – … школы', 'ДО', 'ОКОЛО', 'С', '—', 'A'),
            _q('Ob-havo sababli – … погоды', 'ВМЕСТО', 'ИЗ-ЗА', 'С', '—', 'B'),
            _q('Sen uchun – … тебя', 'ДЛЯ', 'У', 'ИЗ', '—', 'A'),
            _q('Xona o‘rtasida – … комнаты', 'ПОСЕРЕДИНЕ', 'КРОМЕ', 'ИЗ', '—', 'A'),
            _q('Maktab yonida – … школы', 'У', 'ОКОЛО', 'С', '—', 'B'),
            _q('Mashina yonida – … машины', 'ИЗ', 'ДО', 'ОКОЛО', '—', 'C'),
            _q('Do‘stdan – … друга', 'ОТ', 'С', 'НА', '—', 'A'),
            _q("Bog'cha ichidan – … сада", 'С', 'ИЗ', 'ПОСЕРЕДИНЕ', '—', 'B'),
            _q('Оnadan – … мамы', 'НАСЧЁТ', 'ОТ', 'ДО', '—', 'B'),
            _q('Tirbandlik sababli – … пробки', 'С', 'БЕЗ', 'ИЗ-ЗА', '—', 'C'),
            _q('Uy o‘rniga – … дома', 'С', 'ВМЕСТО', 'У', '—', 'B'),
            _q('Akadan tashqari – … брата', 'КРОМЕ', 'ПОСЕРЕДИНЕ', 'НАСЧЁТ', '—', 'A'),
            _q("Dars bo'yicha – … урока", 'НАСЧЁТ', 'ОКОЛО', 'У', '—', 'A'),
            _q('Do‘stnikida – … друга', 'С', 'ДЛЯ', 'У', '—', 'C'),
            _q("Maktabning ro'parasida – … школы", 'ОКОЛО', 'НАПРОТИВ', 'ДО', '—', 'B'),
            _q("Yomg'ir sababli – … дождя", 'ИЗ-ЗА', 'ВМЕСТО', 'С', '—', 'A'),
            _q('Uygacha – … дома', 'НАПРОТИВ', 'В', 'ДО', '—', 'C'),
            _q('Kvartira ichidan – … квартиры', 'ИЗ', 'С', 'ПОСЕРЕДИНЕ', '—', 'A'),
            _q("Do'st uchun – … друга", 'ДЛЯ', 'У', 'ИЗ', '—', 'A'),
        ],
    ),
    GrammarTopic(
        topic_id='ru_odt_instrumental_prepositions',
        level='B1',
        subject="Russian",
        title='Предлоги с творительным падежом',
        rule=(
            "🔻 Predlog - bu ko'makchi so‘z bo‘lib, u boshqa so‘zlar (odatda, otlar bilan) birga ishlatiladi.\\n"
            "🔻 Bu ko'makchilardan keyin kelgan otlar, odatda, 5 - kelishik (падеж) qo'shimchalarini oladi.\\n"
            '➡️ С (со) – bilan\\n'
            "с другом [ do'st bilan ]\\n"
            'с братом [ aka bilan ]\\n'
            'с сестрой [ opa bilan ]\\n'
            'со мной [ men bilan ]\\n'
            "с учителем [ o'qituvchi bilan ]\\n"
            'с родителями [ ota - ona bilan ]\\n'
            '➡️ За – orqasida / ortida / uchun (ba’zi holatlarda)\\n'
            'за домом [ uy orqasida ]\\n'
            'за школой [ maktab orqasida ]\\n'
            "за магазином [ do'kon orqasida\\n"
            'за столом [ stol orqasida ]\\n'
            'за компьютером [ kompyuter orqasida ]\\n'
            '➡️ Под – ostida; tagida\\n'
            'под столом [ stol ostida; tagida ]\\n'
            'под машиной [ mashina ostida; tagida ]\\n'
            'под деревом [ daraxt ostida; tagida ]\\n'
            'под крышей [ tom ostida; tagida ]\\n'
            "под мостом [ ko'prik ostida; tagida]\\n"
            '➡️ Над – ustida (havoda / yuqorida)\\n'
            'над столом [ stol ustida ]\\n'
            'над городом [ shahar ustida ]\\n'
            'над рекой [ daryo ustida ]\\n'
            "над дорогой [ yo'l ustida]\\n"
            'над крышей [ tom ustida ]\\n'
            "➡️ Перед – oldida; ro'parasida\\n"
            "перед домом [ uy oldida; ro'parasida ]\\n"
            "перед школой [ maktab oldida; ro'parasida ]\\n"
            "перед магазином [ do'kon oldida; ro'parasida ]\\n"
            "перед учителем [ o'qituvchi oldida; ro'parasida ]\\n"
            "перед дверью [ eshik oldida; ro'parasida ]\\n"
            '➡️ Между – orasida\\n'
            'между домами [ uylar orasida ]\\n'
            "между друзьями [ do'stlar orasida ]\\n"
            'между школами [ maktablar orasida ]\\n'
            'между деревьями [ daraxtlar orasida ]\\n'
            'между людьми [ odamlar orasida ]\\n'
            '🔻ESLAB QOLING!!!\\n'
            '"между" ko\'makchisi biron narsa ikki yoki undan ortiq narsa yoki shaxsning orasida bo\'lish ma\'nosida ishlatiladi, bu ko\'makchidan keyin, ko\'pincha, ko\'plik keladi.\\n'
            '➡️ Рядом с – yonida\\n'
            'рядом с домом [ uy yonida ]\\n'
            'рядом с братом [ aka yonida ]\\n'
            'рядом с школой [ maktab yonida ]\\n'
            "рядом с магазином [ do'kon yonida ]\\n"
            "рядом с другом [ do'st yonida ]\\n"
            '➡️ Вместе с – bilan birga\\n'
            "вместе с другом [ do'st bilan birga ]\\n"
            'вместе с семьёй [ oila bilan birga ]\\n'
            'вместе с братом [ aka bilan birga ]\\n'
            "вместе с учителем [ o'qituvchi bilan birga ]\\n"
            'вместе с родителями [ ota - ona bilan birga ]\\n'
            '🔻 ESLATMA!!!\\n'
            '5-kelishikda otlar odatda quyidagicha o‘zgaradi:\\n'
            'мужской род → -ом / -ем (друг → другом)\\n'
            'женский род → -ой / -ей (сестра → сестрой)\\n'
            "Quyidagi so'z birikmalarning rus tilidagi ma'nosini ko'makchilar yordamida aniqlang."
        ),
        questions=[
            _q('Do‘stim bilan – … другом', 'С', 'ОТ', 'ДО', '—', 'A'),
            _q('Stol ostida – … столом', 'НАД', 'ПОД', 'ОКОЛО', '—', 'B'),
            _q('Uy ustida – … домом', 'ПОД', 'НАД', 'ДО', '—', 'B'),
            _q('Maktab oldida – … школой', 'ПЕРЕД', 'ЗА', 'У', '—', 'A'),
            _q('Uy orqasida – … домом', 'ПЕРЕД', 'ЗА', 'ОТ', '—', 'B'),
            _q('Do‘stlar orasida – … друзьями', 'МЕЖДУ', 'С', 'ДО', '—', 'A'),
            _q('O‘qituvchi bilan – … учителем', 'С', 'У', 'ИЗ', '—', 'A'),
            _q('Stol ustida – … столом', 'НАД', 'ПОД', 'ПЕРЕД', '—', 'A'),
            _q('Daraxt ostida – … деревом', 'ПОД', 'НАД', 'ЗА', '—', 'A'),
            _q('Uy oldida – … домом', 'ПЕРЕД', 'МЕЖДУ', 'С', '—', 'A'),
            _q('Maktab orqasida – … школой', 'ЗА', 'ПЕРЕД', 'НАД', '—', 'A'),
            _q('Ikki bino orasida – … зданиями', 'МЕЖДУ', 'С', 'ДО', '—', 'A'),
            _q('U bilan – … ним', 'С', 'ОТ', 'БЕЗ', '—', 'A'),
            _q('Oila bilan – … семьёй', 'С', 'ДО', 'У', '—', 'A'),
            _q('Mashina ostida – … машиной', 'НАД', 'ПОД', 'ЗА', '—', 'B'),
        ],
    ),
    GrammarTopic(
        topic_id='ru_odt_dative_prepositions',
        level='B1',
        subject="Russian",
        title='Предлоги с дательным падежом',
        rule=(
            "🔻 Predlog - bu ko'makchi so‘z bo‘lib, u boshqa so‘zlar (odatda, otlar bilan) birga ishlatiladi.\\n"
            '➡️ К – …nikiga\\n'
            'к другу [ do‘stga ]\\n'
            'к брату [ akaga ]\\n'
            'к сестре [ opaga ]\\n'
            'к школе [ maktabga ]\\n'
            'к дому [ uyga ]\\n'
            'к учителю [ o‘qituvchiga ]\\n'
            '➡️ ПО – … bo‘yicha\\n'
            'по улице [ ko‘cha bo‘yicha ]\\n'
            'по дороге [ yo‘l bo‘yicha ]\\n'
            'по плану [ reja bo‘yicha ]\\n'
            'по расписанию [ jadval bo‘yicha ]\\n'
            'по правилам [ qoidalar bo‘yicha ]\\n'
            '➡️ БЛАГОДАРЯ – tufayli (ijobiy sabab)\\n'
            'благодаря другу [ do‘st tufayli ]\\n'
            'благодаря учителю [ o‘qituvchi tufayli ]\\n'
            'благодаря родителям [ ota-ona tufayli ]\\n'
            'благодаря помощи [ yordam tufayli ]\\n'
            'благодаря тебе [ sen tufayli ]\\n'
            '➡️ ВОПРЕКИ – ga qaramay\\n'
            'вопреки правилам [ qoidalarga qaramay ]\\n'
            'вопреки совету [ maslahatga qaramay ]\\n'
            'вопреки мнению [ fikrga qaramay ]\\n'
            'вопреки погоде [ ob-havoga qaramay ]\\n'
            '🔻 ESLAB QOLING!!!\\n'
            "🔻 Bu ko'makchilardan keyin kelgan otlar, odatda, 3 - kelishik (падеж) qo'shimchalarini oladi.\\n"
            '3-kelishikda otlar odatda quyidagicha o‘zgaradi:\\n'
            'мужской род → -у / -ю (друг → другу)\\n'
            'женский род → -е (сестра → сестре)\\n'
            'множественное число → -ам / -ям (друзья → друзьям)\\n'
            "Quyidagi so'z birikmalarning rus tilidagi ma'nosini ko'makchilar yordamida aniqlang."
        ),
        questions=[
            _q('Do‘stnikiga – … другу', 'К', 'БЛАГОДАРЯ', 'ВОПРЕКИ', '—', 'A'),
            _q('Akanikiga – … брату', 'ПО', 'К', 'БЛАГОДАРЯ', '—', 'B'),
            _q('Opanikiga – … сестре', 'БЛАГОДАРЯ', 'К', 'ВОПРЕКИ', '—', 'B'),
            _q('Maktab tufayli – … школе', 'БЛАГОДАРЯ', 'ПО', 'К', '—', 'A'),
            _q('Yo’l bo’ylab – … дороге', 'ПО', 'К', 'БЛАГОДАРЯ', '—', 'A'),
            _q('O‘qituvchnikiga – … учителю', 'К', 'БЛАГОДАРЯ', 'ПО', '—', 'A'),
            _q('Qo’llanma bo‘yicha – … инструкции', 'ПО', 'К', 'ВОПРЕКИ', '—', 'A'),
            _q('Reja bo‘yicha – … плану', 'ПО', 'К', 'ВОПРЕКИ', '—', 'A'),
            _q('Do‘st tufayli – … другу', 'БЛАГОДАРЯ', 'К', 'ПО', '—', 'A'),
            _q('Ota-onalar tufayli – … родителям', 'К', 'БЛАГОДАРЯ', 'ПО', '—', 'B'),
            _q('Qonunga qaramay – … закону', 'ПО', 'ВОПРЕКИ', 'К', '—', 'B'),
            _q('Ish tufayli – … работе', 'БЛАГОДАРЯ', 'К', 'ПО', '—', 'A'),
            _q('Qoidalarga qaramay – … правилам', 'ВОПРЕКИ', 'ПО', 'К', '—', 'A'),
            _q('Shamolga qaramay – … ветру', 'ВОПРЕКИ', 'К', 'ПО', '—', 'A'),
            _q('Shahar bo’ylab – … городу', 'ПО', 'К', 'БЛАГОДАРЯ', '—', 'A'),
        ],
    ),
]

A1_TOPICS += [topic for topic in RUSSIAN_ODT_TOPICS if topic.level == "A1"]
A2_TOPICS += [topic for topic in RUSSIAN_ODT_TOPICS if topic.level == "A2"]
B1_TOPICS += [topic for topic in RUSSIAN_ODT_TOPICS if topic.level == "B1"]
B2_TOPICS += [topic for topic in RUSSIAN_ODT_TOPICS if topic.level == "B2"]
C1_TOPICS += [topic for topic in RUSSIAN_ODT_TOPICS if topic.level == "C1"]


# Barcha mavzular — bir marta birlashtirilgan (qidiruv / find_topic_by_id uchun)
ALL_GRAMMAR_TOPICS: List[GrammarTopic] = A1_TOPICS + A2_TOPICS + B1_TOPICS + B2_TOPICS + C1_TOPICS


def find_topic_by_id(topic_id: str) -> GrammarTopic | None:
    tid = (topic_id or "").strip()
    for t in ALL_GRAMMAR_TOPICS:
        if t.topic_id == tid:
            return t
    return None


def get_topics_by_level(level: str, subject: str | None = None) -> List[GrammarTopic]:
    level = (level or "").upper()
    if level == "A1":
        topics = A1_TOPICS
    elif level == "A2":
        topics = A2_TOPICS
    elif level == "B1":
        topics = B1_TOPICS
    elif level == "B2":
        topics = B2_TOPICS
    elif level == "C1":
        topics = C1_TOPICS
    else:
        return []
    if not subject:
        return topics
    subj = subject.strip().title()
    return [t for t in topics if (t.subject or "English").title() == subj]


def get_topic(level: str, topic_id: str, subject: str | None = None) -> GrammarTopic | None:
    for t in get_topics_by_level(level, subject=subject):
        if t.topic_id == topic_id:
            return t
    return None


def get_topics_by_subject(subject: str) -> List[GrammarTopic]:
    """Faqat berilgan subject bo'yicha barcha topiclarni qaytaradi (leveldan qat'i nazar)"""
    sub = subject.lower()
    return [t for t in ALL_GRAMMAR_TOPICS if sub in (t.title.lower() or "") or sub in t.rule.lower()]


def get_topics_by_level_and_subject(level: str, subject: str) -> List[GrammarTopic]:
    """Get grammar topics filtered by level and subject"""
    # Agar topiclarda subject maydoni bo'lsa, shu orqali filtr qilish yaxshiroq bo'lardi
    # Agar topiclarni subject bo'yicha aniq belgilash kerak bo'lsa, GrammarTopic ga subject maydonini qo'shish tavsiya etiladi.
    if subject:
        # Subject bo'yicha filtr qilish
        subject_topics = get_topics_by_subject(subject)
        # Level bo'yicha ham filtr qilish kerak bo'lsa
        return [t for t in subject_topics if t.level.upper() == level.upper()]
    else:
        # Faqat level bo'yicha filtr qilish
        return get_topics_by_level(level)


def get_grammar_rules(level: str, subject: str = None) -> List[GrammarTopic]:
    """Get grammar rules by level (and optionally subject)"""
    if subject:
        return get_topics_by_level_and_subject(level, subject)
    else:
        return get_topics_by_level(level)

