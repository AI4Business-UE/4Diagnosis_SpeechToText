// API Service for 4Diagnosis Application
const API_BASE_URL = 'http://localhost:8010/api';

class ApiService {
    private async request<T>(
        endpoint: string,
        options: RequestInit = {}
    ): Promise<T> {
        const url = `${API_BASE_URL}${endpoint}`;

        const config: RequestInit = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
            ...options,
        };

        try {
            const response = await fetch(url, config);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: 'Network error' }));
                throw new Error(errorData.error || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API Request failed:', error);
            throw error;
        }
    }

    private async uploadRequest<T>(
        endpoint: string,
        formData: FormData
    ): Promise<T> {
        const url = `${API_BASE_URL}${endpoint}`;

        try {
            const response = await fetch(url, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: 'Network error' }));
                throw new Error(errorData.error || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Upload Request failed:', error);
            throw error;
        }
    }

    // Health check
    async healthCheck() {
        return this.request('/health');
    }

    // Patient API
    async getPatients(params?: {
        search?: string;
        page?: number;
        limit?: number;
    }): Promise<{ patients: any[]; total: number; pages: number }> {
        const queryParams = new URLSearchParams();
        if (params?.search) queryParams.append('search', params.search);
        if (params?.page) queryParams.append('page', params.page.toString());
        if (params?.limit) queryParams.append('limit', params.limit.toString());

        const query = queryParams.toString();
        return this.request(`/patients${query ? `?${query}` : ''}`);
    }

    async getPatient(id: string) {
        return this.request(`/patients/${id}`);
    }

    async createPatient(patientData: any) {
        return this.request('/patients', {
            method: 'POST',
            body: JSON.stringify(patientData),
        });
    }

    async updatePatient(id: string, patientData: any) {
        return this.request(`/patients/${id}`, {
            method: 'PUT',
            body: JSON.stringify(patientData),
        });
    }

    async deletePatient(id: string) {
        return this.request(`/patients/${id}`, {
            method: 'DELETE',
        });
    }

    // Examination API
    async getExaminations(params?: {
        patientId?: string;
        search?: string;
        type?: string;
        page?: number;
        limit?: number;
    }) {
        const queryParams = new URLSearchParams();
        if (params?.patientId) queryParams.append('patientId', params.patientId);
        if (params?.search) queryParams.append('search', params.search);
        if (params?.type) queryParams.append('type', params.type);
        if (params?.page) queryParams.append('page', params.page.toString());
        if (params?.limit) queryParams.append('limit', params.limit.toString());

        const query = queryParams.toString();
        return this.request(`/examinations${query ? `?${query}` : ''}`);
    }

    async getExamination(id: string) {
        return this.request(`/examinations/${id}`);
    }

    async createExamination(examinationData: any, images?: FileList) {
        if (images && images.length > 0) {
            const formData = new FormData();
            formData.append('data', JSON.stringify(examinationData));

            for (let i = 0; i < images.length; i++) {
                formData.append('images', images[i]);
            }

            return this.uploadRequest('/examinations', formData);
        } else {
            return this.request('/examinations', {
                method: 'POST',
                body: JSON.stringify(examinationData),
            });
        }
    }

    async updateExamination(id: string, examinationData: any, images?: FileList) {
        if (images && images.length > 0) {
            const formData = new FormData();
            formData.append('data', JSON.stringify(examinationData));

            for (let i = 0; i < images.length; i++) {
                formData.append('images', images[i]);
            }

            return this.uploadRequest(`/examinations/${id}`, formData);
        } else {
            return this.request(`/examinations/${id}`, {
                method: 'PUT',
                body: JSON.stringify(examinationData),
            });
        }
    }

    async deleteExamination(id: string) {
        return this.request(`/examinations/${id}`, {
            method: 'DELETE',
        });
    }

    async deleteExaminationImage(id: string, imageIndex: number) {
        return this.request(`/examinations/${id}/images/${imageIndex}`, {
            method: 'DELETE',
        });
    }

    // Recording API
    async getRecordings(params?: {
        patientId?: string;
        examinationId?: string;
        search?: string;
        type?: string;
        isImportant?: boolean;
        page?: number;
        limit?: number;
    }) {
        const queryParams = new URLSearchParams();
        if (params?.patientId) queryParams.append('patientId', params.patientId);
        if (params?.examinationId) queryParams.append('examinationId', params.examinationId);
        if (params?.search) queryParams.append('search', params.search);
        if (params?.type) queryParams.append('type', params.type);
        if (params?.isImportant !== undefined) queryParams.append('isImportant', params.isImportant.toString());
        if (params?.page) queryParams.append('page', params.page.toString());
        if (params?.limit) queryParams.append('limit', params.limit.toString());

        const query = queryParams.toString();
        return this.request(`/recordings${query ? `?${query}` : ''}`);
    }

    async getRecording(id: string) {
        return this.request(`/recordings/${id}`);
    }

    async createRecording(recordingData: any, audioFile: File) {
        const formData = new FormData();
        formData.append('data', JSON.stringify(recordingData));
        formData.append('audio', audioFile);

        return this.uploadRequest('/recordings', formData);
    }

    async updateRecording(id: string, recordingData: any) {
        return this.request(`/recordings/${id}`, {
            method: 'PUT',
            body: JSON.stringify(recordingData),
        });
    }

    async deleteRecording(id: string) {
        return this.request(`/recordings/${id}`, {
            method: 'DELETE',
        });
    }

    // Get audio file URL for playback
    getRecordingAudioUrl(id: string): string {
        return `${API_BASE_URL}/recordings/${id}/audio`;
    }

    // Get image URL
    getImageUrl(filename: string): string {
        return `http://localhost:8010/uploads/images/${filename}`;
    }
}

// Create and export a singleton instance
export const apiService = new ApiService();

// Export types for better TypeScript support
export interface Patient {
    _id: string;
    pesel: string;
    firstName: string;
    lastName: string;
    dateOfBirth: Date;
    phone?: string;
    email?: string;
    address?: {
        street?: string;
        city?: string;
        postalCode?: string;
        country?: string;
    };
    medicalHistory?: Array<{
        condition: string;
        diagnosedDate: Date;
        notes: string;
    }>;
    allergies?: string[];
    medications?: Array<{
        name: string;
        dosage: string;
        frequency: string;
        startDate: Date;
        endDate?: Date;
    }>;
    createdAt: Date;
    updatedAt: Date;
}

export interface Examination {
    _id: string;
    patientId: string | Patient;
    title: string;
    type: 'consultation' | 'diagnostic' | 'followup' | 'surgery' | 'other';
    description?: string;
    symptoms?: string[];
    diagnosis?: {
        primary?: string;
        secondary?: string[];
        icd10Code?: string;
    };
    treatment?: {
        medication?: Array<{
            name: string;
            dosage: string;
            frequency: string;
            duration: string;
        }>;
        procedures?: string[];
        recommendations?: string[];
    };
    vitalSigns?: {
        bloodPressure?: {
            systolic: number;
            diastolic: number;
        };
        heartRate?: number;
        temperature?: number;
        weight?: number;
        height?: number;
        bmi?: number;
    };
    images?: Array<{
        filename: string;
        originalName: string;
        mimetype: string;
        size: number;
        uploadDate: Date;
        description?: string;
    }>;
    notes?: string;
    doctorName?: string;
    examinationDate: Date;
    status: 'completed' | 'pending' | 'cancelled';
    createdAt: Date;
    updatedAt: Date;
}

export interface Recording {
    _id: string;
    patientId: string | Patient;
    examinationId?: string | Examination;
    title: string;
    type: 'voice_note' | 'interview' | 'consultation' | 'symptoms' | 'other';
    filename: string;
    originalName: string;
    mimetype: string;
    size: number;
    duration?: number;
    transcription?: {
        text?: string;
        confidence?: number;
        language?: string;
        processingStatus: 'pending' | 'processing' | 'completed' | 'failed';
    };
    tags?: string[];
    description?: string;
    recordingDate: Date;
    doctorName?: string;
    isImportant: boolean;
    createdAt: Date;
    updatedAt: Date;
}
