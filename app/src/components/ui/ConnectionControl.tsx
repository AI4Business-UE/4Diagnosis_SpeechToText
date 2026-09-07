import { ConnectionState } from "@/types/recordingState";
import { Wifi, WifiOff } from "lucide-react";
import { Button } from "./button";

export default function ConnectionControl(
    { connectionState, onConnect, onDisconnect }: 
    { connectionState: ConnectionState, onConnect: () => void, onDisconnect: () => void }
) {
    return (
        <>
            {connectionState === 'connected' ?
            (
                <>
                    <Wifi className="text-green-600" size={20} />
                    <span className="text-green-600 font-medium">
                        Połączono z serwerem
                    </span>
                    <Button
                        onClick={onDisconnect}
                        variant="outline"
                        size="sm"
                        className="ml-4"
                    >
                        Rozłącz
                    </Button>
                </>
            ) : (
                    connectionState === 'connecting' ? 
                    (
                        <>
                            <Wifi className="text-orange-500 animate-pulse" size={20} />
                            <span className="text-orange-500 font-medium animate-pulse">Łączenie...</span>
                            <Button disabled size="sm" className="ml-4">
                                Połącz
                            </Button>
                        </>
                    ) : (
                        <>
                            <WifiOff className="text-red-600" size={20} />
                            <span className="text-red-600 font-medium">Brak połączenia</span>
                            <Button onClick={onConnect} size="sm" className="ml-4">
                                Połącz
                            </Button>
                        </>
                    )
                )
            }
        </>
    )
}