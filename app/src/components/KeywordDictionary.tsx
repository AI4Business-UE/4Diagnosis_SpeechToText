import { X } from "lucide-react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { useEffect, useRef, useState } from "react";
import { API_URL } from "@/config";
import { Keyword } from "./ui/Keyword";

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
            const result = await fetch(`${API_URL}/keyword/list`);
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
        if (!requestRef.current && isDictionaryVisible) {
            fetchKeywords();
            requestRef.current = true;
        }

        return () => {
            requestRef.current = false;
        }
    }, [isDictionaryVisible]);

    return (
        isDictionaryVisible && 
        <div className="fixed inset-0 z-50">
            <div 
                className="absolute bg-slate-800 opacity-50 inset-0"
                onClick={onDialogClose}
            ></div>
            <Card className="absolute max-w-6xl w-[90%] h-100 lg:w-[25%] top-1/2 right-1/2 translate-x-1/2 -translate-y-1/2 z-10 p-4 flex flex-col">
              <div className="absolute top-4 right-4">
                <Button variant="outline" size="icon" onClick={onDialogClose}>
                  <X />
                </Button>
              </div>
              <h2 className="text-2xl font-semibold text-center mb-4">Słownik</h2>
              { errorMessage !== null && <h2 className="text-red-500 font-semibold text-center">{errorMessage}</h2> }
              <ul className="flex flex-col gap-4 max-h-[80%] overflow-x-auto">
                {keywordsList.map(keyword => <Keyword key={keyword.id} text={keyword.text} />)}
              </ul>
            </Card>
        </div>
    )
}