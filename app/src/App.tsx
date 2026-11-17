import { Navigate, Route, Routes, BrowserRouter } from "react-router-dom";
import RecordDescriptionPage from "./ui/pages/Recorder";
import KeywordCatalogPage from "./ui/pages/KeywordDictionary";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/record-description" element={<RecordDescriptionPage />} />
        <Route path="/keywords" element={<KeywordCatalogPage />} />
        <Route path="*" element={<Navigate to="/record-description" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
