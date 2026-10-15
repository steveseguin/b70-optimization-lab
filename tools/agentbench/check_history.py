#!/usr/bin/env python3
"""check_history.py requests.jsonl: does the agent send its whole history every time? (reads the bridge's tap)

Groups the agent's chat-completion requests by conversation (model + system messages + first user message, as
ctxkeeper keys them) and, within each, checks that every request starts with all the messages of the one before
(compared the way ctxkeeper compares: role, whitespace-collapsed text, tool calls by name + arguments). Also reports
what ctxkeeper requires of a client: Chat Completions only, n = 1, Content-Length bodies (no chunked), and whether
tools were sent. Prints one JSON object.
"""
import collections, json, sys


def main():
    rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
    posts = [r for r in rows if r.get("method") == "POST"]
    chat = [r for r in posts if r.get("path", "").split("?")[0].rstrip("/").endswith("/chat/completions")]
    convs = collections.OrderedDict()
    for r in chat:
        convs.setdefault(r.get("conv"), []).append(r)
    out = {
        "requests": len(rows), "posts": len(posts), "chat_completions": len(chat),
        "other_paths": sorted({r.get("path") for r in rows if r not in chat}),
        "responses_api": sum(1 for r in posts if r.get("responses_api") or "/responses" in r.get("path", "")),
        "chunked_bodies": sum(1 for r in posts if r.get("chunked")),
        "n_not_1": sum(1 for r in chat if r.get("n") not in (None, 1)),
        "stream": sorted({str(r.get("stream")) for r in chat}),
        "with_tools": sum(1 for r in chat if r.get("tools")),
        "tool_names": sorted({t for r in chat for t in (r.get("tools") or []) if t}),
        "conversations": [],
    }
    for key, rs in convs.items():
        breaks = [{"i": r["i"], **r["extends_previous"]} for r in rs
                  if r.get("extends_previous") and not r["extends_previous"]["extends"]]
        out["conversations"].append({
            "key": key, "requests": len(rs), "max_messages": max(r.get("n_messages", 0) for r in rs),
            "head_messages": rs[0].get("head"), "first_roles": (rs[0].get("roles") or "")[:12],
            "with_tools": sum(1 for r in rs if r.get("tools")),
            "every_request_extends_previous": not breaks, "breaks": breaks[:10]})
    main_conv = max(out["conversations"], key=lambda c: c["requests"], default=None)
    out["main_conversation"] = main_conv["key"] if main_conv else None
    out["whole_history_ok"] = bool(main_conv and main_conv["every_request_extends_previous"] and main_conv["requests"] > 1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
