export interface GenericManager {
    subscribe: (callback: () => void) => (() => void);
    getSnapshot: () => any;
}