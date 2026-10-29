import re

# Looks at one ticket and tells us what it contains:
# an error code, the environment, repro steps and logs.

# words that tell us the reporter named their setup
ENV_WORDS = ["windows", "macos", "mac os", "ubuntu", "debian", "centos", "linux", "android",
             "ios", "docker", "kubernetes", "chrome", "firefox", "safari", "edge", "node",
             "python", "java", "golang", "rust", "npm", "postgres", "mysql", "sqlite",
             "react", "angular", "vue", "pytorch", "tensorflow", "cuda", "flutter",
             "godot", "electron", "tauri", "deno", "typescript", "gcc", "clang"]
# a tool or OS name followed closely by a version number: "Windows 11", "node: 18.19.0", "Chrome 126"
ENV_REGEX = re.compile(r"\b(" + "|".join(ENV_WORDS) + r")\b\W{0,4}(v|version )?\d", re.I)

# words that say which environment it happened in
STAGE_WORDS = ["production", "staging", "qa environment", "uat", "localhost"]

# error codes: each pattern is one kind of code
ERROR_PATTERNS = [
    r"ORA-\d{4,5}",                                          # oracle
    r"SQLSTATE\W{0,3}\w{5}",                                 # sql
    r"(?:http|status|error|code|response)\W{0,3}[45]\d\d\b", # http 404, status 502
    r"\bE(?:CONNREFUSED|CONNRESET|TIMEDOUT|NOENT|ACCES|PERM)\b",   # network errno
    r"CrashLoopBackOff|OOMKilled|ImagePullBackOff|ErrImagePull",   # kubernetes
    r"invalid_grant|invalid_client|invalid_token|access_denied",   # oauth
    r"exit(?:ed)? (?:with )?(?:code|status) -?\d+",
    r"\bSIG(?:SEGV|ABRT|KILL)\b|\bpanic:",
    r"\bERR_[A-Z_]{4,}",                                     # chrome
]
# names like TypeError or NullPointerException (capital letters matter here)
ERROR_NAME = re.compile(r"\b[A-Z][a-zA-Z]+(?:Error|Exception)\b")

# lines that only show up inside a stack trace
STACK_MARKS = ["Traceback (most recent call last)", "goroutine ", "panic:", "Caused by:",
               "core dumped", "SIGSEGV", "stack backtrace", "Exception in thread"]

NEGATIONS = ["no", "not", "never", "without", "doesn't", "isn't", "don't", "didn't"]


def split_code(text):
    # everything between ``` marks is code, the rest is prose
    parts = text.split("```")
    prose = " ".join(parts[0::2])
    code_blocks = parts[1::2]
    return prose, code_blocks


def mask_noise(text):
    # replace values that change every time, so the model does not memorise them
    text = re.sub(r"https?://\S+", "<URL>", text)
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?\S*", "<TIME>", text)
    text = re.sub(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", "<UUID>", text)
    text = re.sub(r"\b\d{1,3}(\.\d{1,3}){3}\b", "<IP>", text)
    text = re.sub(r"\b0x[0-9a-fA-F]{6,}\b", "<ADDR>", text)
    text = re.sub(r"(/[\w.\-]+){3,}", "<PATH>", text)
    return text


def mentions(text, word):
    # True if the word is in the text and is not denied.
    # Denied means: "no/not/never..." just before it, or "did not / never" just after it.
    text = text.lower()
    start = 0
    while True:
        i = text.find(word, start)
        if i == -1:
            return False
        before = re.findall(r"[\w']+", text[max(0, i - 25):i])
        after = text[i + len(word):i + len(word) + 25]
        denied_before = any(n in before for n in NEGATIONS)
        denied_after = re.match(r"\W*(did not|didn't|never)\b", after)
        if not denied_before and not denied_after:
            return True
        start = i + 1


def find_error_codes(text):
    found = []
    for pattern in ERROR_PATTERNS:
        for m in re.finditer(pattern, text, flags=re.I):
            found.append(m.group(0))
    found += ERROR_NAME.findall(text)
    return list(dict.fromkeys(found))     # remove repeats, keep order


def find_environment(text):
    hits = []
    for line in text.splitlines():
        if ENV_REGEX.search(line):
            hits.append(line.strip()[:60])
        # lines like "OS: Linux" or "Browser: Firefox"
        elif re.search(r"^\W*(os|operating system|browser|platform|device)\W{0,3}\w", line, flags=re.I):
            hits.append(line.strip()[:60])
        # a line like "Version: 0.87.1"
        elif re.search(r"^\W*\w*\s?version\W{0,3}v?\d", line, flags=re.I):
            hits.append(line.strip()[:60])
    lower = text.lower()
    for word in STAGE_WORDS:
        if re.search(r"\b(in|on|from) (the )?" + word + r"\b", lower):
            hits.append(word)
    return hits


def find_repro_steps(text):
    # two or more numbered lines: "1. open the app"
    numbered = re.findall(r"^\s*\d+[.)]\s*\S", text, flags=re.M)
    if len(numbered) >= 2:
        return True
    # a link to a demo that reproduces it
    if re.search(r"codesandbox|stackblitz|jsfiddle|playground|godbolt|dartpad|replit", text, flags=re.I):
        return True
    # the phrase "steps to reproduce" followed by a real description
    m = re.search(r"(?:steps to reproduce|to reproduce|how to reproduce|repro steps)\W{0,3}(.{0,200})",
                  text, flags=re.I | re.S)
    if m:
        after = m.group(1).strip()
        empty = re.match(r"\W*(n/?a|none|no response|not relevant)\b", after, flags=re.I)
        return (not empty) and len(after.split()) >= 8
    return False


def find_logs(text, code_blocks):
    if has_stack_trace(text):
        return True
    # at least two lines that start with a log level
    log_lines = re.findall(r"^.*\b(?:ERROR|WARN|WARNING|FATAL)\b.*$", text, flags=re.M)
    if len(log_lines) >= 2:
        return True
    # a single pasted error message like "error: build failed" or "npm ERR! ..."
    if re.search(r"(?:^|`)\s*(?:error|fatal|npm err!)[:!\[ ]", text, flags=re.M | re.I):
        return True
    # a code block that contains an error word
    for block in code_blocks:
        if re.search(r"error|failed|exception|denied|refused", block, flags=re.I) and block.count("\n") >= 2:
            return True
    return False


def has_stack_trace(text):
    if any(mark in text for mark in STACK_MARKS):
        return True
    # java / javascript frames:  "    at Something.run(File.java:12)"
    if len(re.findall(r"^\s+at .+[:(]\d+", text, flags=re.M)) >= 2:
        return True
    # python frames:  'File "app.py", line 10'
    return bool(re.search(r'^\s*File ".+", line \d+', text, flags=re.M))


def extract_signals(text):
    text = "" if text is None else str(text)
    prose, code_blocks = split_code(text)
    codes = find_error_codes(text)
    env = find_environment(text)
    return {
        "is_empty": len(re.findall(r"\w+", text)) == 0,
        "word_count": len(re.findall(r"\w+", prose)),
        "prose": prose.strip(),
        "n_code_blocks": len(code_blocks),
        "error_codes": codes,
        "env_hits": env,
        "has_error_code": len(codes) > 0,
        "has_environment": len(env) > 0,
        "has_repro_steps": find_repro_steps(text),
        "has_logs": find_logs(text, code_blocks),
        "has_stack_trace": has_stack_trace(text),
    }


if __name__ == "__main__":
    tests = [
        "",
        "broken",
        "Login fails with invalid_grant on staging, Chrome 126 on Windows 11.\nSteps to reproduce:\n1. open the app\n2. click sign in",
        "App crashes.\n```\nTraceback (most recent call last):\n  File \"app.py\", line 10, in <module>\nValueError: bad\n```",
        "There is no error shown and it does not crash, just slow.",
    ]
    for t in tests:
        s = extract_signals(t)
        print(repr(t[:45]), s["has_error_code"], s["has_environment"], s["has_repro_steps"], s["has_logs"])