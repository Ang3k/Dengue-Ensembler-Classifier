import "./App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Home from "./pages/Home";
import Triage from "./pages/Triage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/triagem" element={<Triage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;