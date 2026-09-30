import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./ui/App";
import { PixelRouterDemo } from "./ui/demo/PixelRouterDemo";
import "./ui/styles.css";
import "./ui/pixel-dashboard.css";
import "./ui/demo/pixel-demo.css";

const demoMode = window.location.pathname === "/demo" || new URLSearchParams(window.location.search).get("demo") === "1";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {demoMode ? <PixelRouterDemo /> : <App />}
  </React.StrictMode>,
);
