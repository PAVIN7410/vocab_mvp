#words/intervals.py:

import datetime

def sm2_algorithm(word, grade):
    if grade < 3:
        word.repetitions = 0
        word.interval = 1
    else:
        if word.repetitions == 0:
            word.interval = 1
        elif word.repetitions == 1:
            word.interval = 6
        else:
            word.interval = round(word.interval * word.ease_factor)
        word.repetitions += 1
    word.ease_factor = max(1.3, word.ease_factor + 0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
    word.next_review = datetime.datetime.now() + datetime.timedelta(days=word.interval)
    word.save()
