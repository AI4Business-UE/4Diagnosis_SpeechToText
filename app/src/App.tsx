import { Navigate, Route, Routes, BrowserRouter } from "react-router-dom";
import RecordDescriptionPage from "@/pages/RecordDescription";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/record-description" element={<RecordDescriptionPage />} />
        <Route path="*" element={<Navigate to="/record-description" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
