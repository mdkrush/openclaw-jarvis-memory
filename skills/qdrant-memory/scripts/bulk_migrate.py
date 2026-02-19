#!/usr/bin/env python3
"""
Bulk memory migration to Qdrant kimi_memories collection
Uses snowflake-arctic-embed2 (1024 dimensions)
"""

import json
import os
import re
import sys
import urllib.request
import uuid
from datetime import datetime

QDRANT_URL = "http://10.0.0.40:6333"
COLLECTION_NAME = "kimi_memories"
OLLAMA_URL = "http://localhost:11434/v1"

MEMORY_DIR = "/root/.openclaw/workspace/memory"
MEMORY_MD = "/root/.openclaw/workspace/MEMORY.md"

def get_embedding(text):
    """Generate embedding using snowflake-arctic-embed2 via Ollama"""
    data = json.dumps({
        "model": "snowflake-arctic-embed2",
        "input": text[:8192]  # Limit text length
    }).encode()
    
    req = urllib.request.Request(
        f"{OLLAMA_URL}/embeddings",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode())
            return result["data"][0]["embedding"]
    except Exception as e:
        print(f"Error generating embedding: {e}", file=sys.stderr)
        return None

def store_memory(text, embedding, tags=None, importance="medium", date=None, 
                 source="memory_backup", confidence="high", source_type="user",
                 verified=True):
    """Store memory in Qdrant with metadata"""
    
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    point_id = str(uuid.uuid4())
    
    payload = {
        "text": text,
        "date": date,
        "tags": tags or [],
        "importance": importance,
        "confidence": confidence,
        "source_type": source_type,
        "verified": verified,
        "source": source,
        "created_at": datetime.now().isoformat(),
        "access_count": 0
    }
    
    point = {
        "id": point_id,
        "vector": embedding,
        "payload": payload
    }
    
    data = json.dumps({"points": [point]}).encode()
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points?wait=true",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            return result.get("result", {}).get("status") == "ok"
    except Exception as e:
        print(f"Error storing memory: {e}", file=sys.stderr)
        return False

def extract_memories_from_file(filepath, importance="medium"):
    """Extract memory entries from a markdown file"""
    memories = []
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        return memories
    
    # Extract date from filename or content
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', filepath)
    date = date_match.group(1) if date_match else datetime.now().strftime("%Y-%m-%d")
    
    # Parse sections
    lines = content.split('\n')
    current_section = None
    current_content = []
    
    for line in lines:
        # Section headers
        if line.startswith('# ') and 'Memory' in line:
            continue  # Skip title
        elif line.startswith('## '):
            # Save previous section
            if current_section and current_content:
                section_text = '\n'.join(current_content).strip()
                if len(section_text) > 20:
                    memories.append({
                        "text": f"{current_section}: {section_text}",
                        "date": date,
                        "tags": extract_tags(current_section, section_text),
                        "importance": importance
                    })
            current_section = line[3:].strip()
            current_content = []
        elif line.startswith('### '):
            # Save previous section
            if current_section and current_content:
                section_text = '\n'.join(current_content).strip()
                if len(section_text) > 20:
                    memories.append({
                        "text": f"{current_section}: {section_text}",
                        "date": date,
                        "tags": extract_tags(current_section, section_text),
                        "importance": importance
                    })
            current_section = line[4:].strip()
            current_content = []
        else:
            if current_section:
                current_content.append(line)
    
    # Save final section
    if current_section and current_content:
        section_text = '\n'.join(current_content).strip()
        if len(section_text) > 20:
            memories.append({
                "text": f"{current_section}: {section_text}",
                "date": date,
                "tags": extract_tags(current_section, section_text),
                "importance": importance
            })
    
    return memories

def extract_tags(section, content):
    """Extract relevant tags from section and content"""
    tags = []
    
    # Section-based tags
    if any(word in section.lower() for word in ['voice', 'tts', 'stt', 'audio']):
        tags.extend(['voice', 'audio'])
    if any(word in section.lower() for word in ['memory', 'qdrant', 'remember']):
        tags.extend(['memory', 'qdrant'])
    if any(word in section.lower() for word in ['redis', 'agent', 'message', 'max']):
        tags.extend(['redis', 'messaging', 'agent'])
    if any(word in section.lower() for word in ['youtube', 'seo', 'content']):
        tags.extend(['youtube', 'content'])
    if any(word in section.lower() for word in ['search', 'searxng', 'web']):
        tags.extend(['search', 'web'])
    if any(word in section.lower() for word in ['setup', 'install', 'bootstrap']):
        tags.extend(['setup', 'configuration'])
    
    # Content-based tags
    content_lower = content.lower()
    if 'voice' in content_lower:
        tags.append('voice')
    if 'memory' in content_lower:
        tags.append('memory')
    if 'qdrant' in content_lower:
        tags.append('qdrant')
    if 'redis' in content_lower:
        tags.append('redis')
    if 'youtube' in content_lower:
        tags.append('youtube')
    if 'rob' in content_lower:
        tags.append('user')
    
    return list(set(tags))  # Remove duplicates

def extract_core_memories_from_memory_md():
    """Extract high-importance memories from MEMORY.md"""
    memories = []
    
    try:
        with open(MEMORY_MD, 'r') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading MEMORY.md: {e}", file=sys.stderr)
        return memories
    
    # Core sections with high importance
    sections = [
        ("Identity & Names", "high"),
        ("Core Preferences", "high"),
        ("Communication Rules", "high"),
        ("Voice Settings", "high"),
        ("Lessons Learned", "high"),
    ]
    
    for section_name, importance in sections:
        pattern = f"## {section_name}.*?(?=## |$)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            section_text = match.group(0).strip()
            # Extract subsections
            subsections = re.findall(r'### (.+?)\n', section_text)
            for sub in subsections:
                sub_pattern = f"### {re.escape(sub)}.*?(?=### |## |$)"
                sub_match = re.search(sub_pattern, section_text, re.DOTALL)
                if sub_match:
                    sub_text = sub_match.group(0).strip()
                    if len(sub_text) > 50:
                        memories.append({
                            "text": f"{section_name} - {sub}: {sub_text[:500]}",
                            "date": "2026-02-10",
                            "tags": extract_tags(section_name, sub_text) + ['core', 'longterm'],
                            "importance": importance
                        })
    
    return memories

def main():
    print("Starting bulk memory migration to kimi_memories...")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Model: snowflake-arctic-embed2 (1024 dims)")
    print()
    
    all_memories = []
    
    # Extract from daily logs
    for filename in sorted(os.listdir(MEMORY_DIR)):
        if filename.endswith('.md') and filename.startswith('2026'):
            filepath = os.path.join(MEMORY_DIR, filename)
            print(f"Processing {filename}...")
            memories = extract_memories_from_file(filepath, importance="medium")
            all_memories.extend(memories)
            print(f"  Extracted {len(memories)} memories")
    
    # Extract from MEMORY.md
    print("Processing MEMORY.md...")
    core_memories = extract_core_memories_from_memory_md()
    all_memories.extend(core_memories)
    print(f"  Extracted {len(core_memories)} core memories")
    
    print(f"\nTotal memories to store: {len(all_memories)}")
    print()
    
    # Store each memory
    success_count = 0
    fail_count = 0
    
    for i, memory in enumerate(all_memories, 1):
        print(f"[{i}/{len(all_memories)}] Storing: {memory['text'][:60]}...")
        
        # Generate embedding
        embedding = get_embedding(memory['text'])
        if embedding is None:
            print(f"  ❌ Failed to generate embedding")
            fail_count += 1
            continue
        
        # Store in Qdrant
        if store_memory(
            text=memory['text'],
            embedding=embedding,
            tags=memory['tags'],
            importance=memory['importance'],
            date=memory['date'],
            source="bulk_migration",
            confidence="high",
            source_type="user",
            verified=True
        ):
            print(f"  ✅ Stored")
            success_count += 1
        else:
            print(f"  ❌ Failed to store")
            fail_count += 1
    
    print()
    print("=" * 50)
    print(f"Migration complete!")
    print(f"  Success: {success_count}")
    print(f"  Failed: {fail_count}")
    print(f"  Total: {len(all_memories)}")
    print("=" * 50)

if __name__ == "__main__":
    main()
