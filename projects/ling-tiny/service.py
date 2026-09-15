def start_service():
    """Start the application service using app-ctl."""
    import subprocess
    subprocess.run(["./scripts/app-ctl", "start"], check=True)
