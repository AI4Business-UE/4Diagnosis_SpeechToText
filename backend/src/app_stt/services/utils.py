def extract_patient_data(entities: dict) -> dict:
    patient = entities['patient']
    return {
        'first_name': patient.get('first_name', ''),
        'last_name': patient.get('last_name', ''),
        'pesel': patient.get('pesel', ''),
        'age': patient.get('age', '')
    }    