import { describe, expect, it } from "vitest";

import { resolveFieldControls } from "../src/core/mapping-resolver";
import type { MappingSet } from "../src/shared/config";

const mapping: MappingSet = {
  organ: { selectors: ["#field-organ"], label: "Badany narząd" },
  name: { selectors: ["#field-name"], label: "Imię i nazwisko" },
  age: { selectors: ["#field-age"], label: "Wiek" },
  pesel: { selectors: ["#field-pesel"], label: "PESEL" },
  description: { selectors: ["#field-description"], label: "Opis badania" },
};

function fixture(html: string): Document {
  document.body.innerHTML = html;
  return document;
}

describe("resolveFieldControls", () => {
  it("resolves every mapped field through its first selector candidate", () => {
    const doc = fixture(`
      <form>
        <input id="field-organ" />
        <input id="field-name" />
        <input id="field-age" />
        <input id="field-pesel" />
        <textarea id="field-description"></textarea>
      </form>
    `);

    const resolved = resolveFieldControls(doc, mapping);

    expect(resolved).toHaveLength(5);
    expect(resolved.map((entry) => entry.field)).toEqual([
      "organ",
      "name",
      "age",
      "pesel",
      "description",
    ]);
    for (const entry of resolved) {
      expect(entry.status).toBe("found");
      expect(entry.strategy).toBe("selector");
      expect(entry.element).toBe(doc.getElementById(`field-${entry.field}`));
    }
  });

  it("tries later selector candidates when earlier ones miss", () => {
    const doc = fixture(`<input id="pesel-alt" name="pesel_zz" />`);

    const resolved = resolveFieldControls(doc, {
      ...mapping,
      pesel: {
        selectors: ["#does-not-exist", '[name="pesel_zz"]', "#pesel-alt"],
        label: "PESEL",
      },
    });

    const pesel = resolved.find((entry) => entry.field === "pesel");
    expect(pesel?.status).toBe("found");
    expect(pesel?.strategy).toBe("selector");
    expect(pesel?.element?.id).toBe("pesel-alt");
  });

  it("falls back to the bound label text when no selector hits", () => {
    const doc = fixture(`
      <label for="nr_wieku">  Wiek   pacjenta: </label>
      <input id="nr_wieku" />
    `);

    const resolved = resolveFieldControls(doc, {
      ...mapping,
      age: { selectors: ["#field-age"], label: "Wiek pacjenta" },
    });

    const age = resolved.find((entry) => entry.field === "age");
    expect(age?.status).toBe("found");
    expect(age?.strategy).toBe("label");
    expect(age?.element?.id).toBe("nr_wieku");
  });

  it("matches label text case-insensitively and finds controls wrapped in the label", () => {
    const doc = fixture(`
      <label>Imię i Nazwisko <input name="full_name" /></label>
    `);

    const resolved = resolveFieldControls(doc, mapping);

    const name = resolved.find((entry) => entry.field === "name");
    expect(name?.status).toBe("found");
    expect(name?.strategy).toBe("label");
    expect((name?.element as HTMLInputElement).name).toBe("full_name");
  });

  it("matches label text regardless of Polish diacritics", () => {
    const doc = fixture(`
      <label for="opis_mk">Badanie makroskopowe — opis narządu</label>
      <textarea id="opis_mk"></textarea>
    `);

    const resolved = resolveFieldControls(doc, {
      ...mapping,
      description: {
        selectors: ["#field-description"],
        label: "Badanie makroskopowe - opis narzadu",
      },
    });

    const description = resolved.find((entry) => entry.field === "description");
    expect(description?.status).toBe("found");
    expect(description?.strategy).toBe("label");
    expect(description?.element?.id).toBe("opis_mk");
  });

  it("reports not_found for fields with neither selector hit nor label match", () => {
    const doc = fixture(`<p>Ta strona nie ma formularza.</p>`);

    const resolved = resolveFieldControls(doc, mapping);

    for (const entry of resolved) {
      expect(entry.status).toBe("not_found");
      expect(entry.element).toBeUndefined();
    }
  });
});
