"""Configuration for mutmut mutation testing.

Mutmut introduces small changes (mutations) to the code to verify
that tests catch the bugs. High mutation score = good test coverage.

Run with: mutmut run
View results: mutmut results
Show survivors: mutmut show
"""

def pre_mutation(context):
    """Hook called before each mutation."""
    # Can be used to skip certain mutations
    pass
