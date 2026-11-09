import { useToast } from "@/hooks/useToast";
import Toast from "./Toast";

export default function ToastContainer() {
    const { toasts } = useToast();

    return (<div 
        className="fixed flex flex-col gap-2 top-6 md:bottom-6 md:top-auto mb-5 
            right-[50%] translate-[50%] rounded-full max-w-96"
    >
        {toasts.map(toast => <Toast key={toast.toastId} toast={toast} />)}
    </div>);
}