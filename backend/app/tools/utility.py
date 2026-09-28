import ast
import math
import operator
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field

from app.tools.base import Tool, ToolContext, ToolError, ToolInput

# ---- calculator ----------------------------------------------------------

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {
    name: getattr(math, name)
    for name in (
        "sqrt", "log", "log10", "log2", "exp", "sin", "cos", "tan", "asin", "acos", "atan",
        "floor", "ceil", "factorial", "degrees", "radians", "gcd",
    )
} | {"abs": abs, "round": round, "min": min, "max": max}
_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ToolError("Exponent too large")
        return _BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONSTS:
        return _CONSTS[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    raise ToolError(f"Unsupported expression element: {ast.dump(node)[:80]}")


class CalculatorInput(ToolInput):
    expression: str = Field(description="Arithmetic expression, e.g. '(2 + 3) * sqrt(16) / pi'")


def calculator(args: CalculatorInput, ctx: ToolContext) -> str:
    try:
        tree = ast.parse(args.expression, mode="eval")
    except SyntaxError as e:
        raise ToolError(f"Syntax error: {e.msg}")
    try:
        return repr(_eval(tree))
    except ZeroDivisionError:
        raise ToolError("Division by zero")


# ---- clock ---------------------------------------------------------------


class TimeInput(ToolInput):
    timezone: str = Field(default="UTC", description="IANA timezone name, e.g. 'Asia/Kolkata'")


def get_current_time(args: TimeInput, ctx: ToolContext) -> str:
    try:
        tz = ZoneInfo(args.timezone)
    except ZoneInfoNotFoundError:
        raise ToolError(f"Unknown timezone: {args.timezone}")
    now = datetime.now(tz)
    return f"{now.isoformat(timespec='seconds')} ({now.strftime('%A')}, {args.timezone})"


TOOLS = [
    Tool(
        name="calculator",
        description="Evaluate an arithmetic expression exactly. Use this instead of doing "
        "non-trivial math in your head. Supports + - * / // % **, parentheses, "
        "pi, e, and math functions like sqrt, log, sin, factorial, round.",
        input_model=CalculatorInput,
        handler=calculator,
    ),
    Tool(
        name="get_current_time",
        description="Get the current date and time in a given timezone. Use whenever the "
        "answer depends on today's date or the current time.",
        input_model=TimeInput,
        handler=get_current_time,
    ),
]
