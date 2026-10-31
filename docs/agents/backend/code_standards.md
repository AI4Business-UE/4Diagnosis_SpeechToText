### Separation of concerns

**Business logic should leave separately from interface layer**.
Interfaces handle serialization, reading operations, and service orchestration
while services handle writes and complex validation.

### Validation

Validation targeting specific fields should live at model layer. Additionaly
any sensible database constraints or checks should be used to further 
increase data protection. If validation requires complex logic, eg. targets
multiple models, then it should be moved to the service layer.

### Testing

Tests should live in a `tests` package of specific Django app they test, 
and specific package named after the module they test. 

Tests targeting Django-dependent elements should be created 
under Django test runner. Each test case should be named as follows:
`<CodeArtifactName>Tests`.
