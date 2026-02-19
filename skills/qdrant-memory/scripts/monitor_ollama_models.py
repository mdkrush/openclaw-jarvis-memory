#!/usr/bin/env python3
"""
Monitor Ollama model library for 100B+ parameter models
Only outputs/announces when there are significant new large models.
Always exits with code 0 to prevent "exec failed" logs.
Usage: monitor_ollama_models.py [--json]
"""

import argparse
import sys
import json
import urllib.request
import re
import hashlib
from datetime import datetime

QDRANT_URL = "http://10.0.0.40:6333"
KB_COLLECTION = "knowledge_base"
OLLAMA_LIBRARY_URL = "https://ollama.com/library"

LARGE_MODEL_TAGS = ["100b", "120b", "200b", "400b", "70b", "8x7b", "8x22b"]
GOOD_FOR_OPENCLAW = ["code", "coding", "instruct", "chat", "reasoning", "llama", "qwen", "mistral", "deepseek", "gemma", "mixtral"]

def fetch_library():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    req = urllib.request.Request(OLLAMA_LIBRARY_URL, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.read().decode('utf-8', errors='ignore')
    except:
        return None

def extract_models(html):
    models = []
    model_blocks = re.findall(r'<a[^>]*href="/library/([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
    
    for model_name, block in model_blocks[:50]:
        model_info = {
            "name": model_name, "url": f"https://ollama.com/library/{model_name}",
            "is_large": False, "is_new": False, "tags": [], "description": ""
        }
        
        tag_matches = re.findall(r'<span[^>]*>([^<]+(?:b|B))</span>', block)
        model_info["tags"] = [t.lower() for t in tag_matches]
        
        for tag in model_info["tags"]:
            if any(large_tag in tag for large_tag in LARGE_MODEL_TAGS):
                if "70b" in tag and not ("8x" in model_name.lower() or "mixtral" in model_name.lower()):
                    continue
                model_info["is_large"] = True
                break
        
        desc_match = re.search(r'<p[^>]*>([^<]+)</p>', block)
        if desc_match:
            model_info["description"] = desc_match.group(1).strip()
        
        updated_match = re.search(r'(\d+)\s+(hours?|days?)\s+ago', block, re.IGNORECASE)
        if updated_match:
            num = int(updated_match.group(1))
            unit = updated_match.group(2).lower()
            if (unit.startswith("hour") and num <= 24) or (unit.startswith("day") and num <= 2):
                model_info["is_new"] = True
        
        desc_lower = model_info["description"].lower()
        name_lower = model_name.lower()
        model_info["good_for_openclaw"] = any(kw in desc_lower or kw in name_lower for kw in GOOD_FOR_OPENCLAW)
        
        models.append(model_info)
    return models

def get_embedding(text):
    data = {"model": "nomic-embed-text", "input": text[:500]}
    req = urllib.request.Request("http://localhost:11434/api/embed",
                                  data=json.dumps(data).encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            return result.get("embeddings", [None])[0]
    except:
        return None

def search_kb_for_model(model_name):
    url = f"{QDRANT_URL}/collections/{KB_COLLECTION}/points/scroll"
    data = {"limit": 100, "with_payload": True, "filter": {"must": [
        {"key": "domain", "match": {"value": "AI/LLM"}},
        {"key": "path", "match": {"text": model_name}}
    ]}}
    req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            return result.get("result", {}).get("points", [])
    except:
        return []

def store_model(model_info):
    import uuid
    text = f"{model_info['name']}: {model_info['description']}\nTags: {', '.join(model_info['tags'])}"
    embedding = get_embedding(text)
    if not embedding:
        return False
    
    metadata = {
        "domain": "AI/LLM", "path": f"AI/LLM/Ollama/Models/{model_info['name']}",
        "subjects": ["ollama", "models", "llm", "100b+"] + model_info['tags'],
        "category": "reference", "content_type": "web_page",
        "title": f"Ollama Model: {model_info['name']}", "source_url": model_info['url'],
        "date_added": datetime.now().strftime("%Y-%m-%d"), "date_scraped": datetime.now().isoformat(),
        "model_tags": model_info['tags'], "is_large": model_info['is_large'], "is_new": model_info['is_new'],
        "text_preview": text[:300]
    }
    
    point = {"id": str(uuid.uuid4()), "vector": embedding, "payload": metadata}
    url = f"{QDRANT_URL}/collections/{KB_COLLECTION}/points"
    req = urllib.request.Request(url, data=json.dumps({"points": [point]}).encode(),
                                  headers={"Content-Type": "application/json"}, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            return result.get("status") == "ok"
    except:
        return False

def evaluate_candidate(model_info):
    score = 0
    reasons = []
    
    if not model_info["is_large"]:
        return {"is_candidate": False, "score": 0, "reasons": []}
    
    score += 5
    reasons.append("🦣 100B+ parameters")
    
    if model_info.get("good_for_openclaw"):
        score += 2
        reasons.append("✨ Good for OpenClaw")
    
    if model_info["is_new"]:
        score += 2
        reasons.append("🆕 Recently updated")
    
    return {"is_candidate": score >= 5, "score": score, "reasons": reasons}

def format_notification(candidates):
    lines = ["🤖 New Large Model Alert (100B+)", f"📅 {datetime.now().strftime('%Y-%m-%d')}", ""]
    lines.append(f"📊 {len(candidates)} new large model(s) found:")
    lines.append("")
    
    for model in candidates[:5]:
        eval_info = model["evaluation"]
        lines.append(f"• {model['name']}")
        lines.append(f"  {model['description'][:60]}...")
        lines.append(f"  Tags: {', '.join(model['tags'][:3])}")
        for reason in eval_info["reasons"]:
            lines.append(f"  {reason}")
        lines.append(f"  🔗 {model['url']}")
        lines.append("")
    
    lines.append("💡 Potential gpt-oss:120b replacement")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    
    html = fetch_library()
    if not html:
        if args.json:
            print("{}")
        sys.exit(0)  # Silent fail with exit 0
    
    models = extract_models(html)
    large_models = [m for m in models if m["is_large"]]
    
    candidates = []
    
    for model in large_models:
        existing = search_kb_for_model(model["name"])
        is_new_to_kb = len(existing) == 0
        
        evaluation = evaluate_candidate(model)
        model["evaluation"] = evaluation
        
        if is_new_to_kb:
            store_model(model)
        
        if evaluation["is_candidate"] and is_new_to_kb:
            candidates.append(model)
    
    # Output results
    if args.json:
        if candidates:
            print(json.dumps({"candidates": candidates, "notification": format_notification(candidates)}))
        else:
            print("{}")
    elif candidates:
        print(format_notification(candidates))
    # No output if no candidates (silent)
    
    # Always exit 0 to prevent "exec failed" logs
    sys.exit(0)

if __name__ == "__main__":
    main()
