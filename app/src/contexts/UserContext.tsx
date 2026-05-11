import React, { createContext, useContext, useState, useEffect } from 'react';

interface User {
    id: string;
    name: string;
    email: string;
    role: 'doctor' | 'admin' | 'technician';
    title: string; // e.g., "Dr.", "Prof.", etc.
}

interface UserContextType {
    user: User | null;
    setUser: (user: User | null) => void;
    isAuthenticated: boolean;
    login: (credentials: { email: string; password: string }) => Promise<boolean>;
    logout: () => void;
    getCurrentDoctorName: () => string;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

// Default user for development/demo purposes
const DEFAULT_USER: User = {
    id: '1',
    name: 'Dr. Anna Kowalska',
    email: 'anna.kowalska@hospital.pl',
    role: 'doctor',
    title: 'Dr.'
};

export function UserProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);

    useEffect(() => {
        // Try to load user from localStorage on app start
        const savedUser = localStorage.getItem('currentUser');
        if (savedUser) {
            try {
                setUser(JSON.parse(savedUser));
            } catch (error) {
                console.error('Error parsing saved user:', error);
                // Set default user if parsing fails
                setUser(DEFAULT_USER);
                localStorage.setItem('currentUser', JSON.stringify(DEFAULT_USER));
            }
        } else {
            // Set default user for development
            setUser(DEFAULT_USER);
            localStorage.setItem('currentUser', JSON.stringify(DEFAULT_USER));
        }
    }, []);

    const login = async (credentials: { email: string; password: string }): Promise<boolean> => {
        // TODO: Implement real authentication with backend
        // For now, mock authentication
        if (credentials.email && credentials.password) {
            const mockUser: User = {
                id: '1',
                name: 'Dr. Anna Kowalska',
                email: credentials.email,
                role: 'doctor',
                title: 'Dr.'
            };
            setUser(mockUser);
            localStorage.setItem('currentUser', JSON.stringify(mockUser));
            return true;
        }
        return false;
    };

    const logout = () => {
        setUser(null);
        localStorage.removeItem('currentUser');
    };

    const getCurrentDoctorName = (): string => {
        if (user) {
            return user.name;
        }
        return 'Dr. System'; // Fallback for backwards compatibility
    };

    const value: UserContextType = {
        user,
        setUser,
        isAuthenticated: !!user,
        login,
        logout,
        getCurrentDoctorName
    };

    return (
        <UserContext.Provider value={value}>
            {children}
        </UserContext.Provider>
    );
}

export function useUser() {
    const context = useContext(UserContext);
    if (context === undefined) {
        throw new Error('useUser must be used within a UserProvider');
    }
    return context;
}

export type { User, UserContextType };
