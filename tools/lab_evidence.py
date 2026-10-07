#!/usr/bin/env python3
"""Read pinned lab sources and assemble bounded review packs; no model or host actions."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys

import lab_navigator as nav

SCHEMA = 'lab.evidence.review.v1'
DEFAULT_SOURCE_BYTES = 64 * 1024
DEFAULT_AUTHORITY_BYTES = 64 * 1024
MAX_BUDGET = 4 * 1024**2
MAX_OUTPUT_BYTES = 16 * 1024**2
AUTHORITY_PATHS = ('AGENTS.md', 'AGENT_HANDOFF.md', 'CURRENT.md')


def check_output(result):
    """Bound the complete JSON representation, including its trailing newline."""
    if len((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode()) > MAX_OUTPUT_BYTES:
        raise ValueError('Evidence JSON exceeds serialized output bound; reduce selection')


def checked_budget(value):
    if type(value) is not int or not 0 <= value <= MAX_BUDGET:
        raise ValueError('Byte budget must be an integer between 0 and 4 MiB')
    return value


class Sources:
    """Bind every returned source to a real path in an exact local Git tree."""
    def __init__(self, index, repo, allow_stale=False):
        self.db, self.meta = nav.open_index(index)
        self.repo = Path(repo).resolve()
        self.cache = {}
        try:
            commit = self.meta['commit']
            if not isinstance(commit, str) or not re.fullmatch('[0-9a-f]{40}', commit):
                raise ValueError('Index must name an exact Git commit')
            if nav.git(self.repo, 'rev-parse', '--verify', commit + '^{commit}').decode().strip() != commit:
                raise ValueError('Indexed commit cannot be verified')
            head = nav.git(self.repo, 'rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
            if head != commit and not allow_stale:
                raise ValueError('Index is not at repository HEAD; rebuild it or explicitly use --allow-stale')
            raw = nav.git(self.repo, 'ls-tree', '-r', '-l', '-z', commit)
            self.tree = {}
            for entry in raw.split(b'\0'):
                if not entry:
                    continue
                info, name = entry.split(b'\t', 1)
                mode, kind, oid, size = info.split()
                self.tree[name.decode('utf-8')] = (mode.decode(), kind.decode(), oid.decode(), size)
            status = nav.git(self.repo, 'status', '--porcelain', '--untracked-files=normal')
            self.identity = {'indexed_commit': commit, 'repository_head': head,
                             'index_at_head': head == commit, 'stale_use_explicit': bool(allow_stale),
                             'worktree_dirty': bool(status), 'worktree_status_sha256': nav.sha(status),
                             'git_tree_oid': nav.git(self.repo, 'rev-parse', commit + '^{tree}').decode().strip(),
                             'observed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                             'git_tree_sha256': nav.sha(raw), 'source_binding': 'exact Git tree path and blob bytes',
                             'live_host_state_verified': False}
        except BaseException:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def document(self, path):
        if path in self.cache:
            return self.cache[path]
        # Only indexed, policy-eligible regular blobs. Never open a mentioned local path.
        if not isinstance(path, str) or not nav.eligible(path):
            raise ValueError('Path is outside indexed narrative policy: ' + str(path))
        row = self.db.execute('SELECT * FROM documents WHERE path=?', (path,)).fetchone()
        if row is None:
            raise ValueError('Path is not indexed: ' + path)
        entry = self.tree.get(path)
        if not entry or entry[0] not in ('100644', '100755') or entry[1] != 'blob':
            raise ValueError('Source is not a regular file at indexed commit: ' + path)
        if entry[2] != row['blob'] or int(entry[3]) != row['bytes'] or row['bytes'] > nav.MAX_FILE_BYTES:
            raise ValueError('Indexed source does not match Git tree: ' + path)
        raw = nav.git(self.repo, 'cat-file', 'blob', entry[2])
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if (blob != entry[2] or nav.sha(raw) != row['sha256'] or len(raw) != row['bytes']
                or raw.decode('utf-8') != row['text']):
            raise ValueError('Indexed source bytes differ from pinned Git blob: ' + path)
        text = raw.decode('utf-8')
        doc = {'path': path, 'blob': blob, 'document_sha256': nav.sha(raw),
               'source_bytes': len(raw), 'source_role': nav.source_role(path),
               'line_count': len(text.splitlines()), 'text': text,
               'commit': self.meta['commit']}
        self.cache[path] = doc
        return doc


def outline(doc):
    """ATX headings outside fenced code; navigation only, not a status classifier."""
    rows = []
    fence = None
    for n, line in enumerate(doc['text'].splitlines(), 1):
        mark = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence:
            if mark and mark[1][0] == fence[0] and len(mark[1]) >= fence[1] and not mark[2].strip():
                fence = None
            continue
        if mark:
            fence = (mark[1][0], len(mark[1])); continue
        heading = re.match(r'^ {0,3}(#{1,6})\s+(.+?)\s*$', line)
        if heading:
            rows.append({'line': n, 'level': len(heading[1]), 'title': heading[2]})
    return rows


def excerpt(doc, start, end):
    total = doc['line_count']
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= total:
        raise ValueError('Line range must be within source, using inclusive 1-based bounds')
    text = ''.join(doc['text'].splitlines(keepends=True)[start - 1:end])
    headings = []
    for h in outline(doc):
        if h['line'] > start:
            break
        headings = [x for x in headings if x['level'] < h['level']] + [h]
    return {'start_line': start, 'end_line': end, 'text': text,
            'text_sha256': nav.sha(text.encode()), 'text_bytes': len(text.encode()),
            'text_encoding': 'UTF-8 with original line endings',
            'citation': f'{doc["commit"]}:{doc["path"]}:L{start}-L{end}',
            'section_heading_path': headings,
            'continues_before': start > 1, 'continues_after': end < total}


def metadata(doc):
    return {k: v for k, v in doc.items() if k != 'text'}


def remaining_ranges(total, excerpts):
    """Complement of included line intervals, without one object per source line."""
    cursor = 1
    missing = []
    for first, last in sorted((e['start_line'], e['end_line']) for e in excerpts):
        if first > cursor:
            missing.append({'start_line': cursor, 'end_line': first - 1})
        cursor = max(cursor, last + 1)
    if cursor <= total:
        missing.append({'start_line': cursor, 'end_line': total})
    return missing


def read_source(index, repo, path, start=1, end=None, max_bytes=DEFAULT_SOURCE_BYTES,
                allow_stale=False, outline_only=False):
    checked_budget(max_bytes)
    source = Sources(index, repo, allow_stale)
    try:
        doc = source.document(path)
        result = {'schema': 'lab.evidence.read.v1', 'repository': source.identity,
                  'document': metadata(doc), 'outline': outline(doc), 'warning': nav.WARNING}
        if outline_only:
            result['excerpts'] = []
        elif doc['line_count'] == 0 and start == 1 and end is None:
            result['excerpts'] = []
        else:
            item = excerpt(doc, start, doc['line_count'] if end is None else end)
            if item['text_bytes'] > max_bytes:
                raise ValueError('Requested source exceeds byte budget; request --outline or an explicit smaller line range')
            result['excerpts'] = [item]
        result['omitted_ranges'] = remaining_ranges(doc['line_count'], result['excerpts'])
        result['full_document_included'] = not result['omitted_ranges']
        check_output(result)
        return result
    finally:
        source.close()


def review(index, repo, query, output, limit=8, prefix=None, include=(),
           source_bytes=DEFAULT_SOURCE_BYTES, authority_bytes=DEFAULT_AUTHORITY_BYTES,
           authority_lines=200, allow_stale=False):
    checked_budget(source_bytes); checked_budget(authority_bytes)
    if type(authority_lines) is not int or not 1 <= authority_lines <= 1000:
        raise ValueError('Authority line allowance must be 1..1000')
    if len(include) > 16 or len(set(include)) != len(include):
        raise ValueError('At most 16 unique explicit document paths')
    found = nav.search(index, query, limit, prefix)
    source = Sources(index, repo, allow_stale)
    try:
        if found['commit'] != source.meta['commit']:
            raise ValueError('Index commit changed during retrieval')
        matches = []
        grouped = {}
        for rank, hit in enumerate(found['hits'], 1):
            doc = source.document(hit['path'])
            item = excerpt(doc, hit['start_line'], hit['end_line'])
            if (hit['blob'] != doc['blob'] or hit['document_sha256'] != doc['document_sha256']
                    or hit['text'] != '\n'.join(doc['text'].splitlines()[hit['start_line']-1:hit['end_line']])
                    or hit['passage_sha256'] != nav.sha(hit['text'].encode())):
                raise ValueError('Ranked passage does not match its pinned source')
            matches.append({'rank': rank, 'score': hit['rank'], 'path': hit['path'],
                            'citation': item['citation'], 'start_line': hit['start_line'],
                            'end_line': hit['end_line']})
            grouped.setdefault(hit['path'], []).append(item)
        # Explicit coordinator selection is recorded separately; it never modifies ranking.
        paths = list(include) + [p for p in grouped if p not in include]
        documents = []
        used = 0
        for path in paths:
            doc = source.document(path)
            excerpts = []
            reason = None
            if doc['line_count']:
                full = excerpt(doc, 1, doc['line_count'])
                if full['text_bytes'] <= source_bytes - used:
                    excerpts = [full]; used += full['text_bytes']
                else:
                    reason = 'Full document exceeds remaining source-text byte budget'
                    # Keep exact ranked ranges without duplicate/overlapping text.
                    merged = []
                    for part in sorted(grouped.get(path, []), key=lambda x: x['start_line']):
                        if merged and part['start_line'] <= merged[-1][1] + 1:
                            merged[-1][1] = max(merged[-1][1], part['end_line'])
                        else:
                            merged.append([part['start_line'], part['end_line']])
                    for first, last in merged:
                        part = excerpt(doc, first, last)
                        if part['text_bytes'] <= source_bytes - used:
                            excerpts.append(part); used += part['text_bytes']
            omitted = remaining_ranges(doc['line_count'], excerpts)
            documents.append({**metadata(doc), 'selection': 'explicit' if path in include else 'ranked',
                              'excerpts': excerpts, 'full_document_included': not omitted,
                              'omitted_ranges': omitted, 'omission_reason': reason if omitted else None,
                              'outline': outline(doc)})
        authorities = []
        authority_used = 0
        for path in AUTHORITY_PATHS:
            if source.db.execute('SELECT 1 FROM documents WHERE path=?', (path,)).fetchone() is None:
                authorities.append({'path': path, 'status': 'not-indexed', 'full_document_included': False})
                continue
            doc = source.document(path)
            excerpts = []
            if doc['line_count']:
                last = min(authority_lines, doc['line_count']) if path == 'CURRENT.md' else doc['line_count']
                item = excerpt(doc, 1, last)
                if item['text_bytes'] <= authority_bytes - authority_used:
                    excerpts = [item]; authority_used += item['text_bytes']
            omitted = remaining_ranges(doc['line_count'], excerpts)
            authorities.append({**metadata(doc), 'selection': 'status-first-lines-preview' if path == 'CURRENT.md' else 'separate-full-document-context',
                                'excerpts': excerpts, 'full_document_included': not omitted,
                                'omitted_ranges': omitted,
                                'omission_reason': 'Explicit authority line/byte allowance' if omitted else None,
                                'outline': outline(doc)})
        result = {'schema': SCHEMA, 'generated_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'query': query, 'source_commit': found['commit'], 'repository': source.identity,
                  'index_sha256': nav.sha(Path(index).read_bytes()),
                  'tool_sha256': nav.sha(Path(__file__).read_bytes()),
                  'ranker_sha256': nav.sha(Path(nav.__file__).read_bytes()),
                  'ranking': source.meta['ranking'], 'requested_top_k': limit,
                  'returned_top_k': len(matches), 'explicit_documents': list(include),
                  'status': 'partial_evidence' if paths else 'no_match',
                  'obligations_complete': False, 'live_state_verified': False, 'authority_complete': False,
                  'semantic_grading': 'not-performed', 'warning': nav.WARNING,
                  'limits': 'External workspace instructions and operational authorization are outside this pack. No match does not prove absence. Full selected documents do not prove all relevant documents were selected. Authority excerpts can contain history and omit policies; no applicability or conflict judgement is automated.',
                  'budget': {'unit': 'Original UTF-8 excerpt bytes, preserving line endings; not tokens or total JSON bytes',
                             'source_allowed': source_bytes, 'source_used': used,
                             'authority_allowed': authority_bytes, 'authority_used': authority_used,
                             'current_first_lines': authority_lines},
                  'matches': matches, 'documents': documents, 'authority_context': authorities}
        check_output(result)
        nav.write_json_new(output, result)
        return {'output': str(output), 'sha256': nav.sha(Path(output).read_bytes()),
                'status': result['status'], 'documents': len(documents),
                'full_documents': sum(d['full_document_included'] for d in documents),
                'serialized_output_bytes': Path(output).stat().st_size,
                'source_text_bytes': used, 'authority_text_bytes': authority_used,
                'index_at_head': source.identity['index_at_head']}
    finally:
        source.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('read', 'review'):
        p = sub.add_parser(command)
        p.add_argument('--index', required=True); p.add_argument('--repo', required=True)
        p.add_argument('--allow-stale', action='store_true')
        if command == 'read':
            p.add_argument('--path', required=True); p.add_argument('--start-line', type=int, default=1)
            p.add_argument('--end-line', type=int); p.add_argument('--max-bytes', type=int, default=DEFAULT_SOURCE_BYTES)
            p.add_argument('--outline', action='store_true')
        else:
            p.add_argument('--query', required=True); p.add_argument('--out', required=True)
            p.add_argument('--limit', type=int, default=8); p.add_argument('--path-prefix')
            p.add_argument('--include', action='append', default=[])
            p.add_argument('--source-bytes', type=int, default=DEFAULT_SOURCE_BYTES)
            p.add_argument('--authority-bytes', type=int, default=DEFAULT_AUTHORITY_BYTES)
            p.add_argument('--authority-lines', type=int, default=200)
    args = parser.parse_args()
    if args.command == 'read':
        result = read_source(args.index, args.repo, args.path, args.start_line, args.end_line,
                             args.max_bytes, args.allow_stale, args.outline)
    else:
        result = review(args.index, args.repo, args.query, args.out, args.limit, args.path_prefix,
                        args.include, args.source_bytes, args.authority_bytes, args.authority_lines,
                        args.allow_stale)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, sqlite3.Error, subprocess.SubprocessError) as error:
        print('lab-evidence: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
