import json

log_path = r"C:\Users\chiuk\.gemini\antigravity\brain\5c34a2e7-a352-41ae-9b27-2490369543ab\.system_generated\logs\transcript.jsonl"
with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            step = json.loads(line)
            idx = step.get('step_index', 0)
            if idx < 800 or idx > 1000:
                continue
            tool_calls = step.get("tool_calls", [])
            for tc in tool_calls:
                args = tc.get("args", {})
                args_str = json.dumps(args, ensure_ascii=False)
                if "crawler.py" in args_str or "05_leader_marketer.py" in args_str:
                    name = tc.get("name", "")
                    if "replace" in name or "write" in name:
                        print(f"Step {idx} Tool: {name}")
                        print(args_str)
                        print("="*60)
        except Exception as e:
            pass
