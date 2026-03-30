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
          <div className="sidebar-brand">
            <h2>AI News Tracker</h2>
            <div className="subtitle">Tech Trend Intelligence</div>
          </div>
          <NavLink to="/"><span className="nav-icon">D</span> Dashboard</NavLink>
          <NavLink to="/trends"><span className="nav-icon">T</span> Trends</NavLink>
          <NavLink to="/keywords"><span className="nav-icon">K</span> Keywords</NavLink>
          <NavLink to="/sources"><span className="nav-icon">S</span> Sources</NavLink>
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
