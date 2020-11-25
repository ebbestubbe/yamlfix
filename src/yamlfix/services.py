"""Gather all the orchestration functionality required by the program to work.

Classes and functions that connect the different domain model objects with the adapters
and handlers to achieve the program's purpose.
"""


import re
from io import StringIO
from typing import List, Optional, Tuple

from _io import TextIOWrapper
from ruamel.yaml import YAML  # type: ignore


def fix_files(files: Tuple[TextIOWrapper]) -> Optional[str]:
    """Fix the yaml source code of a list of files.

    If the input is taken from stdin, it will output the value to stdout.

    Args:
        files: List of files to fix.

    Returns:
        Fixed code retrieved from stdin or None.
    """
    for file_wrapper in files:
        source = file_wrapper.read()
        fixed_source = fix_code(source)

        try:
            # Click testing runner doesn't simulate correctly the reading from stdin
            # instead of setting the name attribute to `<stdin>` it gives an
            # AttributeError. But when you use it outside testing, no AttributeError
            # is raised and name has the value <stdin>. So there is no way of testing
            # this behaviour.
            if file_wrapper.name == "<stdin>":  # pragma no cover
                output = "output"
            else:
                output = "file"
        except AttributeError:
            output = "output"

        if output == "file":
            file_wrapper.seek(0)
            file_wrapper.write(fixed_source)
            file_wrapper.truncate()
        else:
            return fixed_source

    return None


def fix_code(source_code: str) -> str:
    """Fix yaml source code to correct the format.

    It corrects these errors:

        * Add --- at the beginning of the file.

    Args:
        source_code: Source code to be corrected.

    Returns:
        Corrected source code.
    """
    fixers = [_ruamel_yaml_fixer, _fix_top_level_lists]
    for fixer in fixers:
        source_code = fixer(source_code)

    return source_code


def _ruamel_yaml_fixer(source_code: str) -> str:
    """Run Ruamel's yaml fixer.

    Args:
        source_code: Source code to be corrected.

    Returns:
        Corrected source code.
    """
    # Configure YAML formatter
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.allow_duplicate_keys = True
    yaml.explicit_start = True  # Start the document with ---
    source_dict = yaml.load(source_code)

    # Return the output to a string
    string_stream = StringIO()
    yaml.dump(source_dict, string_stream)
    source_code = string_stream.getvalue()
    string_stream.close()

    return source_code.strip()


def _fix_top_level_lists(source_code: str) -> str:
    """Deindent the source with a top level list.

    Documents like the following:

    ```yaml
    ---
    - item 1
    - item 2
    ```

    Are wrongly indented by the ruyaml parser:

    ```yaml
    ---
      - item 1
      - item 2
    ```

    This function restores the indentation back to the original.

    Args:
        source_code: Source code to be corrected.

    Returns:
        Corrected source code.
    """
    source_lines = source_code.splitlines()
    fixed_source_lines: List[str] = []
    is_top_level_list: Optional[bool] = None

    for line in source_lines:

        # Skip the heading and first empty lines
        if line in ["---", ""]:
            fixed_source_lines.append(line)
            continue

        # Check if the first valid line is an indented list item
        if re.match(r"\s*- +.*", line) and is_top_level_list is None:
            is_top_level_list = True

            # Extract the indentation level
            serialized_line = re.match(r"(?P<indent>\s*)- +(?P<content>.*)", line)
            if serialized_line is None:
                raise ValueError(f"Error extracting the indentation of line: {line}")
            indent = serialized_line.groupdict()["indent"]

            # Remove the indentation from the line
            fixed_source_lines.append(re.sub(rf"^{indent}(.*)", r"\1", line))
        elif is_top_level_list:
            fixed_source_lines.append(re.sub(rf"^{indent}(.*)", r"\1", line))
        else:
            return source_code

    return "\n".join(fixed_source_lines)
