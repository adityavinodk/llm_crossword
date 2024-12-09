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

solver_prompt_template = read_prompt_template("prompts/solver_prompt_template.txt")

chat_prompt = ChatPromptTemplate.from_messages(
    [
        SystemMessage(content=solver_prompt_template),
        HumanMessagePromptTemplate.from_template(
            "clue_metadata=\n{clue_metadata}\n\nchar_positions=\n{char_positions}\n\nwords={words}\n\ngrid_size={grid_size}"
        ),
    ]
)


def append_new_word(words_dict, new_word):
    words_dict.get("words").append(new_word)


def remove_last_word(words_dict):
    words_dict.get("words").pop()


def solve_puzzle_clue(llm, grid_size, clue_metadata, solved_state, retry_count=1):
    # get character positions
    char_positions, words = get_character_positions_and_words(solved_state, grid_size)
    # print_char_positions_and_words(char_positions, words)

    guessed = False
    new_word_dict = {}

    while not guessed and retry_count > 0:
        # get new word
        response = llm.invoke(
            input=chat_prompt.format_messages(
                clue_metadata=clue_metadata,
                char_positions=char_positions,
                words=words,
                grid_size=grid_size,
            )
        )
        print("Attempting to guess a new clue")
        print(response.content)
        print("*" * 50)

        # extract new word from response1
        print("Extracting guessed word from response")
        new_word_dict = extract_json_from_text(response.content)
        print(new_word_dict)
        print("*" * 50)

        if not new_word_dict.get("message"):
            append_new_word(solved_state, new_word_dict)
            try:
                char_positions, words = get_character_positions_and_words(
                    solved_state, grid_size
                )
                guessed = True
            except (CharacterConflictException, OutOfBoundsException) as e:
                print(e)
                print("Retrying...")
                print("*" * 50)
                remove_last_word(solved_state)
                retry_count -= 1
        else:
            print("Retrying...")
            retry_count -= 1

    new_clue_metadata = clue_metadata
    if guessed:
        new_clue_metadata = [
            clue for clue in clue_metadata if clue["clue"] != new_word_dict["clue"]
        ]

    return guessed, new_clue_metadata, solved_state, new_word_dict


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
        "--puzzle",
        type=str,
        required=True,
        help="File which stores the crossword puzzle state.",
    )

    args = parser.parse_args()

    if args.grid_size < 10:
        parser.error("grid_size must be at least 10.")

    with open("crossword.json", "r") as f:
        puzzle = json.load(f)

    print(f"Model: {args.model}")
    print(f"Grid Size: {args.grid_size}")

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

    unsolved_count = len(puzzle["words"])
    clue_metadata, solution = return_clue_metadata(puzzle)
    guessed = True
    api_retry_count = 3
    solved_state = {"words": []}
    while unsolved_count and api_retry_count > 0:
        guessed, clue_metadata, solved_state, solved_word = solve_puzzle_clue(
            llm, args.grid_size, clue_metadata, solved_state, 5
        )

        if guessed:
            unsolved_count -= 1
            api_retry_count = 3
            print(f"SUCCESS: new word guessed is {solved_word}")
            print(f"Remaining unsolved count: {unsolved_count}")
            print("*" * 50)
        else:
            print("FAILED: calling API to guess word again")
            print("*" * 50)
            api_retry_count -= 1

    print(json.dumps(solved_state, indent=4))
    print(f"Final Solved Word Count: {len(solved_state["words"])}")

    grid_data, _ = get_character_positions_and_words(solved_state, args.grid_size)
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

    correct_count = 0
    for word_d in solved_state["words"]:
        if word_d["word"] == solution[(word_d["row"], word_d["column"], word_d["isAcross"])]:
            correct_count += 1
    print(f"\nCorrect - {correct_count}/{len(puzzle["words"])}")
