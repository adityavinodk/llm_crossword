from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.schema import SystemMessage
from dotenv import load_dotenv
import json
import argparse
from collections import Counter
from configs.solver import solver_configs
import multiprocessing
from multiprocessing import Pool, Manager
from helper import *
from functools import partial
from solver import solve

load_dotenv()

GENERATE_WORD_PROMPT_TEMPLATE = read_prompt_template(
    "prompts/generate_word_prompt_template.txt"
)
GENERATE_APPROPRIATE_CLUE_PROMPT_TEMPLATE = read_prompt_template(
    "prompts/clue_generation_prompt_template.txt"
)
WORD_GENERATION_CHAT_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessage(content=GENERATE_WORD_PROMPT_TEMPLATE),
        HumanMessagePromptTemplate.from_template(
            "char_positions=\n{char_positions}\n\nwords={words}\n\ngrid_size={grid_size}"
        ),
    ]
)
CLUE_GENERATION_CHAT_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessage(content=GENERATE_APPROPRIATE_CLUE_PROMPT_TEMPLATE),
        HumanMessagePromptTemplate.from_template(
            "words:\n{words}\n\ndifficulty:{difficulty}"
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
    # print_char_positions_and_words(char_positions, words)

    generated = False
    new_word_dict = {}

    while not generated and retry_count > 0:
        # get new word
        response1 = llm.invoke(
            input=WORD_GENERATION_CHAT_PROMPT.format_messages(
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


def get_word_perc(crossword, solver_responses):
    solved = Counter()
    unsolved = Counter()
    perc = {}

    # build stats at word level
    for response in solver_responses:
        for word in response["solved"]:
            solved[word] += 1
        for word in response["unsolved"]:
            unsolved[word] += 1

    for word_d in crossword["words"]:
        word = word_d["word"]
        solved_count = solved.get(word, 0)
        unsolved_count = unsolved.get(word, 0)
        perc[word] = solved_count / (solved_count + unsolved_count)

    print("\nWORD SOLVED PERCENTAGE:")
    for word in perc:
        print(f"{word}: {perc[word]}")

    return perc


def determine_clue_updates_needed(crossword, solve_perc, desired_difficulty):
    update_clue = {}

    words = [word_d["word"] for word_d in crossword["words"]]

    low_acc_words = []
    medium_acc_words = []
    high_acc_words = []

    for word in words:
        if solve_perc[word] < 0.5:
            low_acc_words.append(word)
        elif solve_perc[word] > 0.75:
            high_acc_words.append(word)
        else:
            medium_acc_words.append(word)

    if desired_difficulty == Difficulty.EASY.value and len(
        high_acc_words
    ) >= 0.75 * len(words):
        return update_clue

    if desired_difficulty == Difficulty.HARD.value and len(low_acc_words) > 0.5 * len(
        words
    ):
        return update_clue

    if desired_difficulty == Difficulty.MEDIUM.value and 0.5 * len(words) <= len(
        medium_acc_words
    ) < 0.75 * len(words):
        return update_clue

    for word_d in crossword["words"]:
        word = word_d["word"]
        if desired_difficulty == Difficulty.EASY.value:
            update_clue[word] = True if solve_perc[word] < 0.75 else False
        elif desired_difficulty == Difficulty.HARD.value:
            update_clue[word] = True if solve_perc[word] > 0.5 else False
        else:
            update_clue[word] = False if 0.5 <= solve_perc[word] <= 0.75 else True

    return update_clue


def update_crossword(llm, crossword, clue_update_words, desired_difficulty):
    request = {"words": []}

    for word_d in crossword["words"]:
        word = word_d["word"]
        if word in clue_update_words:
            request["words"].append({"word": word, "clue": word_d["clue"]})

    response = llm.invoke(
        input=CLUE_GENERATION_CHAT_PROMPT.format_messages(
            words=request, difficulty=desired_difficulty.upper()
        )
    )

    print("New clues generated are:")
    print(response.content)
    print("*" * 50)

    new_word_clues = json.loads(response.content)

    for word_d in crossword["words"]:
        word = word_d["word"]
        for new_word_d in new_word_clues["words"]:
            if word == new_word_d["word"] and new_word_d["updatedClue"]:
                word_d["clue"] = new_word_d["updatedClue"]


def solve_wrapper(config, grid_size, output_file, queue):
    solver = get_llm(config)
    response = solve(solver, config["model"], grid_size, output_file, queue)
    queue.put(f"RESPONSE {config['model']}: {response}")
    return response


def generate_crossword(llm, grid_size, word_count, desired_difficulty, iterations):
    # crossword, output_file = generate(llm, grid_size, word_count)

    # remove this - here for testing
    output_file = "crossword.json"

    with open("crossword.json", "r") as f:
        crossword = json.load(f)

    for i in range(iterations):
        iteration = i + 1
        print("*" * 50)
        print(f"ITERATION: {iteration}")

        with Manager() as manager:
            log_queue = manager.Queue()

            # Create a process pool
            with Pool(processes=multiprocessing.cpu_count()) as pool:
                # Use partial to pass common arguments to solve_wrapper
                solve_func = partial(
                    solve_wrapper,
                    grid_size=grid_size,
                    output_file=output_file,
                    queue=log_queue,
                )
                responses = pool.map(solve_func, solver_configs)

            # Collect and print logs sequentially
            while not log_queue.empty():
                print(log_queue.get())

        # get metrics and update clues
        solve_perc = get_word_perc(crossword, responses)
        update_clue = determine_clue_updates_needed(
            crossword, solve_perc, desired_difficulty
        )

        if update_clue:
            # filter out all the words that need a clue update
            clue_update_words = [word for word in update_clue if update_clue[word]]
            print(f"CLUE UPDATES NEEDED FOR: {clue_update_words}")

            # update the clues for needed words
            update_crossword(llm, crossword, clue_update_words, desired_difficulty)

        output_file = f"output/crossword-{iteration}.json"
        write_file(crossword, iteration)

        if not update_clue:
            print(
                f"Puzzle difficulty matches user difficulty after {iteration} iteration(s)"
            )
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crossword Puzzle Generator")
    parser.add_argument(
        "--gen_model",
        choices=["claude", "gpt", "llama", "mistral"],
        default="gpt",
        help="Choose the model to use for generating the crossword puzzle",
    )
    parser.add_argument(
        "--grid_size",
        type=int,
        default=15,
        help="Grid size for the crossword puzzle (minimum 10).",
    )
    parser.add_argument(
        "--word_count",
        type=int,
        default=10,
        help="Number of words to generate (minimum 10).",
    )
    parser.add_argument(
        "--difficulty",
        choices=["easy", "medium", "hard"],
        default="medium",
        help="The desired difficulty of the puzzle - {easy, medium, hard}",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of times the crossword should be revised",
    )

    args = parser.parse_args()

    if args.grid_size < 10:
        parser.error("grid_size must be at least 10.")

    print(
        f"GENERATING crossword using: {args.gen_model}, grid size: {args.grid_size}, word count: {args.word_count}, "
        f"difficulty: {args.difficulty}"
    )

    generator_config = {
        "temperature": 1,
        "max_tokens": None,
        "timeout": None,
        "max_retries": 4,
    }

    model = "gpt-4o"
    if args.gen_model == "claude":
        model = "claude-3-5-sonnet-latest"
    elif args.gen_model == "llama":
        model = "llama-3.3-70b-versatile"
    elif args.gen_model == "mistral":
        model = "mistral"

    generator_config["model"] = model

    generate_crossword(
        get_llm(generator_config),
        args.grid_size,
        args.word_count,
        args.difficulty,
        args.iterations,
    )
