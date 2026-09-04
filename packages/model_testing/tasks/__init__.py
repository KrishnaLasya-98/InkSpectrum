from .extraction import ExtractionTask
from .script_gen import ScriptGenTask
from .code_review import CodeReviewTask


TASK_REGISTRY = {
    "extraction": ExtractionTask,
    "script_gen": ScriptGenTask,
    "code_review": CodeReviewTask,
}
