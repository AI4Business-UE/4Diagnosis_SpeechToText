type ErrorBusEvent = {
    message: string;
    severity: 'warning' | 'error';
};

class ErrorBus {
    private callbacks: Set<(error: ErrorBusEvent) => void> = new Set();

    public subscribe = (callback: (error: ErrorBusEvent) => void) => {
        this.callbacks.add(callback);

        return () => this.callbacks.delete(callback);
    }

    public emitError = (error: ErrorBusEvent) => {
        this.callbacks.forEach(callback => {
            callback(error);
        })
    }
}

export const errorBus = new ErrorBus();