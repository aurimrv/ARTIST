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
        
        Args:
            text: Text that might contain Java code
        
        Returns:
            Best guess at Java code content
        """
        lines = text.split('\n')
        code_lines = []
        in_code = False
        
        for line in lines:
            # Skip obvious commentary lines
            if self._is_commentary_line(line):
                continue
            
            # Look for Java code indicators
            if self._looks_like_java_line(line):
                in_code = True
                code_lines.append(line)
            elif in_code and (line.strip() == '' or line.startswith(' ') or line.startswith('\t')):
                # Continue collecting if we're in code and line is indented or empty
                code_lines.append(line)
            elif in_code and not self._looks_like_java_line(line):
                # Stop if we hit non-Java content
                break
        
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
        line = line.strip().lower()
        
        # Skip empty lines
        if not line:
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
            r'^-',      # Bullet points
            r'^\*',     # Asterisk bullet points
            r'^###',    # Markdown headers
            r'^##',
            r'^#',
        ]
        
        for pattern in commentary_patterns:
            if re.match(pattern, line):
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
            r'^import\s+[\w.]+;',
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
        # This is a simple implementation - could be enhanced
        # For now, just return the line as-is since most LLM comments
        # are on separate lines
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
            # For other file types, just remove obvious LLM commentary
            return self._remove_llm_commentary(content)
    
    def _sanitize_xml_content(self, content: str) -> str:
        """
        Sanitize XML content from LLM output.
        
        Args:
            content: Raw XML content
        
        Returns:
            Clean XML content
        """
        # Extract XML from code blocks if present
        xml_match = re.search(r'```xml\s*\n(.*?)\n```', content, re.DOTALL)
        if xml_match:
            return xml_match.group(1).strip()
        
        # Extract XML from generic code blocks
        code_match = re.search(r'```\s*\n(.*?)\n```', content, re.DOTALL)
        if code_match and '<' in code_match.group(1):
            return code_match.group(1).strip()
        
        # If no code blocks, try to extract XML content
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
        
        Args:
            content: Content to clean
        
        Returns:
            Content with commentary removed
        """
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            if not self._is_commentary_line(line):
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()

