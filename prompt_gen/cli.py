import os
import argparse
from pathlib import Path

CHATGPT_INPUT_LIMIT = 12000  # Approximate limit for safety


def load_gitignore(gitignore_path):
    ignore_patterns = set()
    if gitignore_path and os.path.isfile(gitignore_path):
        with open(gitignore_path, 'r') as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith('#'):
                    ignore_patterns.add(line)
    return ignore_patterns


def should_exclude(path, exclude_list, ignore_patterns):
    relative_path = Path(path).as_posix()
    for pattern in exclude_list + list(ignore_patterns):
        if Path(relative_path).match(pattern):
            return True
    return False


def format_tree(root, prefix="", exclude_list=[], ignore_patterns=set()):
    output = []
    entries = sorted(os.listdir(root))
    for index, entry in enumerate(entries):
        path = os.path.join(root, entry)
        if should_exclude(path, exclude_list, ignore_patterns):
            continue
        connector = "└── " if index == len(entries) - 1 else "├── "
        output.append(f"{prefix}{connector}{entry}")
        if os.path.isdir(path):
            extension = "    " if index == len(entries) - 1 else "│   "
            output.extend(format_tree(path, prefix + extension, exclude_list, ignore_patterns))
    return output


def read_files(paths, exclude_list=[], ignore_patterns=set()):
    output = []
    total_length = 0

    for path in paths:
        if should_exclude(path, exclude_list, ignore_patterns):
            continue

        if os.path.isdir(path):
            output.append(f"{os.path.basename(path)}/")
            output.extend(format_tree(path, exclude_list=exclude_list, ignore_patterns=ignore_patterns))

            for root, _, files in os.walk(path):
                if should_exclude(root, exclude_list, ignore_patterns):
                    continue
                for file in files:
                    file_path = os.path.join(root, file)
                    if should_exclude(file_path, exclude_list, ignore_patterns):
                        continue
                    output.append(f"\n//{file_path}")
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        total_length += len(content)
                        output.append(content)
        elif os.path.isfile(path):
            output.append(f"//{path}")
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                total_length += len(content)
                output.append(content)
    if total_length > CHATGPT_INPUT_LIMIT:
        raise ValueError("Warning: Output("+str(total_length)+") exceeds ChatGPT input limit ("+str(CHATGPT_INPUT_LIMIT)+"). Reduce the number of files or content size.")
    return '\n'.join(output)


def display_project_structure(paths, exclude_list=[], ignore_patterns=set()):
    output = []
    for path in paths:
        if should_exclude(path, exclude_list, ignore_patterns):
            continue

        if os.path.isdir(path):
            output.append(f"{os.path.basename(path)}/")
            output.extend(format_tree(path, exclude_list=exclude_list, ignore_patterns=ignore_patterns))
        else:
            output.append(f"{path}")
    return '\n'.join(output)


def run():
    parser = argparse.ArgumentParser(description="Output contents of files or project structure.")
    parser.add_argument('-f', '--files', nargs='+', help="Paths to directories or files to process.")
    parser.add_argument('-s', '--save', help="Save output to a specified file.")
    parser.add_argument('-p', '--project', action='store_true', help="Display only the project structure.")
    parser.add_argument('-e', '--exclude', nargs='+', default=[], help="List of files or directories to exclude.")
    parser.add_argument('--gitignore', help="Path to a .gitignore file for exclusion rules.")

    args = parser.parse_args()

    if args.files:
        paths = args.files
    else:
        paths = [os.getcwd()]

    ignore_patterns = load_gitignore(args.gitignore)

    try:
        if args.project:
            output = display_project_structure(paths, exclude_list=args.exclude, ignore_patterns=ignore_patterns)
        else:
            output = read_files(paths, exclude_list=args.exclude, ignore_patterns=ignore_patterns)
    except ValueError as e:
        print(e)
        return

    if args.save:
        with open(args.save, 'w', encoding='utf-8') as out_file:
            out_file.write(output)
        print(f"Contents stored in {args.save}")
    else:
        print(output)
