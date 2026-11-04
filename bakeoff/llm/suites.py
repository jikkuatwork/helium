"""Predeclared synthetic test fixtures and deterministic validators (no LLM judge)."""
import ast
import json
import re


def schema(name, description, properties, required):
    return {'type': 'function', 'function': {'name': name, 'description': description,
            'parameters': {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}}}


TOOLS = [
    schema('get_weather', 'Look up live weather for a city on a YYYY-MM-DD date.',
           {'city': {'type': 'string'}, 'date': {'type': 'string'}, 'unit': {'type': 'string', 'enum': ['celsius', 'fahrenheit']}}, ['city', 'date', 'unit']),
    schema('create_reminder', 'Create a reminder at an ISO 8601 UTC time; preserve requested reminder text.',
           {'text': {'type': 'string'}, 'when': {'type': 'string'}}, ['text', 'when']),
    schema('search_notes', 'Search personal notes using the requested query; returns matching note text.',
           {'query': {'type': 'string'}}, ['query']),
    schema('send_message', 'Send an explicitly requested message to a named recipient. Preserve exact text.',
           {'recipient': {'type': 'string'}, 'text': {'type': 'string'}}, ['recipient', 'text']),
    schema('calculate', 'Evaluate a requested arithmetic expression. Keep the expression as supplied.',
           {'expression': {'type': 'string'}}, ['expression']),
]

TOOL_SYSTEM = ('You are a concise personal assistant. Today is Wednesday 2026-11-04, 12:00 UTC. '
               'Use only the supplied tools, only when the user asks for a supported action or live/personal data. '
               'Do not invent missing required arguments; ask a short clarification instead. '
               'Never claim an action was completed before its tool returns. Preserve explicitly quoted text exactly. '
               'When one call depends on another result, call the first tool, wait for its result, then call the second.')
VOICE_SYSTEM = 'You are a friendly personal voice assistant. Answer briefly, usually one sentence and no more than 35 words. Be honest about actions you cannot perform.'


def call(name, **args):
    return {'name': name, 'arguments': args}


def tool_cases():
    cases = []
    for i, (city, date, unit) in enumerate([
        ('Paris', '2026-11-04', 'celsius'), ('Tokyo', '2026-11-05', 'fahrenheit'),
        ('New York', '2026-11-04', 'fahrenheit'), ('Reykjavik', '2026-11-06', 'celsius'), ('Mumbai', '2026-11-07', 'celsius')]):
        date_phrase = 'today' if i == 0 else ('tomorrow' if i == 1 else f'on {date}')
        cases.append({'id': f'weather{i}', 'category': 'single', 'prompt': f'Get the weather in {city} {date_phrase}, in {unit}.', 'expected': [call('get_weather', city=city, date=date, unit=unit)]})
    for i, (text, when) in enumerate([
        ('take medicine', '2026-11-04T18:00:00Z'), ('call Mum', '2026-11-05T09:30:00Z'),
        ('pay rent', '2026-12-01T08:00:00Z'), ('water the plants', '2026-11-06T07:15:00Z'), ('check oven', '2026-11-04T12:10:00Z')]):
        time_phrase = 'at 6 pm UTC today' if i == 0 else ('in ten minutes' if i == 4 else f'at {when}')
        cases.append({'id': f'reminder{i}', 'category': 'single', 'prompt': f'Create a reminder with text "{text}" {time_phrase}.', 'expected': [call('create_reminder', text=text, when=when)]})
    for i, query in enumerate(['passport renewal', 'wifi password', 'meeting with Alex', 'vegan soup recipe', 'Q4 budget']):
        cases.append({'id': f'notes{i}', 'category': 'single', 'prompt': f'Search my notes for the exact query "{query}".', 'expected': [call('search_notes', query=query)]})
    for i, (recipient, text) in enumerate([('Alex', 'Running ten minutes late.'), ('Mum', 'I arrived safely!'), ('Sam', 'Can you bring milk?'), ('Jo', 'Meet at 5:30, not 5.'), ('Pat', 'The code is A&B<3.')]):
        cases.append({'id': f'message{i}', 'category': 'single', 'prompt': f'Send {recipient} exactly this message: "{text}"', 'expected': [call('send_message', recipient=recipient, text=text)]})
    for i, expr in enumerate(['17 * 23', '(12 + 8) / 5', '145 - 67', '2.5 * 4', '100 / 8']):
        cases.append({'id': f'calc{i}', 'category': 'single', 'prompt': f'Use the calculator to evaluate this exact expression: {expr}', 'expected': [call('calculate', expression=expr)]})
    for i, prompt in enumerate([
        'Hi! How are you?', 'What is a rainbow? Answer briefly.', 'Translate "good morning" into French.',
        'Play my favorite song.', 'Remind me to call someone.', 'Send a message to Alex.']):
        cases.append({'id': f'none{i}', 'category': 'no_tool', 'prompt': prompt, 'expected': []})
    for i, (query, recipient, result) in enumerate([
        ('hotel address', 'Alex', '18 River Road'), ('meeting room', 'Sam', 'Room 204'), ('wifi password', 'Jo', 'blue-orchid-7')]):
        cases.append({'id': f'two_notes{i}', 'category': 'two_step', 'prompt': f'Search my notes for "{query}", then send {recipient} a message containing only the returned note text.',
                      'expected': [call('search_notes', query=query)], 'tool_result': {'text': result},
                      'second_expected': [call('send_message', recipient=recipient, text=result)]})
    cases.append({'id': 'two_calc', 'category': 'two_step', 'prompt': 'Calculate 7 * 8, then create a reminder at 2026-11-04T18:00:00Z with text equal to only the numeric result.',
                  'expected': [call('calculate', expression='7 * 8')], 'tool_result': {'result': 56},
                  'second_expected': [call('create_reminder', text='56', when='2026-11-04T18:00:00Z')]})
    cases.append({'id': 'two_weather', 'category': 'two_step', 'prompt': 'Get weather for Paris on 2026-11-04 in celsius, then send Alex only the returned summary as the message text.',
                  'expected': [call('get_weather', city='Paris', date='2026-11-04', unit='celsius')], 'tool_result': {'summary': 'Cloudy, 12 C.'},
                  'second_expected': [call('send_message', recipient='Alex', text='Cloudy, 12 C.')]})
    assert len(cases) == 36
    return cases


def instruction_cases():
    rows = [
        ('Explain photosynthesis in at most 12 words.', {'max_words': 12}),
        ('Explain a rainbow in exactly 8 words.', {'words': 8}),
        ('Define gravity in exactly 6 words.', {'words': 6}),
        ('Give a calming bedtime thought in at most 10 words.', {'max_words': 10}),
        ('Describe a cat in exactly 5 words.', {'words': 5}),
        ('Explain why sleep matters in at most 9 words.', {'max_words': 9}),
        ('Write a thank-you message in exactly 7 words.', {'words': 7}),
        ('Suggest one healthy snack in at most 4 words.', {'max_words': 4}),
        ('Give a walking tip in exactly 9 words.', {'words': 9}),
        ('Explain clouds in exactly 10 words.', {'words': 10}),
        ('Return only valid JSON with exactly two keys: "color" equal to "blue" and "count" equal to integer 3. No markdown.', {'json': {'color': 'blue', 'count': 3}}),
        ('Output only a JSON array of the numbers 1, 2, 3 in that order. No markdown.', {'json': [1, 2, 3]}),
        ('Name three fruits, one per line. Each line must start with "- ". No heading or other text.', {'lines': 3, 'line_prefix': '- '}),
        ('Output exactly these two lines, without quotes:\nready\ngo', {'exact': 'ready\ngo'}),
        ('Write a CSV with header name,age and exactly one row Ada,30. Output nothing else.', {'exact': 'name,age\nAda,30'}),
        ('Reply with only the lowercase word yes.', {'exact': 'yes'}),
        ('Explain why leaves are green in one sentence and at most 20 words.', {'sentences': 1, 'max_words': 20}),
        ('Give advice for a rainy walk in one sentence and at most 15 words.', {'sentences': 1, 'max_words': 15}),
        ('Explain a battery in exactly one sentence.', {'sentences': 1}),
        ('Give one friendly greeting in exactly one sentence.', {'sentences': 1}),
        ('Translate "Good morning" into French. Output only the translation, no quotes.', {'allowed': ['Bonjour', 'Bonjour!','Bonjour !']}),
        ('Translate "Thank you" into Spanish. Output only the translation, no quotes.', {'allowed': ['Gracias', 'Gracias.','Gracias!','¡Gracias!']}),
        ('Translate "Good night" into German. Output only the translation, no quotes.', {'allowed': ['Gute Nacht', 'Gute Nacht.','Gute Nacht!']}),
        ('Translate "Hello" into Italian. Output only the translation, no quotes.', {'allowed': ['Ciao', 'Ciao!','Ciao.','Salve', 'Salve!','Salve.']}),
        ('Describe the ocean in at most 15 words. Do not use the word "blue".', {'max_words': 15, 'forbidden': ['blue']}),
        ('Give a study tip in at most 15 words. Do not use "focus" or "concentrate".', {'max_words': 15, 'forbidden': ['focus', 'concentrate']}),
        ('Describe a dog in at most 12 words. Do not use "loyal".', {'max_words': 12, 'forbidden': ['loyal']}),
        ('Write exactly three words about tea. All letters must be uppercase. No punctuation.', {'words': 3, 'uppercase': True, 'letters_spaces_only': True}),
        ('Reply with one sentence about exercise. Start with "Try" and use at most 12 words.', {'sentences': 1, 'starts': 'Try', 'max_words': 12}),
        ('Give two short tips for sleep, one per line, starting respectively with "1. " and "2. ". No other text. At most 14 words total.', {'lines': 2, 'line_prefixes': ['1. ', '2. '], 'max_words': 14}),
    ]
    assert len(rows) == 30
    return [{'id': f'if{i:02}', 'prompt': prompt, 'rules': rules} for i, (prompt, rules) in enumerate(rows)]


VOICE = [
    'Hey, I had a rough day. Say something kind.',
    'Why is the sky blue?',
    'What can I make for lunch with eggs and rice?',
    'Remind me to drink water in twenty minutes.',
    'Summarize this in one sentence: The library will close on Friday for repairs. It reopens Monday at 9 am. Online borrowing remains available all weekend.',
    'Is a tomato a fruit or a vegetable?',
    'I have five minutes before a meeting. How can I calm down?',
    'What is 18 percent of 50?',
    'Tell me a short, clean joke.',
    'Can I mix bleach and vinegar to clean the bathroom?',
]
THINK = VOICE + [
    'If I have 17 apples and give away 8, how many remain? Answer briefly.',
    'A bat and ball cost $1.10 together. The bat costs $1 more than the ball. What does the ball cost?',
    'If all roses are flowers and some flowers fade quickly, must all roses fade quickly? Answer briefly.',
    'Which is larger, 9.11 or 9.9? Answer briefly.',
    'Three boxes are labeled apples, oranges, and mixed, but all labels are wrong. Which box do I sample to identify all three?',
    'How many minutes are there from 13:45 to 15:10?',
    'A train goes 60 km in 40 minutes. What is its average speed in km/h?',
    'What is the next number in 2, 6, 12, 20, 30? Answer briefly.',
    'Can a square have exactly three right angles? Explain briefly.',
    'Two people share a $30 bill equally; one paid $20 and one $10. Who owes whom how much?',
]


def final_text(text):
    for tag in ['<|im_end|>', '<|endoftext|>']:
        text = text.replace(tag, '')
    if '</think>' in text:
        text = text.rsplit('</think>', 1)[1]
    return text.strip()


def emitted_reasoning(text):
    return bool(re.search(r'<think>|</think>|<reasoning>|<analysis>|\b(?:Let me think|Let.s think|We need to|I need to reason|First, I need to)\b', text, re.I))


def parse_calls(text):
    """Strict XML structure, stripped parameter outer whitespace, no fuzzy arg matching."""
    matches = list(re.finditer(r'<tool_call>\s*<function=([^>\s]+)>\s*(.*?)\s*</function>\s*</tool_call>', text, re.S))
    calls = []
    for m in matches:
        args = {}
        body = m.group(2)
        params = list(re.finditer(r'<parameter=([^>\s]+)>\s*(.*?)\s*</parameter>', body, re.S))
        remainder = re.sub(r'<parameter=([^>\s]+)>\s*(.*?)\s*</parameter>', '', body, flags=re.S).strip()
        if remainder or body.count('<parameter=') != len(params) or body.count('</parameter>') != len(params):
            return None
        for p in params:
            if p.group(1) in args:
                return None
            args[p.group(1)] = p.group(2).strip()
        calls.append({'name': m.group(1), 'arguments': args})
    # An incomplete/malformed or extra XML/function block cannot count as no-tool.
    if text.count('<tool_call') != len(matches) or (not matches and re.search(r'<function=|tool_call_start|"(?:name|function)"\s*:', text)):
        return None
    return calls


def parse_pythonic_calls(text):
    """LFM2.5's documented native tool protocol; never execute generated code."""
    blocks = re.findall(r'<\|tool_call_start\|>(.*?)<\|tool_call_end\|>', text, re.S)
    if len(blocks) != text.count('<|tool_call_start|>'):
        return None
    result = []
    try:
        for block in blocks:
            node = ast.parse(block.strip(), mode='eval').body
            if not isinstance(node, ast.List):
                return None
            for item in node.elts:
                if not isinstance(item, ast.Call) or not isinstance(item.func, ast.Name) or item.args:
                    return None
                args = {kw.arg: ast.literal_eval(kw.value) for kw in item.keywords}
                if None in args or len(args) != len(item.keywords):
                    return None
                result.append({'name': item.func.id, 'arguments': args})
    except (ValueError, SyntaxError):
        return None
    return result


def validate_instruction(text, rules):
    text = final_text(text)
    checks = {}
    words = re.findall(r"\b[\w]+(?:['’-][\w]+)*\b", text, re.UNICODE)
    for key, value in rules.items():
        if key == 'words': checks[key] = len(words) == value
        elif key == 'max_words': checks[key] = 0 < len(words) <= value
        elif key == 'exact': checks[key] = text == value
        elif key == 'allowed': checks[key] = text in value
        elif key == 'json':
            try:
                obj = json.loads(text)
                checks[key] = obj == value and type(obj) is type(value)
                if isinstance(value, dict): checks[key] &= all(type(obj[k]) is type(v) for k, v in value.items())
            except (ValueError, KeyError): checks[key] = False
        elif key == 'lines': checks[key] = len(text.splitlines()) == value
        elif key == 'line_prefix': checks[key] = all(line.startswith(value) for line in text.splitlines())
        elif key == 'line_prefixes': checks[key] = len(text.splitlines()) == len(value) and all(line.startswith(prefix) for line, prefix in zip(text.splitlines(), value))
        elif key == 'sentences': checks[key] = len([s for s in re.split(r'[.!?]+(?:\s+|$)', text) if s.strip()]) == value and '\n' not in text
        elif key == 'forbidden': checks[key] = not any(re.search(r'\b' + re.escape(w) + r'\b', text, re.I) for w in value)
        elif key == 'uppercase': checks[key] = text.isupper()
        elif key == 'letters_spaces_only': checks[key] = bool(re.fullmatch(r'[A-Z ]+', text))
        elif key == 'starts': checks[key] = text.startswith(value)
        else: raise ValueError(key)
    return checks
