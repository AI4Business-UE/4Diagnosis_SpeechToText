def extract_patient_data(entities: dict) -> dict:
    patient = entities['patient']
    return {
        'first_name': patient.get('first_name') or '',
        'last_name': patient.get('last_name', '') or '',
        'pesel': patient.get('pesel') or '',
        'age': patient.get('age') or ''
    }


def extract_organs(entities: dict) -> str:
    components = entities.get('components')
    if not components:
        return ''

    component_names = []
    for comp in components:
        name = comp.get('name', '')
        if name == ' ':
            component_names.append('')
            continue

        component_names.append(name)
    return ', '.join(component_names)