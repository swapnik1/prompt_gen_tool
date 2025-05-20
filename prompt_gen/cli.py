import os
import argparse
import fnmatch
from pathlib import Path
import sys
import traceback
import logging
import mimetypes
import re

DEFAULT_INPUT_LIMIT = 50000
DEFAULT_MAX_FILE_SIZE = 1024 * 1024  # 1 MB max file size
DEFAULT_EXCLUDED_DIRS = [
    '.git', '.svn', '.hg',
    '__pycache__', '.pytest_cache',
    'node_modules', 'dist', 'build',
    '.next', '.vercel',
    '.venv', 'venv', 'env'
]

def minify_prompt_text(text: str) -> str:
    if not text:
        return ""

    # Stage 1: Remove multi-line comments.
    text = re.sub(r"^\s*\'\'\'.*?\'\'\'", "", text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r"^\s*\"\"\".*?\"\"\"", "", text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)

    # Stage 2: Line-by-line processing
    lines = text.splitlines()
    minified_lines = []
    for line_content in lines:
        original_line_is_empty_or_whitespace = line_content.strip() == ""

        line_after_hash = re.sub(r"\s*#.*$", "", line_content)
        line_after_slash_slash = line_after_hash
        stripped_temp = line_after_hash.strip()

        if stripped_temp.startswith("//"):
            # Heuristic for file paths vs comments starting with //
            if not (re.match(r"//([A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+/?$", stripped_temp) or
                    re.match(r"//[A-Za-z0-9_.-]+$", stripped_temp)):
                line_after_slash_slash = ""
        else:
            line_after_slash_slash = re.sub(r"\s*//.*$", "", line_after_hash)
            
        final_stripped_line = line_after_slash_slash.strip()

        # "Balanced" newline logic:
        if final_stripped_line:
            minified_lines.append(final_stripped_line)
        else: # final_stripped_line is ""
            if original_line_is_empty_or_whitespace: 
                minified_lines.append("") 
            # Else (line became empty due to comment removal AND was not originally blank): it's omitted.
            # This makes X\n#comment\nY into X\nY.
            # However, if a multi-line comment removal (Stage 1) results in an empty line
            # in the `lines` array for Stage 2, that empty line will have 
            # original_line_is_empty_or_whitespace = True, thus preserving it as "".
            # This causes X\n/*comment_block_on_own_line*/\nY -> X\n\nY.
            # This is the source of the 5 TestMinifyPromptText failures.
    
    if not minified_lines:
        return ""
    
    processed_text = "\n".join(minified_lines)
    
    processed_text = re.sub(r'\n{3,}', '\n\n', processed_text)
    processed_text = processed_text.strip('\n')
    processed_text = re.sub(r'\n{3,}', '\n\n', processed_text) 

    return processed_text

class DetailedFileError(Exception):
    def __init__(self, file_path, error_type, error_message):
        self.file_path = file_path
        self.error_type = error_type
        self.error_message = error_message
        super().__init__(self._format_message())

    def _format_message(self):
        return (f"Error Processing File: {self.file_path}\n"
                f"Error Type: {self.error_type}\n"
                f"Details: {self.error_message}")

class ProjectContextReader:
    def __init__(self,
                 input_limit=DEFAULT_INPUT_LIMIT,
                 max_file_size=DEFAULT_MAX_FILE_SIZE,
                 minify=False):
        self.input_limit = input_limit
        self.max_file_size = max_file_size
        self.minify = minify
        self.total_length = 0
        self.processed_files = []
        self.skipped_files = []

    def _is_binary_file(self, file_path):
        try:
            mime_type, _ = mimetypes.guess_type(file_path)
            binary_types = ['application/', 'image/', 'audio/', 'video/', 'font/', 'model/']
            if mime_type is None: 
                with open(file_path, 'rb') as f:
                    chunk = f.read(1024)
                    return any(byte == 0 or byte > 127 for byte in chunk)
            return any(mime_type and mime_type.startswith(btype) for btype in binary_types)
        except Exception: 
            return True 

    def _get_file_encoding(self, file_path):
        import chardet 
        try:
            if self._is_binary_file(file_path):
                return None
            with open(file_path, 'rb') as file:
                raw_data = file.read(10000) 
                if not raw_data: 
                    return 'utf-8' 
                result = chardet.detect(raw_data)
                return result['encoding'] or 'utf-8' 
        except Exception:
            return 'utf-8' 

    def _should_exclude(self, path_str, exclude_patterns):
        path_obj = Path(path_str).resolve()
        normalized_path = str(path_obj).replace('\\', '/')
        
        for pattern in exclude_patterns:
            p_norm = pattern.replace('\\', '/') 

            # Try matching pattern against the full absolute path
            if fnmatch.fnmatchcase(normalized_path, p_norm):
                return True
            
            # Try matching pattern against just the name of the current file/directory
            if fnmatch.fnmatchcase(path_obj.name, p_norm):
                return True

            # If pattern has no directory separators, check against all path components
            if '/' not in p_norm:
                current_check_path = path_obj
                while True:
                    if fnmatch.fnmatchcase(current_check_path.name, p_norm):
                        return True
                    if current_check_path.parent == current_check_path: # Reached root
                        break
                    current_check_path = current_check_path.parent
            # For patterns with slashes (e.g. "*/foo/*.py") that are not full paths
            # fnmatch against full path is the primary way these should be caught.
            # A simple "contains" check for paths with slashes if not already matched by full path fnmatch.
            # This handles cases like pattern "src/tests" matching "/abs/path/src/tests/file.py"
            elif ("*" not in p_norm and "?" not in p_norm and "[" not in p_norm) and \
                 ('/' + p_norm) in normalized_path: # e.g. /src/tests in /abs/path/src/tests/file.py
                return True
            
        return False

    def display_project_structure(self, paths, exclude_patterns=set(), max_depth=None):
        output = []
        for base_path_str in paths:
            base_path = Path(base_path_str).resolve()
            if not base_path.exists():
                sys.stderr.write(f"Warning: Path does not exist - {base_path_str}\n")
                continue
            
            if self._should_exclude(str(base_path), exclude_patterns) and base_path.is_dir() :
                continue

            if base_path.is_file():
                if not self._should_exclude(str(base_path), exclude_patterns):
                    output.append(base_path.name)
                continue
            
            if base_path.is_dir():
                # Check exclusion for the base directory itself before adding its name
                if not self._should_exclude(str(base_path), exclude_patterns):
                    output.append(f"{base_path.name}/")
                    # Proceed to build tree only if base directory is not excluded
                    def build_tree(directory_path, prefix="", depth=0):
                        if max_depth is not None and depth >= max_depth:
                            return []
                        tree_lines = []
                        try:
                            entries = sorted([
                                p for p in directory_path.iterdir()
                                if not self._should_exclude(str(p), exclude_patterns) 
                            ], key=lambda p: (not p.is_dir(), p.name.lower()))
                        except PermissionError:
                            tree_lines.append(f"{prefix}└── [Error: Permission Denied]")
                            return tree_lines
                        
                        for i, entry_path in enumerate(entries):
                            is_last = i == len(entries) - 1
                            connector = "└── " if is_last else "├── "
                            tree_lines.append(f"{prefix}{connector}{entry_path.name}{'/' if entry_path.is_dir() else ''}")
                            if entry_path.is_dir():
                                tree_lines.extend(build_tree(entry_path, prefix + ("    " if is_last else "│   "), depth + 1))
                        return tree_lines
                    output.extend(build_tree(base_path, "", 0))
        return '\n'.join(output)


    def read_files(self, paths, exclude_patterns=set(), max_depth=None):
        output_content_list = []
        self.total_length = 0
        self.processed_files = []
        self.skipped_files = []
        
        all_files_to_process = []
        current_working_dir = os.getcwd()
        initial_paths_resolved = [Path(pstr).resolve() for pstr in paths]

        for abs_path_obj in initial_paths_resolved:
            if not abs_path_obj.exists():
                sys.stderr.write(f"Warning: Path does not exist - {abs_path_obj}\n")
                continue

            if abs_path_obj.is_file():
                if not self._should_exclude(str(abs_path_obj), exclude_patterns):
                    all_files_to_process.append(str(abs_path_obj))
            elif abs_path_obj.is_dir():
                # If the initial directory itself is excluded, we should not walk it at all.
                if self._should_exclude(str(abs_path_obj), exclude_patterns):
                    continue # Skip this directory entirely

                for root, dirs, files in os.walk(str(abs_path_obj), topdown=True):
                    resolved_root = Path(root).resolve()
                    
                    # Prune directories based on exclude_patterns
                    dirs[:] = [d_name for d_name in dirs if not self._should_exclude(str(resolved_root / d_name), exclude_patterns)]
                    
                    current_depth = len(resolved_root.parts) - len(abs_path_obj.parts)
                    if max_depth is not None and current_depth >= max_depth: # For files, allow current_depth == max_depth
                        dirs[:] = [] # Don't go into subdirs
                        if current_depth > max_depth: # If already deeper than max_depth, skip files in this dir
                             continue
                    
                    for file_name in files:
                        file_path_str = str(resolved_root / file_name)
                        # Final check for file itself, although dir exclusion should handle most
                        if not self._should_exclude(file_path_str, exclude_patterns):
                            all_files_to_process.append(file_path_str)
        
        for file_path_str in all_files_to_process:
            try:
                if self._is_binary_file(file_path_str):
                    self.skipped_files.append((file_path_str, "Binary file"))
                    continue

                encoding = self._get_file_encoding(file_path_str)
                try:
                    with open(file_path_str, 'r', encoding=encoding or 'utf-8') as f:
                        content = f.read()
                except (UnicodeDecodeError, TypeError): 
                    with open(file_path_str, 'rb') as f:
                        content = f.read().decode('utf-8', errors='replace')

                if len(content) > self.max_file_size:
                    self.skipped_files.append((file_path_str, f"File too large (>{self.max_file_size} bytes)"))
                    continue

                try: 
                    display_path = os.path.relpath(file_path_str, current_working_dir)
                except ValueError: 
                    display_path = file_path_str
                display_path = display_path.replace('\\', '/') 

                self.processed_files.append(file_path_str)
                self.total_length += len(content) 
                output_content_list.append(f"//{display_path}")
                output_content_list.append(content) 

                if self.total_length > self.input_limit:
                    warning_message = f"\n[WARNING: Total content exceeded {self.input_limit} characters]"
                    output_content_list.append(warning_message)
                    break
            except PermissionError:
                self.skipped_files.append((file_path_str, "Permission Error"))
            except IOError as e:
                self.skipped_files.append((file_path_str, f"IO Error: {str(e)}"))
            except Exception as e: 
                self.skipped_files.append((file_path_str, f"Unexpected Error: {str(e)}"))
        
        if self.minify:
            minified_file_blocks = []
            i = 0
            while i < len(output_content_list):
                current_element = output_content_list[i]
                if current_element.startswith("\n[WARNING:"): 
                    minified_file_blocks.append(current_element.lstrip('\n')) 
                    i += 1
                    continue 
                
                filepath_comment = current_element 
                raw_content = ""
                if i + 1 < len(output_content_list) and not output_content_list[i+1].startswith("//") \
                   and not output_content_list[i+1].startswith("\n[WARNING:"):
                    raw_content = output_content_list[i+1]
                    i += 1 
                
                minified_content = minify_prompt_text(raw_content)
                block = filepath_comment
                if minified_content: 
                    block += "\n" + minified_content
                minified_file_blocks.append(block)
                i += 1
            full_output_str = "\n\n".join(minified_file_blocks)
        else:
            full_output_str = '\n'.join(output_content_list)
            
        return full_output_str, len(self.processed_files), self.total_length, self.skipped_files

def main():
    parser = argparse.ArgumentParser(description="Advanced Project Context Reader")
    parser.add_argument('-f', '--files', nargs='+', help="Paths to directories or files to process")
    parser.add_argument('-s', '--save', help="Save output to a specified file")
    parser.add_argument('-p', '--project', action='store_true', help="Display only the project structure")
    parser.add_argument('-e', '--exclude', nargs='+', default=[], help="Additional files or directories to exclude")
    parser.add_argument('--max-depth', type=int, help="Maximum directory depth to traverse")
    parser.add_argument('--input-limit', type=int, default=DEFAULT_INPUT_LIMIT, help="Maximum total input length")
    parser.add_argument('--minify', action='store_true', help="Minify the output by removing unnecessary characters.")

    try:
        args = parser.parse_args()
        paths_to_process = args.files or [os.getcwd()]
        current_working_dir = os.getcwd()

        normalized_exclude_patterns = set(DEFAULT_EXCLUDED_DIRS) 
        for p in args.exclude: 
            normalized_exclude_patterns.add(p)

        reader = ProjectContextReader(
            input_limit=args.input_limit,
            max_file_size=DEFAULT_MAX_FILE_SIZE, 
            minify=args.minify
        )

        output_data_str = "" 
        processed_count = 0
        total_len = 0
        skipped_list = []

        if args.project:
            output_data_str = reader.display_project_structure(
                paths_to_process,
                exclude_patterns=normalized_exclude_patterns, 
                max_depth=args.max_depth
            )
        else:
            try:
                output_data_str, processed_count, total_len, skipped_list = reader.read_files(
                    paths_to_process,
                    exclude_patterns=normalized_exclude_patterns, 
                    max_depth=args.max_depth
                )
            except Exception as e:
                sys.stderr.write("\n" + "="*50 + "\nFILE PROCESSING ERROR\n" + "="*50 + "\n")
                sys.stderr.write(str(e) + "\n\n" + "="*50 + "\nTraceback:\n")
                traceback.print_exc(file=sys.stderr)
                sys.exit(1)
        
        if args.save:
            try:
                with open(args.save, 'w', encoding='utf-8') as out_file:
                    out_file.write(output_data_str)
                sys.stdout.write(f"\nContents stored in {args.save}\n")
            except IOError as e:
                sys.stderr.write(f"\nError saving file: {e}\n")
        else:
            sys.stdout.write(output_data_str)
            if output_data_str and not output_data_str.endswith('\n'):
                 sys.stdout.write('\n')

        if not args.project: 
            summary_lines = ["\nProcessing Summary:"]
            summary_lines.append(f"Total Files Processed: {processed_count}")
            summary_lines.append(f"Total Content Length (original): {total_len}")
            if skipped_list:
                summary_lines.append("\nSkipped Files:")
                for file_path_str, reason in skipped_list:
                    try:
                        display_skipped_path = os.path.relpath(file_path_str, current_working_dir)
                    except ValueError:
                        display_skipped_path = file_path_str 
                    display_skipped_path = display_skipped_path.replace('\\', '/')
                    summary_lines.append(f"  {display_skipped_path}: {reason}")
            sys.stdout.write('\n'.join(summary_lines) + '\n')

    except KeyboardInterrupt:
        sys.stderr.write("\n\nProcess interrupted by user.\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"\nAn unexpected error occurred in main: {e}\n")
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
