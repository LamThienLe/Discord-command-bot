from __future__ import annotations

from typing import Dict


# Very small in-memory cache for common commands.
# Extend as needed.
COMMON_ANSWERS: Dict[str, str] = {
    "grep": (
        "Explanation: Search lines that match a pattern in files.\n\n"
        "Syntax:\n"
        "```\n"
        "grep [OPTIONS] PATTERN [FILE...]\n"
        "```\n\n"
        "Example:\n"
        "```\n"
        "grep -R \"error\" /var/log\n"
        "```"
    ),
    "tar": (
        "Explanation: Create or extract archive files.\n\n"
        "Syntax:\n"
        "```\n"
        "tar -cvf archive.tar DIR\n"
        "tar -xvf archive.tar\n"
        "tar -xvzf archive.tar.gz\n"
        "```\n\n"
        "Example:\n"
        "```\n"
        "tar -xvzf backup.tar.gz -C /home/user/data/\n"
        "```"
    ),
    "curl": (
        "Explanation: Transfer data to/from a server.\n\n"
        "Syntax:\n"
        "```\n"
        "curl [OPTIONS] URL\n"
        "```\n\n"
        "Example:\n"
        "```\n"
        "curl -L https://example.com -o page.html\n"
        "```"
    ),
    "docker": (
        "Explanation: Build and run containers.\n\n"
        "Syntax:\n"
        "```\n"
        "docker run [OPTIONS] IMAGE [COMMAND] [ARG...]\n"
        "```\n\n"
        "Example:\n"
        "```\n"
        "docker run --rm -it ubuntu:22.04 bash\n"
        "```"
    ),
    "kubectl": (
        "Explanation: Control Kubernetes clusters.\n\n"
        "Syntax:\n"
        "```\n"
        "kubectl [COMMAND] [TYPE] [NAME] [FLAGS]\n"
        "```\n\n"
        "Example:\n"
        "```\n"
        "kubectl get pods -n kube-system\n"
        "```"
    ),
    "git": (
        "Explanation: Version control system commands.\n\n"
        "Syntax:\n"
        "```\n"
        "git <command> [options]\n"
        "```\n\n"
        "Example:\n"
        "```\n"
        "git clone https://github.com/user/repo.git\n"
        "```"
    ),
}


def get_cached_answer(query_text: str) -> str | None:
    """Return a cached answer if the query looks like a known command.

    The heuristic here is simple: if the query contains a known command token,
    return its cached explanation. Real systems could use embeddings or regexes.
    """
    lowered = query_text.strip().lower()
    for token, answer in COMMON_ANSWERS.items():
        if token in lowered:
            return answer
    return None


