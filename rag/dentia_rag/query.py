"""
QUERY HELPERS - three small steps around the search, to make the module safer and
better with French questions.

1. TRANSLATION  A French (or Arabic) question is translated into English, because the
                 documents are in English. We search with BOTH versions and keep the best
                 passages. A small dental glossary adds the right English words
                 ("dent de sagesse" -> "wisdom tooth third molar").
2. SCOPE GATE   When the best passage is only borderline (score under GATE_BELOW), the
                 language model is asked one thing: "could a dentist ask this?".
                 "How to repair a car engine?" or "best treatment for a broken leg?"
                 are stopped here instead of getting an answer from an unrelated passage.
                 Strong matches never go through the gate, so real questions are not blocked.
3. TRANSLATE BACK  The answer is written and CHECKED in English (the citation check works
                 on the passages' language), then translated to French. The citation
                 markers [1] [2] and the numbers must be identical after the translation,
                 otherwise we keep the English answer.

Every step can be turned off (see generate.py: --no-translate, --no-gate, --no-translate-back)
so that the effect of each one can be measured.
"""

import json
import os
import re
import unicodedata
import urllib.error
import urllib.request

GATE_BELOW = 0.62          # the gate is used only when the best passage scores under this value

# French -> English dental words (keys without accents, lower case)
GLOSSARY = {
    "dent de sagesse": "wisdom tooth third molar", "dents de sagesse": "wisdom teeth third molars",
    "dent de lait": "primary tooth deciduous tooth", "dents de lait": "primary teeth deciduous teeth",
    "dents temporaires": "primary teeth", "dent temporaire": "primary tooth",
    "carie": "caries", "caries": "caries", "carie profonde": "deep caries",
    "pulpite": "pulpitis", "pulpotomie": "pulpotomy", "pulpectomie": "pulpectomy",
    "vitalite pulpaire": "pulp vitality", "pulpe": "pulp", "necrose": "necrosis",
    "devitalisation": "root canal treatment endodontic", "traitement de canal": "root canal treatment",
    "traitement endodontique": "root canal treatment", "abces": "abscess",
    "extraction": "extraction", "avulsion": "extraction", "alveolite": "alveolar osteitis dry socket",
    "detartrage": "scaling", "surfacage": "root planing", "surfacage radiculaire": "scaling and root planing",
    "parodontite": "periodontitis", "gingivite": "gingivitis", "parodontal": "periodontal",
    "implant": "implant", "implants": "implants", "implants dentaires": "dental implants",
    "couronne": "crown", "obturation": "filling restoration", "plombage": "filling restoration",
    "amalgame": "amalgam", "composite": "composite resin", "ciment verre ionomere": "glass ionomer cement",
    "fluor": "fluoride", "vernis fluore": "fluoride varnish", "diamine d'argent": "silver diamine fluoride",
    "diamine argentique": "silver diamine fluoride", "scellement": "sealant", "scellements de sillons": "pit and fissure sealants",
    "sillons": "pit and fissure", "molaire": "molar", "molaires": "molars", "premolaire": "premolar",
    "antibiotique": "antibiotic", "antibiotiques": "antibiotics", "antibioprophylaxie": "antibiotic prophylaxis",
    "prophylaxie": "prophylaxis", "premiere intention": "first choice first line",
    "anesthesie": "anesthesia", "anticoagulant": "anticoagulant", "anticoagulants": "anticoagulants",
    "bisphosphonates": "bisphosphonates", "diabete": "diabetes", "diabetique": "diabetic",
    "grossesse": "pregnancy", "enfant": "child", "enfants": "children", "anxieux": "anxious",
    "anxiete": "anxiety", "douleur": "pain", "saignement": "bleeding", "infection": "infection",
    "orthodontie": "orthodontic", "bruxisme": "bruxism", "prothese": "denture prosthesis",
    "radiographie": "radiograph", "extraire": "extract", "arreter": "arrest", "recommande": "recommended",
}


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def glossary_terms(question: str) -> list[str]:
    """English words for the French dental words found in the question (longest match first)."""
    text = " " + re.sub(r"[^a-z0-9' ]+", " ", strip_accents(question.lower())) + " "
    found: list[str] = []
    for key in sorted(GLOSSARY, key=len, reverse=True):
        pattern = f" {key} "
        if pattern in text:
            text = text.replace(pattern, "  ")               # a longer match hides the shorter ones
            if GLOSSARY[key] not in found:
                found.append(GLOSSARY[key])
    return found


def ask_model(system: str, user: str, model: str, url: str, max_tokens: int = 200,
              timeout: int = 300) -> str:
    """One short, non-streaming call to Ollama. Returns "" if anything goes wrong."""
    body = {"model": model, "stream": False, "keep_alive": "10m",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": 0, "num_predict": max_tokens}}
    if "qwen3" in model.lower():
        body["think"] = False
        body["messages"][1]["content"] += "\n\n/no_think"
    request = urllib.request.Request(url.rstrip("/") + "/api/chat", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = json.loads(response.read().decode("utf-8")).get("message", {}).get("content", "")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return ""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def translate_question(question: str, model: str, url: str) -> str:
    system = ("You translate questions from dentists from French or Arabic into English. "
              "Reply with the English translation ONLY, on one line, nothing else. "
              "Use standard dental terms: wisdom tooth = third molar, dent de lait = primary tooth, "
              "carie = caries, devitalisation = root canal treatment.")
    text = ask_model(system, question, model, url, max_tokens=80)
    text = text.splitlines()[0].strip().strip('"').strip() if text else ""
    return text if 3 <= len(text) <= 300 else ""


def expand_queries(question: str, language: str, model: str | None = None,
                   url: str | None = None) -> list[str]:
    """Extra search queries for a question that is not in English (empty list for English)."""
    if language == "English":
        return []
    model = model or os.environ.get("LLM_MODEL", "qwen2.5:3b")
    url = url or os.environ.get("OLLAMA_URL", "http://localhost:11434")
    english = translate_question(question, model, url)
    terms = [t for t in glossary_terms(question) if t.lower() not in english.lower()]
    query = " ".join(part for part in [english] + terms if part).strip()
    return [query] if query else []


# Words that make a question clearly dental. No model call is needed for these.
DENTAL_WORDS = re.compile(
    r"\b(?:tooth|teeth|dent\w*|oral|mouth|gum|gums|gingiv\w*|periodon\w*|carie\w*|caries|molar\w*|"
    r"pulp\w*|endodon\w*|root canal|canal radiculaire|orthodon\w*|braces|implant\w*|extraction\w*|"
    r"scaling|sealant\w*|fluorid\w*|fluor|bitewing|periapical|jaw|mandib\w*|maxill\w*|bouche|gencive\w*|"
    r"machoire|saliv\w*|stomat\w*|tartar|bruxis\w*|malocclusion|amalgam\w*)\b")


def in_scope(question: str, extra_queries: list[str], model: str, url: str) -> bool:
    """Could a dentist or dental student ask this question at work? (True if unsure or on error).
    1. A dental word in the question (or in its English version) -> yes, no model call.
    2. Otherwise the model decides, and it is told to say NO only for a clearly unrelated question."""
    text = strip_accents(" ".join([question] + list(extra_queries)).lower())
    if DENTAL_WORDS.search(text):
        return True
    system = ("You are a filter for a decision-support tool used by dentists. "
              "Reply with exactly one word: YES or NO. "
              "Reply YES if the question could be part of a dentist's work, including medical questions about "
              "dental patients (drugs, doses, allergies, anticoagulants, heart conditions, pregnancy, children, "
              "emergencies in the dental office). "
              "Reply NO only if the question has nothing to do with dentistry or with the care of dental patients "
              "(for example cooking, cars, sports, geography, finance, shopping, or injuries of other body parts).")
    user = "Question: " + question
    if extra_queries:
        user += f"\n(English: {extra_queries[0]})"
    answer = ask_model(system, user, model, url, max_tokens=5, timeout=120).upper()
    return not answer.startswith("NO")


MARKER = re.compile(r"\[\d+\]|\[\?\]")


def translate_answer(answer: str, language: str, model: str, url: str) -> str | None:
    """Translate a checked English answer. None if the citation markers or numbers changed."""
    system = (f"You translate dental text from English to {language}. Keep every marker like [1], [2] or [?] "
              "exactly where it is, and keep every number and unit exactly. Keep medical terms accurate. "
              "Reply with the translation ONLY.")
    text = ask_model(system, answer, model, url, max_tokens=700, timeout=600)
    if not text:
        return None
    numbers = lambda s: sorted(re.findall(r"\d+(?:[.,]\d+)?", MARKER.sub("", s)))
    if sorted(MARKER.findall(text)) != sorted(MARKER.findall(answer)) or numbers(text) != numbers(answer):
        return None
    return text


def main() -> None:
    """Test the scope gate alone: it must PASS dental questions and BLOCK the others.
        python -m dentia_rag.query --test-gate
    A gate that blocks a real clinical question is worse than no gate, so look at the first list."""
    import argparse
    import sys
    from dentia_rag.embed import load_env
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_env()
    parser = argparse.ArgumentParser(description="Test the scope gate")
    parser.add_argument("--test-gate", action="store_true")
    parser.add_argument("--cases", default="eval/gate_cases.jsonl")
    parser.add_argument("--model")
    args = parser.parse_args()
    if not args.test_gate:
        parser.print_help()
        return
    model = args.model or os.environ.get("LLM_MODEL", "qwen2.5:3b")
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    wrong_blocks, wrong_passes, total = [], [], 0
    for line in open(args.cases, encoding="utf-8"):
        if not line.strip():
            continue
        case = json.loads(line)
        total += 1
        answer = in_scope(case["question"], [], model, url)
        ok = answer == case["in_scope"]
        print(f"{'ok   ' if ok else 'WRONG'} gate={'pass ' if answer else 'block'}  {case['question']}")
        if not ok:
            (wrong_passes if answer else wrong_blocks).append(case["question"])
    print(f"\n{total - len(wrong_blocks) - len(wrong_passes)}/{total} correct")
    print(f"Real dental questions BLOCKED (dangerous): {len(wrong_blocks)}")
    print(f"Off-topic questions that PASSED (the retrieval score and the model still protect): {len(wrong_passes)}")


if __name__ == "__main__":
    main()
