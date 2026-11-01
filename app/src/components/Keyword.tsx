import { Check, Pencil, Trash, X } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";

export function Keyword({
  text,
  onKeywordUpdate,
  onKeywordDelete,
}: {
  text: string;
  onKeywordUpdate: (text: string) => Promise<boolean>;
  onKeywordDelete: () => Promise<void>;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedText, setEditedText] = useState(text);

  async function saveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (await onKeywordUpdate(editedText)) setIsEditing(false);
  }

  function cancelEdit() {
    setEditedText(text);
    setIsEditing(false);
  }

  return (
    <li className="rounded-xl border border-slate-200 p-3 shadow-sm">
      {isEditing ? (
        <form onSubmit={saveEdit} className="flex flex-col gap-2 sm:flex-row">
          <label className="flex-1">
            <span className="sr-only">Edytuj hasło</span>
            <input
              autoFocus
              aria-label="Edytuj hasło"
              type="text"
              maxLength={50}
              value={editedText}
              onChange={(event) => setEditedText(event.target.value)}
              className="w-full rounded-lg border border-slate-300 p-2 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
            />
          </label>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" size="icon" aria-label="Anuluj edycję" onClick={cancelEdit}>
              <X />
            </Button>
            <Button type="submit" variant="outline" size="icon" aria-label="Zapisz zmianę">
              <Check />
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex items-center gap-2">
          <span className="break-words font-semibold">{text}</span>
          <div className="ml-auto flex shrink-0 gap-2">
            <Button type="button" variant="outline" size="icon" aria-label={`Edytuj ${text}`} onClick={() => setIsEditing(true)}>
              <Pencil />
            </Button>
            <Button type="button" variant="destructive" size="icon" aria-label={`Usuń ${text}`} onClick={() => void onKeywordDelete()}>
              <Trash />
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}
