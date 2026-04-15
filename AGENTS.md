# AGENTS.md - Agent Coding Guidelines

## Build, Lint, and Test Commands

### Common Commands

```bash
# Install dependencies
npm install          # JavaScript/TypeScript
pip install -r requirements.txt  # Python
yarn install         # Yarn projects

# Build
npm run build        # JavaScript/TypeScript
npm run dev          # Start dev server
python main.py       # Python scripts

# Linting
npm run lint         # Run linter
npx eslint .         # ESLint
npx tslint .         # TSLint
ruff check .         # Python Ruff
pylint .             # Python Pylint

# Formatting
npm run format       # Prettier
npx prettier --write .
black .              # Python Black
isort .              # Python import sorting

# Type checking
npm run typecheck    # TypeScript
mypy .               # Python MyPy

# Testing - Full suite
npm test             # JavaScript/TypeScript (Jest)
pytest               # Python Pytest

# Testing - Single test file
npx jest path/to/test.spec.ts --verbose    # Jest
pytest path/to/test_file.py                 # Pytest
pytest path/to/test_file.py::test_function  # Specific test function
pytest -k "test_function_name"              # Pytest by keyword

# Testing - Watch mode
npm test -- --watch
pytest -v --tb=short                         # Verbose output

# Testing - Coverage
npm test -- --coverage
pytest --cov=. --cov-report html
```

## Code Style Guidelines

### General Principles

- Keep lines under 100 characters when practical
- Use meaningful, descriptive names for variables, functions, and files
- Write small, focused functions (ideally < 50 lines)
- Document complex business logic with comments
- Avoid premature abstraction - duplicate code is often clearer than bad abstraction

### Imports

**JavaScript/TypeScript:**
```typescript
// Group imports: external → internal → relative
import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';
import { formatDate } from '../utils/date';

// Use absolute imports with path aliases (@/, ~/)
import { Button } from '@/components/Button';
```

**Python:**
```python
# Standard library
import os
import sys
from typing import List, Dict, Optional

# Third-party
import numpy as np
import pandas as pd
from fastapi import FastAPI

# Local application
from . import models
from ..utils.helpers import format_date
```

### Formatting

- Use 2 or 4 space indentation (match project convention)
- Add trailing commas in multiline objects/arrays
- Use semicolons in JavaScript
- Prefer single quotes for strings in JS/TS unless containing apostrophes
- Use f-strings in Python

### Types

**TypeScript:**
```typescript
// Use interfaces for object shapes
interface User {
  id: string;
  name: string;
  email: string;
  createdAt: Date;
}

// Use type for unions, intersections, aliases
type Status = 'pending' | 'active' | 'completed';
type Result<T> = { success: true; data: T } | { success: false; error: string };

// Avoid 'any' - be explicit with types
function processData(data: unknown): string { ... }
```

**Python:**
```python
# Use type hints
def process_items(items: List[dict]) -> Optional[str]:
    ...

# Use TypedDict for structured dicts
from typing import TypedDict

class User(TypedDict):
    id: str
    name: str
    email: str
```

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Variables | camelCase (JS/TS), snake_case (Python) | `userName`, `user_name` |
| Functions | camelCase (JS/TS), snake_case (Python) | `getUserById`, `get_user_by_id` |
| Classes | PascalCase | `UserService`, `UserService` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRIES`, `MAX_RETRIES` |
| Files | kebab-case (JS), snake_case (Python) | `user-service.ts`, `user_service.py` |
| Components | PascalCase | `UserProfile.tsx` |
| Boolean variables | Use prefixes like `is`, `has`, `should` | `isActive`, `hasPermission` |

### Error Handling

```typescript
// Use try-catch with specific error types
try {
  const result = await riskyOperation();
} catch (error) {
  if (error instanceof ValidationError) {
    // Handle specific error
    return { error: error.message };
  }
  // Log and rethrow or handle gracefully
  logger.error('Unexpected error', { error });
  throw error;
}

// Use Result types for explicit error handling
function divide(a: number, b: number): Result<number> {
  if (b === 0) return { success: false, error: 'Division by zero' };
  return { success: true, data: a / b };
}
```

```python
# Use custom exceptions
class ValidationError(Exception):
    pass

# Handle exceptions explicitly
try:
    result = risky_operation()
except ValueError as e:
    logger.warning(f"Invalid value: {e}")
    return None
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise
```

### Async/Await

```typescript
// Always handle errors in async functions
async function fetchUser(id: string): Promise<User> {
  try {
    const response = await api.get(`/users/${id}`);
    return response.data;
  } catch (error) {
    if (error.status === 404) {
      throw new NotFoundError(`User ${id} not found`);
    }
    throw error;
  }
}

// Use Promise.all for parallel operations
const [users, posts] = await Promise.all([
  fetchUsers(),
  fetchPosts()
]);
```

### Testing Guidelines

```typescript
// Use describe/it blocks
describe('UserService', () => {
  describe('getUser', () => {
    it('should return user when found', async () => {
      const user = await userService.getUser('123');
      expect(user.id).toBe('123');
    });

    it('should throw when not found', async () => {
      await expect(userService.getUser('invalid'))
        .rejects.toThrow(NotFoundError);
    });
  });
});
```

```python
import pytest

class TestUserService:
    def test_get_user_returns_user(self):
        user = user_service.get_user("123")
        assert user.id == "123"

    def test_get_user_raises_not_found(self):
        with pytest.raises(NotFoundError):
            user_service.get_user("invalid")
```

### File Organization

- One primary export per file
- Group related functionality together
- Use index files for clean public APIs
- Keep tests co-located with source files (`user.service.ts` → `user.service.spec.ts`)

### Performance Considerations

- Memoize expensive computations
- Use lazy loading for routes/code splitting
- Avoid nested loops when possible
- Use appropriate data structures (Set for unique items, Map for key-value)
- Profile before optimizing

### Security

- Never commit secrets, API keys, or credentials
- Validate all user input
- Use parameterized queries to prevent SQL injection
- Sanitize output to prevent XSS
- Follow principle of least privilege
