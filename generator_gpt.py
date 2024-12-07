from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.schema import SystemMessage, HumanMessage
from dotenv import load_dotenv
import os
import json
from langchain_openai import ChatOpenAI
from helper import *

load_dotenv()

llm = ChatOpenAI(
    model="gpt-4o",
    temperature=1,
    max_tokens=None,
    timeout=None,
    max_retries=4,
)

# Prompt: Add new word to crossword puzzle
generate_word_prompt_template = read_prompt_template('prompts/generate_word_prompt_template.txt')

chat_prompt = ChatPromptTemplate.from_messages([
    SystemMessage(content=generate_word_prompt_template),
    HumanMessagePromptTemplate.from_template("Character positions:\n{char_positions}\n\nWords:\n{words}")
])


def append_new_word(words_dict, new_word):
    words_dict.get('words').append(new_word)


def remove_last_word(words_dict):
    words_dict.get('words').pop()


def generate_next_word(input_words, retry_count=1):
    # get character positions
    char_positions, words = get_character_positions_and_words(input_words)
    print_char_positions_and_words(char_positions, words)

    # get new word
    response1 = llm(messages=chat_prompt.format_messages(char_positions=char_positions, words=words))
    print("Attempting to generate a new word")
    print(response1.content)
    print('*' * 50)

    # extract new word from response1
    print("Extracting new word from response")
    new_word = extract_new_word_from_text(response1.content)
    print(new_word)
    print('*' * 50)

    generate = False

    if not new_word.get('message'):
        append_new_word(input_words, new_word)

        # again get character positions
        char_positions, words = get_character_positions_and_words(input_words)
        print_char_positions_and_words(char_positions, words)

        # validate new word after adding it to input_words
        print("Performing validation step")
        valid = validate_crossword_puzzle(char_positions)

        if not valid:
            print(f"VALIDATION FAILURE: {new_word}; Retrying with another word")
            print('*' * 50)
            remove_last_word(input_words)
            retry_count -= 1
            if retry_count >= 0:
                generate, input_words, new_word = generate_next_word(input_words, retry_count)
        else:
            generate = True
            print(f"VALIDATION SUCCESS: {new_word}")

    return generate, input_words, new_word


# Sample Input
crossword_json = {
    "words": [
        {
            "word": "bravo",
            "row": 0,
            "column": 1,
            "isAcross": True,
            "clue": "form of joy",
            "positions": "(b, 0, 1), (r, 0, 2), (a, 0, 3), (v, 0, 4), (o, 0, 5)"
        },
        {
            "word": "air",
            "row": 0,
            "column": 3,
            "isAcross": False,
            "clue": "used to breathe",
            "positions": "(a, 0, 3), (i, 1, 3), (r, 2, 3)"
        }
    ]
}

if __name__ == "__main__":
    count = 0

    while True:
        generate, input_words, added_word = generate_next_word(crossword_json, 3)
        if not generate or len(input_words['words']) >= 10:
            break

        count += 1

        print(f"SUCCESS: new word added is {added_word}")
        print(f"New word count: {count}")
        print('*' * 50)

        crossword_json = input_words

    final_crossword = json.dumps(crossword_json)

    print(final_crossword)