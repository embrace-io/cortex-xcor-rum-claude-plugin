import unittest

from scripts.check_plugin.frontmatter import FrontmatterError, parse_frontmatter


class ParseFrontmatterTests(unittest.TestCase):
    def test_plain_and_quoted_scalars(self) -> None:
        fields = parse_frontmatter("---\nname: demo\ndescription: 'a: b'\n---\nbody\n")
        self.assertEqual(fields, {"name": "demo", "description": "a: b"})

    def test_folded_block_scalar_joins_lines_with_spaces(self) -> None:
        fields = parse_frontmatter("---\ndescription: >\n  one\n  two\n---\n")
        self.assertEqual(fields["description"], "one two")

    def test_literal_block_scalar_keeps_newlines(self) -> None:
        fields = parse_frontmatter("---\ndescription: |\n  one\n  two\n---\n")
        self.assertEqual(fields["description"], "one\ntwo")

    def test_plain_scalar_continues_on_indented_lines(self) -> None:
        fields = parse_frontmatter("---\ndescription: one\n  two\n---\n")
        self.assertEqual(fields["description"], "one two")

    def test_empty_value_is_an_empty_string(self) -> None:
        self.assertEqual(
            parse_frontmatter("---\ndescription:\n---\n"), {"description": ""}
        )

    def assertRejected(self, text: str, fragment: str) -> None:
        with self.assertRaises(FrontmatterError) as ctx:
            parse_frontmatter(text)
        self.assertIn(fragment, str(ctx.exception))

    def test_rejects_missing_opening_fence(self) -> None:
        self.assertRejected("name: demo\n", "doesn't start with")

    def test_rejects_missing_closing_fence(self) -> None:
        self.assertRejected("---\nname: demo\n", "no closing")

    def test_rejects_a_line_that_is_not_a_key_value_pair(self) -> None:
        self.assertRejected("---\nname: demo\njunk\n---\n", "frontmatter line 3")

    def test_rejects_unterminated_quote(self) -> None:
        self.assertRejected("---\nname: 'demo\n---\n", "unterminated")

    def test_rejects_colon_space_in_plain_scalar(self) -> None:
        self.assertRejected(
            "---\ndescription: about this: that\n---\n", "wrap it in quotes"
        )


if __name__ == "__main__":
    unittest.main()
