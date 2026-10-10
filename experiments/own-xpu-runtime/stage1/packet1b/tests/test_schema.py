import copy
import json
from pathlib import Path
import unittest
import jsonschema

SCHEMA=json.loads(Path(__file__).with_name('fixture-extraction.schema.json').read_text())


def synthetic_example(schema):
    if '$ref' in schema:
        return synthetic_example(SCHEMA['$defs'][schema['$ref'].split('/')[-1]])
    if 'const' in schema: return schema['const']
    if 'enum' in schema: return schema['enum'][0]
    kind=schema['type']
    if isinstance(kind,list): kind=kind[0]
    if kind=='object': return {k:synthetic_example(v) for k,v in schema.get('properties',{}).items()}
    if kind=='array': return [synthetic_example(schema['items']) for _ in range(schema.get('minItems',0))]
    if kind=='boolean': return False
    if kind=='integer': return schema.get('minimum',0)
    if kind=='string':
        pattern=schema.get('pattern','')
        if pattern=='^[0-9a-f]{64}$': return '0'*64
        if pattern=='^[0-9a-f]{40}$': return '0'*40
        if pattern.startswith('^sha256:'): return 'sha256:'+'0'*64
        return 'synthetic-'+'x'*schema.get('minLength',1)


class FixtureSchema(unittest.TestCase):
    def test_schema_itself(self): jsonschema.Draft202012Validator.check_schema(SCHEMA)
    def test_unverified_fixture_shape(self): jsonschema.validate(synthetic_example(SCHEMA),SCHEMA)
    def test_missing_binary_identity(self):
        v=synthetic_example(SCHEMA); del v['comparator']['kernel_binaries']
        with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(v,SCHEMA)
    def test_no_unqualified_promotion(self):
        v=synthetic_example(SCHEMA); v['status']='qualified'
        with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(v,SCHEMA)
    def test_reject_unsafe_path(self):
        for path in ('/tmp/foo','../foo','x/../foo'):
            v=synthetic_example(SCHEMA); v['authorization_receipt']['path']=path
            with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(v,SCHEMA)
    def test_hash_required(self):
        v=synthetic_example(SCHEMA); v['inputs'][0]['artifact']['sha256']='unknown'
        with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(v,SCHEMA)
