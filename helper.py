import json


class CharacterConflictException(Exception):
    def __init__(self, row, column, existing_char):
        self.row = row
        self.column = column
        self.existing_char = existing_char
        super().__init__(
            f"CONFLICT - Row: {row}, Column: {column}, Existing: '{existing_char}'"
        )


class OutOfBoundsException(Exception):
    def __init__(self, row, column):
        self.row = row
        self.column = column
        super().__init__(f"OUT OF BOUNDS - Row: {row}, Column: {column}")


def read_prompt_template(file_path):
    with open(file_path, "r") as file:
        return file.read()


def get_character_positions_and_words(words_json, grid_size):
    char_positions = []
    words = []
    position_map = {}

    for data in words_json["words"]:
        word = data["word"]
        words.append(word)
        is_across = True if data["isAcross"] else False
        row, column = data["row"], data["column"]

        for i, char in enumerate(word):
            pos_key = (row, column)
            if pos_key in position_map:
                existing_char = position_map[pos_key]
                if existing_char != char:
                    raise CharacterConflictException(
                        row=row,
                        column=column,
                        existing_char=existing_char,
                    )
            elif row > grid_size or column > grid_size:
                raise OutOfBoundsException(
                    row=row,
                    column=column,
                )
            else:
                position_map[pos_key] = char

            char_positions.append(
                {"row": int(row), "column": int(column), "character": char}
            )

            if is_across:
                column += 1
            else:
                row += 1
    return char_positions, words


def print_char_positions_and_words(char_positions, words):
    print("Getting character positions and words")

    for cp in char_positions:
        print(cp)

    print(words)
    print("*" * 50)


def extract_json_from_text(text):
    """
    Extracts JSON content from the end of the input text.
    """
    try:
        # Find the last occurrence of '{'
        json_start = text.rindex("{")
        json_end = text.rindex("}")

        # Extract everything from that point to the end
        json_text = text[json_start : json_end + 1]

        # Validate that it's valid JSON by parsing it
        data = json.loads(json_text)

        return data
    except json.JSONDecodeError:
        return "Error: Invalid JSON format"
    except ValueError:
        return "Error: No valid JSON found at the end of the text"
