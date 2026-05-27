# Stylized brand-string detection fixture (OQ-16)

The scanner is case-insensitive, so the following mixed-case forms MUST
be detected as leakage:

- HeRmEs (mixed case)
- HERMES (all caps)
- Hermes (CamelCase)

If any of these slip past `grep -i hermes`, that's the bug this fixture
exists to catch.
