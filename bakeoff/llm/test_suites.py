import unittest
from suites import (tool_cases, instruction_cases, parse_calls, parse_pythonic_calls,
                    emitted_reasoning, final_text, validate_instruction)
from runner import state_output


class FixturesTest(unittest.TestCase):
    def test_counts_and_categories(self):
        cases = tool_cases()
        self.assertEqual(len(cases), 36)
        self.assertEqual(sum(c['category'] == 'single' for c in cases), 25)
        self.assertEqual(sum(c['category'] == 'no_tool' for c in cases), 6)
        self.assertEqual(sum(c['category'] == 'two_step' for c in cases), 5)
        self.assertEqual(len(instruction_cases()), 30)

    def test_state_mapping(self):
        self.assertEqual(state_output('past_conv.0'), 'present_conv.0')
        self.assertEqual(state_output('past_recurrent.1'), 'present_recurrent.1')
        self.assertEqual(state_output('past_key_values.3.key'), 'present.3.key')

    def test_xml_strict(self):
        good = '<tool_call>\n<function=send_message>\n<parameter=recipient>Alex</parameter>\n<parameter=text>The code is A&B<3.</parameter>\n</function>\n</tool_call>'
        self.assertEqual(parse_calls(good), [{'name': 'send_message', 'arguments': {'recipient': 'Alex', 'text': 'The code is A&B<3.'}}])
        self.assertEqual(parse_calls('Hello!'), [])
        self.assertIsNone(parse_calls(good + '<tool_call>'))
        self.assertIsNone(parse_calls(good.replace('</parameter>', '', 1)))
        self.assertIsNone(parse_calls('<tool_call>{"name": "send_message"}</tool_call>'))
        self.assertIsNone(parse_calls('{"name": "send_message", "arguments": {}}'))
        self.assertIsNone(parse_calls(good.replace('<parameter=text>', '<parameter=recipient>')))

    def test_pythonic_safe(self):
        self.assertEqual(parse_pythonic_calls('<|tool_call_start|>[calculate(expression="2 * 3")]<|tool_call_end|>'), [{'name': 'calculate', 'arguments': {'expression': '2 * 3'}}])
        self.assertIsNone(parse_pythonic_calls('<|tool_call_start|>[__import__("os").system("oops")]<|tool_call_end|>'))
        self.assertIsNone(parse_pythonic_calls('<|tool_call_start|>[calculate(**{})]<|tool_call_end|>'))

    def test_reasoning(self):
        self.assertFalse(emitted_reasoning('Paris.<|im_end|>'))
        self.assertTrue(emitted_reasoning('<think>Hmm.</think>Paris.'))
        self.assertEqual(final_text('reasoning</think>Paris.<|im_end|>'), 'Paris.')

    def test_constraints(self):
        self.assertTrue(all(validate_instruction('TEA IS WARM', {'words': 3, 'uppercase': True, 'letters_spaces_only': True}).values()))
        self.assertFalse(all(validate_instruction('TEA IS WARM!', {'words': 3, 'uppercase': True, 'letters_spaces_only': True}).values()))
        self.assertTrue(all(validate_instruction('Clouds are water.', {'sentences': 1, 'max_words': 5}).values()))
        self.assertFalse(all(validate_instruction('Clouds are water. They float.', {'sentences': 1}).values()))
        self.assertFalse(all(validate_instruction('```json\n[1,2,3]\n```', {'json': [1, 2, 3]}).values()))
        self.assertFalse(all(validate_instruction('{"count": true}', {'json': {'count': 1}}).values()))


if __name__ == '__main__':
    unittest.main()
