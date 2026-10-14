"""
MOCK RAG service. Same contract as the real one, fake content.
The passages below are invented placeholders, NOT real literature and NOT clinical advice.
Swap this service for the real Chroma-backed one without changing the agent code.
"""
import re
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="RAG mock", version="0.1")


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=10)
    language: str | None = None  # "fr" | "en", ignored by the mock


class SearchResult(BaseModel):
    id: str
    title: str
    authors: str
    journal: str
    year: int
    doi: str | None
    url: str
    passage: str   # exact text the answer must be based on
    score: float   # 0..1, higher = more relevant


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    insufficient_evidence: bool  # true => the assistant must say "I don't know"


MOCK_DOCS = [
    {
        "id": "mock-001",
        "title": "[MOCK] Diagnosis of dental caries on radiographs",
        "authors": "Mock A, Mock B",
        "journal": "Mock Journal of Dentistry",
        "year": 2021,
        "doi": "10.0000/mock.001",
        "url": "https://example.org/mock/001",
        "passage": "Placeholder text: bitewing radiographs are commonly used to detect interproximal caries lesions, with sensitivity varying by lesion depth.",
        "keywords": {"caries", "cavity", "bitewing", "decay", "interproximal", "carie", "carieuse", "froid", "sensibilite", "sensibilité"},
    },
    {
        "id": "mock-002",
        "title": "[MOCK] Periapical lesions: imaging and management",
        "authors": "Mock C",
        "journal": "Mock Endodontic Review",
        "year": 2022,
        "doi": "10.0000/mock.002",
        "url": "https://example.org/mock/002",
        "passage": "Placeholder text: periapical radiolucency may indicate apical periodontitis and is assessed together with clinical symptoms and pulp testing.",
        "keywords": {"periapical", "lesion", "radiolucency", "abscess", "endodontic", "pulp", "pain", "toothache", "douleur", "abces", "abcès", "pulpe"},
    },
    {
        "id": "mock-003",
        "title": "[MOCK] Alveolar bone loss in periodontitis",
        "authors": "Mock D, Mock E",
        "journal": "Mock Periodontology Reports",
        "year": 2020,
        "doi": None,
        "url": "https://example.org/mock/003",
        "passage": "Placeholder text: horizontal bone loss on panoramic radiographs is used to stage periodontitis alongside probing depth and attachment loss.",
        "keywords": {"bone", "loss", "periodontitis", "periodontal", "gum", "panoramic", "bleeding", "parodontite", "gencive", "saignement", "os"},
    },
    {
        "id": "mock-004",
        "title": "[MOCK] Management of impacted third molars",
        "authors": "Mock F",
        "journal": "Mock Oral Surgery Journal",
        "year": 2023,
        "doi": "10.0000/mock.004",
        "url": "https://example.org/mock/004",
        "passage": "Placeholder text: impacted third molars are evaluated for position and proximity to the inferior alveolar nerve before surgical planning.",
        "keywords": {"impacted", "wisdom", "molar", "third", "extraction", "nerve", "surgery", "incluse", "sagesse", "molaire", "nerf"},
    },
]


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zà-ÿ]+", text.lower()))


@app.get("/health")
def health():
    return {"status": "ok", "mock": True}


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    q = tokenize(req.query)
    scored = []
    for doc in MOCK_DOCS:
        overlap = len(q & doc["keywords"])
        if overlap:
            scored.append((min(1.0, overlap / 3), doc))
    scored.sort(key=lambda x: x[0], reverse=True)

    results = [
        SearchResult(**{k: v for k, v in doc.items() if k != "keywords"}, score=round(score, 2))
        for score, doc in scored[: req.top_k]
    ]
    # no match => the agent must answer "not enough evidence", never invent
    return SearchResponse(query=req.query, results=results, insufficient_evidence=len(results) == 0)