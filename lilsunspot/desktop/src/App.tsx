import { AppShell } from "./app/AppShell";
import { ModeProvider } from "./features/mode/ModeState";

export default function App() {
  return (
    <ModeProvider>
      <AppShell />
    </ModeProvider>
  );
}
