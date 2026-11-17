import { useToast } from "@/hooks/useToast";
import Toast from "./Toast";

export default function ToastContainer() {
    const { toasts } = useToast();

    return (<div 
        className="fixed bottom-6 left-1/2 z-50 flex max-h-[70vh] w-full max-w-md -translate-x-1/2 
            flex-col items-center justify-end gap-2 overflow-hidden px-4 md:max-w-2xl"
    >
        {toasts.map(toast => <Toast key={toast.toastId} toast={toast} />)}
    </div>);
}
