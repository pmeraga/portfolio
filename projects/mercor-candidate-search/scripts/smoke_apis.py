"""Verify Voyage rerank, OpenAI model availability, and eval API (health + register)."""
import os
import json

import requests
from dotenv import load_dotenv

load_dotenv()

VOYAGE_KEY = os.environ["VOYAGE_API_KEY"]
OAI_KEY = os.environ["OAI_KEY"]
EVAL_EMAIL = os.environ["EVAL_EMAIL"]
EVAL_BASE = "https://mercor-dev--search-eng-interview.modal.run"


def test_voyage_rerank():
    import voyageai
    vo = voyageai.Client(api_key=VOYAGE_KEY)
    docs = [
        "Experienced tax attorney with a JD, handling IRS audits and corporate tax compliance.",
        "Mechanical engineer skilled in SolidWorks and ANSYS thermal simulation.",
        "Radiologist MD reading CT and MRI scans for 5 years.",
    ]
    for model in ["rerank-2.5", "rerank-2.5-lite", "rerank-2", "rerank-lite-1"]:
        try:
            r = vo.rerank("tax lawyer with JD and IRS audit experience", docs, model=model, top_k=3)
            print(f"  rerank model OK: {model} -> top idx {r.results[0].index} score {r.results[0].relevance_score:.4f}")
            return model
        except Exception as e:
            print(f"  rerank model FAILED: {model}: {type(e).__name__} {str(e)[:120]}")
    return None


def test_openai():
    from openai import OpenAI
    client = OpenAI(api_key=OAI_KEY)
    candidates = ["gpt-4.1-mini", "gpt-4o-mini", "gpt-5-mini", "gpt-5-nano", "gpt-4.1-nano", "gpt-4o"]
    for model in candidates:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Reply with exactly the word: ok"}],
                max_completion_tokens=5,
            )
            print(f"  OpenAI model OK: {model} -> {resp.choices[0].message.content!r}")
            return model
        except Exception as e:
            msg = str(e)[:140]
            print(f"  OpenAI model FAILED: {model}: {type(e).__name__} {msg}")
    return None


def test_eval_api():
    print("  GET / health:")
    try:
        r = requests.get(EVAL_BASE + "/", timeout=30)
        print("   ", r.status_code, r.text[:200])
    except Exception as e:
        print("    health error:", type(e).__name__, str(e)[:160])

    print("  POST /add_user (register email):")
    try:
        r = requests.post(
            EVAL_BASE + "/add_user",
            headers={"Authorization": EVAL_EMAIL, "Content-Type": "application/json"},
            json={"email": EVAL_EMAIL},
            timeout=30,
        )
        print("   ", r.status_code, r.text[:300])
    except Exception as e:
        print("    add_user error:", type(e).__name__, str(e)[:160])


if __name__ == "__main__":
    print("== Voyage rerank ==")
    rm = test_voyage_rerank()
    print("CHOSEN RERANK MODEL:", rm)
    print("\n== OpenAI ==")
    om = test_openai()
    print("CHOSEN OPENAI MODEL:", om)
    print("\n== Eval API ==")
    test_eval_api()
