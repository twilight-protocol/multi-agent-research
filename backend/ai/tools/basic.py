"""基础工具：计算器、当前时间。
"""
import ast
import operator
from datetime import datetime

from langchain_core.tools import tool

_BIN_OPS = {
    ast.Add: operator.add,        # +
    ast.Sub: operator.sub,        # -
    ast.Mult: operator.mul,       # *
    ast.Div: operator.truediv,    # /  （真除法，5/2=2.5）
    ast.FloorDiv: operator.floordiv,  # // （整除，5//2=2）
    ast.Mod: operator.mod,        # %  （取余）
    ast.Pow: operator.pow,        # ** （幂）
}
_UNARY_OPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}

# 幂运算加限制：2**99999999 会让进程卡死（DoS）
_MAX_POW_EXPONENT = 1000


def _eval(node: ast.AST) -> float:
    """只递归求值数字/四则运算/幂，其它语法一律拒绝。

    不用 eval()：模型或用户可能传出 __import__("os").system("...") 这类表达式，
    eval 会直接执行 → 白名单 AST 求值没有执行任意代码的能力。
    """
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("只支持数字")
        return node.value
    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise ValueError("不支持的运算符")
        if isinstance(node.op, ast.Pow):
            exp = _eval(node.right)
            if abs(exp) > _MAX_POW_EXPONENT:
                raise ValueError(f"幂指数过大（上限 {_MAX_POW_EXPONENT}）")
            return op(_eval(node.left), exp)
        return op(_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise ValueError("不支持的一元运算符")
        return op(_eval(node.operand))
    raise ValueError("表达式包含不支持的语法")


@tool
def calculator(expression: str) -> str:
    """计算纯数学表达式，支持 + - * / // % ** 与括号，例如 "12*8"、"(3+5)/2"。
    仅能做数字运算；无法处理单位换算、变量、函数调用或文字应用题。
    需要精确结果时优先调用本工具，不要自己心算。
    """
    try:
        result = _eval(ast.parse(expression, mode="eval"))
    except Exception as e:
        return f"计算失败：{e}"
    return str(int(result)) if isinstance(result, float) and result.is_integer() else str(result)


@tool
def get_current_time() -> str:
    """获取当前日期与时间（服务器本地时区）。
    当用户问「现在几点」「今天几号」「距今多少天」等需要当前时间的问题时必须调用，
    禁止凭记忆回答。
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
