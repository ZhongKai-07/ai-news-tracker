import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import TrendAnalysis from "./pages/TrendAnalysis";
import KeywordManage from "./pages/KeywordManage";
import SourceManage from "./pages/SourceManage";
import "./App.css";

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <nav className="sidebar">
          <h2>AI News Tracker</h2>
          <NavLink to="/">Dashboard</NavLink>
          <NavLink to="/trends">Trends</NavLink>
          <NavLink to="/keywords">Keywords</NavLink>
          <NavLink to="/sources">Sources</NavLink>
        </nav>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/trends" element={<TrendAnalysis />} />
            <Route path="/keywords" element={<KeywordManage />} />
            <Route path="/sources" element={<SourceManage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
