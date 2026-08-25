import { type ToastMessage, type Toast} from '@/contexts/ToastContext';
import { Check, CircleX, Info, TriangleAlert } from 'lucide-react';
import { useTransition } from 'react';

const resolveToastCss = (type: ToastMessage["type"]) => {
    switch(type) {
        case 'success': {
            return "flex items-center gap-2 text-center py-2 px-3 bg-green-600 text-white font-semibold rounded-lg animate-fade-in";
        }
        case 'info': {
            return "flex items-center gap-2 text-center py-2 px-3 bg-blue-500 text-white font-semibold rounded-lg animate-fade-in";
        }
        case 'error': {
            return "flex items-center gap-2 text-center py-2 px-3 bg-red-600 text-white font-semibold rounded-lg animate-fade-in";
        }
        case 'warning': {
            return "flex items-center gap-2 text-center py-2 px-3 bg-orange-500 text-white font-semibold rounded-lg animate-fade-in";
        }
    }
};

const resovleToastIcon = (type: ToastMessage["type"]) => {
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
    const icon = resovleToastIcon(toast.type);

    return (<div id={toast.toastId} className={cssClasses}>
        {icon}<p>{toast.message}</p>
    </div>);
}