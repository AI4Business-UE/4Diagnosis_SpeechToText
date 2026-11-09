/**
 * Typed promise facades over the MV3 chrome.* APIs the extension uses.
 * @types/chrome still types these as callback-based; MV3 returns promises.
 * Casting the namespace object (not the method) keeps the receiver intact.
 */

type Mv3Storage = {
  get: (keys: string | string[]) => Promise<Record<string, unknown>>;
  set: (items: Record<string, unknown>) => Promise<void>;
};

type Mv3Tabs = {
  query: (queryInfo: { url: string }) => Promise<TabInfo[]>;
  sendMessage: (tabId: number, message: unknown) => Promise<unknown>;
};

type Mv3Runtime = {
  sendMessage: (message: unknown) => Promise<unknown>;
};

export type TabInfo = { id?: number; url?: string };

const storageLocal = chrome.storage.local as unknown as Mv3Storage;
const tabsApi = chrome.tabs as unknown as Mv3Tabs;
const runtimeApi = chrome.runtime as unknown as Mv3Runtime;

export function storageGet(keys: string | string[]): Promise<Record<string, unknown>> {
  return storageLocal.get(keys);
}

export function storageSet(items: Record<string, unknown>): Promise<void> {
  return storageLocal.set(items);
}

export function queryTabsByUrl(url: string): Promise<TabInfo[]> {
  return tabsApi.query({ url });
}

export function sendMessageToTab<T>(tabId: number, message: unknown): Promise<T> {
  return tabsApi.sendMessage(tabId, message) as Promise<T>;
}

export function sendMessageToRuntime<T>(message: unknown): Promise<T> {
  return runtimeApi.sendMessage(message) as Promise<T>;
}
