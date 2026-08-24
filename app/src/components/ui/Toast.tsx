import { type ToastMessage, type Toast} from '@/contexts/ToastContext';
import { useTransition } from 'react';

const resolveToastCss = (type: ToastMessage["type"]) => {
    switch(type) {
        case 'success': {
            return "py-2 px-3 bg-green-600 text-white font-semibold rounded-lg animate-fade-in";
        }
        case 'info': {
            return "py-2 px-3 bg-blue-500 text-white font-semibold rounded-lg animate-fade-in";
        }
        case 'error': {
            return "py-2 px-3 bg-red-600 text-white font-semibold rounded-lg animate-fade-in";
        }
        case 'warning': {
            return "py-2 px-3 bg-orange-600 text-white font-semibold rounded-lg animate-fade-in";
        }
    }
};

export default function Toast({ toast }: { toast: Toast }) {
    const cssClasses = resolveToastCss(toast.type);

    return (<div id={toast.toastId} className={cssClasses}>
        <p>{toast.message}</p>
    </div>);
}