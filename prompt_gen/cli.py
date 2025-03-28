import os
import argparse
import fnmatch
from pathlib import Path
import sys
import traceback
import logging
import mimetypes

DEFAULT_INPUT_LIMIT = 50000
DEFAULT_MAX_FILE_SIZE = 1024 * 1024  # 1 MB max file size
DEFAULT_EXCLUDED_DIRS = [
    '.git', '.svn', '.hg',
    '__pycache__', '.pytest_cache',
    'node_modules', 'dist', 'build',
    '.next', '.vercel',
    '.venv', 'venv', 'env'
]

class DetailedFileError(Exception):
    """Detailed exception for file processing errors."""
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
                 max_file_size=DEFAULT_MAX_FILE_SIZE):
        """
        Initialize the ProjectContextReader with configurable parameters.
        :param input_limit: Maximum total input length
        :param max_file_size: Maximum size of individual files to read
        """
        self.input_limit = input_limit
        self.max_file_size = max_file_size
        self.total_length = 0
        self.processed_files = []
        self.skipped_files = []

    def _is_binary_file(self, file_path):
        """
        Determine if a file is binary by checking its MIME type.
        :param file_path: Path to the file
        :return: Boolean indicating if file is binary
        """
        try:
            # Use mimetypes to guess the file type
            mime_type, _ = mimetypes.guess_type(file_path)

            # List of binary or non-text MIME types to exclude
            binary_types = [
                'application/',
                'image/',
                'audio/',
                'video/',
                'font/',
                'model/'
            ]

            # If no MIME type detected, try to peek at the file contents
            if mime_type is None:
                with open(file_path, 'rb') as f:
                    chunk = f.read(1024)
                    # Check for null bytes or high bit set bytes
                    return any(byte == 0 or byte > 127 for byte in chunk)

            # Check if MIME type suggests binary content
            return any(mime_type and mime_type.startswith(btype) for btype in binary_types)
        except Exception:
            # If any error occurs, assume it might be binary to be safe
            return True

    def _get_file_encoding(self, file_path):
        """
        Detect the file encoding with fallback.
        :param file_path: Path to the file
        :return: Detected encoding or default 'utf-8'
        """
        import chardet
        try:
            # For binary files, return None
            if self._is_binary_file(file_path):
                return None

            with open(file_path, 'rb') as file:
                raw_data = file.read(10000)  # Read first 10k bytes for detection
                result = chardet.detect(raw_data)
                return result['encoding'] or 'utf-8'
        except Exception:
            return 'utf-8'

    def _should_exclude(self, path, exclude_patterns):
        """
        Determine if a path should be excluded based on patterns.
        :param path: Path to check
        :param exclude_patterns: Set of exclusion patterns
        :return: Boolean indicating if path should be excluded
        """
        # Normalize path to absolute path with forward slashes
        abs_path = os.path.abspath(path)
        normalized_path = abs_path.replace('\\', '/')

        # Normalize and process exclude patterns
        normalized_patterns = []
        for pattern in exclude_patterns:
            # Convert to absolute path and normalize
            norm_pattern = os.path.abspath(pattern).replace('\\', '/') if os.path.exists(pattern) else pattern
            normalized_patterns.append(norm_pattern)

        # Helper function to check if path matches pattern
        def path_matches_pattern(full_path, pattern):
            # Check if pattern is a directory and full_path is under that directory
            if os.path.isdir(pattern) and full_path.startswith(pattern + '/'):
                return True

            # Check basename match
            if fnmatch.fnmatch(os.path.basename(full_path), os.path.basename(pattern)):
                return True

            # Check full path with wildcard
            if fnmatch.fnmatch(full_path, pattern.replace('\\', '/') + '*'):
                return True

            # Check if any parent directory matches the pattern
            path_parts = full_path.split('/')
            for i in range(len(path_parts)):
                partial_path = '/'.join(path_parts[:i+1])
                if any(
                    fnmatch.fnmatch(partial_path, pattern.replace('\\', '/')) or
                    fnmatch.fnmatch(path_parts[i], pattern)
                    for pattern in normalized_patterns
                ):
                    return True

            return False

        # Check if path matches any of the exclusion patterns
        return any(path_matches_pattern(normalized_path, pattern) for pattern in normalized_patterns)

    def display_project_structure(self, paths, exclude_patterns=set(), max_depth=None):
        """
        Display project structure with optional depth control and exclusions.
        :param paths: List of paths to process
        :param exclude_patterns: Set of exclusion patterns
        :param max_depth: Maximum directory depth to display
        :return: Formatted project structure string
        """
        output = []
        for base_path in paths:
            base_path = os.path.abspath(base_path)
            if not os.path.exists(base_path):
                print(f"Warning: Path does not exist - {base_path}")
                continue

            # Handle single files
            if os.path.isfile(base_path):
                if not self._should_exclude(base_path, exclude_patterns):
                    output.append(os.path.basename(base_path))
                continue

            # Handle directories
            if os.path.isdir(base_path):
                base_name = os.path.basename(base_path)
                output.append(f"{base_name}/")

                # Internal function to recursively build tree
                def build_tree(directory, prefix="", depth=0):
                    if max_depth is not None and depth > max_depth:
                        return []

                    tree_output = []
                    try:
                        # Sort entries for consistent output
                        entries = sorted(os.listdir(directory))
                    except PermissionError:
                        return []

                    # Process entries
                    for index, entry in enumerate(entries):
                        full_path = os.path.join(directory, entry)

                        # Skip excluded paths
                        if self._should_exclude(full_path, exclude_patterns):
                            continue

                        # Determine connectors for tree display
                        is_last = index == len(entries) - 1
                        connector = "└── " if is_last else "├── "

                        # Add current entry
                        entry_display = f"{prefix}{connector}{entry}"
                        if os.path.isdir(full_path):
                            entry_display += "/"
                        tree_output.append(entry_display)

                        # Recursively process subdirectories
                        if os.path.isdir(full_path):
                            extension = "    " if is_last else "│   "
                            tree_output.extend(
                                build_tree(
                                    full_path,
                                    prefix + extension,
                                    depth + 1
                                )
                            )
                    return tree_output

                # Generate and extend output with directory tree
                output.extend(build_tree(base_path))

        return '\n'.join(output)

    def read_files(self, paths, exclude_patterns=set(), max_depth=None):
        """
        Read contents of files or directories with advanced error handling.
        :param paths: List of paths to process
        :param exclude_patterns: Set of exclusion patterns
        :param max_depth: Maximum directory depth to traverse
        :return: Formatted string of file contents
        """
        output = []
        self.total_length = 0
        self.processed_files = []
        self.skipped_files = []
        # Flatten and validate input paths
        all_files_to_process = []
        for path in paths:
            path = os.path.abspath(path)
            if not os.path.exists(path):
                print(f"Warning: Path does not exist - {path}")
                continue
            if os.path.isfile(path):
                if not self._should_exclude(path, exclude_patterns):
                    all_files_to_process.append(path)
            elif os.path.isdir(path):
                # Walk directory with depth control
                for root, dirs, files in os.walk(path):
                    # Remove excluded directories in-place
                    dirs[:] = [d for d in dirs if not self._should_exclude(os.path.join(root, d), exclude_patterns)]
                    # Optional depth control
                    if max_depth is not None:
                        current_depth = root[len(path):].count(os.path.sep)
                        if current_depth >= max_depth:
                            continue
                    for file in files:
                        file_path = os.path.join(root, file)
                        if not self._should_exclude(file_path, exclude_patterns):
                            all_files_to_process.append(file_path)

        # Process files with comprehensive error handling
        for file_path in all_files_to_process:
            try:
                # Check if file is binary or exceed max file size
                if self._is_binary_file(file_path):
                    self.skipped_files.append((file_path, "Binary file"))
                    continue

                # Determine file encoding
                encoding = self._get_file_encoding(file_path)

                # Read file with detected or fallback encoding
                try:
                    with open(file_path, 'r', encoding=encoding or 'utf-8') as f:
                        content = f.read()
                except (UnicodeDecodeError, TypeError):
                    # If encoding fails, try reading as bytes and convert to string
                    with open(file_path, 'rb') as f:
                        content = f.read().decode('utf-8', errors='replace')

                # Check file size
                if len(content) > self.max_file_size:
                    self.skipped_files.append((file_path, f"File too large (>{self.max_file_size} bytes)"))
                    continue

                # Track processed files and content
                self.processed_files.append(file_path)
                self.total_length += len(content)
                output.append(f"\n//{file_path}")
                output.append(content)

                # Break if total length exceeds limit
                if self.total_length > self.input_limit:
                    output.append(f"\n[WARNING: Total content exceeded {self.input_limit} characters]")
                    break

            except PermissionError:
                self.skipped_files.append((file_path, "Permission Error"))
            except IOError as e:
                self.skipped_files.append((file_path, f"IO Error: {str(e)}"))
            except Exception as e:
                self.skipped_files.append((file_path, f"Unexpected Error: {str(e)}"))

        # Print summary
        print("\nProcessing Summary:")
        print(f"Total Files Processed: {len(self.processed_files)}")
        print(f"Total Content Length: {self.total_length}")
        if self.skipped_files:
            print("\nSkipped Files:")
            for file, reason in self.skipped_files:
                print(f"  {file}: {reason}")
        return '\n'.join(output)

def main():
    parser = argparse.ArgumentParser(description="Advanced Project Context Reader")
    parser.add_argument('-f', '--files', nargs='+', help="Paths to directories or files to process")
    parser.add_argument('-s', '--save', help="Save output to a specified file")
    parser.add_argument('-p', '--project', action='store_true', help="Display only the project structure")
    parser.add_argument('-e', '--exclude', nargs='+', default=[], help="Additional files or directories to exclude")
    parser.add_argument('--max-depth', type=int, help="Maximum directory depth to traverse")
    parser.add_argument('--input-limit', type=int, default=DEFAULT_INPUT_LIMIT, help="Maximum total input length")

    try:
        args = parser.parse_args()
        # Use current directory if no paths specified
        paths = args.files or [os.getcwd()]

        # Additional exclude patterns
        exclude_patterns = set(DEFAULT_EXCLUDED_DIRS)
        exclude_patterns.update(args.exclude)

        # Initialize reader
        reader = ProjectContextReader(
            input_limit=args.input_limit
        )

        # Generate output
        try:
            # Generate output based on mode
            if args.project:
                output = reader.display_project_structure(
                    paths,
                    exclude_patterns=exclude_patterns,
                    max_depth=args.max_depth
                )
            else:
                output = reader.read_files(
                    paths,
                    exclude_patterns=exclude_patterns,
                    max_depth=args.max_depth
                )
        except Exception as e:
            # Detailed error handling
            print("\n" + "="*50)
            print("FILE PROCESSING ERROR")
            print("="*50)
            print(str(e))
            print("\n" + "="*50)
            print("Traceback:")
            traceback.print_exc()
            sys.exit(1)

        # Output handling
        if args.save:
            with open(args.save, 'w', encoding='utf-8') as out_file:
                out_file.write(output)
            print(f"\nContents stored in {args.save}")
        else:
            print(output)

    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
