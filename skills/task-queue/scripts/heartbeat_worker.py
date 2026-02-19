#!/usr/bin/env python3
"""
Heartbeat worker - GPT-powered task execution.
Sends tasks to Ollama for command generation, executes via SSH.
"""

import redis
import json
import time
import os
import sys
import subprocess
import requests
from datetime import datetime

REDIS_HOST = os.environ.get("REDIS_HOST", "10.0.0.36")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")

def get_redis():
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True
    )

def generate_task_id():
    return f"task_{int(time.time())}_{os.urandom(4).hex()}"

def check_active_task(r):
    """Check if there's already an active task."""
    active = r.lrange("tasks:active", 0, -1)
    if active:
        task_id = active[0]
        task = r.hgetall(f"task:{task_id}")
        started_at = int(task.get("started_at", 0))
        elapsed = time.time() - started_at
        print(f"[BUSY] Task {task_id} active for {elapsed:.0f}s")
        return True
    return False

def get_pending_task(r):
    """Pop a task from pending queue."""
    task_id = r.rpop("tasks:pending")
    if task_id:
        return task_id
    return None

def clean_json_content(content):
    """Strip markdown code blocks if present."""
    cleaned = content.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()

def ask_gpt_for_commands(task_description, target_host="10.0.0.38", ssh_user="n8n", sudo_pass="passw0rd"):
    """
    Send task to Ollama/GPT to generate SSH commands.
    Returns dict with commands, expected results, and explanation.
    """
    system_prompt = f"""You have SSH access to {ssh_user}@{target_host}
Sudo password: {sudo_pass}

Your job is to generate shell commands to complete the given task.
Respond ONLY with valid JSON in this format:
{{
    "commands": [
        "ssh -t {ssh_user}@{target_host} 'sudo apt update'",
        "ssh -t {ssh_user}@{target_host} 'sudo apt install -y docker.io'"
    ],
    "expected_results": [
        "apt updated successfully",
        "docker installed and running"
    ],
    "explanation": "Updating packages and installing Docker"
}}

Rules:
- Commands should use ssh -t (allocates TTY for sudo password) to execute on the remote host
- Use sudo when needed (password: {sudo_pass})
- Keep commands safe and idempotent where possible
- If task is unclear, ask for clarification in explanation

For Docker-related tasks:
- Search Docker Hub for official images (docker.io/library/ or verified publishers)
- Prefer latest stable versions
- Use official images over community when available
- Verify image exists before trying to pull
- Map volumes as specified in the task (e.g., -v /root/html:/usr/share/nginx/html)"""

    user_prompt = f"Task: {task_description}\n\nGenerate the commands to complete this task."

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": "kimi-k2.5:cloud",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": False,
                "format": "json"
            },
            timeout=120
        )
        response.raise_for_status()
        
        result = response.json()
        content = result.get("message", {}).get("content", "{}")
        
        # Parse the JSON response
        try:
            cleaned = clean_json_content(content)
            gpt_plan = json.loads(cleaned)
            return gpt_plan
        except json.JSONDecodeError:
            # If GPT didn't return valid JSON, wrap the raw response
            return {
                "commands": [],
                "expected_results": [],
                "explanation": f"GPT response: {content[:200]}",
                "parse_error": "GPT did not return valid JSON"
            }
            
    except Exception as e:
        return {
            "commands": [],
            "expected_results": [],
            "explanation": f"Failed to get commands from GPT: {e}",
            "error": str(e)
        }

def execute_ssh_command_with_sudo(command, sudo_pass, timeout=300):
    """
    Execute an SSH command with sudo password handling.
    Uses -t flag for TTY allocation and handles sudo password prompt.
    """
    try:
        # Ensure command has -t flag for TTY
        if not "-t" in command and command.startswith("ssh "):
            command = command.replace("ssh ", "ssh -t ", 1)
        
        # Use expect-like approach with subprocess
        # Send password when prompted
        import pty
        import select
        import termios
        import tty
        
        master_fd, slave_fd = pty.openpty()
        
        process = subprocess.Popen(
            command,
            shell=True,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=os.setsid
        )
        
        os.close(slave_fd)
        
        output = []
        password_sent = False
        start_time = time.time()
        
        while process.poll() is None:
            if time.time() - start_time > timeout:
                process.kill()
                return {
                    "success": False,
                    "stdout": "".join(output),
                    "stderr": "Command timed out",
                    "exit_code": -1
                }
            
            ready, _, _ = select.select([master_fd], [], [], 0.1)
            if ready:
                try:
                    data = os.read(master_fd, 1024).decode()
                    output.append(data)
                    
                    # Check for sudo password prompt
                    if "password:" in data.lower() or "password for" in data.lower():
                        if not password_sent:
                            os.write(master_fd, (sudo_pass + "\n").encode())
                            password_sent = True
                            time.sleep(0.5)
                except OSError:
                    break
        
        os.close(master_fd)
        
        stdout = "".join(output)
        return {
            "success": process.returncode == 0,
            "stdout": stdout,
            "stderr": "" if process.returncode == 0 else stdout,
            "exit_code": process.returncode
        }
        
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1
        }

def execute_ssh_command_simple(command, timeout=300):
    """
    Execute an SSH command without sudo (simple version).
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Command timed out",
            "exit_code": -1
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1
        }

def execute_task_with_gpt(task):
    """
    Execute task using GPT to generate commands, then run via SSH.
    """
    task_description = task.get("description", "No description")
    target_host = task.get("target_host", "10.0.0.38")
    ssh_user = task.get("ssh_user", "n8n")
    sudo_pass = task.get("sudo_pass", "passw0rd")
    
    print(f"[GPT] Generating commands for: {task_description}")
    
    # Get commands from GPT
    gpt_plan = ask_gpt_for_commands(task_description, target_host, ssh_user, sudo_pass)
    
    if not gpt_plan.get("commands"):
        comments = f"GPT failed to generate commands: {gpt_plan.get('explanation', 'Unknown error')}"
        return {
            "success": False,
            "gpt_plan": gpt_plan,
            "execution_results": [],
            "comments": comments
        }
    
    print(f"[GPT] Plan: {gpt_plan.get('explanation', 'No explanation')}")
    print(f"[EXEC] Running {len(gpt_plan['commands'])} commands...")
    
    # Execute each command
    execution_results = []
    any_failed = False
    
    for i, cmd in enumerate(gpt_plan["commands"]):
        print(f"[CMD {i+1}] {cmd[:80]}...")
        
        # Check if command uses sudo
        if "sudo" in cmd.lower():
            result = execute_ssh_command_with_sudo(cmd, sudo_pass)
        else:
            result = execute_ssh_command_simple(cmd)
            
        execution_results.append({
            "command": cmd,
            "result": result
        })
        
        if not result["success"]:
            any_failed = True
            print(f"[FAIL] Exit code {result['exit_code']}: {result['stderr'][:100]}")
        else:
            print(f"[OK] Success")
    
    # Build comments field
    if any_failed:
        failed_cmds = [r for r in execution_results if not r["result"]["success"]]
        comments = f"ERRORS ({len(failed_cmds)} failed):\n"
        for r in failed_cmds:
            comments += f"- Command: {r['command'][:60]}...\n"
            comments += f"  Error: {r['result']['stderr'][:200]}\n"
    else:
        comments = "OK"
    
    return {
        "success": not any_failed,
        "gpt_plan": gpt_plan,
        "execution_results": execution_results,
        "comments": comments
    }

def execute_simple_task(task):
    """
    Execute simple tasks (notify, command) without GPT.
    """
    task_type = task.get("type", "default")
    description = task.get("description", "No description")
    sudo_pass = task.get("sudo_pass", "passw0rd")
    
    if task_type == "notify":
        # For now, just log it (messaging handled elsewhere)
        return {
            "success": True,
            "result": f"Notification: {task.get('message', description)}",
            "comments": "OK"
        }
    
    elif task_type == "command":
        # Execute shell command directly
        command = task.get("command", "")
        if command:
            if "sudo" in command.lower():
                result = execute_ssh_command_with_sudo(command, sudo_pass)
            else:
                result = execute_ssh_command_simple(command)
            comments = "OK" if result["success"] else f"Error: {result['stderr'][:500]}"
            return {
                "success": result["success"],
                "result": result["stdout"][:500],
                "comments": comments
            }
        else:
            return {
                "success": False,
                "result": "No command specified",
                "comments": "ERROR: No command provided"
            }
    
    else:
        # Default: use GPT
        return execute_task_with_gpt(task)

def mark_completed(r, task_id, result_data):
    """Mark task as completed with full result data."""
    r.hset(f"task:{task_id}", mapping={
        "status": "completed" if result_data["success"] else "failed",
        "completed_at": str(int(time.time())),
        "result": json.dumps(result_data.get("result", "")),
        "comments": result_data.get("comments", "")
    })
    r.lrem("tasks:active", 0, task_id)
    r.lpush("tasks:completed", task_id)
    
    status = "DONE" if result_data["success"] else "FAILED"
    print(f"[{status}] {task_id}")
    if result_data.get("comments") and result_data["comments"] != "OK":
        print(f"[COMMENTS] {result_data['comments'][:200]}")

def mark_failed(r, task_id, error):
    """Mark task as failed."""
    r.hset(f"task:{task_id}", mapping={
        "status": "failed",
        "completed_at": str(int(time.time())),
        "result": f"Error: {error}",
        "comments": f"Worker error: {error}"
    })
    r.lrem("tasks:active", 0, task_id)
    r.lpush("tasks:completed", task_id)
    print(f"[FAILED] {task_id}: {error}")

def main():
    r = get_redis()
    
    # Check if already busy
    if check_active_task(r):
        sys.exit(0)
    
    # Get next pending task
    task_id = get_pending_task(r)
    if not task_id:
        print("[IDLE] No pending tasks")
        sys.exit(0)
    
    # Load task details
    task = r.hgetall(f"task:{task_id}")
    if not task:
        print(f"[ERROR] Task {task_id} not found")
        sys.exit(1)
    
    # Move to active
    r.hset(f"task:{task_id}", mapping={
        "status": "active",
        "started_at": str(int(time.time()))
    })
    r.lpush("tasks:active", task_id)
    
    print(f"[START] {task_id}: {task.get('description', 'No description')}")
    
    try:
        # Execute the task
        result_data = execute_simple_task(task)
        mark_completed(r, task_id, result_data)
        print(f"[WAKE] Task complete - check comments field for status")
        
    except Exception as e:
        mark_failed(r, task_id, str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
