import re


ERROR_PATTERNS = [
    r"\bORA-\d{4,5}\b",
    r"\bSQLSTATE\W{0,3}[0-9A-Z]{5}\b",
    r"\b(?:HTTP|status|error|code|response)\W{0,3}[45]\d\d\b",
    r"\b[45]\d\d\s+(?:bad request|unauthorized|forbidden|not found|"
    r"internal server error|bad gateway|service unavailable|"
    r"gateway time-?out|too many requests)\b",
    r"\bE(?:CONNREFUSED|CONNRESET|TIMEDOUT|NOENT|ACCES|PERM|"
    r"ADDRINUSE|HOSTUNREACH|PIPE)\b",
    r"\b[A-Z][A-Za-z]+(?:Error|Exception)\b",
    r"\b(?:CrashLoopBackOff|OOMKilled|ImagePullBackOff|"
    r"ErrImagePull|Evicted)\b",
    r"\b(?:invalid_grant|invalid_client|invalid_token|"
    r"unauthorized_client|access_denied)\b",
    r"\bexit(?:ed)?(?: with)? (?:code|status) -?\d+\b",
    r"\bSIG(?:SEGV|ABRT|KILL|BUS)\b",
    r"\berror\[E\d{4}\]",
    r"\berror TS\d{4}\b",
    r"\berror C\d{4}\b",
    r"\b(?:net::)?ERR_[A-Z_]{4,}\b",
    r"\bCVE-\d{4}-\d{4,}\b",
    r"\bpanic:",
]

STACK_PATTERNS = [
    r"Traceback \(most recent call last\)",
    r"^\s+at [\w.$<>\[\]/-]+\(.*\)",
    r"^\s+at .+:\d+:\d+",
    r'^\s*File ".+", line \d+',
    r"goroutine \d+ \[",
    r"^\s*#\d+\s+0x[0-9a-f]+",
    r"Exception in thread",
    r"^Caused by:",
    r"stack backtrace",
    r"core dumped",
    r"\bSIGSEGV\b",
]

ENVIRONMENT_NAMES = (
    r"Windows|macOS|Mac OS|OS X|Ubuntu|Debian|CentOS|Fedora|"
    r"RHEL|Arch Linux|Linux|Android|iOS|WSL2?|Docker|Kubernetes|"
    r"K8s|Chrome|Chromium|Firefox|Safari|Edge|Node(?:\.js)?|"
    r"Python|Java|JDK|Golang|Go|Rustc|Rust|npm|Yarn|GCC|Clang|"
    r"Postgres(?:ql)?|MySQL|SQLite|Kafka|Airflow|React|Angular|"
    r"Vue|Next\.js|PyTorch|TensorFlow|CUDA|Flutter|Dart|Godot|"
    r"Electron|Tauri|Deno|TypeScript|PHP|Ruby|Dotnet|\.NET"
)

STAGE_PATTERN = (
    r"\b(?:production|prod|staging|qa|uat|dev cluster|"
    r"dev environment|localhost)\b"
)

REPRO_HEADING = re.compile(
    r"^\s*(?:#{1,6}\s*)?"
    r"(?:steps?\s+to\s+reproduce|reproduction steps?|"
    r"how to reproduce|repro steps?)\s*:?\s*$",
    re.I | re.M,
)

REPRO_PHRASE = re.compile(
    r"(?:steps? to reproduce|how to reproduce|repro steps?|"
    r"reproduction steps?|minimal reproducible example)",
    re.I,
)

REPRO_LINK = re.compile(
    r"\b(?:codesandbox|stackblitz|jsfiddle|playground|"
    r"godbolt|dartpad|repl\.it|replit|gist\.github)\b",
    re.I,
)

PLACEHOLDER = re.compile(
    r"^\W*(?:n/?a|none|no response|_no response_|-|"
    r"todo|not relevant|unknown)\b",
    re.I,
)


def split_code(text):
    """Separate prose from fenced Markdown code blocks."""
    parts = text.split("```")
    prose = []
    blocks = []

    for index, part in enumerate(parts):
        if index % 2 == 0:
            prose.append(part)
        else:
            # A language marker, such as `python`, may appear first.
            lines = part.splitlines()
            if lines and re.fullmatch(r"\s*[\w+-]+\s*", lines[0]):
                part = "\n".join(lines[1:])
            blocks.append(part)

    return "\n".join(prose), blocks


def mask_noise(text):
    """Replace variable identifiers that may distract text models."""
    text = re.sub(r"https?://\S+", "<URL>", text)
    text = re.sub(
        r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}"
        r"(?::\d{2}(?:\.\d+)?)?Z?\b",
        "<TIME>",
        text,
    )
    text = re.sub(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
        r"[0-9a-f]{4}-[0-9a-f]{12}\b",
        "<UUID>",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"\b(?:25[0-5]|2[0-4]\d|1?\d?\d)"
        r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b",
        "<IP>",
        text,
    )
    text = re.sub(r"\b[0-9a-f]{32,64}\b", "<HASH>", text, flags=re.I)
    text = re.sub(r"\b0x[0-9a-f]{6,}\b", "<ADDR>", text, flags=re.I)
    text = re.sub(
        r"(?:[A-Za-z]:\\|/)(?:[\w.-]+[\\/])+[\w.-]*",
        "<PATH>",
        text,
    )
    return text


def mentions(text, pattern):
    """Check for a pattern, ignoring a nearby explicit negation."""
    for match in re.finditer(pattern, text, flags=re.I):
        before = text[max(0, match.start() - 40):match.start()]

        if not re.search(
            r"\b(?:no|not|never|without|neither|nor|isn't|"
            r"doesn't|don't|didn't)\b[\w\s,]{0,25}$",
            before,
            flags=re.I,
        ):
            return True

    return False


def find_error_codes(text):
    found = []

    for pattern in ERROR_PATTERNS:
        for match in re.finditer(pattern, text):
            found.append(match.group(0).strip())

    return list(dict.fromkeys(found))


def find_environment(text):
    found = []

    version_pattern = (
        r"[A-Za-z][\w ./+-]{0,30}?\s*version"
        r"[^\n\d]{0,40}?[a-z]{0,6}\d+\.\d+[\w.-]*"
    )

    for match in re.finditer(version_pattern, text, flags=re.I):
        found.append(match.group(0).strip())

    tool_version_pattern = (
        r"\b(?:" + ENVIRONMENT_NAMES + r")"
        r"\b[ :/v-]{1,3}\d{1,3}(?:\.\d+)*\b"
    )

    for match in re.finditer(tool_version_pattern, text, flags=re.I):
        found.append(match.group(0).strip())

    platform_pattern = (
        r"^\s*(?:os|operating system|platform|browser|"
        r"device|terminal)[^\n:=]{0,25}[:=]\s*(\S[^\n]{1,80})"
    )

    for match in re.finditer(platform_pattern, text, flags=re.I | re.M):
        value = match.group(1).strip()

        if not PLACEHOLDER.match(value):
            found.append(match.group(0).strip())

    for match in re.finditer(STAGE_PATTERN, text, flags=re.I):
        found.append(match.group(0).strip())

    return list(dict.fromkeys(found))


def has_repro_steps(text):
    """Look for evidence of actual steps rather than any numbered list."""
    lines = text.splitlines()
    in_repro_section = False
    section_lines = []

    for line in lines:
        if REPRO_HEADING.match(line):
            in_repro_section = True
            continue

        if in_repro_section and re.match(r"^\s*#{1,6}\s+", line):
            break

        if in_repro_section:
            section_lines.append(line)

    if section_lines:
        section = "\n".join(section_lines).strip()

        if PLACEHOLDER.match(section):
            return False

        steps = re.findall(
            r"^\s*(?:\d+[.)]|[-*])\s+\S",
            section,
            flags=re.M,
        )

        if len(steps) >= 2 or len(section.split()) >= 8:
            return True

    if REPRO_LINK.search(text):
        return True

    # Recognized phrases need some meaningful content after them.
    for match in REPRO_PHRASE.finditer(text):
        following = text[match.end():match.end() + 250].strip(" :\t\n-")

        if not PLACEHOLDER.match(following) and len(following.split()) >= 8:
            return True

    return False


def has_stack_trace(text):
    return any(
        re.search(pattern, text, flags=re.I | re.M)
        for pattern in STACK_PATTERNS
    )


def has_log_output(text, code_blocks):
    if has_stack_trace(text):
        return True

    log_levels = re.findall(
        r"^\s*(?:\[[^\]]+\]\s*)?"
        r"(?:ERROR|WARN|WARNING|FATAL|CRITICAL)\b.*$",
        text,
        flags=re.I | re.M,
    )

    timestamps = re.findall(
        r"^\s*\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}.*$",
        text,
        flags=re.M,
    )

    if len(log_levels) >= 2 or len(timestamps) >= 2:
        return True

    if re.search(
        r"(?:^|`)\s*(?:error|fatal|npm err!)\b[:\[! ]",
        text,
        flags=re.I | re.M,
    ):
        return True

    for block in code_blocks:
        lines = block.strip().splitlines()

        if len(lines) < 2:
            continue

        if any(
            re.search(pattern, block, flags=re.I | re.M)
            for pattern in STACK_PATTERNS
        ):
            return True

        diagnostic_lines = re.findall(
            r"^\s*(?:ERROR|WARN|WARNING|FATAL|CRITICAL)\b.*$",
            block,
            flags=re.I | re.M,
        )

        if len(diagnostic_lines) >= 2:
            return True

    return False


def extract_signals(text):
    """Extract diagnostic signals from one support ticket."""
    if text is None:
        text = ""

    text = str(text)
    prose, code_blocks = split_code(text)

    error_codes = find_error_codes(text)
    environments = find_environment(text)

    return {
        "is_empty": not bool(re.search(r"\w", text)),
        "word_count": len(re.findall(r"\w+", prose)),
        "prose": prose.strip(),
        "n_code_blocks": len(code_blocks),
        "error_codes": error_codes,
        "env_hits": environments,
        "has_error_code": bool(error_codes),
        "has_environment": bool(environments),
        "has_repro_steps": has_repro_steps(text),
        "has_logs": has_log_output(text, code_blocks),
        "has_stack_trace": has_stack_trace(text),
    }


if __name__ == "__main__":
    examples = [
        "",
        "broken",
        (
            "Login fails with invalid_grant on staging, Chrome 126 on Windows 11.\n"
            "Steps to reproduce:\n"
            "1. Open the app\n"
            "2. Click sign in and observe the error"
        ),
        (
            "App crashes.\n"
            "```\n"
            "Traceback (most recent call last):\n"
            '  File "app.py", line 10, in <module>\n'
            "ValueError: bad input\n"
            "```"
        ),
        "There is no error shown and it does not crash, just slow.",
    ]

    for example in examples:
        result = extract_signals(example)
        print("\nTicket:", repr(example[:60]))
        print(result)
