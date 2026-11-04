"""Fixed authored corpus. Raw and deliberately pre-normalized spoken forms.

No model output or ASR result was used to select/edit these references.
"""
import json
from pathlib import Path

DATA = {
'prose': [
'The quick brown fox jumps over the lazy dog.',
'Please close the window before you leave the room.',
'The library opens early and stays quiet until lunch.',
'We planted a small tree beside the old stone bridge.',
'I forgot my umbrella but the rain stopped before dinner.',
'Your package should arrive tomorrow morning at the front desk.',
'The children watched the ducks swim across the pond.',
'Save your work before restarting the computer.',
'Would you like a cup of tea or a glass of water?',
'A warm breeze carried the smell of bread through the village.'
],
'structured': [
('The total is $23.45, including tax.', 'The total is twenty three dollars and forty five cents, including tax.'),
('The meeting is on 03/15/2026 at 9:30 AM.', 'The meeting is on March fifteenth, twenty twenty six at nine thirty a m.'),
('Sales increased by 12.5% last quarter.', 'Sales increased by twelve point five percent last quarter.'),
('The train leaves at 6:05 PM from platform 7.', 'The train leaves at six oh five p m from platform seven.'),
('She finished 21st in a race with 108 runners.', 'She finished twenty first in a race with one hundred eight runners.'),
('The blue notebook costs €5.50 and the pen costs £2.', 'The blue notebook costs five euros and fifty cents and the pen costs two pounds.'),
('Call 202-555-0198 and ask for extension 42.', 'Call two zero two five five five zero one nine eight and ask for extension forty two.'),
('The temperature fell from 18°C to -3°C overnight.', 'The temperature fell from eighteen degrees Celsius to minus three degrees Celsius overnight.'),
('Send the report to alex@example.com before Friday.', 'Send the report to alex at example dot com before Friday.'),
('The shipment contains 2,450 bolts weighing 3.75 kg.', 'The shipment contains two thousand four hundred fifty bolts weighing three point seven five kilograms.')
],
'names': [
'Maya Thompson met Daniel Brooks near the station.',
'Aisha Khan and Priya Patel are leading the new project.',
'Siobhan Murphy sent a letter to Niamh O Sullivan.',
'Xavier Rodriguez booked a flight from Seattle to Chicago.',
'Professor Nguyen invited Zhang Wei to the seminar.',
'Fatima Hassan visited the museum with Gabriel Santos.',
'Charlotte Beaumont moved from Edinburgh to Cambridge.',
'Joaquin Alvarez spoke with Saoirse Ronan after the rehearsal.',
'The river runs through Worcester before reaching Gloucester.',
'Anjali Menon and Dimitri Petrov shared a table at the cafe.'
],
'acronyms': [
('NASA launched a new satellite on Tuesday.', 'NASA launched a new satellite on Tuesday.'),
('The CPU and GPU share access to the same memory.', 'The c p u and g p u share access to the same memory.'),
('Use the API to send a JSON response over HTTP.', 'Use the a p i to send a jay son response over h t t p.'),
('The FBI contacted the local police about the case.', 'The f b i contacted the local police about the case.'),
('A USB cable connects the SSD to the laptop.', 'A u s b cable connects the s s d to the laptop.'),
('The BBC and CNN reported the result this morning.', 'The b b c and c n n reported the result this morning.'),
('Enable HTTPS and check the DNS configuration.', 'Enable h t t p s and check the d n s configuration.'),
('The MRI scan was reviewed by the hospital team.', 'The m r i scan was reviewed by the hospital team.'),
('NATO and UNESCO issued separate statements.', 'NATO and UNESCO issued separate statements.'),
('Our SQL database stores each URL as plain text.', 'Our s q l database stores each u r l as plain text.')
],
'long': [
'Although the forecast predicted heavy rain throughout the afternoon, the volunteers arrived at the park before sunrise, collected the fallen branches, repaired the wooden benches, and finished planting flowers just as the first visitors walked through the gate.',
'When you receive the replacement device, please copy your documents to a separate drive, check that every important file opens correctly, sign out of your accounts, and only then reset the old device to its original settings.',
'The research team compared several approaches to the problem, but they chose the simplest method because it was easier to explain, used less memory, and continued to work reliably when the network connection failed during the final demonstration.',
'After spending the summer restoring the old house, the family invited their neighbors to dinner, opened the windows to let in the evening breeze, and talked about the years when the garden had been full of fruit trees.',
'If the train is delayed again tomorrow, we can take the earlier bus to the city, leave our bags at the hotel, and walk along the river before meeting everyone at the small restaurant opposite the theater.'
]}

SHORT = 'Please bring the blue notebook to our meeting this morning.'
PARAGRAPH = ('The town library is preparing a new reading room for local families. '
'Volunteers have painted the walls, repaired the shelves, and arranged comfortable chairs beside the windows. '
'Children will be able to borrow books, listen to stories, and practice reading with patient helpers. '
'The room will also offer a quiet place for students to study after school. '
'Everyone is invited to the opening on Saturday morning, when the librarian will explain how the new program works.')
LONG = ('On a clear morning, the team walked from the station to the small workshop beside the river. '
'They wanted to build a speaking assistant that could run without an internet connection. '
'The device needed to be simple enough for anyone to use and small enough to fit inside a wooden box. '
'First they tested the microphone in a quiet room, then they repeated the same experiment while traffic passed outside. '
'The assistant understood most requests, but a few unusual names and long addresses still caused problems. '
'Rather than hide those mistakes, the team wrote them down and prepared a careful list of examples. '
'Next they compared two voices using exactly the same sentences. '
'One voice spoke slowly and clearly, while the other sounded lively and natural. '
'They measured how long each system took to begin speaking, how much memory it needed, and whether it could keep up with a conversation. '
'They also asked a separate speech recognizer to transcribe every recording, knowing that this was only a rough measure of intelligibility. '
'After lunch they listened to the samples through headphones and through the tiny speaker inside the box. '
'Some differences were easy to hear, but others depended on the sentence and the volume. '
'By the end of the afternoon they had enough evidence to choose a promising direction, though they agreed that the final test should happen on the actual device. '
'Their report included the source of every model, the settings used for every run, and a list of questions that still needed answers. '
'Before leaving, they saved the results, closed the workshop windows, and placed the prototype on a shelf for the next morning.')


def corpus():
    rows = []
    for category, entries in DATA.items():
        for item in entries:
            raw, spoken = item if isinstance(item, tuple) else (item, item)
            rows.append({'id': f'{category}-{len(rows)+1:02}', 'category': category,
                         'raw': raw, 'spoken': spoken})
    return rows

if __name__ == '__main__':
    root = Path.home()/'datasets/tts'
    root.mkdir(parents=True,exist_ok=True)
    (root/'corpus.json').write_text(json.dumps(corpus(), indent=2, ensure_ascii=False)+'\n')
    (root/'speed_texts.json').write_text(json.dumps({'short': SHORT, 'paragraph': PARAGRAPH, 'long': LONG},indent=2)+'\n')
