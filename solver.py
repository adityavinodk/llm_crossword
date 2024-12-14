from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.schema import SystemMessage
from dotenv import load_dotenv
import json
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


def solve_puzzle_clue(llm, grid_size, clue_metadata, solved_state, queue):
    # get character positions
    char_positions, words = get_character_positions_and_words(solved_state, grid_size)
    # queue.put_char_positions_and_words(char_positions, words)

    guessed = False
    new_word_dict = {}

    try:
        response = llm.invoke(
            input=chat_prompt.format_messages(
                clue_metadata=clue_metadata,
                char_positions=char_positions,
                words=words,
                grid_size=grid_size,
            )
        )
    except Exception as e:
        queue.put(str(e))
        return guessed, clue_metadata, solved_state, new_word_dict

    queue.put("Attempting to guess a new clue")
    queue.put(response.content)
    queue.put("*" * 50)

    # extract new word from response1
    queue.put("Extracting guessed word from response")
    new_word_dict = extract_json_from_text(response.content)
    queue.put(new_word_dict)
    queue.put("*" * 50)

    if isinstance(new_word_dict, dict) and not new_word_dict.get("message"):
        append_new_word(solved_state, new_word_dict)
        try:
            char_positions, words = get_character_positions_and_words(
                solved_state, grid_size
            )
            guessed = True
        except (CharacterConflictException, OutOfBoundsException) as e:
            queue.put(str(e))
            queue.put("*" * 50)
            remove_last_word(solved_state)
    else:
        queue.put("Retrying...")

    new_clue_metadata = clue_metadata
    if guessed:
        new_clue_metadata = [
            clue for clue in clue_metadata if clue["clue"] != new_word_dict["clue"]
        ]

    return guessed, new_clue_metadata, solved_state, new_word_dict


def solve(llm, model, grid_size, puzzle, queue):
    if grid_size < 10:
        queue.put("grid_size must be at least 10.")
        return

    with open(puzzle, "r") as f:
        puzzle = json.load(f)

    queue.put("*" * 50)
    queue.put(f"SOLVING puzzle using: {model}")

    unsolved_count = len(puzzle["words"])
    clue_metadata, solution = return_clue_metadata(puzzle)
    guessed = True
    api_retry_count = 5
    solved_state = {"words": []}
    while unsolved_count and api_retry_count > 0:
        guessed, clue_metadata, solved_state, solved_word = solve_puzzle_clue(
            llm, grid_size, clue_metadata, solved_state, queue
        )

        if guessed:
            unsolved_count -= 1
            api_retry_count = 3
            queue.put(f"SUCCESS: new word guessed is {solved_word}")
            queue.put(f"Remaining unsolved count: {unsolved_count}")
            queue.put("*" * 50)
        else:
            queue.put("FAILED: calling API to guess word again")
            queue.put("*" * 50)
            api_retry_count -= 1

    queue.put(json.dumps(solved_state, indent=4))
    queue.put(f"Final Solved Word Count: {len(solved_state['words'])}")

    grid_data, _ = get_character_positions_and_words(solved_state, grid_size)
    positions = {}
    for d in grid_data:
        positions[f"{d['row']},{d['column']}"] = d["character"]

    queue.put("\nCROSSWORD -")
    c_s = ""
    for i in range(grid_size):
        for j in range(grid_size):
            if f"{i},{j}" in positions:
                c_s += positions[f"{i},{j}"] + " "
            else:
                c_s += "_ "
        c_s += "\n"
    queue.put(c_s)

    response = {"solved": [], "unsolved": []}

    correct_count = 0

    seen = {}

    for word_d in solved_state["words"]:
        metadata_tup = (word_d["row"], word_d["column"], word_d["isAcross"])
        if (
                metadata_tup in solution
                and solution[metadata_tup] == word_d["word"].lower()
                and word_d["word"] not in seen
        ):
            seen[word_d["word"]] = True
            correct_count += 1
            response["solved"].append(word_d["word"])
    queue.put(f"\nCorrect - {correct_count}/{len(puzzle['words'])}")

    for word in solution.keys():
        if solution[word] not in response["solved"]:
            response["unsolved"].append(solution[word])

    return response
