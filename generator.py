from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.schema import SystemMessage
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv
import json
import os
import argparse
from configs.solver import solver_configs
from helper import *
from solver import solve

load_dotenv()

MAX_CROSSWORD_ITERATIONS = 3

generate_word_prompt_template = read_prompt_template(
    "prompts/generate_word_prompt_template.txt"
)

generate_appropriate_clue_prompt_template = read_prompt_template(
    "prompts/clue_generation_prompt_template.txt"
)

word_generation_chat_prompt = ChatPromptTemplate.from_messages(
    [
        SystemMessage(content=generate_word_prompt_template),
        HumanMessagePromptTemplate.from_template(
            "char_positions=\n{char_positions}\n\nwords={words}\n\ngrid_size={grid_size}"
        ),
    ]
)

clue_generation_chat_prompt = ChatPromptTemplate.from_messages(
    [
        SystemMessage(content=generate_appropriate_clue_prompt_template),
        HumanMessagePromptTemplate.from_template(
            "words:\n{words}\n\ndifficulty:{difficulty}"
        )
    ]
)


def append_new_word(words_dict, new_word):
    words_dict.get("words").append(new_word)


def remove_last_word(words_dict):
    words_dict.get("words").pop()


def generate_next_word(llm, grid_size, input_words, retry_count=1):
    # get character positions
    char_positions, words = get_character_positions_and_words(input_words, grid_size)
    # print_char_positions_and_words(char_positions, words)

    generated = False
    new_word_dict = {}

    while not generated and retry_count > 0:
        # get new word
        response1 = llm.invoke(
            input=word_generation_chat_prompt.format_messages(
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

        if isinstance(new_word_dict, dict) and not new_word_dict.get("message"):
            append_new_word(input_words, new_word_dict)
            try:
                char_positions, words = get_character_positions_and_words(
                    input_words, grid_size
                )
                generated = True
            except (CharacterConflictException, OutOfBoundsException) as e:
                print(e)
                print("Retrying...")
                print("*" * 50)
                remove_last_word(input_words)
                retry_count -= 1
        else:
            print("Retrying...")
            retry_count -= 1
    return generated, input_words, new_word_dict


def generate(llm, grid_size, word_count):
    count = 0
    generated = True
    api_retry_count = 3
    crossword_json = {"words": []}
    while count < word_count and api_retry_count > 0:
        generated, input_words, added_word = generate_next_word(
            llm, grid_size, crossword_json, 5
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

    write_file(crossword_json, 0)
    print(f"Final Added Word Count: {count}")

    grid_data, _ = get_character_positions_and_words(crossword_json, grid_size)
    positions = {}
    for d in grid_data:
        positions[f"{d['row']},{d['column']}"] = d["character"]

    print(f"\nCROSSWORD:")
    for i in range(grid_size):
        for j in range(grid_size):
            if f"{i},{j}" in positions:
                print(positions[f"{i},{j}"], end=" ")
            else:
                print("_", end=" ")
        print()

    return crossword_json, "output/crossword-0.json"


def get_solver(config):
    if "gpt" in config.get("model"):
        return ChatOpenAI(**config)
    elif "claude" in config.get("model"):
        return ChatAnthropic(**config)


# List[{"solved": [...], "unsolved": [...]}]
def get_word_accuracy(crossword, solver_responses):
    solved = {}
    unsolved = {}
    accuracy = {}

    # build stats at word level
    for response in solver_responses:
        for word in response["solved"]:
            if word in solved:
                solved[word] = solved[word] + 1
            else:
                solved[word] = 1

        for word in response["unsolved"]:
            if word in unsolved:
                unsolved[word] = unsolved[word] + 1
            else:
                unsolved[word] = 1

    for word_d in crossword["words"]:
        word = word_d['word']
        solved_count = solved[word] if word in solved else 0
        unsolved_count = unsolved[word] if word in unsolved else 0
        accuracy[word] = solved_count / (solved_count + unsolved_count)

    print_word_accuracy(accuracy)

    return accuracy


def determine_clue_updates_needed(crossword, accuracy, desired_difficulty):
    # see if a change in clue is required based on word accuracy
    update_clue = {}

    words = [word_d['word'] for word_d in crossword["words"]]

    low_acc_words = []
    medium_acc_words = []
    high_acc_words = []

    for word in words:
        if accuracy[word] < 0.5:
            low_acc_words.append(word)
        elif accuracy[word] > 0.75:
            high_acc_words.append(word)
        else:
            medium_acc_words.append(word)

    if desired_difficulty == Difficulty.EASY.value:
        if high_acc_words and len(high_acc_words) >= 0.75 * len(words):
            return update_clue

    if desired_difficulty == Difficulty.HARD.value:
        if low_acc_words and len(low_acc_words) > 0.5 * len(words):
            return update_clue

    if desired_difficulty == Difficulty.MEDIUM.value:
        if medium_acc_words and 0.5 * len(words) <= len(medium_acc_words) < 0.75 * len(words):
            return update_clue

    for word_d in crossword["words"]:
        word = word_d['word']
        if desired_difficulty == Difficulty.EASY.value:
            if accuracy[word] < 0.75:
                update_clue[word] = True
            else:
                update_clue[word] = False
        elif desired_difficulty == Difficulty.HARD.value:
            if accuracy[word] > 0.50:
                update_clue[word] = True
            else:
                update_clue[word] = False
        else:
            if 0.5 <= accuracy[word] <= 0.75:
                update_clue[word] = False
            else:
                update_clue[word] = True

    return update_clue


def update_crossword(llm, crossword, words_which_need_clue_updates, desired_difficulty):
    request = {"words": []}

    for word_d in crossword["words"]:
        word = word_d['word']
        if word in words_which_need_clue_updates:
            request["words"].append({
                "word": word,
                "clue": word_d["clue"]
            })

    print(f"Generating new clues for: {request}")

    response = llm.invoke(input=clue_generation_chat_prompt.format_messages(
        words=request,
        difficulty=desired_difficulty.upper()
    ))

    print("New clues generated are:")
    print(response.content)
    print("*" * 50)

    new_word_clues = json.loads(response.content)

    for word_d in crossword["words"]:
        word = word_d['word']
        for new_word_d in new_word_clues["words"]:
            if word == new_word_d['word'] and new_word_d['updatedClue']:
                word_d['clue'] = new_word_d['updatedClue']


def generate_crossword(llm, grid_size, word_count, desired_difficulty):
    crossword, output_file = generate(llm, grid_size, word_count)

    # remove this - here for testing
    # output_file = "crossword.json"
    #
    # with open("crossword.json", "r") as f:
    #     crossword = json.load(f)

    for i in range(MAX_CROSSWORD_ITERATIONS):
        iteration = i + 1
        print('*' * 50)
        print(f"ITERATION: {iteration}")

        responses = []

        # give the puzzle to different solvers
        for config in solver_configs:
            solver = get_solver(config)
            response = solve(solver, grid_size, output_file)
            responses.append(response)
            print(f"RESPONSE {solver.model_name}: {response}")

        # get metrics and update clues
        accuracy = get_word_accuracy(crossword, responses)
        update_clue = determine_clue_updates_needed(crossword, accuracy, desired_difficulty)

        if update_clue:
            # filter out all the words that need a clue update
            words_which_need_clue_updates = [word for word in update_clue if update_clue[word] is True]
            print(f"CLUE UPDATES NEEDED FOR: {words_which_need_clue_updates}")

            # update the clues for needed words
            update_crossword(llm, crossword, words_which_need_clue_updates, desired_difficulty)

        output_file = f"output/crossword-{iteration}.json"
        write_file(crossword, iteration)

        if not update_clue:
            print(f"Puzzle difficulty matches user difficulty after {iteration} iteration(s)")
            break


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

    parser.add_argument(
        "--difficulty",
        choices=["easy", "medium", "hard"],
        required=True,
        help="The desired difficulty of the puzzle.",
    )

    args = parser.parse_args()

    if args.grid_size < 10:
        parser.error("grid_size must be at least 10.")

    print(f"GENERATING crossword using: {args.model}, grid size: {args.grid_size}, word count: {args.word_count}, "
          f"difficulty: {args.difficulty}")

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

    generate_crossword(llm, args.grid_size, args.word_count, args.difficulty)
