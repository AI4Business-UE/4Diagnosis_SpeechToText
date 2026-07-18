def extract_patient_data(entities: dict) -> dict:
    patient = entities['patient']
    return {
        'first_name': patient.get('first_name') or '',
        'last_name': patient.get('last_name', '') or '',
        'pesel': patient.get('pesel') or '',
        'age': patient.get('age') or ''
    }    