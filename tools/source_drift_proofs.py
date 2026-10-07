"""Narrow CPU proofs for declared drift; none establishes fresh acceptance."""
import ast
import copy
import json

TIMEOUT_VALIDATOR = """def validate_timeout_seconds(timeout_seconds):
    try:
        valid = (not isinstance(timeout_seconds, bool)
                 and isinstance(timeout_seconds, (int, float))
                 and math.isfinite(timeout_seconds) and timeout_seconds > 0)
    except (TypeError, ValueError, OverflowError):
        valid = False
    if not valid:
        raise ValueError("timeout_seconds must be a finite positive number")
"""
ADDED_SMALL = {".gitattributes", "LICENSE", "README.md", "chat_template.jinja", "config.json",
               "crc32.txt", "generation_config.json", "merges.txt", "model.safetensors.index.json",
               "preprocessor_config.json", "tokenizer_config.json", "video_preprocessor_config.json", "vocab.json"}


def tree(source):
    return ast.parse(source)


def dump(node):
    return ast.dump(node, include_attributes=False)


def prove_default_timeout_120(entry, frozen_source, current_source):
    """Normalize only the reviewed optional-120-second parameterization.

    Everything else in the complete module must retain the exact same AST.
    The inserted validator is checked in full before its default no-op call is
    removed. This proves the default path, not arbitrary timeout overrides.
    """
    before, after = tree(frozen_source), tree(current_source)
    validator = next((n for n in after.body if isinstance(n, ast.FunctionDef) and n.name == "validate_timeout_seconds"), None)
    assert validator is not None and dump(validator) == dump(tree(TIMEOUT_VALIDATOR).body[0]), "timeout validator differs"
    after.body.remove(validator)
    imports = [n for n in after.body if isinstance(n, ast.Import) and dump(n) == dump(tree("import math").body[0])]
    assert len(imports) == 1, "expected only the added math import"
    after.body.remove(imports[0])
    for name in ("consume_stream", "request_one"):
        fn = next(n for n in after.body if isinstance(n, ast.FunctionDef) and n.name == name)
        assert len(fn.args.kwonlyargs) == 1 and fn.args.kwonlyargs[0].arg == "timeout_seconds", "unexpected keyword parameter"
        assert dump(fn.args.kw_defaults[0]) == dump(ast.Constant(120)), "default timeout changed"
        fn.args.kwonlyargs = []; fn.args.kw_defaults = []
        assert dump(fn.body[1 if name == "consume_stream" else 0]) == dump(tree("validate_timeout_seconds(timeout_seconds)").body[0]), "default validation call differs"
        fn.body.pop(1 if name == "consume_stream" else 0)
        class Normalize(ast.NodeTransformer):
            def visit_Name(self, node):
                return ast.Constant(120) if node.id == "timeout_seconds" else node
            def visit_JoinedStr(self, node):
                expected = tree('f"request exceeded {timeout_seconds:g}-second total stream limit"').body[0].value
                if dump(node) == dump(expected):
                    return ast.Constant("request exceeded 120-second total stream limit")
                return self.generic_visit(node)
            def visit_Call(self, node):
                if isinstance(node.func, ast.Name) and node.func.id == "consume_stream":
                    assert len(node.keywords) == 1 and node.keywords[0].arg == "timeout_seconds" and isinstance(node.keywords[0].value, ast.Name) and node.keywords[0].value.id == "timeout_seconds", "stream forwarding differs"
                    node.keywords = []
                return self.generic_visit(node)
        Normalize().visit(fn)
    assert dump(before) == dump(after), "module differs beyond optional timeout default equivalence"


def prove_model_metadata_addition(entry, frozen_source, current_source):
    before, after = json.loads(frozen_source), json.loads(current_source)
    weights = before["lfs_files"]
    assert len(weights) == 66 and all(x["path"].endswith(".safetensors") for x in weights), "expected exact 66-weight historical manifest"
    assert after["lfs_files"][:66] == weights, "existing weight identity changed"
    additions = after["lfs_files"][66:]
    assert len(additions) == 1 and additions[0]["path"] == "tokenizer.json", "unexpected large-file addition"
    assert before["small_files"] == [], "historical metadata list differs"
    small = after["small_files"]
    assert len(small) == len(ADDED_SMALL) and {x["path"] for x in small} == ADDED_SMALL, "metadata additions differ"
    import re
    for item in additions + small:
        key, width = ("sha256", 64) if item["path"] == "tokenizer.json" else ("git_blob", 40)
        assert set(item) == {"path", "bytes", key} and type(item["bytes"]) is int and item["bytes"] > 0, "metadata size or fields invalid"
        assert re.fullmatch("[0-9a-f]{%d}" % width, item[key]), "metadata digest invalid"
    assert after["metadata_provenance"] == "model-metadata-20261007.json" and isinstance(after["metadata_note"], str) and after["metadata_note"], "metadata provenance differs"
    restored = copy.deepcopy(after)
    restored["lfs_files"] = restored["lfs_files"][:66]; restored["small_files"] = []
    del restored["metadata_provenance"]; del restored["metadata_note"]
    assert restored == before, "model identity or original manifest fields changed"


PROOFS = {"default_timeout_120": prove_default_timeout_120, "model_metadata_addition": prove_model_metadata_addition}
