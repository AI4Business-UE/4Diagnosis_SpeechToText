import { describe, expect, it } from "vitest";

import { fillControl } from "../src/core/form-filler";

function fixture(html: string): Document {
  document.body.innerHTML = html;
  return document;
}

describe("fillControl", () => {
  it("sets a text input through the native setter and fires input/change events", () => {
    const doc = fixture(`<input id="field-name" />`);
    const input = doc.getElementById("field-name") as HTMLInputElement;

    const events: string[] = [];
    input.addEventListener("input", () => events.push("input"));
    input.addEventListener("change", () => events.push("change"));

    fillControl(input, "Jan Kowalski");

    expect(input.value).toBe("Jan Kowalski");
    expect(events).toEqual(["input", "change"]);
  });

  it("updates state held by a framework-style controlled listener", () => {
    // Simulates React's controlled input: only the native value setter
    // bypasses the framework's stale descriptor; the 'input' event syncs state.
    const doc = fixture(`<input id="field-pesel" />`);
    const input = doc.getElementById("field-pesel") as HTMLInputElement;
    let frameworkState = "";
    input.addEventListener("input", () => {
      frameworkState = input.value;
    });

    fillControl(input, "99123456789");

    expect(frameworkState).toBe("99123456789");
    expect(input.value).toBe("99123456789");
  });

  it("sets a textarea value", () => {
    const doc = fixture(`<textarea id="field-description"></textarea>`);
    const textarea = doc.getElementById("field-description") as HTMLTextAreaElement;

    fillControl(textarea, "Makroskopowy opis badania...");

    expect(textarea.value).toBe("Makroskopowy opis badania...");
  });

  it("selects an option by value or by visible option text", () => {
    const doc = fixture(`
      <select id="s1">
        <option value="">--</option>
        <option value="skura">Skóra</option>
      </select>
      <select id="s2">
        <option value="">--</option>
        <option value="PL-sk">Płuco</option>
      </select>
    `);

    fillControl(doc.getElementById("s1") as HTMLSelectElement, "Skóra");
    fillControl(doc.getElementById("s2") as HTMLSelectElement, "PL-sk");

    expect((doc.getElementById("s1") as HTMLSelectElement).value).toBe("skura");
    expect((doc.getElementById("s2") as HTMLSelectElement).value).toBe("PL-sk");
  });

  it("throws when a select has no option matching value or text", () => {
    const doc = fixture(`
      <select id="s1">
        <option value="">--</option>
        <option value="skura">Skóra</option>
      </select>
    `);

    expect(() => fillControl(doc.getElementById("s1") as HTMLSelectElement, "Wątroba")).toThrow();
  });

  it("throws for elements that are not fillable controls", () => {
    const doc = fixture(`<div id="not-a-field"></div>`);

    expect(() => fillControl(doc.getElementById("not-a-field") as HTMLElement, "x")).toThrow();
  });
});
