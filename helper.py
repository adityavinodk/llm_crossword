import json
import re

GRID_SIZE = 10


def read_prompt_template(file_path):
    with open(file_path, 'r') as file:
        return file.read()


def get_character_positions_and_words(words_json):
    char_positions = []
    words = []

    for data in words_json["words"]:
        words.append(data["word"])

        positions_str = data["positions"].strip("()").split("), (")
        for pos in positions_str:
            char, row, col = pos.split(", ")
            char_positions.append({
                "row": int(row),
                "column": int(col),
                "character": char.strip("'")
            })

    return char_positions, words


def print_char_positions_and_words(char_positions, words):
    print("Getting character positions and words")

    for cp in char_positions:
        print(cp)

    print(words)
    print('*' * 50)


def extract_new_word_from_text(text):
    """
    Extracts JSON content from the end of the input text.
    """
    try:
        # Find the last occurrence of '{'
        json_start = text.rindex('{')
        json_end = text.rindex('}')

        # Extract everything from that point to the end
        word = text[json_start:json_end + 1]

        # Validate that it's valid JSON by parsing it
        word = json.loads(word)

        return word
    except json.JSONDecodeError as e:
        return "Error: Invalid JSON format"
    except ValueError as e:
        return "Error: No valid JSON found at the end of the text"


def validate_crossword_puzzle(char_positions):
    positions = {}

    for cp in char_positions:
        row = cp['row']
        col = cp['column']
        character = cp['character']

        if row >= GRID_SIZE or col >= GRID_SIZE:
            return False

        position = (row, col)
        if position in positions:
            if positions[position] != character:
                return False
        else:
            positions[position] = character

    return True
