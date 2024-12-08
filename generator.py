from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.schema import SystemMessage
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv
import json
import os
import argparse
from helper import *

load_dotenv()


# Prompt: Add new word to crossword puzzle
generate_word_prompt_template = read_prompt_template(
    "prompts/generate_word_prompt_template.txt"
)

chat_prompt = ChatPromptTemplate.from_messages(
    [
        SystemMessage(content=generate_word_prompt_template),
        HumanMessagePromptTemplate.from_template(
            "Character positions:\n{char_positions}\n\nWords:{words}\n\nGrid Size:{grid_size}"
        ),
    ]
)


def append_new_word(words_dict, new_word):
    words_dict.get("words").append(new_word)


def remove_last_word(words_dict):
    words_dict.get("words").pop()


def generate_next_word(llm, grid_size, input_words, retry_count=1):
    # get character positions
    char_positions, words = get_character_positions_and_words(input_words, grid_size)
    print_char_positions_and_words(char_positions, words)

    generated = False
    new_word_dict = {}

    while not generated and retry_count > 0:
        # get new word
        response1 = llm.invoke(
            input=chat_prompt.format_messages(
                char_positions=char_positions, words=words, grid_size=grid_size
            )
        )
        print("Attempting to generate a new word")
        print(response1.content)
        print("*" * 50)

        # extract new word from response1
        print("Extracting new word from response")
        new_word_dict = extract_json_from_text(response1.content)
        print(new_word_dict)
        print("*" * 50)

        if not new_word_dict.get("message"):
            append_new_word(input_words, new_word_dict)
            try:
                char_positions, words = get_character_positions_and_words(
                    input_words, grid_size
                )
                generated = True
            except CharacterConflictException as e:
                print(e)
                print("Retrying...")
                print("*" * 50)
                remove_last_word(input_words)
                retry_count -= 1
        else:
            print("Retrying...")
            retry_count -= 1
    return generated, input_words, new_word_dict


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crossword Puzzle Generator")
    parser.add_argument(
        "--model",
        choices=["claude", "openai"],
        required=True,
        help="Choose the model to use: 'claude' or 'openai'.",
    )
    parser.add_argument(
        "--grid_size",
        type=int,
        required=True,
        help="Grid size for the crossword puzzle (minimum 10).",
    )
    parser.add_argument(
        "--word_count",
        type=int,
        required=True,
        help="Number of words to generate (minimum 10).",
    )

    args = parser.parse_args()

    if args.grid_size < 10:
        parser.error("grid_size must be at least 10.")
    if args.word_count < 5:
        parser.error("word_count must be at least 10.")

    # Print parsed arguments
    print(f"Model: {args.model}")
    print(f"Grid Size: {args.grid_size}")
    print(f"Word Count: {args.word_count}")

    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=1,
        max_tokens=None,
        timeout=None,
        max_retries=4,
    )
    if args.model == "claude":
        llm = ChatAnthropic(
            model="claude-3-sonnet-20240229",
            anthropic_api_key=os.getenv("CLAUDE_API_KEY"),
            temperature=1,
            max_tokens=1000,
        )

    count = 0
    generated = True
    api_retry_count = 3
    crossword_json = {"words": []}
    while count < args.word_count and api_retry_count > 0:
        generated, input_words, added_word = generate_next_word(
            llm, args.grid_size, crossword_json, 5
        )

        if generated:
            count += 1
            api_retry_count = 3
            print(f"SUCCESS: new word added is {added_word}")
            print(f"New word count: {count}")
            print("*" * 50)
        else:
            print("FAILED: calling API to add word again")
            print("*" * 50)
            api_retry_count -= 1

        crossword_json = input_words

    print(json.dumps(crossword_json, indent=4))
    print(f"Final Added Word Count: {count}")

    grid_data, _ = get_character_positions_and_words(crossword_json, args.grid_size)
    positions = {}
    for d in grid_data:
        positions[f"{d['row']},{d['column']}"] = d["character"]

    print("\nCROSSWORD -")
    for i in range(args.grid_size):
        for j in range(args.grid_size):
            if f"{i},{j}" in positions:
                print(positions[f"{i},{j}"], end=" ")
            else:
                print("_", end=" ")
        print()
