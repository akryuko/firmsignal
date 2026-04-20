import re

from fastapi import HTTPException


# Limits
MIN_LENGTH = 2
MAX_LENGTH = 100

# Characters valid in a company name:
# letters, numbers, spaces, dots, commas, ampersands, hyphens, apostrophes, parens
VALID_PATTERN = re.compile(r"^[a-zA-Z0-9\s\.\,\&\-\'\(\)]+$")

# Known garbage inputs to reject immediately
BLOCKED_INPUTS = {
    "test", "asdf", "qwerty", "foo", "bar",
    "null", "none", "undefined", "na", "n/a",
}


def validate_company_name(raw: str) -> str:
    """
    Validates and sanitizes a company name input.
    Returns the cleaned string or raises HTTPException.

    Called before anything else in POST /analyze.
    """

    # Step 1 — strip whitespace
    cleaned = raw.strip()

    # Step 2 — check not empty
    if not cleaned:
        raise HTTPException(
            status_code=422,
            detail="Company name cannot be empty.",
        )

    # Step 3 — check minimum length
    if len(cleaned) < MIN_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Company name must be at least {MIN_LENGTH} characters.",
        )

    # Step 4 — check maximum length
    if len(cleaned) > MAX_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Company name cannot exceed {MAX_LENGTH} characters.",
        )

    # Step 5 — check for valid characters only
    if not VALID_PATTERN.match(cleaned):
        raise HTTPException(
            status_code=422,
            detail=(
                "Company name contains invalid characters. "
                "Only letters, numbers, spaces, and basic punctuation are allowed."
            ),
        )

    # Step 6 — reject obvious garbage
    if cleaned.lower() in BLOCKED_INPUTS:
        raise HTTPException(
            status_code=422,
            detail=f"'{cleaned}' is not a valid company name.",
        )

    # Step 7 — normalize multiple spaces to a single space
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned
