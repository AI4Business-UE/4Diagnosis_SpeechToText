import { Trash } from "lucide-react";
import { Button } from "./button";
import { useCallback } from "react";
import { API_URL } from "@/config";


export function Keyword(
    { id, text, onKeywordDelete }: 
    { id: number, text: string; onKeywordDelete: () => Promise<void> }
) {
    const deleteKeyword = useCallback(async (id: number) => {
        const result = await fetch(
            `${API_URL}/keyword/delete/${id}`,
            {
                method: 'DELETE'
            }
        );
        if (result.ok) {
            await onKeywordDelete();
        }
    }, []);

    return (
        <li className="p-2 border-1 border-slate-200 rounded-xl shadow-sm">
            <div className="flex">
                <div className="font-semibold ml-6 self-center">{text}</div>
                <Button 
                    className="ml-auto" variant="destructive" size="icon"
                    onClick={async () => await deleteKeyword(id)}
                >
                    <Trash />
                </Button>                
            </div>
        </li>
    )
}