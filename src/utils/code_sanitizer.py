"""
Code sanitization utilities for cleaning LLM-generated code output.
"""

import re
from typing import Optional, List
from pathlib import Path

from .logger import LoggerMixin


class CodeSanitizer(LoggerMixin):
    """Utility class for sanitizing LLM-generated code output."""
    
    def __init__(self):
        """Initialize the code sanitizer."""
        self.logger.info("Initializing Code Sanitizer")
    
    def sanitize_java_code(self, llm_output: str) -> str:
        """
        Sanitize Java code from LLM output by extracting only the code between triple backticks.
        
        Args:
            llm_output: Raw LLM output containing code and commentary
        
        Returns:
            Clean Java code without LLM commentary
        """
        try:
            # Extract code between triple backticks
            code = self._extract_code_blocks(llm_output)

            #print(f"#### sanitizer llm_output:{llm_output}")

            if not code:
                self.logger.warning("No code blocks found in LLM output, using fallback extraction")
                code = self._fallback_code_extraction(llm_output)
            
            # Clean the extracted code
            code = self._clean_java_code(code)
            
            # Validate the code structure
            if not self._validate_java_code_structure(code):
                self.logger.warning("Generated code may have structural issues")
            
            return code
            
        except Exception as e:
            self.logger.error(f"Error sanitizing Java code: {e}")
            # Return fallback extraction as last resort
            return self._fallback_code_extraction(llm_output)
    
    def _extract_code_blocks(self, text: str) -> str:
        """
        Extract code from markdown code blocks.
        
        Args:
            text: Text containing code blocks
        
        Returns:
            Extracted code or empty string if not found
        """
        # Pattern to match code blocks with optional language specification
        patterns = [
            r'```java\s*\n(.*?)\n```',  # ```java ... ```
            r'```\s*\n(.*?)\n```',     # ``` ... ```
            r'```java(.*?)```',        # ```java...``` (no newlines)
            r'```(.*?)```'             # ```...``` (no newlines)
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            if matches:
                # Take the first (usually largest) code block
                code = matches[0].strip()
                if code and self._looks_like_java_code(code):
                    self.logger.info(f"Extracted code block using pattern: {pattern}")
                    return code
        
        return ""
    
    def _fallback_code_extraction(self, text: str) -> str:
        """
        Fallback method to extract Java code when code blocks are not found.

        Finds the first Java anchor line (package, import, class declaration, annotation)
        and collects every line from that point until the end, skipping only obvious
        standalone commentary lines that appear *before* the code starts.

        Args:
            text: Text that might contain Java code
        
        Returns:
            Best guess at Java code content
        """
        lines = text.split('\n')

        # 1. Find where the Java code begins
        start_index = None
        for i, line in enumerate(lines):
            if self._is_java_anchor_line(line):
                start_index = i
                break

        if start_index is None:
            # No clear Java anchor found — fall back to the original heuristic
            self.logger.warning("No Java anchor line found in fallback extraction")
            return self._heuristic_code_extraction(lines)

        # 2. Collect all lines from the anchor onward, removing only
        #    commentary lines that appear on their own (not inside the code body).
        #    Once we are inside the class body (brace_depth > 0) we keep everything.
        code_lines = []
        brace_depth = 0
        inside_body = False

        for line in lines[start_index:]:
            # Track brace depth to know when we are inside a class/method body
            brace_depth += line.count('{') - line.count('}')
            if brace_depth > 0:
                inside_body = True

            if not inside_body and self._is_commentary_line(line):
                # Skip commentary that appears before the class body opens
                continue

            code_lines.append(line)

            # If brace depth returns to 0 after we entered the body,
            # the top-level class is closed — stop collecting.
            if inside_body and brace_depth <= 0:
                break

        return '\n'.join(code_lines).strip()

    def _is_java_anchor_line(self, line: str) -> bool:
        """
        Return True if the line is a strong Java anchor: package, import,
        a class/interface declaration, or a top-level annotation.

        Args:
            line: Line to inspect

        Returns:
            True if the line is a reliable start-of-Java-code marker
        """
        stripped = line.strip()
        anchor_patterns = [
            r'^package\s+[\w.]+;',
            r'^import\s+[\w.*]+;',
            r'^(public\s+)?(abstract\s+)?class\s+\w+',
            r'^(public\s+)?interface\s+\w+',
            r'^(public\s+)?enum\s+\w+',
            r'^@\w+',   # Top-level annotation
        ]
        for pattern in anchor_patterns:
            if re.match(pattern, stripped):
                return True
        return False

    def _heuristic_code_extraction(self, lines: list) -> str:
        """
        Original heuristic-based extraction used as a last resort.

        The key fix over the original implementation is that we do NOT break
        on non-Java-looking lines once we are inside the code — blank lines and
        closing braces would previously terminate collection prematurely.

        Args:
            lines: Lines of the source text

        Returns:
            Extracted code string
        """
        code_lines = []
        in_code = False
        consecutive_non_java = 0
        MAX_CONSECUTIVE_NON_JAVA = 5  # tolerate up to 5 ambiguous lines

        for line in lines:
            if self._is_commentary_line(line):
                if in_code:
                    consecutive_non_java += 1
                    if consecutive_non_java > MAX_CONSECUTIVE_NON_JAVA:
                        break
                    code_lines.append(line)
                continue

            if self._looks_like_java_line(line):
                in_code = True
                consecutive_non_java = 0
                code_lines.append(line)
            elif in_code:
                # Inside code: keep blank / indented lines, tolerate ambiguous ones
                if line.strip() == '' or line.startswith(' ') or line.startswith('\t') or line.strip() == '}':
                    consecutive_non_java = 0
                    code_lines.append(line)
                else:
                    consecutive_non_java += 1
                    if consecutive_non_java > MAX_CONSECUTIVE_NON_JAVA:
                        break
                    code_lines.append(line)

        return '\n'.join(code_lines).strip()

    def _clean_java_code(self, code: str) -> str:
        """
        Clean Java code by removing unwanted elements.
        
        Args:
            code: Raw Java code
        
        Returns:
            Cleaned Java code
        """
        lines = code.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Remove lines that look like LLM commentary
            if self._is_commentary_line(line):
                continue
            
            # Remove inline LLM comments but keep Java comments
            line = self._remove_inline_llm_comments(line)
            
            cleaned_lines.append(line)
        
        # Join and clean up extra whitespace
        cleaned_code = '\n'.join(cleaned_lines)
        cleaned_code = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_code)  # Remove excessive blank lines
        
        return cleaned_code.strip()
    
    def _is_commentary_line(self, line: str) -> bool:
        """
        Check if a line is LLM commentary rather than code.
        
        Args:
            line: Line to check
        
        Returns:
            True if line appears to be commentary
        """
        stripped = line.strip()
        lower = stripped.lower()
        
        # Keep empty lines — they are part of code formatting
        if not stripped:
            return False

        # Never treat lines that look like Java constructs as commentary,
        # even if they happen to match a commentary pattern superficially.
        if self._looks_like_java_line(line):
            return False
        
        # LLM commentary patterns
        commentary_patterns = [
            r'^here\'s',
            r'^this (code|class|method|test)',
            r'^the (above|following|code|class)',
            r'^explanation:',
            r'^note:',
            r'^important:',
            r'^\d+\.',  # Numbered lists
            r'^-\s',    # Bullet points (dash + space, to avoid matching -> or --)
            r'^\*\s',   # Asterisk bullet points (with space)
            r'^###',    # Markdown headers
            r'^##',
            r'^#(?!\s*!)',  # Markdown H1, but not shebang lines
        ]
        
        for pattern in commentary_patterns:
            if re.match(pattern, lower):
                return True
        
        return False
    
    def _looks_like_java_line(self, line: str) -> bool:
        """
        Check if a line looks like Java code.
        
        Args:
            line: Line to check
        
        Returns:
            True if line appears to be Java code
        """
        line = line.strip()
        
        # Java code indicators
        java_patterns = [
            r'^package\s+[\w.]+;',
            r'^import\s+[\w.*]+;',
            r'^public\s+class\s+\w+',
            r'^class\s+\w+',
            r'^@\w+',  # Annotations
            r'^public\s+\w+',
            r'^private\s+\w+',
            r'^protected\s+\w+',
            r'^\w+\s*\(',  # Method calls
            r'.*\{$',      # Opening braces
            r'^\}',        # Closing braces
            r'.*;\s*$',    # Statements ending with semicolon
        ]
        
        for pattern in java_patterns:
            if re.match(pattern, line):
                return True
        
        return False
    
    def _looks_like_java_code(self, code: str) -> bool:
        """
        Check if the extracted code looks like valid Java code.
        
        Args:
            code: Code to validate
        
        Returns:
            True if code appears to be Java
        """
        # Must contain some Java keywords
        java_keywords = ['class', 'public', 'import', 'package', '@Test']
        
        for keyword in java_keywords:
            if keyword in code:
                return True
        
        return False
    
    def _remove_inline_llm_comments(self, line: str) -> str:
        """
        Remove inline LLM comments while preserving Java comments.
        
        Args:
            line: Line to process
        
        Returns:
            Line with LLM comments removed
        """
        return line
    
    def _validate_java_code_structure(self, code: str) -> bool:
        """
        Validate basic Java code structure.
        
        Args:
            code: Java code to validate
        
        Returns:
            True if code has valid basic structure
        """
        # Check for balanced braces
        open_braces = code.count('{')
        close_braces = code.count('}')
        
        if open_braces != close_braces:
            self.logger.warning(f"Unbalanced braces: {open_braces} open, {close_braces} close")
            return False
        
        # Check for required elements
        if 'class ' not in code:
            self.logger.warning("No class declaration found")
            return False
        
        return True
    
    def sanitize_file_content(self, file_path: Path, content: str) -> str:
        """
        Sanitize content for a specific file type.
        
        Args:
            file_path: Path to the file being processed
            content: Raw content to sanitize
        
        Returns:
            Sanitized content
        """
        if file_path.suffix == '.java':
            return self.sanitize_java_code(content)
        elif file_path.suffix == '.xml':
            return self._sanitize_xml_content(content)
        else:
            return self._remove_llm_commentary(content)
    
    def _sanitize_xml_content(self, content: str) -> str:
        """
        Sanitize XML content from LLM output.
        """
        xml_match = re.search(r'```xml\s*\n(.*?)\n```', content, re.DOTALL)
        if xml_match:
            return xml_match.group(1).strip()
        
        code_match = re.search(r'```\s*\n(.*?)\n```', content, re.DOTALL)
        if code_match and '<' in code_match.group(1):
            return code_match.group(1).strip()
        
        lines = content.split('\n')
        xml_lines = []
        in_xml = False
        
        for line in lines:
            if '<' in line and '>' in line:
                in_xml = True
                xml_lines.append(line)
            elif in_xml and (line.strip() == '' or line.startswith(' ') or line.startswith('\t')):
                xml_lines.append(line)
            elif in_xml and not ('<' in line or line.strip() == ''):
                break
        
        return '\n'.join(xml_lines).strip()
    
    def _remove_llm_commentary(self, content: str) -> str:
        """
        Remove LLM commentary from generic content.
        """
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            if not self._is_commentary_line(line):
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()

    def ensure_test500_imports(self, java_code: str) -> str:
        """
        Programmatic safety net for *500Test.java files.

        Ensures that the following imports are always present, regardless of
        what the LLM generated.  If an import is already present it is NOT
        duplicated; if it is missing it is injected immediately after the last
        existing import statement (or after the package declaration when there
        are no imports yet).

        Required imports:
          - import static org.junit.Assert.*;   (assertEquals, assertTrue, …)
          - import org.junit.Test;               (@Test annotation)
          - import org.glassfish.jersey.server.ResourceConfig;
          - import org.glassfish.jersey.test.JerseyTest;
          - import javax.ws.rs.core.Response;
          - import org.mockito.MockedStatic;
          - import org.mockito.Mockito;

        Args:
            java_code: Java source code string (already sanitized).

        Returns:
            Java source code with all mandatory imports guaranteed.
        """
        MANDATORY_IMPORTS = [
            "import static org.junit.Assert.*;",
            "import org.junit.Test;",
            "import org.glassfish.jersey.server.ResourceConfig;",
            "import org.glassfish.jersey.test.JerseyTest;",
            "import javax.ws.rs.core.Response;",
            "import org.mockito.MockedStatic;",
            "import org.mockito.Mockito;",
        ]

        lines = java_code.split('\n')

        # Determine which mandatory imports are already present
        missing = []
        for imp in MANDATORY_IMPORTS:
            # Normalise whitespace for the check
            normalised = ' '.join(imp.split())
            already_present = any(' '.join(l.split()) == normalised for l in lines)
            if not already_present:
                missing.append(imp)

        if not missing:
            return java_code  # Nothing to do

        # Find the best insertion point:
        #   1. After the last 'import …;' line
        #   2. Fallback: after the 'package …;' line
        #   3. Last resort: prepend to the file
        last_import_idx = None
        package_idx = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('import '):
                last_import_idx = i
            elif stripped.startswith('package '):
                package_idx = i

        if last_import_idx is not None:
            insert_after = last_import_idx
        elif package_idx is not None:
            insert_after = package_idx
        else:
            insert_after = -1  # Prepend

        # Build the injection block
        injection = [''] + missing  # blank line separator before the block

        if insert_after == -1:
            new_lines = missing + [''] + lines
        else:
            new_lines = lines[:insert_after + 1] + injection + lines[insert_after + 1:]

        injected = ', '.join(m.replace('import ', '').rstrip(';') for m in missing)
        self.logger.info(
            f"[500Test import guard] Injected {len(missing)} missing import(s): {injected}"
        )
        return '\n'.join(new_lines)
    # ------------------------------------------------------------------
    # Status-code immutability guard
    # ------------------------------------------------------------------

    def extract_status_codes_per_method(self, java_code: str) -> dict:
        """
        Extract the set of .statusCode(N) values for every @Test method in
        the given Java source code.

        The extraction is done with a simple line-by-line scan that is
        intentionally independent of any specific API implementation.  It
        works for any JUnit 4 / Rest Assured test class.

        Returns:
            A dict mapping method_name -> set of integer status codes found
            inside that method's body.

        Example::

            {
                "test_get_v2_alpha_codes_not_found": {404},
                "test_get_v2_alpha_codes_server_error": {500},
            }
        """
        result: dict = {}
        current_method: str | None = None
        brace_depth: int = 0
        method_brace_start: int = 0

        # Patterns (no API-specific knowledge required)
        method_decl_re = re.compile(
            r'public\s+void\s+(\w+)\s*\('
        )
        status_code_re = re.compile(
            r'\.statusCode\s*\(\s*(\d+)\s*\)'
        )

        for line in java_code.split('\n'):
            # Track brace depth to know when a method body ends
            brace_depth += line.count('{') - line.count('}')

            # Detect start of a new public void method
            m = method_decl_re.search(line)
            if m:
                current_method = m.group(1)
                result.setdefault(current_method, set())
                method_brace_start = brace_depth
                continue

            if current_method is not None:
                # Collect status codes inside this method
                for sc_match in status_code_re.finditer(line):
                    result[current_method].add(int(sc_match.group(1)))

                # Method body closed when brace depth returns to where it was
                # before the opening brace of the method
                if brace_depth < method_brace_start:
                    current_method = None

        return result

    def enforce_status_code_immutability(
        self,
        original_code: str,
        corrected_code: str,
        add_ignore_on_violation: bool = True,
    ) -> tuple:
        """
        Compare the status codes in *original_code* with those in
        *corrected_code*.  If the LLM changed any `.statusCode(N)` value for
        any @Test method, the violation is handled as follows:

        * If *add_ignore_on_violation* is True (default): the offending test
          method in *corrected_code* is reverted to the original method body
          (i.e., the original method replaces the corrected one) and an
          ``@Ignore`` annotation is added with a descriptive reason.
        * The method returns the (possibly patched) code and a list of
          violation descriptions.

        This guard is entirely generic — it does not know anything about the
        API under test.  It simply compares integer literals inside
        ``.statusCode(...)`` calls before and after LLM correction.

        Args:
            original_code:          Java source before LLM correction.
            corrected_code:         Java source after LLM correction.
            add_ignore_on_violation: Whether to patch violations automatically.

        Returns:
            (patched_code: str, violations: list[str])
        """
        orig_map = self.extract_status_codes_per_method(original_code)
        corr_map = self.extract_status_codes_per_method(corrected_code)

        violations: list = []
        patched_code = corrected_code

        for method_name, orig_codes in orig_map.items():
            if not orig_codes:
                continue  # method has no statusCode assertion — nothing to guard

            corr_codes = corr_map.get(method_name, set())

            if orig_codes != corr_codes:
                violation_msg = (
                    f"Status code changed in '{method_name}': "
                    f"original={sorted(orig_codes)} → corrected={sorted(corr_codes)}"
                )
                violations.append(violation_msg)
                self.logger.warning(
                    f"[status-code guard] {violation_msg}"
                )

                if add_ignore_on_violation:
                    # Revert the method body to the original and add @Ignore
                    patched_code = self._revert_method_to_original(
                        patched_code,
                        original_code,
                        method_name,
                        reason=(
                            f"LLM changed statusCode from {sorted(orig_codes)} "
                            f"to {sorted(corr_codes)} — spec value preserved, "
                            f"test needs manual review"
                        ),
                    )

        return patched_code, violations

    # ------------------------------------------------------------------
    # Internal helpers for status-code guard
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_method_block(java_code: str, method_name: str) -> str | None:
        """
        Return the full text of the named public void method (including its
        @Test / @Ignore annotations and closing brace) from *java_code*, or
        None if the method is not found.
        """
        lines = java_code.split('\n')
        method_decl_re = re.compile(
            rf'public\s+void\s+{re.escape(method_name)}\s*\('
        )

        # Walk backward from the method declaration to collect leading
        # annotations (@Test, @Ignore, @Before, …)
        decl_idx = None
        for i, line in enumerate(lines):
            if method_decl_re.search(line):
                decl_idx = i
                break

        if decl_idx is None:
            return None

        # Collect annotations that immediately precede the declaration
        start_idx = decl_idx
        for i in range(decl_idx - 1, -1, -1):
            stripped = lines[i].strip()
            if stripped.startswith('@') or stripped == '':
                start_idx = i
            else:
                break

        # Collect lines until the method body closes
        brace_depth = 0
        end_idx = decl_idx
        body_started = False
        for i in range(decl_idx, len(lines)):
            brace_depth += lines[i].count('{') - lines[i].count('}')
            if brace_depth > 0:
                body_started = True
            if body_started and brace_depth <= 0:
                end_idx = i
                break

        return '\n'.join(lines[start_idx:end_idx + 1])

    def _revert_method_to_original(
        self,
        corrected_code: str,
        original_code: str,
        method_name: str,
        reason: str,
    ) -> str:
        """
        Replace the method *method_name* in *corrected_code* with the version
        from *original_code*, and prepend an ``@Ignore`` annotation to it.

        If the method cannot be located in either source, *corrected_code* is
        returned unchanged (fail-safe).
        """
        orig_block = self._extract_method_block(original_code, method_name)
        corr_block = self._extract_method_block(corrected_code, method_name)

        if orig_block is None or corr_block is None:
            self.logger.warning(
                f"[status-code guard] Could not locate '{method_name}' for revert"
            )
            return corrected_code

        # Escape the reason for use inside a Java string literal
        safe_reason = reason.replace('"', '\\"').replace('\n', ' ')

        # Add @Ignore before the first @Test annotation in the original block
        ignore_annotation = f'@Ignore("{safe_reason}")'
        if '@Ignore' not in orig_block:
            orig_block_annotated = re.sub(
                r'(@Test(?:\s*\([^)]*\))?)',
                f'{ignore_annotation}\n    \\1',
                orig_block,
                count=1,
            )
        else:
            orig_block_annotated = orig_block  # already ignored

        # Ensure @Ignore import is present
        if 'import org.junit.Ignore;' not in corrected_code:
            corrected_code = re.sub(
                r'(import org\.junit\.Test;)',
                r'\1\nimport org.junit.Ignore;',
                corrected_code,
                count=1,
            )

        # Replace the corrected block with the reverted+annotated original
        patched = corrected_code.replace(corr_block, orig_block_annotated, 1)
        if patched == corrected_code:
            self.logger.warning(
                f"[status-code guard] Could not replace block for '{method_name}' "
                f"(block not found verbatim in corrected code)"
            )
        return patched
