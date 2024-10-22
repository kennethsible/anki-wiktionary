import re
from argparse import ArgumentParser
from bz2 import BZ2File
from itertools import zip_longest

from ordered_set import OrderedSet
from wiktionary_de_parser import Parser

bzfile_path = 'dewiktionary-latest-pages-articles-multistream.xml.bz2'
bz_file = BZ2File(bzfile_path)
umlaut = OrderedSet(['ä', 'ü', 'ö'])
articles = OrderedSet(['der', 'die', 'das'])


def pl_diff(singular: str, plural: str) -> str:
    suffix: OrderedSet[str] = OrderedSet()
    for x, y in zip_longest(singular, plural, fillvalue=''):
        if x != y:
            suffix.add(y)
    if suffix.intersection(umlaut):
        return ', -̈' + ''.join(suffix - umlaut)
    if None in suffix:
        print((singular, plural))
    return ', -' + ''.join(suffix)


def extract_verb(record: dict, fields: list[str]) -> str:
    if 'flexion' not in record:
        return fields[1]
    entry, flexion = fields[1], record['flexion']
    try:
        if 'Präsens_er, sie, es' not in flexion:
            entry += ', ' + flexion['Präsens_er, sie, es ']
        else:
            entry += ', ' + flexion['Präsens_er, sie, es']
        entry += ', ' + flexion['Präteritum_ich']
        entry += ', ' + ('hat' if flexion['Hilfsverb'] == 'haben' else 'ist')
        entry += ' ' + flexion['Partizip II']
    except KeyError as e:
        print(record)
        raise e
    return entry


def extract_substantiv(record: dict, fields: list[str]) -> str:
    if 'flexion' not in record:
        return fields[1]
    entry, flexion = '', record['flexion']
    if 'Genus' in flexion or 'Genus 1' in flexion:
        genus = 'Genus' if 'Genus' in flexion else 'Genus 1'
        if flexion[genus] == 'm':
            entry += 'der'
        elif flexion[genus] == 'f':
            entry += 'die'
        elif flexion[genus] == 'n':
            entry += 'das'
        else:
            print(record)
            raise RuntimeError()
        entry += ' ' + fields[1]
        if 'Nominativ Plural' in flexion:
            entry += pl_diff(record['title'], flexion['Nominativ Plural'])
        elif 'Nominativ Plural 1' in flexion:
            entry += pl_diff(record['title'], flexion['Nominativ Plural 1'])
    elif 'Nominativ Plural' in flexion:
        entry += 'die ' + fields[1]
    else:
        print(record)
        raise RuntimeError()
    return entry


def extract_entry(record: dict, fields: list[str]) -> str:
    pos_flag = False
    entry = ''
    tags: OrderedSet[str] = OrderedSet()
    for k in [2, 6, 10]:
        if len(fields) > k:
            tag = fields[k]
            if ',' in tag:
                tags = tags.union(tag.split(', '))
            elif '(' not in tag:
                tags.add(tag)
    if 'Verb' in record['pos'] and 'verb' in tags:
        if pos_flag:
            raise RuntimeError(record['title'])
        pos_flag = True
        entry += extract_verb(record, fields)
    if 'Substantiv' in record['pos'] and tags.intersection(articles):
        if pos_flag:
            raise RuntimeError(record['title'])
        pos_flag = True
        entry += extract_substantiv(record, fields)
    ipa = record['ipa'][0] if 'ipa' in record else ''
    if pos_flag:
        entry = '\t'.join([fields[0], entry, ipa, *fields[2:]])
    else:
        entry = '\t'.join([*fields[0:2], ipa, *fields[2:]])
    return entry.rstrip() + '\t' + ' '.join(tags) + '\n'


def main():
    parser = ArgumentParser()
    parser.add_argument('--input-deck', metavar='FILE_PATH', required=True, help='original deck')
    parser.add_argument('--output-deck', metavar='FILE_PATH', required=True, help='enhanced deck')
    parser.add_argument('--exceptions', metavar='FILE_PATH', help='manually-corrected exceptions')
    args = parser.parse_args()

    output = []
    with open(args.input_deck) as input_f:
        lines = list(input_f.readlines())
        for record in Parser(bz_file):
            if 'lang_code' not in record or record['lang_code'] != 'de':
                continue
            for i, line in enumerate(lines):
                fields = line.split('\t')
                if record['title'] == re.sub(r'\s\((sich|r, s)\)', '', fields[1]):
                    output.append(extract_entry(record, fields).rstrip() + '\n')
                    lines.pop(i)
                    break
            if len(output) == len(lines):
                break

    sorted_output = output[:]
    for line in lines:
        fields = line.split('\t')
        sorted_output.append('\t'.join([*fields[0:2], '', *fields[2:]]).rstrip())
        tags = OrderedSet()
        for k in [2, 6, 10]:
            if len(fields) > k:
                tag = fields[k]
                if ',' in tag:
                    tags = tags.union(tag.split(', '))
                elif '(' not in tag:
                    tags.add(tag)
        sorted_output[-1] += '\t' + ' '.join(tags) + '\n'
    sorted_output.sort(key=lambda x: int(x.split('\t')[0]))

    with open(args.exceptions) as exceptions_f:
        for line in exceptions_f.readlines():
            sorted_output[int(line.split('\t')[0]) - 1] = line

    with open(args.output_deck, 'w') as output_f:
        output_f.writelines(sorted_output)


if __name__ == '__main__':
    main()
