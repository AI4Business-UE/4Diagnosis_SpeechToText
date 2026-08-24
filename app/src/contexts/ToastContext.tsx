import React, { createContext, useCallback, useEffect, useState } from "react";

export type ToastMessage = {
    type: 'success' | 'info' | 'warning' | 'error';
    message: string;
}

export type Toast = {
    toastId: string;
} & ToastMessage;

type ToastContext = {
    toasts: Toast[];
    addMessage: (message: ToastMessage) => void;
}

export const ToastContext = createContext<ToastContext | null>(null);

export function ToastProvider({ children }: React.PropsWithChildren) {
    const [toastMessages, setToastMessages] = useState<Toast[]>([]);

    const filterFromMessageArray = useCallback((toastId: string) => {
        setToastMessages(prev => {
            return prev.filter(message => message.toastId !== toastId);
        });
    }, []);

    const addMessage = useCallback((message: ToastMessage) => {
        const toastId = window.crypto.randomUUID();
        setToastMessages(prev => {
            return [...prev, { ...message, toastId }];
        });

        setTimeout(() => {
           const toast = document.getElementById(toastId);
           if (!toast) return;

           toast.style.animation = 'fade-out 0.3s ease-in-out';
           toast.style.animationFillMode = 'forwards';
           console.log('animation added');
           setTimeout(() => {
                filterFromMessageArray(toastId);
                console.log('filtered from array');
           }, 1000);
        }, 2000);
    }, [filterFromMessageArray]);
    
    return (
        <ToastContext value={{
            toasts: toastMessages,
            addMessage,
        }}>{ children }</ToastContext>
    );
}