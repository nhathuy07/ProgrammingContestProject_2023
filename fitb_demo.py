import underthesea as uts
from stopwords import stopwords_vi
from random import randint, sample, choice
from string import *
from math import inf
import requests

"""Part of speech"""
NOUN_POS = ('N', 'Np', 'Nu', 'Nb')

# N: Noun
# Np: Proper noun
# Nu: Unit noun
# Nb: Abbreviation noun
# V: Verb
# A: Adjective
# R: Adverb
# P: Pronoun
# L: Determiner
# M: Numeral
# B: Preposition
# E: Conjunction
# C: Subordinating conjunction
# I: Interjection

raw_text = """Trong vật lý, chuyển động tròn là chuyển động quay của một chất điểm trên một vòng tròn: một cung tròn hoặc quỹ đạo tròn. Nó có thể là một chuyển động đều với vận tốc góc không đổi, hoặc chuyển động không đều với vận tốc góc thay đổi theo thời gian. Các phương trình mô tả chuyển động tròn của một vật không có kích thước hình học, đúng hơn là chuyển động của một điểm giả định trên một mặt phẳng. Trong thực tế, khối tâm của vật đang xét có thể được coi là chuyển động tròn.

Ví dụ chuyển động tròn của một vệ tinh nhân tạo bay quanh Trái Đất theo một quỹ đạo địa tĩnh, một hòn đá được cột với một sợi dây và quay tròn (ném tạ), một chiếc xe đua chạy qua một đường cong trong một đường đua, một electron chuyển động vuông góc với một từ trường đều, và bánh răng quay trong một máy cơ khí.

Chuyển động tròn là không đều ngay cả khi vận tốc góc ω không đổi, bởi vì vector vận tốc v của điểm đang xét liên tục đổi hướng. Sự thay đổi hướng của vận tốc liên quan đến gia tốc gây ra do lực hướng tâm kéo vật di chuyển về phía tâm của quỹ đạo tròn. Nếu không có gia tốc này, đối tượng sẽ di chuyển trên một đường thẳng theo các định luật của Newton về chuyển động."""

definitions = {
    "Chuyển động tròn": "Chuyển động quay của một chất điểm trên một vòng tròn",
    "Vận tốc góc": "Tốc độ xoay của chuyển động tròn",
    "Quỹ đạo": "Đường cong mà chất điểm di chuyển trong chuyển động tròn",
    "Khối tâm": "Điểm giả định trong chuyển động tròn, được coi là vật không có kích thước hình học",
    "Hướng tâm": "Hướng tác dụng của lực kéo vật đi về phía tâm của quỹ đạo tròn",
    "Gia tốc": "Thay đổi vận tốc theo thời gian",
    "Định luật Newton về chuyển động": "Định luật miêu tả chuyển động của vật được đưa ra bởi Sir Isaac Newton."
}

sentences = raw_text.split('\n')[1:]

def fetch_summarization(fullform: str, length: int):
    
    _r = requests.post(
        url='https://api.openai.com/v1/chat/completions',
        headers= {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer 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'
        },
        json=
        {
            "model": "gpt-3.5-turbo",
            "temperature": 0.18, 
            "top_p": 1.0,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "max_tokens": 2048,
            "messages": [
            {
                "role": "system",
                "content": "You are a language model that can extract key sentences."
            },
            {
                "role": "user",
                "content": fullform
            },
            {
                "role": "assistant",
                "content": f"Sure, here are {length} key sentences in Vietnamese"
            }
        ]}
    )
    _raw_responses: list[str] = _r.json()['choices'][0]['message']['content'].split('.')

    for res in _raw_responses:
        if res.isnumeric() or res == '':
            _raw_responses.remove(res)

    return _raw_responses
        

def fetch_content_phrase(sentence):
    """Fetch content phrase from sentence"""
    pos_tagged = uts.pos_tag(sentence)
    print([(i, y) for i, y in enumerate(pos_tagged)])
    content_phrase_buffer = ""
    result = []
    for index, item in enumerate(pos_tagged):
        # if the current word is not stopword and is a content word
        # add the word to the content phrase buffer
        if (item[1] in NOUN_POS or item[1] in ('V', 'A', 'M', 'R')) and item[0].lower() not in stopwords_vi:
            result.append((index, item[0]))
    
    return {"content_words": (result), "full_form": pos_tagged}

def generate_fitb(content_words: dict[str, list[any]], blank_cnt: str):
    _s = content_words["full_form"]
    _c = content_words["content_words"]
    _answers = []

    _type: str = choice(("FITB", "FITB_MCQ"))

    if _type == 'FITB':
        _blank_cnt = min(int(blank_cnt), len(content_words["content_words"]))
        for _ in range(_blank_cnt):
            # select a random content phrase in sentence
            _i = randint(0, len(_c) - 1)
            _t = _c.pop(_i)

            # truncate the beginning of the grams
            _t_truncated = _t[1].split(" ")
            _t_truncated = map(lambda _g: _g.replace(_g[1:], "..."), _t_truncated)
            _t_truncated = " ".join(tuple(_t_truncated))

            _answers.append(_t)

            # replace the phrase with a blank
            try:
                _s[_t[0]] = (f"<{_t_truncated}>", _s[_t[0]])
            except:
                pass
            
        _s = " ".join([x for x, _ in _s])

    elif _type == 'FITB_MCQ':
        _blank_cnt = min(5, len(content_words["content_words"]))
        for _ in range(int(_blank_cnt)):
            # select a random content phrase in sentence
            _i = randint(0, len(_c) - 1)
            _t = _c.pop(_i)

            _answers.append(_t)
        
            # replace the phrase with a blank
            try:
                _s[_t[0]] = (f"<...>", _s[_t[0]])
            except:
                pass
        
        _s = " ".join([x for x, _ in _s])

    
    # sort the keys by ascending order in original sentence
    _answers.sort(key=lambda x: x[0])

    return (_type, _s, tuple(_answers))

def generate_wh_qs_from_definitions(definitions: dict[str, str], key: str, value: str):
    qs = []

    possible_keys = list(definitions.keys())
    possible_vals = list(definitions.values())
    possible_key_num = len(definitions)

    definition_pos_tag = uts.pos_tag(value)
    is_noun = definition_pos_tag[0][1] in NOUN_POS
    _r = randint(0, 1)
    word_definition = f"{'Sự ' if not is_noun else ''}{value.rstrip('.') if is_noun else value.replace(value[0], value[0].lower())}"

    match _r:
        case 0:
            incorrect_answers = possible_keys.copy()
            incorrect_answers.remove(key)
            qs.append((f'Từ nào mang nghĩa: {word_definition.replace(word_definition[0], word_definition[0].lower())}?' , key, sample(incorrect_answers, min(3, possible_key_num))))
        case 1:
            incorrect_answers = possible_vals.copy()
            incorrect_answers.remove(value)
            qs = (f'{key} có nghĩa là gì?' , word_definition, sample(incorrect_answers, min(3, possible_key_num)))

    return qs

def generate_true_false_qs(definitions: dict[str, str], _key: str):
    qs = []
    _vals = list(definitions.values())

    _val = choice(_vals)
    if _val == definitions[_key]:
        qs = ((f'{_key} có nghĩa là {_val.replace(_val[0], _val[0].lower())}.', True))
    else:
        qs = ((f'{_key} có nghĩa là: {_val.replace(_val[0], _val[0].lower())}.', False))
    
    return qs
