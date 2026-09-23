"""工具集统一出口。

agent.py 只 import ALL_TOOLS 一处，以后新增工具只改这一个文件。
"""

from backend.ai.tools.basic import calculator, get_current_time
from backend.ai.tools.knowledge import search_knowledge_base

ALL_TOOLS = [search_knowledge_base, calculator, get_current_time]
