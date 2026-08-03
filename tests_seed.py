from db import delete_all_tests, get_conn

question_data = [
    # English level-checking test (50 questions)
    ('English', 'Hello! My name _ Anna.', 'am', 'is', 'are', 'be', 'B'),
    ('English', 'Where _ you from?', 'is', 'am', 'are', 'be', 'C'),
    ('English', 'I saw _ elephant at the zoo.', 'a', 'an', 'the', '-', 'B'),
    ('English', 'She _ to the market every Sunday.', 'go', 'goes', 'going', 'went', 'B'),
    ('English', 'Yesterday I _ pizza for dinner.', 'eat', 'eats', 'ate', 'eating', 'C'),
    ('English', 'Look! It _ right now.', 'rain', 'rains', 'is raining', 'rained', 'C'),
    ('English', 'I think it _ tomorrow.', 'rains', 'will rain', 'is raining', 'rained', 'B'),
    ('English', 'I _ Paris three times.', 'visit', 'visited', 'have visited', 'am visiting', 'C'),
    ('English', 'This car is _ than that one.', 'fast', 'faster', 'fastest', 'more fast', 'B'),
    ('English', 'Mount Everest is the _ mountain in the world.', 'high', 'higher', 'highest', 'most high', 'C'),
    ('English', 'The book is _ the table.', 'in', 'on', 'at', 'to', 'B'),
    ('English', 'You _ smoke here. It’s forbidden.', 'can', 'must', 'must not', 'may', 'C'),
    ('English', 'If I _ rich, I would travel the world.', 'am', 'was', 'were', 'have been', 'C'),
    ('English', 'This house _ in 1990.', 'built', 'is built', 'was built', 'builds', 'C'),
    ('English', 'He said he _ tired.', 'is', 'was', 'be', 'been', 'B'),
    ('English', 'The man _ lives next door is a doctor.', 'who', 'which', 'where', 'when', 'A'),
    ('English', 'I enjoy _ books in my free time.', 'read', 'to read', 'reading', 'reads', 'C'),
    ('English', 'I want _ you tomorrow.', 'help', 'to help', 'helping', 'helped', 'B'),
    ('English', 'Please _ the lights when you leave the room.', 'turn off', 'turn on', 'turn up', 'turn down', 'A'),
    ('English', 'I _ a mistake in my homework.', 'made', 'did', 'took', 'had', 'A'),
    ('English', 'The synonym of "big" is:', 'small', 'large', 'short', 'thin', 'B'),
    ('English', 'The opposite of "hot" is:', 'cold', 'warm', 'boiling', 'cool', 'A'),
    ('English', 'She sings very _.', 'beautiful', 'beautifully', 'beauty', 'beautify', 'B'),
    ('English', 'He _ up smoking last year.', 'gave', 'give', 'gives', 'given', 'A'),
    ('English', '"To postpone" means:', 'cancel', 'delay', 'start', 'finish', 'B'),
    ('English', 'If she had studied harder, she _ the exam.', 'would pass', 'would have passed', 'will pass', 'passed', 'B'),
    ('English', 'I wish I _ a new car.', 'have', 'had', 'would have', 'having', 'B'),
    ('English', 'I had my hair _ yesterday.', 'cut', 'to cut', 'cutting', 'cuts', 'A'),
    ('English', 'Never _ I seen such a beautiful place.', 'have', 'has', 'had', 'having', 'A'),
    ('English', 'It is essential that everyone _ on time.', 'is', 'be', 'are', 'was', 'B'),
    ('English', 'The prefix for the opposite of "happy" is:', 'un-', 'dis-', 'in-', 'im-', 'A'),
    ('English', '"Ubiquitous" means:', 'rare', 'found everywhere', 'old', 'expensive', 'B'),
    ('English', 'Despite the bad weather, we decided to _ the picnic.', 'call off', 'go ahead with', 'put off', 'look forward to', 'B'),
    ('English', 'Strong _ is my favourite drink in the morning.', 'tea', 'coffee', 'milk', 'juice', 'B'),
    ('English', 'The noun form of "beautiful" is:', 'beauty', 'beautifully', 'beautify', 'beautifulness', 'A'),
    ('English', 'I feel very _ today after the good news.', 'happy', 'happily', 'happiness', 'happier', 'A'),
    ('English', 'The meeting was _ because of the holiday.', 'cancelled', 'postponed', 'started', 'finished', 'A'),
    ('English', 'She is the most _ person I know – she never tells lies.', 'honest', 'dishonest', 'honesty', 'honestly', 'A'),
    ('English', 'If it rains tomorrow, we _ inside.', 'stay', 'will stay', 'stayed', 'would stay', 'B'),
    ('English', 'The children _ quietly while the teacher was speaking.', 'sat', 'were sitting', 'have sat', 'sit', 'B'),
    ('English', 'I have known her _ 2015.', 'for', 'since', 'from', 'at', 'B'),
    ('English', 'This is the best film I _ this year.', 'see', 'saw', 'have seen', 'am seeing', 'C'),
    ('English', 'By the time we arrived, the movie _.', 'started', 'had started', 'has started', 'starts', 'B'),
    ('English', 'You can borrow my book as long as you _ it back next week.', 'bring', 'brought', 'will bring', 'brings', 'A'),
    ('English', 'The teacher asked us _ we had finished our homework.', 'if', 'that', 'what', 'who', 'A'),
    ('English', 'The more you practise, _ your English will become.', 'the better', 'better', 'the best', 'best', 'A'),
    ('English', 'She suggested _ to the cinema tonight.', 'go', 'to go', 'going', 'went', 'C'),
    ('English', '"I’ll call you later," he said. → He said he _ me later.', 'will call', 'would call', 'calls', 'called', 'B'),
    ('English', 'Had I known the answer, I _ the question.', 'would answer', 'would have answered', 'will answer', 'answered', 'B'),
    ('English', 'The committee recommended that the project _ immediately.', 'starts', 'start', 'started', 'to start', 'B'),
    # Russian full list from user
    ('Russian', 'Я ... Вас, молодой человек. Что у Вас болит?', 'слушаю', 'слышу', 'грустю', 'пью', 'B'),
    ('Russian', 'Здесь шумно, я не ..., что ты говоришь.', 'слушаю', 'слышу', 'вижу', 'читаю', 'B'),
    ('Russian', 'Утром я обязательно ... радио.', 'слушаю', 'слышу', 'танцую', 'ем', 'A'),
    ('Russian', 'Все счастливые семьи ... друг на друга.', 'одинаковые', 'похожи', 'любят', 'живут', 'B'),
    ('Russian', 'Мы с Леной случайно купили ... сумки.', 'одинаковые', 'похожие', 'новые', 'старые', 'B'),
    ('Russian', 'На фотографии братья очень ... .', 'одинаковые', 'похожи', 'ровные', 'сильные', 'B'),
    ('Russian', 'Такого озера больше нигде нет, оно ... в мире.', 'редкое', 'единственное', 'единое', 'розовое', 'B'),
    ('Russian', 'Хлеб очень свежий, посмотри, какой он … .', 'крепкий', 'твёрдый', 'мягкий', 'сладкий', 'C'),
    ('Russian', 'Бабушка не пьёт очень ... чай.', 'крепкий', 'сильный', 'твёрдый', 'солёный', 'A'),
    ('Russian', 'Я не умею ... машину.', 'ездить', 'возить', 'водить', 'стирать', 'C'),
    ('Russian', 'Мы долго ходили ... музею.', 'по', 'к', 'в', 'на', 'A'),
    ('Russian', 'Банк работает ... 9 часов.', 'во время', 'от', 'с', 'на', 'C'),
    ('Russian', 'Наша кошка всегда спит под … .', 'кресло', 'креслом', 'кресле', 'кроватью', 'B'),
    ('Russian', 'Мы проехали мимо … .', 'остановку', 'остановки', 'остановке', 'остановках', 'B'),
    ('Russian', 'Сейчас в магазине перерыв до … .', 'трёх часов', 'трём часам', 'три часа', 'тремя часами', 'A'),
    ('Russian', 'У меня болит рука, завтра пойду … .', 'к хирургу', 'с хирургом', 'у хирурга', 'в хирурге', 'A'),
    ('Russian', 'Архангельск стоит на берегу ... .', 'Белым морем', 'Белого моря', 'Белому морю', 'Белое море', 'B'),
    ('Russian', 'Виктор давно интересуется … .', 'Древняя Греция', 'Древнюю Грецию', 'Древней Грецией', 'Древними Грециями', 'C'),
    ('Russian', 'Дай, пожалуйста, бутылку … .', 'красное вино', 'красного вина', 'красному вину', 'красным вином', 'B'),
    ('Russian', 'Антон каждый вечер водит … гулять.', 'с младшим братом', 'младшему брату', 'младшего брата', 'младшим братом', 'C'),
    ('Russian', 'Концерт ... 2 часа.', 'начинался', 'продолжался', 'кончался', 'проходил', 'B'),
    ('Russian', 'После жаркого дня наконец ... вечер.', 'выступил', 'поступил', 'наступил', 'окончил', 'C'),
    ('Russian', 'Мы попросили Виктора Ивановича ... новые слова.', 'обсудить', 'объяснить', 'рассказать', 'написать', 'B'),
    ('Russian', 'Мне нравятся часы, которые ... на стене.', 'лежат', 'стоят', 'висят', 'виснут', 'C'),
    ('Russian', 'Наташа ... квартиру весь день.', 'убирала', 'собирала', 'собиралась', 'убирается', 'A'),
    ('Russian', 'Я люблю ... дома.', 'учиться', 'изучать', 'заниматься', 'работать', 'A'),
    ('Russian', 'Я привыкла рано … .', 'встаю', 'вставала', 'вставать', 'встать', 'C'),
    ('Russian', 'Брат попросил Артёма ... вечером.', 'позвонить', 'позвонил', 'позвонит', 'позвонив', 'A'),
    ('Russian', 'Банк уже закрыт, я не успел ... деньги.', 'поменять', 'поменяю', 'поменял', 'поменяв', 'A'),
    ('Russian', 'Вчера Виктор …, что скоро женится.', 'объявляет', 'объявит', 'объявил', 'объявляя', 'C'),
    ('Russian', 'В детстве Люба часто ... в цирк.', 'шла', 'ходила', 'ходит', 'идти', 'B'),
    ('Russian', 'Сегодня Антон ... раньше всех.', 'пришёл', 'приходил', 'приходит', 'придёт', 'A'),
    ('Russian', 'Обычно папа ... с работы поздно.', 'пришёл', 'приходил', 'приходит', 'приходил(а)', 'B'),
    ('Russian', 'Вчера я опоздал и ... в театр после начала спектакля.', 'пришёл', 'приходил', 'приходящ', 'приходят', 'A'),
    ('Russian', 'Почему Вы решили ... завтра во Владимир?', 'ехать', 'ездить', 'едете', 'поехать', 'A'),
    ('Russian', 'Разве ты любишь ... на машине?', 'ехать', 'ездить', 'едешь', 'поехать', 'B'),
    ('Russian', 'Николай Петрович только вчера ... из Парижа.', 'прилетал', 'прилетел', 'приехал', 'приезжал', 'B'),
    ('Russian', 'Он ... в Москву и сразу поехал в университет.', 'прилетал', 'прилетел', 'приехал', 'приходил', 'B'),
    ('Russian', 'Театр был недалеко, Вася ... до него за 10 минут.', 'дошёл', 'вышел', 'ушёл', 'пришёл', 'A'),
    ('Russian', 'Девочка испугалась и … .', 'добежала', 'убежала', 'прибежала', 'приехала', 'B'),
    ('Russian', 'Я знаю, ... писателе вы говорите.', 'какое', 'с каким', 'какому', 'о каком', 'D'),
    ('Russian', 'Я не знаю, ... звонил Николай.', 'о ком', 'кто', 'кого', 'кому', 'B'),
    ('Russian', 'Я не знаю, … он обещал сделать.', 'что', 'чем', 'к чему', 'о чём', 'A'),
    ('Russian', 'Пабло не объяснил, ... он поехал в Россию.', 'куда', 'где', 'как', 'зачем', 'D'),
    ('Russian', 'Борис был очень занят, ... он не пошёл в парк.', 'потому что', 'поэтому', 'и', 'но', 'B'),
    ('Russian', 'Я прочитал в газете, ... открылся новый музей.', 'что', 'чтобы', 'когда', 'где', 'A'),
    ('Russian', 'Оля купила овощи, ... сделать салат.', 'чтобы', 'что', 'для того чтобы', 'как', 'A'),
    ('Russian', 'Борис любит шахматы, ... мы нет.', 'а', 'и', 'но', 'или', 'A'),
    ('Russian', 'Не понимаю, ... он поехал в Сибирь.', 'почему', 'где', 'куда', 'когда', 'A'),
    ('Russian', 'Надо рано вставать, ... много сделать.', 'чтобы', 'если', 'тогда', 'чтоб', 'A'),
]


def seed(force=False):
    if force:
        delete_all_tests()

    inserted = 0
    skipped = 0
    conn = get_conn()
    cur = conn.cursor()
    try:
        for subject, question, a, b, c, d, correct in question_data:
            cur.execute(
                "SELECT id FROM tests WHERE LOWER(TRIM(subject))=LOWER(TRIM(?)) AND question=? LIMIT 1",
                (subject, question),
            )
            if cur.fetchone():
                skipped += 1
                continue
            cur.execute(
                """
                INSERT INTO tests (subject, question, option_a, option_b, option_c, option_d, correct_option)
                VALUES (?,?,?,?,?,?,?)
                """,
                (subject, question, a, b, c, d, correct),
            )
            inserted += 1
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()
    return {"inserted": inserted, "skipped": skipped, "total": len(question_data)}


if __name__ == '__main__':
    seed(force=True)
