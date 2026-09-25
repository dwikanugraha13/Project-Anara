import asyncio
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Registered callbacks for live Agent HUD broadcasting
_AGENT_EVENT_LISTENERS: List[Callable[[Dict[str, Any]], Any]] = []

# Pending question futures: question_id -> asyncio.Future
_PENDING_QUESTION_FUTURES: Dict[str, asyncio.Future] = {}


def register_agent_event_listener(listener: Callable[[Dict[str, Any]], Any]):
    if listener not in _AGENT_EVENT_LISTENERS:
        _AGENT_EVENT_LISTENERS.append(listener)


def _emit_agent_event(event_type: str, data: Dict[str, Any]):
    for listener in _AGENT_EVENT_LISTENERS:
        try:
            res = listener({"type": event_type, **data})
            if asyncio.iscoroutine(res):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(res)
                except RuntimeError:
                    pass
        except Exception as e:
            logger.debug(f"[AgentTools] Listener callback error: {e}")


async def request_interactive_question(questions: List[Dict[str, Any]], timeout: float = 300.0) -> Dict[str, Any]:
    """
    Broadcasts an interactive question wizard card to the user and awaits their choices.
    """
    question_id = f"q_{uuid.uuid4().hex[:8]}"
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    _PENDING_QUESTION_FUTURES[question_id] = fut

    _emit_agent_event("interactive_question", {
        "question_id": question_id,
        "questions": questions
    })

    try:
        user_res = await asyncio.wait_for(fut, timeout=timeout)
        is_dismissed = False
        user_answers = user_res

        if isinstance(user_res, dict):
            is_dismissed = bool(user_res.get("dismissed", False))
            user_answers = user_res.get("answers", [])

        # Check if all answers are empty or no answer marker
        if isinstance(user_answers, list) and user_answers:
            all_empty = all(
                (a.get("answer") if isinstance(a, dict) else str(a)).strip() in ("(no answer)", "")
                for a in user_answers
            )
            if all_empty:
                is_dismissed = True

        if is_dismissed:
            return {
                "status": "dismissed",
                "dismissed": True,
                "question_id": question_id,
                "message": "Questionnaire dismissed by user.",
                "answers": user_answers
            }

        return {
            "status": "success",
            "dismissed": False,
            "question_id": question_id,
            "message": "User completed the questionnaire.",
            "answers": user_answers
        }
    except asyncio.TimeoutError:
        logger.info(f"[InteractiveQuestion] Question {question_id} timed out after {timeout}s.")
        fallback_answers = [
            {"header": q.get("header", ""), "question": q.get("question", ""), "answer": "(no answer)"}
            for q in questions
        ]
        return {
            "status": "dismissed",
            "dismissed": True,
            "question_id": question_id,
            "message": "Questionnaire timed out without selections.",
            "answers": fallback_answers
        }
    finally:
        _PENDING_QUESTION_FUTURES.pop(question_id, None)


def resolve_question_response(question_id: str, answers: Any, dismissed: bool = False) -> bool:
    """Resolves a pending question future when client sends question_response."""
    fut = _PENDING_QUESTION_FUTURES.get(question_id)
    if fut and not fut.done():
        fut.set_result({"answers": answers, "dismissed": dismissed})
        return True
    return False

