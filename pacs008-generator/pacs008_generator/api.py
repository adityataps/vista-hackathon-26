"""FastAPI wrapper + Demo-UI.

Start:  uvicorn pacs008_generator.api:app --port 8080
UI:     http://localhost:8080/        (Demo-Oberflaeche)
Docs:   http://localhost:8080/docs
"""
import os
import re
import subprocess
import sys
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .errors import load_catalog
from .generator import generate_batch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_FILE = os.path.join(BASE_DIR, "ui", "index.html")
RUNS_DIR = os.path.join(BASE_DIR, "output", "ui-runs")

app = FastAPI(title="pacs.008 CBPR+ Generator",
              description="Generiert XSD-valide pacs.008 Meldungen mit "
                          "konfigurierbaren Business-Fehlern (Use Case A).",
              version="0.2.0")


class GenerateRequest(BaseModel):
    count: int = Field(10, ge=1, le=500)
    error_rate: float = Field(0.3, ge=0.0, le=1.0)
    faulty: Optional[int] = Field(None, ge=0, description="absolute Anzahl, ueberschreibt error_rate")
    seed: Optional[int] = None
    error_codes: Optional[List[str]] = None
    include_xml: bool = True
    write_files: bool = True


@app.get("/")
def ui():
    return FileResponse(UI_FILE)


@app.get("/errors")
def list_errors():
    """Fehlerkatalog fuer die UI (Checkbox-Liste)."""
    return load_catalog()


@app.post("/generate")
def generate(req: GenerateRequest):
    """Erzeugt einen Batch, schreibt ihn in output/ui-runs/<run_id>/ und
    liefert Meldungen + Ground-Truth-Manifest."""
    import json
    try:
        manifest = generate_batch(
            count=req.count, error_rate=req.error_rate, faulty=req.faulty,
            seed=req.seed, error_codes=req.error_codes, write_files=False)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    manifest["output_dir"] = None
    if req.write_files:
        out_dir = os.path.join(RUNS_DIR, manifest["run_id"])
        os.makedirs(out_dir, exist_ok=True)
        for m in manifest["messages"]:
            with open(os.path.join(out_dir, m["file"]), "w", encoding="utf-8") as f:
                f.write(m["xml"])
        slim = json.loads(json.dumps(manifest))
        for m in slim["messages"]:
            m.pop("xml", None)
        with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(slim, f, indent=2, ensure_ascii=False)
        manifest["output_dir"] = out_dir
    if not req.include_xml:
        for m in manifest["messages"]:
            m.pop("xml", None)
    return manifest


@app.post("/runs/{run_id}/open")
def open_run_folder(run_id: str):
    """Oeffnet den Output-Ordner des Laufs im Finder/Explorer (lokale Demo)."""
    if not re.match(r"^[A-Za-z0-9]+$", run_id):
        raise HTTPException(status_code=400, detail="ungueltige run_id")
    path = os.path.join(RUNS_DIR, run_id)
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Lauf nicht gefunden")
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, path])
    return {"opened": path}


@app.get("/health")
def health():
    return {"status": "ok"}
