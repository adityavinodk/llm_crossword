# LLM Based Crossword Puzzle Generator

This project consists of an LLM pipeline to create crossword puzzles. Here is a brief summary of how it works -

1. The PuzzleLLM generates the crossword puzzle iteratively using the system prompt `prompts/generate_word_prompt_template.txt`
2. Multiple SolverLLMs try to solve the generated crossword puzzle using the system prompt `prompts/solver_prompt_template.txt`
3. Based on the evaluation criteria, the solutions from the different SolverLLMs are accumulated and the crossword puzzle clues are updated using the system prompt `prompts/clue_generation_prompt_template.txt`

## How to Run

To run this pipeline, you simply have to do the following -

1. Run `pip install -r requirements.txt`
2. Create a `.env` file in this directory and add 3 API keys - `OPENAI_API_KEY`, `CLAUDE_API_KEY` and `GROQ_API_KEY`.
3. Run `python generator.py`. You have the following additional flags for this program -

```
--gen_model {claude,gpt,llama,mistral}
    Choose the model to use for generating the crossword puzzle
    Defaults to gpt
--grid_size
    Grid size for the crossword puzzle (minimum 10)
    Defaults to 15
--word_count
    Number of words to generate
    Defaults to 10
--difficulty {easy,medium,hard}
    The desired difficulty of the puzzle - {easy, medium, hard}
    Defaults to medium
--iterations
    Number of times the crossword should be revised
    Defaults to 1
--verbose
    Enable verbose output for SolverLLMs
```

4. Additionally, in order to add further SolverLLMs, you can edit the model configurations list in `configs/solver.py`. Note that you might also have to edit the `get_llm()` function in `helper.py` if they involve different models.
