import "./App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Home from "./pages/Home";
import Triage from "./pages/Triage";
import Graphics from "./pages/Graphics";

function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/triagem" element={<Triage />} />
        <Route path="/graphics" element={<Graphics />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;