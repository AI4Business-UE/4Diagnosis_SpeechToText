### Testing

Tests should live in a `tests` package of specific Django app they test, 
and specific package named after the module they test. 

Tests targeting Django-dependent elements should be created 
under Django test runner. Each test case should be named as follows:
`<CodeArtifactName>Tests`.
