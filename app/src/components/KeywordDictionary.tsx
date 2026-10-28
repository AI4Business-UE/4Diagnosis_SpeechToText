import { X } from "lucide-react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { useEffect, useRef, useState } from "react";

type KeywordList = { id: number; text: string; }[];

export default function KeywordDictionary(
    { 
        isDictionaryVisible, 
        onDialogClose
    }: 
    { 
        isDictionaryVisible: boolean;
        onDialogClose: () => void;
    }
) {
    const [keywordsList, setKeywordsList] = useState<KeywordList>([]);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const requestRef = useRef(false);
    const fetchKeywords = async () => {
        try {
            const result = await fetch("/api/keyword");
            const body = await result.json();
            if (result.ok && Array.isArray(body)) {
                setKeywordsList(body);
            } else {
                const errors = Object.values(body);
                if (errors.length > 0)  setErrorMessage(errors[0] as string);
            }
        } catch (err) {
            setErrorMessage("Nie udało się wysłać żądania.");
        }
    };

    useEffect(() => {
        if (!requestRef.current) {
            fetchKeywords();
        }
    });

    return (
        isDictionaryVisible && 
        <div className="absolute inset-0">
          <dialog className="absolute max-w-6xl w-[50%] top-1/2 right-1/2 translate-x-[50%] translate-y-[-70%] z-101">
            <Card className="relative p-4 flex flex-col">
              <div className="absolute top-4 right-4">
                <Button variant="destructive" size="icon" onClick={onDialogClose}>
                  <X />
                </Button>
              </div>
              <h2 className="text-2xl font-semibold text-center">Słownik</h2>
              { errorMessage !== null && <h2 className="text-red">{errorMessage}</h2> }
              <ul>
                {keywordsList.map(keyword => <li key={keyword.id}>{keyword.text}</li>)}
              </ul>
            </Card>
          </dialog>
          <div 
            className="absolute bg-slate-800 opacity-50 inset-0 z-100"
            onClick={onDialogClose}
          ></div>
        </div>
    )
}