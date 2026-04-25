## Linting & Formatting

Check for lint issues:
```bash
ruff check .
```

Auto-fix lint issues where possible:
```bash
ruff check --fix .
```

Auto-fix including unsafe fixes:
```bash
ruff check --fix --unsafe-fixes .
```

Format code:
```bash
ruff format .
```

Check formatting without modifying files:
```bash
ruff format --check .
```