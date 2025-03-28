# prompt-gen

A powerful CLI tool for extracting and displaying project file contents with advanced filtering and customization options.

## Features

- Read contents of files in specified directories
- Generate project structure trees
- Flexible exclusion rules (gitignore, custom configs)
- Control directory traversal depth
- Configurable file size and total input limits
- Output to console or save to file

## Installation

```bash
pip install prompt-gen
```

## Usage

### Basic Usage

```bash
# Read contents of current directory
prompt-gen

# Read contents of specific directory
prompt-gen -f src/

# Save output to a file
prompt-gen -f src/ -s project_contents.txt
```

### Advanced Options

```bash
# Display only project structure
prompt-gen -p

# Exclude specific files/directories
prompt-gen -f src/ -e .env __pycache__

# Limit directory depth
prompt-gen -f src/ --max-depth 2

# Use custom gitignore
prompt-gen -f src/ --gitignore .gitignore
```

## Command Line Arguments

- `-f, --files`: Paths to directories or files to process
- `-s, --save`: Save output to a specified file
- `-p, --project`: Display only the project structure
- `-e, --exclude`: Additional files or directories to exclude
- `--gitignore`: Path to a .gitignore file for exclusion rules
- `--exclude-config`: Path to a JSON/YAML config file with exclusion rules
- `--max-depth`: Maximum directory depth to traverse
- `--input-limit`: Maximum total input length (default: 12000 chars)
- `--max-file-size`: Maximum file size to read (default: 1 MB)

## Development and Testing

### Running Tests

To run the test suite, first install the test dependencies:

```bash
pip install -e .[test]
```

Then run the tests using pytest:

```bash
# Run all tests
pytest tests/

# Run with coverage report
pytest tests/ --cov=prompt_gen
```

### Test Coverage

The test suite covers:
- File and directory exclusion
- Project structure generation
- Depth limitation
- Input and file size limitations
- Wildcard pattern matching

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License
