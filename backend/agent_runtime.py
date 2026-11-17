"""
Tiny agent runtime. A run is a loop:
  the code decides which actions are POSSIBLE this step (policy) and the model CHOOSES among them
  (its answer is constrained to a JSON schema built from that policy)
  -> the code validates the arguments and executes the tool
  -> the observation goes back to the model, until it calls finish or the step limit is hit.
Hard limits live in code, not in the prompt: a small model cannot be trusted to budget or to avoid loops.
"""
import json
import logging
import time
from dataclasses import dataclass
from typing import Callable

from llm import call_json

log = logging.getLogger("uvicorn.error")

ARG_TYPES = {"string": {"type": "string"}, "integer": {"type": "integer"}}


@dataclass
class Tool:
    name: str
    description: str
    args: dict            # {"query": "string", "days": "integer"}
    fn: Callable          # fn(ctx, **args) -> dict (the observation)
    optional: tuple = ()  # argument names the model may omit (the tool has a default)


def _schema(tools, enums, can_finish):
    names = [t.name for t in tools] + (["finish"] if can_finish else [])
    props = {"thought": {"type": "string"}, "action": {"type": "string", "enum": names}}
    if can_finish:
        props["summary"] = {"type": "string"}
    for t in tools:
        for k, typ in t.args.items():
            props[k] = {**ARG_TYPES[typ], **({"enum": enums[k]} if k in enums else {})}
    return {"type": "object", "properties": props, "required": ["thought", "action"]}


def _tool_list(tools, enums, can_finish):
    lines = []
    for t in tools:
        parts = []
        for k, typ in t.args.items():
            label = f"one of {enums[k]}" if k in enums else typ
            parts.append(f"{k}{'?' if k in t.optional else ''}: {label}")
        lines.append(f"- {t.name}({', '.join(parts)}): {t.description}")
    if can_finish:
        lines.append("- finish(summary: string): stop. Give a short French summary of what you did and found.")
    return "\n".join(lines)


def _clip(obs, limit=1500):
    text = json.dumps(obs, ensure_ascii=False, default=str)
    return obs if len(text) <= limit else {"truncated": text[:limit]}


def run_agent(*, system, goal, tools, ctx, max_steps=12, on_step=None, state_fn=None, policy_fn=None):
    """policy_fn(ctx) -> (allowed action names, {arg name: allowed values}); without it, everything is allowed."""
    by_name = {t.name: t for t in tools}
    steps, history, done_before = [], [], set()
    errors_in_a_row = 0
    status, summary = "stopped", ""

    def push(step):
        steps.append(step)
        if on_step:
            try:
                on_step(steps)
            except Exception:
                log.warning("agent: could not save step", exc_info=True)

    for n in range(1, max_steps + 1):
        if policy_fn:
            allowed, enums = policy_fn(ctx)
        else:
            allowed, enums = [t.name for t in tools] + ["finish"], {}
        step_tools = [t for t in tools if t.name in allowed]
        can_finish = "finish" in allowed
        schema = _schema(step_tools, enums, can_finish)

        recent = "\n".join(history[-6:]) or "(nothing yet)"
        state = state_fn(ctx) if state_fn else ""
        user = (f"<goal>\n{goal}\n</goal>\n<tools>\n{_tool_list(step_tools, enums, can_finish)}\n</tools>\n"
                + (f"<state>\n{state}\n</state>\n" if state else "")
                + f"<history>\n{recent}\n</history>\n"
                f"Steps left: {max_steps - n + 1}. Choose the next action.")
        t0 = time.time()
        try:
            d = call_json(system, user, schema)
        except Exception as e:
            push({"n": n, "action": "error", "observation": {"error": f"model: {str(e)[:200]}"}})
            status, summary = "failed", "Le modèle n'a pas répondu correctement."
            break

        action = d.get("action")
        step = {"n": n, "action": action, "thought": str(d.get("thought") or "")[:300]}
        if action == "finish" and can_finish:
            summary = str(d.get("summary") or "").strip()[:600]
            step["observation"] = "fin de la veille"
            push(step)
            status = "completed"
            break

        args, obs = {}, None
        tool = next((t for t in step_tools if t.name == action), None)
        if tool is None:
            obs = {"error": f"action '{action}' is not available"}
        else:
            for k, typ in tool.args.items():
                v = d.get(k)
                if v is None or v == "":
                    if k in tool.optional:
                        continue
                    obs = {"error": f"missing argument '{k}'"}
                    break
                good = isinstance(v, str) if typ == "string" else (isinstance(v, int) and not isinstance(v, bool))
                if not good:
                    obs = {"error": f"invalid argument '{k}'"}
                    break
                if k in enums and v not in enums[k]:
                    obs = {"error": f"'{k}' must be one of {enums[k]}"}
                    break
                args[k] = v.strip() if typ == "string" else v
        if obs is None:
            key = json.dumps([action, args], sort_keys=True)
            if key in done_before:
                obs = {"error": "identical action already done: choose another or finish"}
            else:
                done_before.add(key)
                try:
                    obs = tool.fn(ctx, **args)
                except Exception as e:
                    obs = {"error": str(e)[:200]}

        step.update(args=args, observation=_clip(obs), ms=int((time.time() - t0) * 1000))
        push(step)
        history.append(f"step {n}: {action} {json.dumps(args, ensure_ascii=False)} -> "
                       f"{json.dumps(obs, ensure_ascii=False, default=str)[:800]}")
        errors_in_a_row = errors_in_a_row + 1 if isinstance(obs, dict) and "error" in obs else 0
        if errors_in_a_row >= 3:
            status, summary = "failed", "Trop d'erreurs consécutives."
            break

    if status == "stopped" and not summary:
        summary = f"Limite de {max_steps} pas atteinte."
    return {"status": status, "summary": summary, "steps": steps}