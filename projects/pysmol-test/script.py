import re

logs = run_command("journalctl -b 0 -n 100")
errors = re.findall(r"error: (.*)", logs, re.IGNORECASE)
final_answer({"total_errors": len(errors), "sample": errors[:3]})
