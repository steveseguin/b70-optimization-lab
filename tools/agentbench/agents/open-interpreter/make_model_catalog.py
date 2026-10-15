#!/usr/bin/env python3
# Usage: make_model_catalog.py OPEN_INTERPRETER_SOURCE_AT_rust-v0.0.56 model-catalog.json
# Builds agents/open-interpreter/model-catalog.json: Open Interpreter's own fallback metadata for an unknown model
# (codex-rs/models-manager/src/model_info.rs model_info_from_slug, rust-v0.0.56), unchanged except the context window.
import json, sys
src, out = sys.argv[1], sys.argv[2]
prompt = open(src + "/codex-rs/models-manager/prompt.md", encoding="utf-8").read()
assert "@MODEL@" not in prompt
m = {
    "slug": "@MODEL@", "display_name": "@MODEL@", "description": None,
    "supported_reasoning_levels": [], "reasoning_control": "none", "shell_type": "default", "visibility": "none",
    "supported_in_api": True, "priority": 99, "additional_speed_tiers": [], "service_tiers": [],
    "availability_nux": None, "upgrade": None,
    "model_messages": {"instructions_template": prompt},
    "include_skills_usage_instructions": False, "supports_reasoning_summaries": False,
    "include_plugin_usage_instructions": False, "include_apps_usage_instructions": False,
    "supports_reasoning_summary_parameter": True, "default_reasoning_summary": "auto",
    "support_verbosity": False, "default_verbosity": None, "apply_patch_tool_type": None,
    "web_search_tool_type": "text", "truncation_policy": {"mode": "bytes", "limit": 10000},
    "supports_image_detail_original": False,
    "context_window": 10000000, "max_context_window": 10000000,
    "effective_context_window_percent": 95, "experimental_supported_tools": [],
    "input_modalities": ["text", "image"],
    "supports_search_tool": False, "supports_experimental_context": False, "use_responses_lite": False,
    "supports_reasoning_effort_updates": False, "node_repl_auto_review_required": False, "node_repl_disabled": False,
}
json.dump({"models": [m]}, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
open(out, "a").write("\n")
