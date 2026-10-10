"""Phase 3 workflow: draft a risk sheet, then stop and wait for a human to decide.

Run:  .venv\\Scripts\\python workflow.py "Fairfax County"

Built with LangGraph. The graph has three steps:

    gather evidence  ->  draft the sheet  ->  human review

The review step pauses the graph. Nothing is marked approved until a person answers.
"""
import sys
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from common import find_localities
from risk import check_quotes, draft_sheet, gather_evidence, record_decision, save_sheet, sources


class State(TypedDict, total=False):
    """What the graph remembers as it moves from step to step."""
    ein: str
    evidence: dict
    sheet: dict
    quote_problems: list
    sheet_id: int
    decision: dict


def gather(state: State):
    return {"evidence": gather_evidence(state["ein"])}


def draft(state: State):
    """Draft the sheet, check its quotes, and store it with status 'draft'."""
    sheet, usage = draft_sheet(state["evidence"])
    problems = check_quotes(sheet, state["evidence"])
    sheet_id = save_sheet(state["evidence"], sheet, usage, problems)
    # The sheet travels through the graph as a plain dictionary.
    return {"sheet": sheet.model_dump(), "quote_problems": problems, "sheet_id": sheet_id}


def human_review(state: State):
    """Pause here. interrupt() hands the draft to a person and returns whatever they answer.

    When the graph is resumed this step runs again from its first line, which is why the
    expensive drafting lives in its own step above and only the decision is recorded here.
    """
    decision = interrupt({"sheet": state["sheet"], "quote_problems": state["quote_problems"]})
    record_decision(state["sheet_id"], decision["status"], decision["final_rating"],
                    decision["reviewer"], decision["note"])
    return {"decision": decision}


def build_graph():
    graph = StateGraph(State)
    graph.add_node("gather", gather)
    graph.add_node("draft", draft)
    graph.add_node("human_review", human_review)
    graph.add_edge(START, "gather")
    graph.add_edge("gather", "draft")
    graph.add_edge("draft", "human_review")
    graph.add_edge("human_review", END)
    # The checkpointer is what lets the graph stop and pick up again. This one keeps its notes in
    # memory; a Postgres checkpointer would let a review wait for days and survive a restart.
    return graph.compile(checkpointer=InMemorySaver())


# ---------- The reviewer's side: a small command-line screen ----------

def find_locality(text):
    matches = find_localities(text)
    if len(matches) == 1:
        return matches[0]["auditee_ein"]
    if not matches:
        sys.exit(f"No locality matches '{text}'.")
    sys.exit("More than one locality matches. Be more specific:\n  " + "\n  ".join(m["auditee_name"] for m in matches[:25]))


def show(state):
    sheet = state["sheet"]
    print(f"\n=== DRAFT RISK SHEET: {state['evidence']['name']} ===")
    print(f"Rating: {sheet['rating'].replace('_', ' ').upper()}")
    print(f"\n{sheet['summary']}")
    for number, reason in enumerate(sheet["reasons"], 1):
        print(f"\n{number}. {reason['reason']}")
        print(f"   \"{reason['quote']}\"")
        print(f"   Finding {reason['reference_number']}, audit year {reason['audit_year']}")
    print("\nCheck next:")
    for check in sheet["next_checks"]:
        print(f"  - {check}")
    print("\nSource audits:")
    for source in sources(state["evidence"]):
        print(f"  {source['audit_year']}: {source['url']}")
    for problem in state["quote_problems"]:
        print(f"\n!! QUOTE CHECK FAILED ({problem['problem']}): \"{problem['quote']}\"")


def ask_reviewer(draft_rating):
    print("\nNothing is final until you decide.")
    choice = ""
    while choice not in ("a", "c", "r"):
        choice = input("[a]pprove as drafted, [c]hange the rating and approve, or [r]eject? ").strip().lower()
    final_rating = draft_rating
    if choice == "c":
        while final_rating == draft_rating or final_rating not in ("low", "medium", "high", "no_basis"):
            final_rating = input("Your rating (low, medium, high, no_basis): ").strip().lower()
    return {
        "status": "rejected" if choice == "r" else "approved",
        "final_rating": None if choice == "r" else final_rating,
        "reviewer": input("Your name: ").strip(),
        "note": input("Note (why, or what you changed): ").strip(),
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    graph = build_graph()
    run = {"configurable": {"thread_id": "review-1"}}  # the name of this one paused conversation

    graph.invoke({"ein": find_locality(sys.argv[1])}, run)  # runs until human_review pauses it
    paused = graph.get_state(run).values
    show(paused)

    decision = ask_reviewer(paused["sheet"]["rating"])
    graph.invoke(Command(resume=decision), run)  # picks up inside human_review with the answer
    print(f"\nRecorded: {decision['status']}" + (f" as {decision['final_rating']}" if decision["final_rating"] else "")
          + f" by {decision['reviewer']}. Sheet id {paused['sheet_id']}.")
