solver_configs = {
    "gpt-4o": [
        {
            "model": "claude-3-5-sonnet-latest",
            "temperature": 1,
            "max_tokens": 1000,
            "timeout": None,
            "max_retries": 4,
        },
        {
            "model": "claude-3-5-haiku-latest",
            "temperature": 1,
            "max_tokens": 1000,
            "timeout": None,
            "max_retries": 4,
        },
        {
            "model": "llama-3.3-70b-versatile",
            "temperature": 1,
            "max_tokens": None,
            "timeout": None,
            "max_retries": 4,
        },
        {
            "model": "mistral",
            "temperature": 1,
            "max_tokens": None,
            "timeout": None,
            "max_retries": 4,
        },
    ],
    "claude-3-5-sonnet-latest": [
        {
            "model": "gpt-4o",
            "temperature": 1,
            "max_tokens": None,
            "timeout": None,
            "max_retries": 4,
        },
        {
            "model": "gpt-4o-mini",
            "temperature": 1,
            "max_tokens": None,
            "timeout": None,
            "max_retries": 4,
        },
        {
            "model": "llama-3.3-70b-versatile",
            "temperature": 1,
            "max_tokens": None,
            "timeout": None,
            "max_retries": 4,
        },
        {
            "model": "mistral",
            "temperature": 1,
            "max_tokens": None,
            "timeout": None,
            "max_retries": 4,
        }
    ]
}
