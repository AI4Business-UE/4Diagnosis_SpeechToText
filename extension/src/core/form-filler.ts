/**
 * Framework-safe value setting for the Target Page: writes go through the
 * element's *native* value setter (bypassing any framework-installed
 * accessor) and `input`/`change` events are dispatched so React/Angular/Vue
 * and plain-JS controlled listeners observe the new value. Never submits
 * the form or touches buttons.
 */
export function fillControl(element: HTMLElement, value: string): void {
  const tag = element.tagName.toLowerCase();

  if (tag === "input") {
    setNativeValue(element as HTMLInputElement, value);
    fireFormEvents(element);
  } else if (tag === "textarea") {
    setNativeValue(element as HTMLTextAreaElement, value);
    fireFormEvents(element);
  } else if (tag === "select") {
    selectOption(element as HTMLSelectElement, value);
    fireFormEvents(element);
  } else {
    throw new Error(`Element <${tag}> jest polem formularza nieobsługiwanym przez Transfer`);
  }
}

function selectOption(select: HTMLSelectElement, value: string): void {
  const match = Array.from(select.options).find(
    (option) => option.value === value || option.textContent?.trim() === value,
  );
  if (!match) {
    // The message reaches the value-free Transfer Report; never embed the value.
    throw new Error("Brak pasującej opcji na stronie docelowej");
  }
  setNativeValue(select, match.value);
}

function setNativeValue(
  element: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement,
  value: string,
): void {
  const prototype =
    element instanceof HTMLSelectElement
      ? HTMLSelectElement.prototype
      : element instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype;

  const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
  const nativeSetter = descriptor?.set;
  if (nativeSetter) {
    nativeSetter.call(element, value);
  } else {
    element.value = value;
  }
}

function fireFormEvents(element: HTMLElement): void {
  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
}
