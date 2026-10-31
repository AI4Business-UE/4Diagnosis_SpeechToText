### Separation of concerns

Business logic should be separated from React components
which should directly manage only the state of UI.
The logic should be placed in custom hooks if the logic
naturally falls into React lifecycle, or should be 
encapsulated in a **manager** class (kept under `app/src/lib/managers/`)
if it doesn't, eg. `AudioStreamManager.ts` interfaces browser 
AudioWorklet API. The manager can be integrated directly with the UI
via `useSyncExternalStore` hook and implementation of `GenericManager` interface.
If use case requires coordination of multiple managers, a **controller**
class (kept in `app/src/lib/controllers`) can be introduced 
which orchestrates their work. In this casethe managers 
should extend `EventTarget` interface 
and communicate in Subscriber-Publisher pattern.