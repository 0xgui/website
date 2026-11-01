import unittest

from scripts.worker_dry_run import committed_namespace_id, created_id, namespace_id, with_namespace_id

TOML = '''[[kv_namespaces]]
binding = "SNAPSHOT"
id = "pending"
'''


class DryRunParseTests(unittest.TestCase):
    def test_namespace_list_finds_the_title(self):
        listing = 'log line\n[{"id": "abcabcabcabcabcabcabcabcabcabcab", "title": "binary-paths-snapshot"}]'
        self.assertEqual(namespace_id(listing, "binary-paths-snapshot"), "abcabcabcabcabcabcabcabcabcabcab")
        self.assertIsNone(namespace_id("[]", "binary-paths-snapshot"))

    def test_create_output_and_toml_replacement(self):
        text = '{ binding = "SNAPSHOT", id = "0123456789abcdef0123456789abcdef" }'
        found = created_id(text)
        updated = with_namespace_id(TOML, found)
        self.assertEqual(committed_namespace_id(updated), found)
        self.assertEqual(committed_namespace_id(TOML), "pending")


if __name__ == "__main__":
    unittest.main()
