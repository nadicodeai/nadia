# Positive fixture: a literal `hermes` reference NOT covered by any
# exception or skip_context. The verify_no_leakage.py scanner must report
# this line and exit 1.

hermes_thing = "this should be detected as leakage"
