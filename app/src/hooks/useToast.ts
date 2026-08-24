import { ToastContext } from "@/contexts/ToastContext";
import { useContext } from "react"

export function useToast() {
    const context = useContext(ToastContext);

    if (!context) {
        throw new Error('useToast hook must be used exclusively inside ToastProvider');
    }

    return context;
}