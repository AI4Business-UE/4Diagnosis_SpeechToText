import { Trash } from "lucide-react";
import { Button } from "./button";


export function Keyword({ text }: { text: string; }) {
    return (
        <li className="p-2 border-1 border-slate-200 rounded-xl shadow-sm">
            <div className="flex">
                <div className="font-semibold ml-6 self-center">{text}</div>
                <Button className="ml-auto" variant="destructive" size="icon">
                    <Trash />
                </Button>                
            </div>
        </li>
    )
}