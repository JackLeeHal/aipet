import sys
import io
import contextlib
import traceback
from ..base import Skill
import os

class PythonExecutionSkill(Skill):
    def __init__(self, bus=None):
        self.bus = bus

    @property
    def name(self) -> str:
        return "execute_python"

    @property
    def description(self) -> str:
        return "Execute arbitrary Python code. Use this to run calculations, file operations, or use imported libraries like docx, pdf, etc."

    @property
    def parameters(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "execute_python",
                "description": "Execute Python code and return stdout/stderr.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The Python code to execute."
                        }
                    },
                    "required": ["code"]
                }
            }
        }

    async def execute(self, code: str) -> str:
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()

        # Add skills directory to path to allow importing 'docx', 'pdf', 'reminder' etc.
        current_dir = os.path.dirname(os.path.abspath(__file__))
        skills_dir = os.path.dirname(current_dir) # desktop_aipet/src/skills

        # Add docx and pptx directories to path to handle their internal absolute imports (e.g. 'import ooxml')
        # Note: This might cause conflicts if both have ooxml, but it's a best effort to make them work.
        docx_dir = os.path.join(skills_dir, 'docx')
        pptx_dir = os.path.join(skills_dir, 'pptx')

        original_path = sys.path.copy()
        if skills_dir not in sys.path:
            sys.path.append(skills_dir)
        if docx_dir not in sys.path and os.path.exists(docx_dir):
            sys.path.append(docx_dir)
        if pptx_dir not in sys.path and os.path.exists(pptx_dir):
             sys.path.append(pptx_dir)

        try:
            with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
                exec(code, {'__name__': '__main__'})

            output = stdout_buffer.getvalue()
            error = stderr_buffer.getvalue()

            result = ""
            if output:
                result += f"Stdout:\n{output}\n"
            if error:
                result += f"Stderr:\n{error}\n"

            if not result:
                result = "Code executed successfully (no output)."

            return result

        except Exception:
            return f"Error executing code:\n{traceback.format_exc()}"
        finally:
            sys.path = original_path
