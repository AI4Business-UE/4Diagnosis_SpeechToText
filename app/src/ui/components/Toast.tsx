import { type ToastMessage, type Toast } from '@/contexts/ToastContext';
import { Check, CircleX, Info, TriangleAlert } from 'lucide-react';

const baseCss = "flex items-start gap-3 w-full px-4 py-3 text-left text-base font-semibold rounded-lg shadow-lg animate-fade-in";

const resolveToastCss = (type: ToastMessage["type"]) => {
    switch(type) {
        case 'success': {
            return `${baseCss} bg-green-600 text-white`;
        }
        case 'info': {
            return `${baseCss} bg-blue-500 text-white`;
        }
        case 'error': {
            return `${baseCss} bg-red-600 text-white`;
        }
        case 'warning': {
            return `${baseCss} bg-orange-500 text-white`;
        }
    }
};

const resolveToastIcon = (type: ToastMessage["type"]) => {
    switch(type) {
        case 'success': {
            return <Check className='text-white' size={20} />;
        }
        case 'info': {
            return <Info className='text-white' size={20} />;
        }
        case 'error': {
            return <CircleX className='text-white' size={20} />;
        }
        case 'warning': {
            return <TriangleAlert className='text-white' size={20} />;
        }
    }
}

export default function Toast({ toast }: { toast: Toast }) {
    const cssClasses = resolveToastCss(toast.type);
    const icon = resolveToastIcon(toast.type);

    return (
        <div id={toast.toastId} className={cssClasses}>
            <span className="mt-0.5 shrink-0">{icon}</span>
            <p className="min-w-0 break-words">{toast.message}</p>
        </div>
    );
}
