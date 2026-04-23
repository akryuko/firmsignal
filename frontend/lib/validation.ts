export interface ValidationResult {
  valid: boolean
  error: string | null
}

const VALID_PATTERN = /^[a-zA-Z0-9\s.,&\-'()]+$/
const MIN_LENGTH = 2
const MAX_LENGTH = 100
const BLOCKED = new Set(["test", "asdf", "qwerty", "foo", "bar", "null", "none", "undefined", "na", "n/a"])

/**
 * Real-time checks — runs on every keystroke.
 * Only covers errors that are unambiguous mid-input:
 *   - exceeded max length
 *   - invalid character just typed
 * Intentionally skips empty / too-short / blocked-word checks
 * (those are only meaningful after the user signals they're done).
 */
export function getLiveError(value: string): string | null {
  if (value.length > MAX_LENGTH) {
    return `Company name cannot exceed ${MAX_LENGTH} characters`
  }
  if (value.length > 0 && !VALID_PATTERN.test(value)) {
    return "Only letters, numbers, and basic punctuation allowed"
  }
  return null
}

export function validateCompanyInput(raw: string): ValidationResult {
  const cleaned = raw.trim()

  if (!cleaned) {
    return { valid: false, error: "Please enter a company name" }
  }

  if (cleaned.length < MIN_LENGTH) {
    return { valid: false, error: "Company name is too short" }
  }

  if (cleaned.length > MAX_LENGTH) {
    return {
      valid: false,
      error: `Company name cannot exceed ${MAX_LENGTH} characters`,
    }
  }

  if (!VALID_PATTERN.test(cleaned)) {
    return {
      valid: false,
      error: "Only letters, numbers, and basic punctuation allowed",
    }
  }

  if (BLOCKED.has(cleaned.toLowerCase())) {
    return { valid: false, error: `"${cleaned}" is not a valid company name` }
  }

  return { valid: true, error: null }
}
